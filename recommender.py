def generate_recommendations(data, predicted_score):
    recommendations = []

    if data["study_hours"] < 3:
        recommendations.append({
            "title": "Increase Daily Study Time",
            "text": "Try to study at least 3 to 4 focused hours daily. Use small study sessions with short breaks."
        })

    if data["attendance"] < 75:
        recommendations.append({
            "title": "Improve Attendance",
            "text": "Your attendance is below the safe level. Attend classes regularly because lectures improve understanding."
        })

    if data["previous_score"] < 60:
        recommendations.append({
            "title": "Revise Basic Concepts",
            "text": "Your previous score shows that core concepts need revision. Start with weak topics and practice daily."
        })

    if data["sleep_hours"] < 6:
        recommendations.append({
            "title": "Improve Sleep Routine",
            "text": "Low sleep can reduce focus and memory. Try to sleep 7 to 8 hours for better learning."
        })

    if data["assignments_completed"] < 70:
        recommendations.append({
            "title": "Complete Assignments on Time",
            "text": "Assignment completion is important for practice. Make a weekly task plan and submit work on time."
        })

    if data["participation"] < 5:
        recommendations.append({
            "title": "Participate in Class",
            "text": "Ask questions and take part in discussions. Participation helps build confidence and understanding."
        })

    if data["internet_access"] == 0:
        recommendations.append({
            "title": "Use Learning Resources",
            "text": "Try to access online lectures, notes, and practice tests through school lab, library, or shared internet."
        })

    if data["parental_support"] < 5:
        recommendations.append({
            "title": "Build Support System",
            "text": "Discuss your study goals with parents, teachers, or friends so they can support your routine."
        })

    if data["extra_classes"] == 0 and predicted_score < 65:
        recommendations.append({
            "title": "Consider Extra Classes",
            "text": "Extra classes or tutoring can help improve weak subjects and increase your confidence."
        })

    if not recommendations:
        recommendations.append({
            "title": "Keep Your Routine Strong",
            "text": "Your habits look good. Keep practicing, revise regularly, and maintain consistency."
        })

    return recommendations
