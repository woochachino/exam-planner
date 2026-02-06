"""Document processing - extracts topics with estimated study hours."""

from typing import List
from google.adk.tools import ToolContext
import re
import hashlib


def process_document(
    file_path: str,
    subject: str,
    tool_context: ToolContext,
) -> dict:
    """Extract topics from PDF with estimated study hours."""
    try:
        import fitz
    except ImportError:
        return {"status": "error", "message": "PyMuPDF not installed. Run: pip install pymupdf"}

    filename = file_path.split("/")[-1] if "/" in file_path else file_path

    if not filename.lower().endswith('.pdf'):
        return {"status": "error", "message": f"Not a PDF: {filename}"}

    try:
        pdf_doc = None
        uploaded = tool_context.state.get("uploaded_files", {})

        if filename in uploaded:
            import base64
            data = uploaded[filename]
            if isinstance(data, bytes):
                pdf_doc = fitz.open(stream=data, filetype="pdf")
            else:
                pdf_doc = fitz.open(stream=base64.b64decode(data), filetype="pdf")
        else:
            pdf_doc = fitz.open(file_path)

        total_pages = len(pdf_doc)
        structure = _extract_structure(pdf_doc, total_pages)
        section_samples = _sample_section_content(pdf_doc, structure)
        pdf_doc.close()

        topics = _create_topics(structure, section_samples, subject, filename, total_pages, tool_context)

        doc_id = hashlib.md5(f"{filename}_{total_pages}".encode()).hexdigest()[:8]
        documents = tool_context.state.get("documents", {})
        documents[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "subject": subject,
            "total_pages": total_pages,
            "topics": [t["topic_id"] for t in topics],
        }
        tool_context.state["documents"] = documents

        total_hours = sum(t["estimated_hours"] for t in topics)

        return {
            "status": "success",
            "subject": subject,
            "filename": filename,
            "pages": total_pages,
            "topics_created": len(topics),
            "total_hours": round(total_hours, 1),
            "topics": [f"{t['title']} ({t['estimated_hours']}h)" for t in topics[:15]],
            "message": f"Found {len(topics)} topics requiring {total_hours:.1f} hours total"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def _extract_structure(pdf_doc, total_pages: int) -> List[dict]:
    """Get major sections - chapters/units from TOC or heading patterns."""
    structure = []

    skip_lower = {'contents', 'index', 'bibliography', 'references', 'glossary',
                  'acknowledgment', 'preface', 'foreword', 'dedication', 'about the author',
                  'table of contents', 'list of figures', 'list of tables', 'credits',
                  'back cover', 'front cover', 'cover', 'title page', 'copyright',
                  'copyright page', 'appendix', 'answers', 'data sets', 'websites',
                  'odd-numbered', 'even-numbered'}

    # Try TOC first - level 1 and 2 (Parts + Chapters)
    toc = pdf_doc.get_toc()
    if toc:
        for level, title, page in toc:
            title_clean = title.strip()
            title_lower = title_clean.lower()
            if level <= 2 and len(title_clean) > 2:
                if title_lower not in skip_lower and not any(skip in title_lower for skip in skip_lower):
                    structure.append({"title": title_clean, "page": page})

    # If no TOC, scan for chapter headings across ALL pages
    if len(structure) < 3:
        patterns = [
            r'^Chapter\s+\d+',
            r'^Unit\s+\d+',
            r'^Module\s+\d+',
            r'^\d+\.\s+[A-Z][a-z]',
        ]
        seen_titles = set()

        for page_num in range(total_pages):
            text = pdf_doc[page_num].get_text()
            for line in text.split('\n')[:10]:
                line = line.strip()
                if 5 < len(line) < 80 and line.lower() not in skip_lower:
                    for p in patterns:
                        if re.match(p, line, re.IGNORECASE):
                            # deduplicate running headers
                            if line not in seen_titles:
                                seen_titles.add(line)
                                structure.append({"title": line, "page": page_num + 1})
                            break

    # Fallback: create chunks by page ranges
    if len(structure) < 2:
        pages_per_chunk = max(20, total_pages // 10)
        for i in range(0, total_pages, pages_per_chunk):
            structure.append({
                "title": f"Section {i // pages_per_chunk + 1} (Pages {i+1}-{min(i+pages_per_chunk, total_pages)})",
                "page": i + 1
            })

    structure.sort(key=lambda x: x["page"])
    return structure


def _sample_section_content(pdf_doc, structure: List[dict]) -> dict:
    """Sample first page of each section for complexity estimation."""
    samples = {}
    for section in structure:
        start_page = section["page"] - 1
        if start_page < len(pdf_doc):
            samples[section["title"]] = pdf_doc[start_page].get_text()[:1500]
    return samples


def _estimate_complexity(text: str, subject: str) -> float:
    """Estimate complexity 0.3-0.9 from content. Used for scheduling hard topics during peak hours."""
    if not text:
        return 0.5

    math_symbols = len(re.findall(r'[∑∫∂∇≤≥≠±×÷√∞∈∀∃=]', text))
    formulas = len(re.findall(r'\b[a-z]\s*=\s*[^,\n]{3,}', text.lower()))
    definitions = len(re.findall(r'\b(defined?|means?|refers?\s+to|is\s+called)\b', text.lower()))

    complexity = 0.4
    if math_symbols > 3:
        complexity += 0.15
    if formulas > 2:
        complexity += 0.15
    if definitions > 3:
        complexity += 0.1

    subject_lower = subject.lower()
    if any(s in subject_lower for s in ['physics', 'math', 'calculus', 'chem']):
        complexity += 0.1

    return min(0.9, max(0.3, complexity))


def _create_topics(
    structure: List[dict],
    samples: dict,
    subject: str,
    filename: str,
    total_pages: int,
    tool_context: ToolContext,
) -> List[dict]:
    """Create topics with estimated hours."""
    all_topics = tool_context.state.get("topics", [])
    new_topics = []
    doc_id = hashlib.md5(f"{filename}_{total_pages}".encode()).hexdigest()[:8]

    for i, section in enumerate(structure):
        title = section["title"][:60]
        start_page = section["page"]
        end_page = structure[i + 1]["page"] - 1 if i + 1 < len(structure) else total_pages
        pages = max(1, end_page - start_page + 1)

        sample_text = samples.get(section["title"], "")
        complexity = _estimate_complexity(sample_text, subject)

        # Hours = pages × 0.4 (25 min/page) × complexity factor (0.8-1.4)
        complexity_factor = 0.5 + complexity
        estimated_hours = round(pages * 0.4 * complexity_factor, 1)
        estimated_hours = max(0.5, min(estimated_hours, 8.0))

        topic = {
            "topic_id": f"{doc_id}_{i:02d}",
            "subject": subject,
            "title": title,
            "page_range": [start_page, end_page],
            "estimated_hours": estimated_hours,
            "complexity": round(complexity, 2),  # Used for peak hours scheduling
        }
        new_topics.append(topic)
        all_topics.append(topic)

    tool_context.state["topics"] = all_topics
    return new_topics


def list_topics(tool_context: ToolContext) -> dict:
    """List all topics grouped by subject."""
    topics = tool_context.state.get("topics", [])

    by_subject = {}
    for t in topics:
        subj = t.get("subject", "Unknown")
        if subj not in by_subject:
            by_subject[subj] = {"topics": [], "total_hours": 0}
        by_subject[subj]["topics"].append({
            "title": t["title"],
            "hours": t.get("estimated_hours", 1),
        })
        by_subject[subj]["total_hours"] += t.get("estimated_hours", 1)

    for subj in by_subject:
        by_subject[subj]["total_hours"] = round(by_subject[subj]["total_hours"], 1)

    total_hours = sum(t.get("estimated_hours", 1) for t in topics)

    return {
        "status": "success",
        "total_topics": len(topics),
        "total_hours": round(total_hours, 1),
        "by_subject": by_subject,
    }


def clear_topics(tool_context: ToolContext) -> dict:
    """Clear all topics and documents."""
    tool_context.state["topics"] = []
    tool_context.state["documents"] = {}
    return {"status": "success", "message": "All topics cleared"}
