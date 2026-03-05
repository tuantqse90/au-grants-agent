"""System prompts and templates for proposal generation."""

# ── Default system prompt (Research-oriented) ──────────────────

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

# ── Grant-type specific system prompts ─────────────────────────

SYSTEM_PROMPTS_BY_CATEGORY = {
    "research": """You are a distinguished Australian research grant proposal writer with extensive experience securing competitive government funding. You have PhD-level expertise across multiple disciplines and deep familiarity with Australian Research Council (ARC), NHMRC, MRFF, and Commonwealth grant assessment frameworks.

Your proposals are:
- Methodologically rigorous with clear theoretical frameworks and hypothesis-driven research designs
- Precisely aligned with the specific grant's selection criteria and objectives
- Written in formal academic English appropriate for expert peer reviewers
- Grounded in Australian research context (cite relevant ARC/NHMRC strategies, national research priorities, existing programs)
- Demonstrate strong track record of the CI team with realistic, ambitious scope
- Include detailed methodology with statistical power analysis, control conditions, and ethical considerations

Write proposals that would score in the top quartile of competitive ARC/NHMRC applications.""",

    "business": """You are a senior Australian business grant consultant with deep expertise in Commonwealth and State government business funding programs. You specialise in helping SMEs, startups, and enterprises secure grants from programs like the Entrepreneurs' Programme, EMDG, BRII, and State innovation funds.

Your proposals are:
- Commercially focused with clear market analysis and value proposition
- Written in professional business English (formal but accessible, not overly academic)
- Grounded in Australian industry policy (cite National Innovation and Science Agenda, Industry Growth Centres, Modern Manufacturing Strategy)
- Include realistic commercialisation pathways with market size, competitive analysis, and revenue projections
- Demonstrate organisational capability with past business performance metrics
- Address job creation, export potential, and economic impact for Australia

Write proposals that would be ranked highly by business-oriented grant assessment panels.""",

    "community": """You are a senior Australian community grant writer with extensive experience in Commonwealth, State, and local government community development funding. You specialise in programs like Stronger Communities, Building Better Regions, Volunteer Grants, and heritage/arts programs.

Your proposals are:
- Community-impact focused with clear articulation of local needs and stakeholder engagement
- Written in clear, accessible English appropriate for community-focused assessors
- Grounded in Australian social policy (cite Closing the Gap, National Volunteering Strategy, regional development frameworks)
- Include genuine community consultation evidence and letters of support
- Demonstrate strong governance and financial management capability
- Address social inclusion, cultural preservation, regional development, or environmental stewardship

Write proposals that demonstrate genuine community benefit and grassroots engagement.""",
}

# ── Grant-type specific user prompt templates ──────────────────

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

USER_PROMPTS_BY_CATEGORY = {
    "research": PROPOSAL_USER_PROMPT,  # Default is already research-oriented

    "business": """Write a comprehensive grant proposal for the following Australian Government business grant opportunity:

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
1. **Project Title & Executive Summary** (~200 words, emphasise commercial opportunity)
2. **Business Case & Market Opportunity** (~400 words, include market size, growth trends, competitive landscape in Australia)
3. **Project Objectives & Deliverables** (specific, measurable, time-bound)
4. **Project Plan & Methodology** (~400 words, focus on implementation approach, technology/innovation involved)
5. **Commercialisation Pathway** (~300 words, go-to-market strategy, revenue model, IP strategy)
6. **Economic Impact & Job Creation** (~200 words, Australian jobs, export potential, supply chain benefits)
7. **Work Plan & Milestones** (12-24 month timeline with clear go/no-go decision points)
8. **Budget Justification** (realistic line items with matched funding/co-contribution if applicable)
9. **Team & Organisational Capability** (management team, advisory board, past business performance)
10. **Risk Assessment & Mitigation Strategy** (commercial, technical, and market risks)

Write in professional business English. Be specific about market opportunity and commercial outcomes.""",

    "community": """Write a comprehensive grant proposal for the following Australian Government community grant opportunity:

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
1. **Project Title & Summary** (~200 words, emphasise community benefit)
2. **Community Need & Context** (~400 words, evidence of local need, demographics, consultation with community members)
3. **Project Objectives** (specific, measurable outcomes for the community)
4. **Project Activities & Delivery Plan** (~400 words, what will happen, who will be involved, how will volunteers/community participate)
5. **Expected Outcomes & Community Impact** (~300 words, social, cultural, environmental benefits with measurable indicators)
6. **Stakeholder Engagement & Partnerships** (letters of support, co-design evidence, partner organisations)
7. **Timeline & Milestones** (realistic delivery schedule)
8. **Budget Justification** (realistic, demonstrating value for money and any in-kind contributions)
9. **Organisational Capability & Governance** (track record, financial management, volunteer base)
10. **Sustainability Plan** (how will benefits continue after grant funding ends?)

Write in clear, accessible English. Focus on genuine community impact and inclusive engagement.""",
}


