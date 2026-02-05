"""Schedule Optimizer Agent - Generates study plans."""

from google.adk.agents import LlmAgent

from ..tools.optimization_tools import (
    generate_schedule,
    export_schedule_csv,
    export_schedule_markdown,
    add_exam,
)


OPTIMIZER_INSTRUCTION = """Generate study schedules with simple calls.

## Generate schedule:
```
generate_schedule(start_date="2026-02-04", end_date="2026-02-15")
```

This distributes all topics proportionally across available days, putting harder topics during peak hours.

## Export with:
```
export_schedule_markdown()
```

## Two calls total:
1. generate_schedule(start_date, end_date)
2. export_schedule_markdown()

Report the results and return to coordinator."""


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
