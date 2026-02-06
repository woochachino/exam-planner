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

    # user preferences
    session_profile = profile.get("session_profile", {})
    max_daily = session_profile.get("max_daily_deep_hours", 6)
    max_session = session_profile.get("max_session_time", 1.5)

    # time allocation calculations
    total_days = (end - start).days + 1
    total_avail = total_days * max_daily
    total_needed = sum(t.get("estimated_hours", 1) for t in topics)
    scale = min(1.5, total_avail / total_needed) if total_needed > 0 else 1

    # organize topics by subject, preserving order
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

    subjects = list(by_subject.keys())
    # flat list for summary tracking
    all_items = [item for subj in subjects for item in by_subject[subj]]

    # track current topic index per subject
    subj_idx = {s: 0 for s in subjects}

    # build schedule day by day
    days = []
    current = start

    while current <= end:
        # calculate remaining hours per subject
        subj_remaining = {}
        for s in subjects:
            rem = sum(t["remaining"] for t in by_subject[s])
            if rem >= 0.25:
                subj_remaining[s] = rem

        if not subj_remaining:
            break

        # allocate daily hours proportionally to each subject's remaining workload
        total_remaining = sum(subj_remaining.values())
        subj_daily_budget = {}
        for s, rem in subj_remaining.items():
            subj_daily_budget[s] = round((rem / total_remaining) * max_daily, 2)

        sessions = []
        day_hours = 0
        time = 8.0

        # round-robin through subjects with remaining work
        active_subjects = sorted(subj_remaining.keys(), key=lambda s: -subj_remaining[s])
        subj_time_used = {s: 0 for s in active_subjects}

        keep_going = True
        while day_hours < max_daily and keep_going:
            keep_going = False
            for s in active_subjects:
                if day_hours >= max_daily:
                    break

                budget_left = subj_daily_budget.get(s, 0) - subj_time_used[s]
                if budget_left < 0.25:
                    continue

                # find next topic with remaining time in this subject
                topic = None
                while subj_idx[s] < len(by_subject[s]):
                    candidate = by_subject[s][subj_idx[s]]
                    if candidate["remaining"] >= 0.25:
                        topic = candidate
                        break
                    subj_idx[s] += 1

                if topic is None:
                    continue

                session_hours = min(max_session, topic["remaining"], budget_left, max_daily - day_hours)
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
                subj_time_used[s] += session_hours
                time += session_hours + 0.25

                # advance to next topic if this one is done
                if topic["remaining"] < 0.25:
                    subj_idx[s] += 1

                keep_going = True

        if sessions:
            days.append({
                "date": current.strftime("%Y-%m-%d"),
                "day_of_week": current.strftime("%A"),
                "sessions": sessions,
                "total_hours": round(day_hours, 1),
            })

        current += timedelta(days=1)

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
            "topics_scheduled": len([t for t in all_items if t["remaining"] < t["total_hours"] - 0.1]),
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
    """Export schedule to a CSV file and return the file path."""
    import os

    schedule = tool_context.state.get("current_schedule", {})
    if not schedule:
        return {"status": "error", "message": "No schedule found"}

    summary = schedule.get("summary", {})
    lines = ["Date,Day,Start,End,Subject,Topic,Minutes"]

    for day in schedule.get("days", []):
        for s in day["sessions"]:
            title = s["title"][:50].replace(",", ";")
            start_h, start_m = map(int, s["start_time"].split(":"))
            duration_min = int(s["duration_hours"] * 60)
            total_min = start_h * 60 + start_m + duration_min
            end_time = f"{total_min // 60:02d}:{total_min % 60:02d}"
            lines.append(f"{day['date']},{day['day_of_week']},{s['start_time']},{end_time},{s['subject']},{title},{duration_min}")

    csv_content = "\n".join(lines)
    tool_context.state["schedule_csv"] = csv_content

    out_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(out_dir, "study_schedule.csv")
    with open(out_path, "w") as f:
        f.write(csv_content)

    return {
        "status": "success",
        "file": out_path,
        "rows": len(lines) - 1,
        "summary": {
            "period": f"{schedule['start_date']} to {schedule['end_date']}",
            "total_hours": summary.get("total_study_hours", 0),
            "study_days": summary.get("study_days", 0),
            "topics_scheduled": f"{summary.get('topics_scheduled', 0)}/{summary.get('total_topics', 0)}",
            "hours_per_subject": summary.get("hours_per_subject", {}),
        },
        "message": f"Full schedule saved to {out_path}",
    }


def export_schedule_markdown(tool_context: ToolContext) -> dict:
    """Export schedule to Markdown file and return the file path."""
    import os

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

    # save to file so the full schedule is viewable without LLM truncation
    out_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(out_dir, "study_schedule.md")
    with open(out_path, "w") as f:
        f.write(md)

    return {
        "status": "success",
        "file": out_path,
        "summary": {
            "period": f"{schedule['start_date']} to {schedule['end_date']}",
            "total_hours": summary.get("total_study_hours", 0),
            "study_days": summary.get("study_days", 0),
            "topics_scheduled": f"{summary.get('topics_scheduled', 0)}/{summary.get('total_topics', 0)}",
            "hours_per_subject": summary.get("hours_per_subject", {}),
        },
        "message": f"Full schedule saved to {out_path}",
    }


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
