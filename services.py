from .models import Task, db, Note
from datetime import datetime, timedelta

def add_schedule_block(title, target_date, current_time, duration_minutes, is_pomodoro=False):
    """Helper to add a task block and return the new current_time."""
    start = datetime.combine(target_date, current_time.time())
    end = start + timedelta(minutes=duration_minutes)
    
    task = Task(
        title=title, 
        is_pomodoro=is_pomodoro, 
        date_created=target_date,
        start_time=start,
        end_time=end
    )
    db.session.add(task)
    return end

def generate_health_driven_timetable(prediction_score, input_data):
    """
    Generates a 7-day holistic 24-hour schedule using a time cursor.
    """
    today = datetime.utcnow().date()
    
    # Analyze weak areas
    weak_areas = []
    if input_data["previous_score"] < 60:
        weak_areas.append("Core Subject Review")
    if input_data["participation"] < 5:
        weak_areas.append("Class Prep & Readings")
    if not weak_areas:
        weak_areas.append("General Study")

    needs_assignments = input_data["assignments_completed"] < 70
    needs_leisure = prediction_score > 85

    for day_offset in range(7):
        target_date = today + timedelta(days=day_offset)
        
        # Check if schedule already exists for this day
        if Task.query.filter_by(date_created=target_date).first():
            continue # Skip if day already generated
            
        # Time Cursor starts at 07:00
        current_time = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=7)
        
        # 07:00 - 07:30 Breakfast
        current_time = add_schedule_block("Breakfast & Morning Routine", target_date, current_time, 30)
        
        # 07:30 - 12:30 Morning Block (Classes/Self-Study)
        current_time = add_schedule_block("Morning Classes / Independent Work", target_date, current_time, 300)
        
        # 12:30 - 13:15 Lunch
        current_time = add_schedule_block("Lunch Break", target_date, current_time, 45)
        
        # 13:15 - 15:15 Assignment Block (if needed) or regular study
        if needs_assignments:
            current_time = add_schedule_block("Assignment Work", target_date, current_time, 120)
        else:
            current_time = add_schedule_block("Afternoon Classes / Projects", target_date, current_time, 120)
            
        # 15:15 - 17:15 Deep Study (Pomodoro blocks for weak areas)
        for i, weak_area in enumerate(weak_areas):
            if i > 1: break # Max 2 specific pomodoro blocks here to fit time
            # 50 min work
            title = f"{weak_area} - Pomodoro (50m Focus)"
            add_schedule_block(title, target_date, current_time, 50, is_pomodoro=True)
            current_time += timedelta(minutes=50)
            
            # 10 min rest
            add_schedule_block(f"Short Break", target_date, current_time, 10)
            current_time += timedelta(minutes=10)
            
        # Fill remaining afternoon if Pomodoros didn't take full 2 hours
        current_time = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=17, minutes=15)
        
        # 17:15 - 19:00 Leisure or Extra Study
        if needs_leisure:
            current_time = add_schedule_block("Free Time / Recreation", target_date, current_time, 105)
        else:
            current_time = add_schedule_block("Review & Practice", target_date, current_time, 105)
            
        # 19:00 - 19:45 Dinner
        current_time = add_schedule_block("Dinner", target_date, current_time, 45)
        
        # 19:45 - 23:00 Evening Routine / Wind Down
        current_time = add_schedule_block("Evening Routine / Wind Down", target_date, current_time, 195)
        
        # 23:00 - 07:00 (next day) Sleep 8 Hours
        add_schedule_block("Sleep 8 Hours", target_date, current_time, 480)

        db.session.flush() # ensure IDs exist for notes
        
        # Add a note to the first Pomodoro task as placeholder
        first_pomo = Task.query.filter_by(date_created=target_date, is_pomodoro=True).first()
        if first_pomo:
            placeholder = Note(
                content=f"**Daily Goal:** Focus on understanding core concepts.", 
                task_id=first_pomo.id
            )
            db.session.add(placeholder)

    db.session.commit()

def rollover_tasks():
    today = datetime.utcnow().date()
    pending_tasks = Task.query.filter(Task.status == "Pending", Task.date_created < today).all()
    
    for task in pending_tasks:
        if task.is_pomodoro or "Assignment" in task.title:
            task.date_created = today
            task.start_time = None # Cleared so they appear at top of schedule
            task.end_time = None
        else:
            task.status = "Missed"
    
    db.session.commit()
