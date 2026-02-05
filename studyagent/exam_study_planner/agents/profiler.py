from google.adk.agents import LlmAgent

from ..tools.survey_tools import (
    get_survey_questions,
    start_study_survey,
    process_survey_response,
    calculate_profile_scores,
    update_subject_confidence,
)


PROFILER_INSTRUCTION = """You help understand a student's study capacity and peak hours.

## Quick Survey (2 questions)
1. How long they can focus (determines daily study hours)
2. When they feel sharpest (determines when to schedule hard topics)

## How to Run
1. Use `start_study_survey` to begin
2. Present each question, use `process_survey_response` after each answer
3. Use `calculate_profile_scores` when done

## Communication
- Be friendly and quick
- Explain briefly why each question matters
- Present the summary at the end

The profile affects:
- How many hours per day get scheduled
- When difficult topics are placed (during peak hours)"""


profiler_agent = LlmAgent(
    name="ProfilerAgent",
    model="gemini-2.5-flash",
    description="Quick 2-question survey to determine daily study capacity and peak focus hours.",
    instruction=PROFILER_INSTRUCTION,
    tools=[
        get_survey_questions,
        start_study_survey,
        process_survey_response,
        calculate_profile_scores,
        update_subject_confidence,
    ],
    output_key="profiler_output",
)
