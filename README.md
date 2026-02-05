# Exam Study Planner

A multi-agent system that generates personalized study schedules based on your course materials, learning style, and exam dates.

## What It Does

Upload your textbooks/notes as PDFs, answer a few questions about how you study, tell it when your exams are — and it creates a day-by-day study schedule that:

- Distributes topics proportionally across your available time
- Puts harder material during your peak focus hours
- Adjusts time allocation based on your cognitive strengths
- Exports to Markdown or CSV

## Architecture

```
CoordinatorAgent (main)
    ├── ProfilerAgent      → conducts study style survey
    ├── DocumentInterpreter → extracts topics from PDFs
    └── OptimizerAgent     → generates the schedule
```

Built on Google's Agent Development Kit (ADK). Each agent has specific tools it can call.

## How It Works

### 1. Profiling (`survey_tools.py`)

An 8-question survey assesses:
- **Session style**: Deep work vs pomodoro vs short bursts
- **Focus duration**: How long before you need a break
- **Peak hours**: When you're most mentally sharp
- **Cognitive strengths**: Math comfort, memorization, abstract reasoning, reading speed
- **Subject switching**: Prefer variety or focusing on one thing?

Responses map to a learner profile with numerical scores (0-1) for each cognitive area.

### 2. Document Processing (`document_tools.py`)

PDFs are processed to extract topics:

1. **Structure extraction**: Pulls table of contents if available, otherwise scans pages for chapter/section headings
2. **Content sampling**: Reads first ~1000 characters of each section
3. **Complexity estimation**: Analyzes sampled text for math symbols, formulas, definitions to estimate difficulty (0.3-0.9)
4. **Weight calculation**: `weight = pages × (0.5 + complexity)`

**Key design decision**: Topics get *relative weights*, not absolute hours. This solves the problem where "87 hours needed" gets compressed to 40 hours scheduled — weights scale proportionally to fit whatever time you actually have.

### 3. Schedule Generation (`optimization_tools.py`)

The scheduler distributes topics across available days:

```
total_hours = days_until_exam × max_daily_hours
hours_per_weight = total_hours / sum(all_weights)

For each topic:
    scheduled_hours = weight × hours_per_weight × strength_factor
```

Where `strength_factor = 1.5 - user_strength` (weaker areas get more time).

**Time assignment**:
- Sessions progress chronologically through the day (8am → lunch break → continue)
- High-complexity topics scheduled during user's peak hours
- Lower-complexity topics fill remaining slots

## Why This Approach

### Relative Weights vs Absolute Hours

Early versions estimated "2.5 hours for Chapter 3" based on page count. Problem: if you only have 3 days before the exam, those estimates don't fit. The schedule would overflow or leave topics unscheduled.

Solution: weights are unitless. A topic with weight 10 gets twice as much time as one with weight 5, regardless of whether you have 2 days or 2 weeks. Actual hours are computed at scheduling time based on real availability.

### Content Sampling for Complexity

Reading entire PDFs would be slow. Instead, we sample the first page of each section (~1000 chars) and look for complexity indicators:
- Math symbols (∑, ∫, ≤, etc.)
- Formula patterns (`x = ...`)
- Definition keywords ("defined as", "refers to")

This gives reasonable complexity estimates without processing hundreds of pages.

### Peak Hours for Hard Topics

Cognitive performance varies throughout the day. The survey identifies when you feel sharpest, and the scheduler prioritizes difficult material for those windows. Easier review material goes in off-peak slots.

### Cognitive Strength Adjustment

If you're strong at memorization (0.8) but weak at calculation (0.3), a memorization-heavy topic needs less time than a calculation-heavy one:
- Strong area (0.8): factor = 0.7 (less time needed)
- Weak area (0.3): factor = 1.2 (more time needed)

## Project Structure

```
exam_study_planner/
├── agent.py                 # Main coordinator agent
├── agents/
│   ├── profiler.py          # Study style assessment
│   ├── document_interpreter.py
│   └── optimizer.py
├── tools/
│   ├── survey_tools.py      # Profile survey logic
│   ├── document_tools.py    # PDF processing (~300 lines)
│   └── optimization_tools.py # Schedule generation (~290 lines)
└── models/
    ├── learner_profile.py
    ├── topic.py
    └── schedule.py
```

## Running It

```bash
# Install dependencies
pip install google-adk pymupdf

# Set up API key
echo "GOOGLE_API_KEY=your_key_here" > .env

# Run the web interface
adk web

# Or run directly
adk run exam_study_planner
```

## Example Output

```markdown
### Monday, 2026-02-10 (4.0h)

| Time  | Subject | Topic                          | Duration |
|-------|---------|--------------------------------|----------|
| 08:00 | HLTH    | 1. Introduction to Statistics  | 1.2h     |
| 09:30 | BSN     | Systems Thinking Basics        | 45m      |
| 17:00 | PHYS    | Quantum State Vectors          | 2.0h     |
```

## Limitations

- Only processes PDFs
- Complexity estimation is heuristic-based
- No calendar app integration (export only)
- Assumes consistent daily availability

## Dependencies

- `google-adk` - Agent framework
- `pymupdf` - PDF text extraction
