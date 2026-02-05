from google.adk.agents import LlmAgent

from ..tools.document_tools import (
    process_document,
    list_topics,
    clear_topics,
)


DOCUMENT_INTERPRETER_INSTRUCTION = """Process documents to extract study topics.

## Available tools:
- clear_topics() - IMPORTANT!!!: Call this first if reprocessing or if there are old topics
- process_document(file_path, subject) - Extract topics from a PDF
- list_topics() - Show all current topics

## Workflow:
1. If user says "clear" or "restart" or there are too many topics: call clear_topics()
2. For each PDF: call process_document(file_path="...", subject="Subject Name")
3. Report results and return to coordinator

Example:
- User: "Clear topics and process my physics.pdf"
- You: Call clear_topics(), then process_document(file_path="physics.pdf", subject="Physics")
- Report: "Cleared old data. Found X topics requiring Y hours."
"""


document_interpreter_agent = LlmAgent(
    name="DocumentInterpreterAgent",
    model="gemini-2.5-flash",
    description="Processes PDFs to extract study topics. Can clear old topics with clear_topics().",
    instruction=DOCUMENT_INTERPRETER_INSTRUCTION,
    tools=[
        clear_topics,
        process_document,
        list_topics,
    ],
    output_key="document_output",
)
