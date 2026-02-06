"""Schedule Optimizer Agent - Generates study plans."""

from datetime import date

from google.adk.agents import LlmAgent

from ..tools.optimization_tools import (
    generate_schedule,
    export_schedule_csv,
    export_schedule_markdown,
    add_exam,
)


_today = date.today().isoformat()

OPTIMIZER_INSTRUCTION = f"""Generate study schedules with simple calls.

## Generate schedule:
Today's date is {_today}. Always use today as the start_date unless the user specifies otherwise.
```
generate_schedule(start_date="{_today}", end_date="YYYY-MM-DD")
```

This distributes all topics proportionally across available days, putting harder topics during peak hours.

## Export with:
```
export_schedule_csv()
```

## Two calls total:
1. generate_schedule(start_date, end_date)
2. export_schedule_csv()

## IMPORTANT: export_schedule_csv() saves the full schedule to a CSV file.
Tell the user the file path so they can open it. Also share the summary (period, total hours, hours per subject).
Do NOT try to print the schedule inline — it's saved to the file."""


optimizer_agent = LlmAgent(
    name="OptimizerAgent",
    model="gemini-2.5-flash",
    description="Creates study schedules based on topic weights and learner profile.",
    instruction=OPTIMIZER_INSTRUCTION,
    tools=[
        generate_schedule,
        export_schedule_markdown,
        export_schedule_csv,
        add_exam,
    ],
    output_key="optimizer_output",
)
