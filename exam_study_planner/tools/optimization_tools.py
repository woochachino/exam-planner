"""Schedule generation"""

from google.adk.tools import ToolContext
from datetime import datetime, timedelta
import hashlib


def generate_schedule(
    start_date: str,
    end_date: str,
    tool_context: ToolContext,
) -> dict:
    """Generate study schedule with variety - different topics each session."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date: {e}"}

    topics = tool_context.state.get("topics", [])
    profile = tool_context.state.get("learner_profile", {})

    if not topics:
        return {"status": "error", "message": "No topics found. Process documents first."}

    if len(topics) > 100:
        return {"status": "error", "message": f"Too many topics ({len(topics)}). Run clear_topics() first."}

    # user preferences
    session_profile = profile.get("session_profile", {})
    max_daily = session_profile.get("max_daily_deep_hours", 6)
    max_session = session_profile.get("max_session_time", 1.5)

    # time allocation calculations
    total_days = (end - start).days + 1
    total_avail = total_days * max_daily
    total_needed = sum(t.get("estimated_hours", 1) for t in topics)
    scale = min(1.5, total_avail / total_needed) if total_needed > 0 else 1

    # alternating subject/topic queue for variety
    by_subject = {}
    for t in topics:
        subj = t.get("subject", "General")
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append({
            "id": t["topic_id"],
            "subject": subj,
            "title": t.get("title", "Topic"),
            "total_hours": round(t.get("estimated_hours", 1) * scale, 1),
            "remaining": round(t.get("estimated_hours", 1) * scale, 1),
            "complexity": t.get("complexity", 0.5),
        })

    # 
    subjects = list(by_subject.keys())
    queue = []
    max_len = max(len(by_subject[s]) for s in subjects)
    for i in range(max_len):
        for subj in subjects:
            if i < len(by_subject[subj]):
                queue.append(by_subject[subj][i])

    # build schedule
    days = []
    current = start
    queue_idx = 0

    while current <= end and queue_idx < len(queue) * 3:  # limit
        sessions = []
        day_hours = 0
        time = 8.0
        topics_today = set()  # track the topics scheduled today (avoid excessive repeats)

        # fill day with varied topics
        scan_start = queue_idx
        scanned = 0

        while day_hours < max_daily and scanned < len(queue):
            topic = queue[queue_idx % len(queue)]
            queue_idx += 1
            scanned += 1

            # skip if already scheduled today OR completed
            if topic["id"] in topics_today or topic["remaining"] < 0.25:
                continue

            # schedule time per study SESSION
            session_hours = min(max_session, topic["remaining"], max_daily - day_hours)
            if session_hours < 0.25:
                continue

            # skip lunch
            if 12 <= time < 13:
                time = 13

            sessions.append({
                "topic_id": topic["id"],
                "subject": topic["subject"],
                "title": topic["title"],
                "start_time": f"{int(time):02d}:{int((time % 1) * 60):02d}",
                "duration_hours": round(session_hours, 1),
                "complexity": topic["complexity"],
            })

            topic["remaining"] -= session_hours
            day_hours += session_hours
            time += session_hours + 0.25
            topics_today.add(topic["id"])

        if sessions:
            days.append({
                "date": current.strftime("%Y-%m-%d"),
                "day_of_week": current.strftime("%A"),
                "sessions": sessions,
                "total_hours": round(day_hours, 1),
            })

        current += timedelta(days=1)

        # check if all topics are done
        if all(t["remaining"] < 0.25 for t in queue):
            break

    # summary
    hrs_by_subj = {}
    for d in days:
        for s in d["sessions"]:
            hrs_by_subj[s["subject"]] = hrs_by_subj.get(s["subject"],0) + s["duration_hours"]

    schedule = {
        "schedule_id": hashlib.md5(f"{start_date}_{end_date}".encode()).hexdigest()[:8],
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "summary": {
            "total_study_hours": round(sum(d["total_hours"] for d in days), 1),
            "study_days": len(days),
            "hours_per_subject": {k: round(v, 1) for k, v in hrs_by_subj.items()},
            "topics_scheduled": len([t for t in queue if t["remaining"] < t["total_hours"] - 0.1]),
            "total_topics": len(topics),
        }
    }

    tool_context.state["current_schedule"] = schedule

    return {
        "status": "success",
        "days": len(days),
        "total_hours": schedule["summary"]["total_study_hours"],
        "hours_by_subject": hrs_by_subj,
        "message": f"Scheduled {len(topics)} topics across {len(days)} days"
    }


def export_schedule_csv(tool_context: ToolContext) -> dict:
    """Export schedule to CSV."""
    schedule = tool_context.state.get("current_schedule", {})
    if not schedule:
        return {"status": "error", "message": "No schedule found"}

    lines = ["Date,Day,Start,End,Subject,Topic,Hours"]

    for day in schedule.get("days", []):
        for s in day["sessions"]:
            title = s["title"][:50].replace(",", ";")
            start_h, start_m = map(int, s["start_time"].split(":"))
            total_min = start_h * 60 + start_m + int(s["duration_hours"] * 60)
            end_time = f"{total_min // 60:02d}:{total_min % 60:02d}"
            lines.append(f"{day['date']},{day['day_of_week']},{s['start_time']},{end_time},{s['subject']},{title},{s['duration_hours']}")

    csv = "\n".join(lines)
    tool_context.state["schedule_csv"] = csv
    return {"status": "success", "content": csv, "rows": len(lines) - 1}


def export_schedule_markdown(tool_context: ToolContext) -> dict:
    """Export schedule to Markdown."""
    schedule = tool_context.state.get("current_schedule", {})
    if not schedule:
        return {"status": "error", "message": "No schedule found"}

    summary = schedule.get("summary", {})
    lines = [
        "# Study Schedule",
        "",
        f"**Period:** {schedule['start_date']} to {schedule['end_date']}",
        f"**Total Time:** {summary.get('total_study_hours', 0)} hours across {summary.get('study_days', 0)} days",
        f"**Topics:** {summary.get('topics_scheduled', 0)}/{summary.get('total_topics', 0)}",
        "",
        "## Hours by Subject",
        "",
        "| Subject | Hours |",
        "|---------|------:|",
    ]

    for subj, hrs in sorted(summary.get("hours_per_subject", {}).items()):
        lines.append(f"| {subj} | {hrs} |")

    lines.extend(["", "## Daily Plan", ""])

    for day in schedule.get("days", []):
        lines.append(f"### {day['day_of_week']}, {day['date']} ({day['total_hours']}h)")
        lines.append("")
        lines.append("| Time | Subject | Topic | Duration |")
        lines.append("|------|---------|-------|----------|")

        for s in day["sessions"]:
            title = s["title"][:40] + "..." if len(s["title"]) > 40 else s["title"]
            dur = f"{s['duration_hours']}h" if s['duration_hours'] >= 1 else f"{int(s['duration_hours']*60)}m"
            lines.append(f"| {s['start_time']} | {s['subject']} | {title} | {dur} |")

        lines.append("")

    md = "\n".join(lines)
    tool_context.state["schedule_markdown"] = md
    return {"status": "success", "content": md}


def add_exam(subject: str, exam_date: str, tool_context: ToolContext) -> dict:
    """Add an exam to track"""
    try:
        datetime.strptime(exam_date, "%Y-%m-%d")
    except ValueError:
        return {"status": "error", "message": "Use YYYY-MM-DD format"}

    exams = tool_context.state.get("exams", [])
    for e in exams:
        if e["subject"] == subject:
            e["exam_date"] = exam_date
            tool_context.state["exams"] = exams
            return {"status": "success", "message": f"Updated {subject} exam to {exam_date}"}

    exams.append({"subject": subject, "exam_date": exam_date})
    tool_context.state["exams"] = exams
    return {"status": "success", "message": f"Added {subject} exam on {exam_date}"}
