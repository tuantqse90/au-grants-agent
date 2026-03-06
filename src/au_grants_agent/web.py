"""Streamlit web UI for AU Grants Agent."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import streamlit as st

from au_grants_agent.config import settings
from au_grants_agent.database import Database

# Page config
st.set_page_config(
    page_title="AU Grants Agent",
    page_icon="🇦🇺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header { color: #00ff88; font-size: 2rem; font-weight: bold; }
    .metric-card {
        background: #1a1a2e; border-left: 4px solid #00ff88;
        padding: 16px; border-radius: 4px; margin: 8px 0;
    }
    .grant-card {
        border: 1px solid #333; border-radius: 8px;
        padding: 16px; margin: 8px 0; background: #0d1117;
    }
    .score-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-weight: bold; color: white;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db() -> Database:
    return Database()


def page_dashboard():
    """Dashboard with stats and overview."""
    st.markdown('<p class="main-header">AU Grants Agent Dashboard</p>', unsafe_allow_html=True)

    db = get_db()
    try:
        stats = db.get_stats()
    except Exception:
        st.warning("Database not initialized. Run `au-grants init` first.")
        return

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Grants", stats["total_grants"])
    col2.metric("Open Grants", stats["open_grants"])
    col3.metric("Proposals", stats["total_proposals"])
    col4.metric("Sources", len(stats.get("sources", {})))

    # Sources breakdown
    st.subheader("Grants by Source")
    sources = stats.get("sources", {})
    if sources:
        col_a, col_b = st.columns(2)
        with col_a:
            import pandas as pd
            df = pd.DataFrame(list(sources.items()), columns=["Source", "Count"])
            st.bar_chart(df.set_index("Source"))
        with col_b:
            st.dataframe(
                pd.DataFrame(list(sources.items()), columns=["Source", "Count"]),
                use_container_width=True,
            )

    # Top categories
    if stats.get("top_categories"):
        st.subheader("Top Categories")
        import pandas as pd
        cat_df = pd.DataFrame(
            list(stats["top_categories"].items()),
            columns=["Category", "Count"],
        )
        st.bar_chart(cat_df.set_index("Category"))


def page_grants():
    """Browse and filter grants."""
    st.markdown('<p class="main-header">Browse Grants</p>', unsafe_allow_html=True)

    db = get_db()

    # Filters in sidebar
    with st.sidebar:
        st.subheader("Filters")
        status_filter = st.selectbox("Status", ["All", "Open", "Closed"])
        category_filter = st.text_input("Category (contains)")
        closing_soon = st.slider("Closing within (days)", 0, 365, 0)
        sort_by = st.selectbox("Sort by", ["closing_date", "title", "agency"])

    # Fetch grants
    status = status_filter if status_filter != "All" else None
    grants = db.list_grants(
        status=status,
        category=category_filter or None,
        sort_by=sort_by,
        closing_soon_days=closing_soon if closing_soon > 0 else None,
    )

    st.info(f"Showing {len(grants)} grants")

    if not grants:
        st.warning("No grants found. Run `au-grants crawl` to populate the database.")
        return

    # Display as table
    import pandas as pd
    rows = []
    for g in grants:
        amount = ""
        if g.amount_min:
            amount = f"${g.amount_min:,.0f}"
            if g.amount_max and g.amount_max != g.amount_min:
                amount += f" - ${g.amount_max:,.0f}"
        rows.append({
            "ID": g.id[:8],
            "Title": g.title[:60],
            "Agency": (g.agency or "")[:30],
            "Category": (g.category or "")[:25],
            "Amount": amount,
            "Closing": g.closing_date or "N/A",
            "Status": g.status,
            "Source": g.source or "",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=500)

    # Detail view
    st.subheader("Grant Detail")
    grant_ids = [g.id[:8] for g in grants]
    selected = st.selectbox("Select a grant", grant_ids)

    if selected:
        grant = next((g for g in grants if g.id.startswith(selected)), None)
        if grant:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Title:** {grant.title}")
                st.write(f"**Agency:** {grant.agency or 'N/A'}")
                st.write(f"**Category:** {grant.category or 'N/A'}")
                st.write(f"**Status:** {grant.status}")
                st.write(f"**GO ID:** {grant.go_id or 'N/A'}")
            with col2:
                amount = "Not specified"
                if grant.amount_min:
                    amount = f"${grant.amount_min:,.0f}"
                    if grant.amount_max and grant.amount_max != grant.amount_min:
                        amount += f" - ${grant.amount_max:,.0f}"
                st.write(f"**Amount:** {amount}")
                st.write(f"**Closing:** {grant.closing_date or 'N/A'}")
                st.write(f"**Source:** {grant.source or 'N/A'}")
                if grant.source_url:
                    st.write(f"**URL:** [{grant.source_url}]({grant.source_url})")

            if grant.eligibility:
                st.write("**Eligibility:**")
                st.text(grant.eligibility[:500])
            if grant.description:
                st.write("**Description:**")
                st.text(grant.description[:1000])


def page_matching():
    """Grant matching with org profiles."""
    st.markdown('<p class="main-header">Grant Matching</p>', unsafe_allow_html=True)

    from au_grants_agent.proposal.matcher import rank_grants
    from au_grants_agent.proposal.profiles import list_profiles, load_profile

    profiles = list_profiles()
    if not profiles:
        st.warning("No profiles found. Run `au-grants profile example` to create one.")
        return

    # Profile selector
    profile_names = [p[1] for p in profiles]
    profile_files = [p[0] for p in profiles]
    selected_idx = st.selectbox("Organisation Profile", range(len(profile_names)),
                                format_func=lambda i: profile_names[i])

    profile = load_profile(profile_files[selected_idx].replace(".yaml", ""))

    # Profile summary
    with st.expander("Profile Details"):
        st.write(f"**Name:** {profile.name}")
        st.write(f"**Type:** {profile.type or 'N/A'}")
        st.write(f"**State:** {profile.state or 'N/A'}")
        if profile.research_strengths:
            st.write(f"**Research Strengths:** {', '.join(profile.research_strengths)}")

    # Matching settings
    col1, col2 = st.columns(2)
    min_score = col1.slider("Minimum Score", 0.0, 1.0, 0.1, 0.05)
    top_n = col2.number_input("Top N Results", 5, 50, 20)

    db = get_db()
    grants = db.list_grants(status="open")

    if st.button("Run Matching", type="primary"):
        with st.spinner("Matching grants to profile..."):
            results = rank_grants(grants, profile, min_score=min_score, top_n=top_n)

        if not results:
            st.warning("No grants match above the threshold.")
            return

        st.success(f"Found {len(results)} matching grants")

        import pandas as pd
        rows = []
        for m in results:
            rows.append({
                "Score": f"{m.score:.0%}",
                "Rating": m.rating,
                "Title": m.grant.title[:50],
                "Agency": (m.grant.agency or "")[:25],
                "Category": (m.grant.category or "")[:20],
                "Reasons": "; ".join(m.reasons[:2]),
                "GO ID": m.grant.go_id or m.grant.id[:8],
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)


def page_crawl():
    """Crawl management page."""
    st.markdown('<p class="main-header">Crawl Management</p>', unsafe_allow_html=True)

    sources = ["All", "grants.gov.au", "business.gov.au", "arc.gov.au", "nhmrc.gov.au"]
    selected_source = st.selectbox("Source", sources)
    dry_run = st.checkbox("Dry Run (no save)")

    if st.button("Start Crawl", type="primary"):
        from au_grants_agent.crawler import ARCCrawler, BusinessGovCrawler, GrantsGovCrawler, NHMRCCrawler

        db = get_db()
        db.init_db()

        crawlers_map = {
            "grants.gov.au": GrantsGovCrawler,
            "business.gov.au": BusinessGovCrawler,
            "arc.gov.au": ARCCrawler,
            "nhmrc.gov.au": NHMRCCrawler,
        }

        if selected_source == "All":
            classes = list(crawlers_map.values())
        else:
            classes = [crawlers_map[selected_source]]

        for CrawlerClass in classes:
            with st.spinner(f"Crawling {CrawlerClass.SOURCE_NAME}..."):
                async def do_crawl(cls=CrawlerClass):
                    crawler = cls(db=db)
                    return await crawler.crawl(dry_run=dry_run)

                result = asyncio.run(do_crawl())

            status_color = "green" if result.status == "success" else "red"
            st.markdown(f"""
            **{result.source}** — :{status_color}[{result.status}]
            - Found: {result.grants_found} | New: {result.grants_new} | Updated: {result.grants_updated}
            - Duration: {result.duration_seconds}s
            """)
            if result.error_message:
                st.error(result.error_message)


def page_propose():
    """Proposal generation page."""
    st.markdown('<p class="main-header">Generate Proposal</p>', unsafe_allow_html=True)

    if not settings.has_api_key:
        st.error("API key not configured. Set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY in .env")
        return

    db = get_db()
    grants = db.list_grants(status="open")

    if not grants:
        st.warning("No grants available. Run a crawl first.")
        return

    # Grant selector
    grant_options = {f"{g.id[:8]} — {g.title[:60]}": g for g in grants}
    selected = st.selectbox("Select Grant", list(grant_options.keys()))
    grant = grant_options[selected]

    col1, col2 = st.columns(2)
    org_name = col1.text_input("Organisation Name", "")
    focus_area = col2.text_input("Focus Area", "")
    use_refine = st.checkbox("3-Pass Generation (Draft → Review → Refine)", value=True)

    if st.button("Generate Proposal", type="primary"):
        from au_grants_agent.proposal.generator import ProposalGenerator

        with st.spinner("Generating proposal... (this may take a few minutes)"):
            generator = ProposalGenerator(db=db)
            proposal = generator.generate(
                grant=grant,
                org_name=org_name or None,
                focus_area=focus_area or None,
                refine=use_refine,
            )

        st.success(f"Proposal generated! ({proposal.tokens_used:,} tokens)")

        tab1, tab2 = st.tabs(["English Proposal", "Vietnamese Summary"])
        with tab1:
            st.markdown(proposal.content_en)
        with tab2:
            st.markdown(proposal.summary_vi)


# ── Main App ──────────────────────────────────────────────────

PAGES = {
    "Dashboard": page_dashboard,
    "Browse Grants": page_grants,
    "Grant Matching": page_matching,
    "Crawl": page_crawl,
    "Generate Proposal": page_propose,
}

st.sidebar.title("AU Grants Agent")
st.sidebar.markdown(f"*Provider: {settings.provider_display}*")
st.sidebar.divider()

selection = st.sidebar.radio("Navigation", list(PAGES.keys()))
PAGES[selection]()

st.sidebar.divider()
st.sidebar.caption("NullShift | au-grants-agent v0.1.0")
