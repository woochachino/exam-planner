"""Survey tools for learner profiling - only questions that affect scheduling."""

from google.adk.tools import ToolContext


# Only questions that actually affect the schedule
SURVEY_QUESTIONS = {
    "focus_duration": {
        "id": "focus_duration",
        "question": "How long can you typically maintain deep focus before needing a break?",
        "options": [
            {"key": "a", "text": "Less than 30 minutes", "maps_to": {"max_daily_deep_hours": 4}},
            {"key": "b", "text": "30-60 minutes", "maps_to": {"max_daily_deep_hours": 5}},
            {"key": "c", "text": "1-2 hours", "maps_to": {"max_daily_deep_hours": 6}},
            {"key": "d", "text": "More than 2 hours", "maps_to": {"max_daily_deep_hours": 8}},
        ],
    },
    "peak_time": {
        "id": "peak_time",
        "question": "When do you feel most mentally sharp?",
        "options": [
            {"key": "a", "text": "Early morning (6am-10am)", "maps_to": {"peak_windows": ["06:00"]}},
            {"key": "b", "text": "Late morning to afternoon (10am-3pm)", "maps_to": {"peak_windows": ["10:00"]}},
            {"key": "c", "text": "Evening (5pm-9pm)", "maps_to": {"peak_windows": ["17:00"]}},
            {"key": "d", "text": "Night (after 9pm)", "maps_to": {"peak_windows": ["21:00"]}},
        ],
    },
}


def get_survey_questions(tool_context: ToolContext) -> dict:
    """Get all survey questions."""
    questions = []
    for q_id, q_data in SURVEY_QUESTIONS.items():
        questions.append({
            "id": q_data["id"],
            "question": q_data["question"],
            "options": [{"key": opt["key"], "text": opt["text"]} for opt in q_data["options"]]
        })

    return {
        "status": "success",
        "total_questions": len(questions),
        "questions": questions,
    }


def start_study_survey(tool_context: ToolContext) -> dict:
    """Start a new survey."""
    tool_context.state["survey_responses"] = {}

    question_ids = list(SURVEY_QUESTIONS.keys())
    first_question = SURVEY_QUESTIONS[question_ids[0]]

    return {
        "status": "started",
        "total_questions": len(SURVEY_QUESTIONS),
        "current_question": 1,
        "question": {
            "id": first_question["id"],
            "text": first_question["question"],
            "options": [{"key": opt["key"], "text": opt["text"]} for opt in first_question["options"]]
        }
    }


def process_survey_response(question_id: str, answer: str, tool_context: ToolContext) -> dict:
    """Process a survey answer and return next question or complete."""
    answer = answer.lower().strip()

    if question_id not in SURVEY_QUESTIONS:
        return {"status": "error", "message": f"Unknown question: {question_id}"}

    question = SURVEY_QUESTIONS[question_id]
    valid_answers = [opt["key"] for opt in question["options"]]

    if answer not in valid_answers:
        return {"status": "invalid_answer", "message": f"Please answer with: {', '.join(valid_answers)}"}

    # Store response
    responses = tool_context.state.get("survey_responses", {})
    responses[question_id] = answer
    tool_context.state["survey_responses"] = responses

    # Get next question
    question_ids = list(SURVEY_QUESTIONS.keys())
    current_idx = question_ids.index(question_id)

    if current_idx + 1 < len(question_ids):
        next_q_id = question_ids[current_idx + 1]
        next_question = SURVEY_QUESTIONS[next_q_id]

        return {
            "status": "next_question",
            "current_question": current_idx + 2,
            "total_questions": len(question_ids),
            "question": {
                "id": next_question["id"],
                "text": next_question["question"],
                "options": [{"key": opt["key"], "text": opt["text"]} for opt in next_question["options"]]
            }
        }
    else:
        return {"status": "complete", "message": "Survey complete! Calculating profile..."}


def calculate_profile_scores(tool_context: ToolContext) -> dict:
    """Calculate learner profile from responses."""
    responses = tool_context.state.get("survey_responses", {})

    if not responses:
        return {"status": "error", "message": "No survey responses found"}

    # Simple profile with only values that affect scheduling
    profile = {
        "session_profile": {"max_daily_deep_hours": 6},
        "chronotype": {"peak_windows": ["17:00"]},
    }

    # Apply responses
    for q_id, answer in responses.items():
        if q_id not in SURVEY_QUESTIONS:
            continue
        question = SURVEY_QUESTIONS[q_id]
        selected = next((opt for opt in question["options"] if opt["key"] == answer), None)
        if not selected:
            continue

        mappings = selected.get("maps_to", {})
        for key, value in mappings.items():
            if key == "max_daily_deep_hours":
                profile["session_profile"]["max_daily_deep_hours"] = value
            elif key == "peak_windows":
                profile["chronotype"]["peak_windows"] = value

    tool_context.state["learner_profile"] = profile

    max_hrs = profile["session_profile"]["max_daily_deep_hours"]
    peak = profile["chronotype"]["peak_windows"][0]

    return {
        "status": "success",
        "profile": profile,
        "summary": f"**Daily Capacity:** {max_hrs} hours\n**Peak Focus Time:** {peak}"
    }


def update_subject_confidence(subject: str, confidence: float, tool_context: ToolContext) -> dict:
    """Update confidence for a subject (stored but not currently used in scheduling)."""
    profile = tool_context.state.get("learner_profile", {})
    if not profile:
        return {"status": "error", "message": "Complete the survey first."}

    subject_confidence = profile.get("subject_confidence", {})
    subject_confidence[subject] = max(0.0, min(1.0, confidence))
    profile["subject_confidence"] = subject_confidence
    tool_context.state["learner_profile"] = profile

    return {"status": "success", "message": f"Set {subject} confidence to {confidence*100:.0f}%"}
