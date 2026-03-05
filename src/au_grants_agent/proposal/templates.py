"""System prompts and templates for proposal generation."""

SYSTEM_PROMPT_EN = """You are a distinguished Australian research grant proposal writer with extensive experience securing competitive government funding. You have PhD-level expertise across multiple disciplines and deep familiarity with Australian Research Council (ARC), NHMRC, and Commonwealth grant assessment frameworks.

Your proposals are:
- Methodologically rigorous with clear theoretical frameworks
- Precisely aligned with the specific grant's selection criteria and objectives
- Written in formal academic English appropriate for Australian government reviewers
- Grounded in Australian policy context (cite relevant national strategies, white papers, existing programs)
- Realistic in scope, timeline, and budget

Write proposals that would score in the top quartile of competitive applications."""

SYSTEM_PROMPT_VI = """You are a bilingual research consultant fluent in both English and Vietnamese. Given an English grant proposal, produce a concise Vietnamese summary (Tóm tắt bằng Tiếng Việt) covering:
- Tên dự án và mục tiêu chính
- Phương pháp nghiên cứu
- Ngân sách dự kiến
- Kết quả mong đợi và tác động
- Timeline tổng quan

Write naturally in Vietnamese as a native speaker would. Not machine-translated. Academic but accessible tone. Keep it 300-500 words."""

PROPOSAL_USER_PROMPT = """Write a comprehensive grant proposal for the following Australian Government grant opportunity:

**Grant Title:** {title}
**Agency:** {agency}
**Category:** {category}
**Funding Range:** {funding_range}
**Closing Date:** {closing_date}
**Eligibility:** {eligibility}

**Grant Description:**
{description}

{org_section}
{focus_section}

Structure the proposal with these sections:
1. **Project Title & Executive Summary** (~200 words)
2. **Background & Significance** (~400 words, grounded in Australian research context)
3. **Research Questions & Objectives** (specific, measurable)
4. **Methodology & Research Design** (~400 words, detailed)
5. **Expected Outcomes & National Benefit** (~200 words)
6. **Work Plan & Milestones** (12-24 month Gantt-style table)
7. **Budget Justification** (realistic line items within the grant funding range)
8. **Team & Institutional Capability**
9. **Risk Assessment & Mitigation Strategy**
10. **References** (10-15 indicative references with realistic authors and journals)

Write in formal academic English. Be specific, concrete, and compelling."""

VIETNAMESE_SUMMARY_PROMPT = """Produce a concise Vietnamese summary (Tóm tắt bằng Tiếng Việt) of the following English grant proposal. Cover:
- Tên dự án và mục tiêu chính
- Phương pháp nghiên cứu
- Ngân sách dự kiến
- Kết quả mong đợi và tác động
- Timeline tổng quan

Write naturally in Vietnamese as a native speaker would. Academic but accessible tone. 300-500 words.

---
PROPOSAL:
{proposal_text}"""


def build_proposal_prompt(
    title: str,
    agency: str | None = None,
    category: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    closing_date: str | None = None,
    eligibility: str | None = None,
    description: str | None = None,
    org_name: str | None = None,
    focus_area: str | None = None,
) -> str:
    """Build the user prompt for English proposal generation."""
    funding_range = "Not specified"
    if amount_min and amount_max:
        funding_range = f"${amount_min:,.0f} – ${amount_max:,.0f}"
    elif amount_min:
        funding_range = f"${amount_min:,.0f}"

    org_section = ""
    if org_name:
        org_section = f"**Applicant Organisation:** {org_name}\nTailor the proposal to this organisation's likely capabilities and research strengths."

    focus_section = ""
    if focus_area:
        focus_section = f"**Research Focus Area:** {focus_area}\nEnsure the proposal directly addresses this focus area."

    return PROPOSAL_USER_PROMPT.format(
        title=title,
        agency=agency or "Australian Government",
        category=category or "General",
        funding_range=funding_range,
        closing_date=closing_date or "Not specified",
        eligibility=eligibility or "See grant guidelines",
        description=description or "No detailed description available.",
        org_section=org_section,
        focus_section=focus_section,
    )