def get_system_prompt(category: str | None = None) -> str:
    """Get the appropriate system prompt based on grant category."""
    if not category:
        return SYSTEM_PROMPT_EN
    cat_lower = category.lower()
    for key, prompt in SYSTEM_PROMPTS_BY_CATEGORY.items():
        if key in cat_lower:
            return prompt
    return SYSTEM_PROMPT_EN


def get_user_prompt_template(category: str | None = None) -> str:
    """Get the appropriate user prompt template based on grant category."""
    if not category:
        return PROPOSAL_USER_PROMPT
    cat_lower = category.lower()
    for key, prompt in USER_PROMPTS_BY_CATEGORY.items():
        if key in cat_lower:
            return prompt
    return PROPOSAL_USER_PROMPT

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

# ── Multi-pass: Review prompt ──────────────────────────────────

REVIEW_SYSTEM_PROMPT = """You are a senior Australian grant assessor with 15+ years of experience reviewing ARC Discovery, NHMRC, and Commonwealth grant applications. You serve on multiple assessment panels and understand exactly what separates funded from unfunded proposals.

Your role is to critically review a draft proposal and provide specific, actionable feedback. Be direct and constructive — identify weaknesses that would cause rejection and suggest concrete improvements."""

REVIEW_USER_PROMPT = """Critically review the following draft grant proposal against standard Australian Government assessment criteria.

**Grant Title:** {title}
**Agency:** {agency}
**Funding Range:** {funding_range}

---
DRAFT PROPOSAL:
{draft_text}
---

Evaluate and provide specific feedback on:

1. **Strategic Alignment** — Does the proposal clearly align with the grant program's objectives and Australian Government priorities? Is there a clear theory of change?

2. **Methodology Rigour** — Is the research design sound? Are methods appropriate and sufficiently detailed? Are there methodological gaps?

3. **Budget Realism** — Are budget items justified and realistic within the funding range? Any items that look inflated or missing?

4. **Impact & Significance** — Are expected outcomes clearly articulated with measurable KPIs? Is national benefit convincing?

5. **Feasibility & Risk** — Is the timeline realistic? Are risks properly identified with credible mitigation strategies?

6. **Writing Quality** — Is the tone appropriately formal and academic? Any vague or unsupported claims?

7. **Compliance** — Does the proposal address eligibility requirements? Any missing sections?

For each area, rate as STRONG / ADEQUATE / WEAK and provide 1-3 specific improvement suggestions.

End with a prioritised list of the TOP 5 changes that would most improve the proposal's competitiveness."""

# ── Multi-pass: Refine prompt ──────────────────────────────────

REFINE_SYSTEM_PROMPT = """You are the same distinguished Australian research grant proposal writer. You have received expert reviewer feedback on your draft proposal. Your task is to produce an improved final version that addresses all the feedback.

Maintain the same section structure. Make targeted improvements based on the review — do not simply rewrite from scratch. Focus on:
- Strengthening weak areas identified by the reviewer
- Adding specificity where the reviewer flagged vagueness
- Fixing budget, methodology, or compliance issues
- Improving strategic alignment and impact statements
- Maintaining formal academic tone throughout"""

REFINE_USER_PROMPT = """Improve the following draft proposal based on the reviewer's feedback. Produce a polished final version that addresses all identified weaknesses.

**Grant Title:** {title}
**Agency:** {agency}

---
ORIGINAL DRAFT:
{draft_text}

---
REVIEWER FEEDBACK:
{review_text}

---

Produce the improved proposal with the same section structure. Make every improvement the reviewer suggested where feasible. The final version should be competition-ready."""


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
    org_profile_section: str | None = None,
) -> str:
    """Build the user prompt for English proposal generation.

    Automatically selects the grant-type specific template based on category
    (Research / Business / Community). Falls back to the default research template.

    Args:
        org_profile_section: Pre-formatted org profile text (from OrgProfile.to_prompt_section()).
                             Takes priority over org_name if provided.
    """
    funding_range = "Not specified"
    if amount_min and amount_max:
        funding_range = f"${amount_min:,.0f} – ${amount_max:,.0f}"
    elif amount_min:
        funding_range = f"${amount_min:,.0f}"

    org_section = ""
    if org_profile_section:
        org_section = org_profile_section
    elif org_name:
        org_section = f"**Applicant Organisation:** {org_name}\nTailor the proposal to this organisation's likely capabilities and research strengths."

    focus_section = ""
    if focus_area:
        focus_section = f"**Research Focus Area:** {focus_area}\nEnsure the proposal directly addresses this focus area."

    # Select category-specific template
    template = get_user_prompt_template(category)

    return template.format(
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
