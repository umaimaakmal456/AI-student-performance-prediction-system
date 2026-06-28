from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import joblib
import numpy as np
from pathlib import Path
import markdown
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from .recommender import generate_recommendations
from .models import PredictionHistory, Task, Note, User, db
from .services import generate_health_driven_timetable, rollover_tasks

main = Blueprint("main", __name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "student_performance_model.pkl"
SCALER_PATH = Path(__file__).resolve().parent.parent / "models" / "scaler.pkl"

def get_performance_category(score):
    if score < 50: return "Low"
    if score < 70: return "Average"
    if score < 85: return "Good"
    return "Excellent"

def is_logged_in():
    return session.get("logged_in") == True

# ------------------------------------------------------------------
# Public Routes
# ------------------------------------------------------------------

@main.route("/")
def home():
    if is_logged_in():
        return redirect(url_for('main.dashboard'))
    return render_template("index.html")

@main.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["logged_in"] = True
            session["user_email"] = user.email
            session["username"] = user.username
            return redirect(url_for("main.dashboard"))
        else:
            error = "Invalid email or password."

    return render_template("login.html", error=error)

@main.route("/register", methods=["GET", "POST"])
def register():
    if is_logged_in():
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password:
            error = "All fields are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            session["logged_in"] = True
            session["user_email"] = new_user.email
            session["username"] = new_user.username
            return redirect(url_for("main.dashboard"))

    return render_template("register.html", error=error)

@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.home"))

@main.route("/about")
def about():
    return render_template("about.html")

# ------------------------------------------------------------------
# Protected Routes
# ------------------------------------------------------------------

@main.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("main.login"))

    rollover_tasks()
    today = datetime.utcnow().date()

    history = PredictionHistory.query.order_by(PredictionHistory.timestamp.asc()).all()
    chart_labels = [h.timestamp.strftime("%m/%d %H:%M") for h in history]
    chart_data = [h.score for h in history]

    latest_history = history[-1] if history else None
    latest_recs = latest_history.recommendations if latest_history else []

    # Sort tasks chronologically
    tasks = Task.query.filter_by(date_created=today).order_by(Task.start_time.asc()).all()
    sleep_task = next((t for t in tasks if "Sleep" in t.title), None)
    pending_tasks = [t for t in tasks if t.status == "Pending" and "Sleep" not in t.title]
    next_task = pending_tasks[0] if pending_tasks else None

    recent_notes = Note.query.order_by(Note.timestamp.desc()).limit(10).all()
    for note in recent_notes:
        note.html_content = markdown.markdown(note.content)

    # Consume the popup data from session (one-time display)
    popup = session.pop("prediction_popup", None)

    return render_template("dashboard.html",
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           tasks=tasks,
                           next_task=next_task,
                           sleep_task=sleep_task,
                           recent_notes=recent_notes,
                           latest_recs=latest_recs,
                           popup=popup,
                           datetime=datetime)

@main.route("/predict", methods=["GET", "POST"])
def predict():
    if not is_logged_in():
        return redirect(url_for("main.login"))

    if request.method == "POST":
        data = {
            "study_hours": float(request.form["study_hours"]),
            "attendance": float(request.form["attendance"]),
            "previous_score": float(request.form["previous_score"]),
            "sleep_hours": float(request.form["sleep_hours"]),
            "assignments_completed": float(request.form["assignments_completed"]),
            "participation": float(request.form["participation"]),
            "internet_access": int(request.form["internet_access"]),
            "parental_support": float(request.form["parental_support"]),
            "extra_classes": int(request.form["extra_classes"])
        }

        if not MODEL_PATH.exists() or not SCALER_PATH.exists():
            return render_template("predict.html", error="Model/Scaler not found. Please run: python train_model.py")

        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)

        features = np.array([[
            data["study_hours"], data["attendance"], data["previous_score"],
            data["sleep_hours"], data["assignments_completed"], data["participation"],
            data["internet_access"], data["parental_support"], data["extra_classes"]
        ]])

        scaled_features = scaler.transform(features)
        predicted_score = round(float(model.predict(scaled_features)[0]), 2)
        predicted_score = max(0, min(100, predicted_score))
        category = get_performance_category(predicted_score)

        recommendations = generate_recommendations(data, predicted_score)

        # --- Comparison Logic ---
        last_prediction = PredictionHistory.query.order_by(PredictionHistory.timestamp.desc()).first()

        if last_prediction is None:
            comparison_state = "first"
            comparison_msg = None
        elif predicted_score > last_prediction.score:
            comparison_state = "improved"
            comparison_msg = f"Congratulations! Your predicted performance has improved by {round(predicted_score - last_prediction.score, 1)} points since last time."
        elif predicted_score < last_prediction.score:
            comparison_state = "degraded"
            comparison_msg = f"Your predicted score has dropped by {round(last_prediction.score - predicted_score, 1)} points. You need to work harder and stick to the new schedule."
        else:
            comparison_state = "same"
            comparison_msg = "Your predicted score is the same as your last submission. Keep pushing!"

        # Save new prediction
        new_prediction = PredictionHistory(
            score=predicted_score,
            input_data=data,
            recommendations=recommendations
        )
        db.session.add(new_prediction)
        db.session.commit()

        # Build popup payload into session
        session["prediction_popup"] = {
            "score": predicted_score,
            "category": category,
            "comparison_state": comparison_state,
            "comparison_msg": comparison_msg,
            "recommendations": recommendations[:3],  # Top 3 for brevity
        }

        generate_health_driven_timetable(predicted_score, data)
        return redirect(url_for("main.dashboard"))

    return render_template("predict.html", error=None)

# ------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------

@main.route("/api/notes", methods=["POST"])
def save_note():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    content = data.get("content")
    task_id = data.get("task_id")

    if content:
        note = Note(content=content, task_id=task_id)
        db.session.add(note)
        db.session.commit()
        html_content = markdown.markdown(content)
        return jsonify({"message": "Note saved", "html": html_content, "id": note.id}), 201

    return jsonify({"error": "Content required"}), 400

@main.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get_or_404(task_id)
    task.status = "Completed"
    db.session.commit()
    return jsonify({"message": "Task completed"})
