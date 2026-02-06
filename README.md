# Exam Study Planner

A multi-agent system built on Google's Agent Development Kit (ADK) that takes your course PDFs, asks a couple questions about how you study, and generates a day-by-day study schedule tailored to you.

## What it does

1. You upload your textbook PDFs and tell it your exam dates
2. It asks you 2 quick questions (how long you can focus, when you're sharpest)
3. It extracts every chapter/topic from your PDFs and estimates how long each one will take
4. It builds a full study schedule distributed across your available days, exported as a CSV you can open in Excel or Google Sheets

## How to run it

```bash
pip install google-adk pymupdf python-dotenv
```

Create a `.env` file inside `exam_study_planner/` with your Gemini API key:

```
GOOGLE_API_KEY=your_key_here
```

Then start it:

```bash
adk web exam_study_planner
```

Or run it in the terminal:

```bash
adk run exam_study_planner
```

## Project structure

```
exam_study_planner/
├── agent.py                    # Coordinator agent (routes between the others)
├── agents/
│   ├── profiler.py             # 2-question study style survey
│   ├── document_interpreter.py # PDF topic extraction
│   └── optimizer.py            # Schedule generation
├── tools/
│   ├── survey_tools.py         # Survey logic and profile scoring
│   ├── document_tools.py       # PDF parsing and complexity estimation
│   └── optimization_tools.py   # Scheduling algorithm and CSV/Markdown export
├── course_materials/           # Drop your PDFs here
├── .env                        # Your API key (not tracked by git)
└── requirements.txt
```

## How it works

### Agents

There are 4 agents that talk to each other through shared state:

- **CoordinatorAgent** - The main one. It guides you through the process and hands off to the right agent at each step.
- **ProfilerAgent** - Runs a 2-question survey to figure out your daily study capacity and when you focus best.
- **DocumentInterpreterAgent** - Reads your PDFs, finds all the chapters/sections, and estimates how complex each on is.
- **OptimizerAgent** - Takes all the topics and your profile, then builds the schedule and exports it to CSV.

### Profiling

The survey is intentionally short - just 2 questions:

| Question | What it determines |
|----------|-------------------|
| How long can you maintain deep focus? | Max daily study hours (4-8h) and session length (30min-2h) |
| When are you mentally sharpest? | Peak focus window (morning, midday, evening, night) |

### PDF processing

When you upload a PDF, it tries to extract the structure in this order:

1. **Table of contents** - Most reliable if the PDF has one
2. **Chapter heading patterns** - Scans every page for lines matching "Chapter 1...", "Unit 2...", etc. Deduplicates running headers that repeat on every page
3. **Page chunking** - Last resort fallback, splits the PDF into even chunks

For each section it finds, it samples the first page of text and estimates complexity (0.3-0.9) by counting math symbols, formulas, and definition keywords. STEM subjects get a slight complexity bump.

Study time per topic is estimated as: `pages x 0.4 hours x (0.5 + complexity)`, capped between 30 min and 8 hours.

### Scheduling

The scheduler works day by day:

1. Calculates how much total time is available (days x max daily hours)
2. Scales all topic estimates to fit the available window (never expands beyond 1.5x)
3. For each day, allocates time to each subject proportionally based on how much work remains
4. Fills sessions by cycling through subjects round-robin style, capping each session at your max focus duration
5. Skips 12-1pm for lunch

The schedule is saved to `study_schedule.csv` with columns: Date, Day, Start, End, Subject, Topic, Minutes.

### Why relative weights instead of fixed hours

If your PDFs total up to 200 hours of estimated study time but you only have 2 weeks, fixed hour estimates would overflow. Instead, the estimates act as relative weights - a topic estimated at 4 hours gets twice as much scheduled time as one estimated at 2 hours, regardless of how many days you actually have. The real hours are calculated at scheduling time based on your actual availability.

## Limitations

- Only works with PDFs (no web content, slides, or images)
- Complexity estimation is heuristic-based, not perfect
- No calendar integration - exports to CSV only
- Assumes you study every day (no weekend/holiday handling)
- Peak focus hours are tracked but not yet used for ordering hard topics first

## Dependencies

- [google-adk](https://google.github.io/adk-docs/) - Agent framework
- [google-genai](https://ai.google.dev/) - Gemini API
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF text extraction
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable loading
