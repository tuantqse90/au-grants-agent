"""Click CLI entrypoint for au-grants-agent."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from au_grants_agent.config import settings

THEME = Theme({"info": "#00ff88", "warning": "yellow", "error": "bold red"})
console = Console(theme=THEME)


class Context:
    """Shared CLI context."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose


pass_ctx = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """AU Grants Agent — Crawl Australian grants & generate proposals."""
    from au_grants_agent.utils.logger import setup_logging

    ctx.ensure_object(Context)
    ctx.obj.verbose = verbose
    setup_logging(verbose=verbose)


# ── init ────────────────────────────────────────────────────────

@cli.command()
@pass_ctx
def init(ctx: Context) -> None:
    """Initialize database and verify API key."""
    from au_grants_agent.database import Database

    settings.ensure_dirs()
    db = Database()
    db.init_db()

    console.print(Panel(
        f"[bold]Database:[/bold] {settings.db_path}\n"
        f"[bold]LLM Provider:[/bold] {settings.provider_display}\n"
        f"[bold]API Key:[/bold] {'[green]Configured[/green]' if settings.has_api_key else '[red]NOT SET[/red]'}\n"
        f"[bold]Proposals Dir:[/bold] {settings.proposals_dir}",
        title="[#00ff88]AU Grants Agent — Initialized[/#00ff88]",
        border_style="#00ff88",
    ))

    if not settings.has_api_key:
        if settings.llm_provider == "deepseek":
            console.print("[yellow]Set DEEPSEEK_API_KEY in .env to enable proposal generation.[/yellow]")
        else:
            console.print("[yellow]Set ANTHROPIC_API_KEY in .env to enable proposal generation.[/yellow]")


# ── config ──────────────────────────────────────────────────────

@cli.command()
@pass_ctx
def config(ctx: Context) -> None:
    """Show current configuration."""
    table = Table(title="Configuration", border_style="#00ff88")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("DB Path", str(settings.db_path))
    table.add_row("LLM Provider", settings.provider_display)
    table.add_row("API Key", "[green]Configured[/green]" if settings.has_api_key else "[red]NOT SET[/red]")
    table.add_row("Crawl Delay", f"{settings.crawl_delay}s")
    table.add_row("Log Level", settings.log_level)
    table.add_row("Export Format", settings.default_export_format)
    table.add_row("Proposals Dir", str(settings.proposals_dir))

    console.print(table)


# ── crawl ───────────────────────────────────────────────────────

@cli.command()
@click.option("--source", type=click.Choice(["grants.gov.au", "business.gov.au", "arc.gov.au", "nhmrc.gov.au"]), help="Crawl a specific source")
@click.option("--category", default=None, help="Filter by category")
@click.option("--dry-run", is_flag=True, help="Fetch & parse without saving")
@pass_ctx
def crawl(ctx: Context, source: Optional[str], category: Optional[str], dry_run: bool) -> None:
    """Crawl Australian Government grant websites."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from au_grants_agent.crawler import ARCCrawler, BusinessGovCrawler, GrantsGovCrawler, NHMRCCrawler
    from au_grants_agent.database import Database

    db = Database()
    db.init_db()

    crawlers = []
    if source == "grants.gov.au" or source is None:
        crawlers.append(GrantsGovCrawler(db=db))
    if source == "business.gov.au" or source is None:
        crawlers.append(BusinessGovCrawler(db=db))
    if source == "arc.gov.au" or source is None:
        crawlers.append(ARCCrawler(db=db))
    if source == "nhmrc.gov.au" or source is None:
        crawlers.append(NHMRCCrawler(db=db))

    async def run_crawl():
        results = []
        for crawler in crawlers:
            with Progress(
                SpinnerColumn(style="#00ff88"),
                TextColumn("[bold]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Crawling {crawler.SOURCE_NAME}...", total=None)
                result = await crawler.crawl(dry_run=dry_run, category=category)
                progress.update(task, completed=True)
            results.append(result)

            # Display result
            status_color = "green" if result.status == "success" else "red"
            console.print(Panel(
                f"[bold]Source:[/bold] {result.source}\n"
                f"[bold]Status:[/bold] [{status_color}]{result.status}[/{status_color}]\n"
                f"[bold]Grants Found:[/bold] {result.grants_found}\n"
                f"[bold]New:[/bold] {result.grants_new}  |  [bold]Updated:[/bold] {result.grants_updated}\n"
                f"[bold]Duration:[/bold] {result.duration_seconds}s"
                + (f"\n[bold red]Error:[/bold red] {result.error_message}" if result.error_message else ""),
                title=f"[#00ff88]Crawl Result — {result.source}[/#00ff88]",
                border_style="#00ff88",
            ))
        return results

    asyncio.run(run_crawl())


# ── list ────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--status", default=None, help="Filter by status (Open, Closed)")
@click.option("--sort", "sort_by", default="closing_date", help="Sort field")
@click.option("--category", default=None, help="Filter by category")
@click.option("--closing-soon", type=int, default=None, help="Closing within N days")
@pass_ctx
def list_grants(
    ctx: Context,
    status: Optional[str],
    sort_by: str,
    category: Optional[str],
    closing_soon: Optional[int],
) -> None:
    """List grants in a rich table."""
    from au_grants_agent.database import Database

    db = Database()
    grants = db.list_grants(
        status=status, category=category, sort_by=sort_by, closing_soon_days=closing_soon,
    )

    if not grants:
        console.print("[yellow]No grants found. Run 'au-grants crawl' first.[/yellow]")
        return

    table = Table(title=f"Grants ({len(grants)})", border_style="#00ff88", show_lines=True)
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Title", max_width=50)
    table.add_column("Agency", max_width=25)
    table.add_column("Category", max_width=20)
    table.add_column("Amount", justify="right")
    table.add_column("Closing", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Source")

    now = datetime.utcnow()
    for g in grants:
        # Color status
        status_style = "grey50"
        if g.status and g.status.lower() == "open":
            status_style = "green"
        if g.closing_date:
            try:
                cd = datetime.fromisoformat(g.closing_date)
                days_left = (cd - now).days
                if 0 <= days_left <= 30:
                    status_style = "red"
            except ValueError:
                pass

        amount = ""
        if g.amount_min and g.amount_max:
            amount = f"${g.amount_min:,.0f}–${g.amount_max:,.0f}"
        elif g.amount_min:
            amount = f"${g.amount_min:,.0f}"

        table.add_row(
            g.id[:8],
            g.title[:50],
            (g.agency or "")[:25],
            (g.category or "")[:20],
            amount,
            g.closing_date or "",
            f"[{status_style}]{g.status or 'Unknown'}[/{status_style}]",
            g.source or "",
        )

    console.print(table)


# ── show ────────────────────────────────────────────────────────

@cli.command()
@click.argument("grant_id")
@pass_ctx
def show(ctx: Context, grant_id: str) -> None:
    """Show full details for a grant."""
    from au_grants_agent.database import Database

    db = Database()

    # Support partial ID match
    grant = db.get_grant(grant_id)
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break

    if not grant:
        console.print(f"[red]Grant '{grant_id}' not found.[/red]")
        return

    amount = "Not specified"
    if grant.amount_min and grant.amount_max:
        amount = f"${grant.amount_min:,.0f} – ${grant.amount_max:,.0f}"
    elif grant.amount_min:
        amount = f"${grant.amount_min:,.0f}"

    content = (
        f"[bold]Title:[/bold] {grant.title}\n"
        f"[bold]GO ID:[/bold] {grant.go_id or 'N/A'}\n"
        f"[bold]Agency:[/bold] {grant.agency or 'N/A'}\n"
        f"[bold]Category:[/bold] {grant.category or 'N/A'}\n"
        f"[bold]Amount:[/bold] {amount}\n"
        f"[bold]Closing Date:[/bold] {grant.closing_date or 'N/A'}\n"
        f"[bold]Status:[/bold] {grant.status}\n"
        f"[bold]Source:[/bold] {grant.source or 'N/A'}\n"
        f"[bold]URL:[/bold] {grant.source_url or 'N/A'}\n"
        f"\n[bold]Eligibility:[/bold]\n{grant.eligibility or 'N/A'}\n"
        f"\n[bold]Description:[/bold]\n{(grant.description or 'N/A')[:1000]}"
    )

    console.print(Panel(
        content,
        title=f"[#00ff88]Grant: {grant.id[:8]}[/#00ff88]",
        border_style="#00ff88",
    ))


# ── stats ───────────────────────────────────────────────────────

@cli.command()
@pass_ctx
def stats(ctx: Context) -> None:
    """Show summary dashboard."""
    from au_grants_agent.database import Database

    db = Database()
    try:
        s = db.get_stats()
    except Exception:
        console.print("[yellow]Database not initialized. Run 'au-grants init' first.[/yellow]")
        return

    table = Table(title="Dashboard", border_style="#00ff88")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Grants", str(s["total_grants"]))
    table.add_row("Open Grants", str(s["open_grants"]))
    table.add_row("Total Proposals", str(s["total_proposals"]))

    for source, count in s.get("sources", {}).items():
        table.add_row(f"  Source: {source}", str(count))

    console.print(table)

    if s.get("top_categories"):
        cat_table = Table(title="Top Categories", border_style="#00ff88")
        cat_table.add_column("Category")
        cat_table.add_column("Count", justify="right")
        for cat, count in s["top_categories"].items():
            cat_table.add_row(cat, str(count))
        console.print(cat_table)


# ── export-grants ───────────────────────────────────────────────

@cli.command("export-grants")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv"]))
@click.option("--output", "output_path", default=None, help="Output file path")
@pass_ctx
def export_grants(ctx: Context, fmt: str, output_path: Optional[str]) -> None:
    """Export all grants to CSV."""
    from au_grants_agent.database import Database

    db = Database()
    grants = db.list_grants()

    if not grants:
        console.print("[yellow]No grants to export.[/yellow]")
        return

    out_path = Path(output_path) if output_path else Path(f"grants_export_{datetime.utcnow().strftime('%Y%m%d')}.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "go_id", "title", "agency", "category",
            "amount_min", "amount_max", "closing_date", "status", "source", "source_url",
        ])
        for g in grants:
            writer.writerow([
                g.id, g.go_id, g.title, g.agency, g.category,
                g.amount_min, g.amount_max, g.closing_date, g.status, g.source, g.source_url,
            ])

    console.print(f"[#00ff88]Exported {len(grants)} grants to {out_path}[/#00ff88]")


# ── profile ────────────────────────────────────────────────────

@cli.group()
def profile() -> None:
    """Manage organisation profiles for tailored proposals."""
    pass


@profile.command("create")
@click.option("--name", prompt="Organisation name", help="Organisation name")
@click.option("--type", "org_type", default=None, help="Type (University, Research Institute, SME)")
@click.option("--state", default=None, help="State (NSW, VIC, QLD, etc.)")
@click.option("--description", "desc", default=None, help="Short description")
def profile_create(name: str, org_type: Optional[str], state: Optional[str], desc: Optional[str]) -> None:
    """Create a new organisation profile."""
    from au_grants_agent.proposal.profiles import OrgProfile, save_profile

    profile_obj = OrgProfile(
        name=name,
        type=org_type,
        state=state,
        description=desc,
    )
    path = save_profile(profile_obj)
    console.print(f"[#00ff88]Profile created: {path}[/#00ff88]")
    console.print("[dim]Edit the YAML file to add research strengths, personnel, past grants, etc.[/dim]")


@profile.command("example")
def profile_example() -> None:
    """Create an example profile YAML for reference."""
    from au_grants_agent.proposal.profiles import create_example_profile

    path = create_example_profile()
    console.print(f"[#00ff88]Example profile created: {path}[/#00ff88]")
    console.print("[dim]Copy and edit this file to create your own profile.[/dim]")


@profile.command("list")
def profile_list() -> None:
    """List available organisation profiles."""
    from au_grants_agent.proposal.profiles import list_profiles

    profiles = list_profiles()
    if not profiles:
        console.print("[yellow]No profiles found. Run 'au-grants profile example' to get started.[/yellow]")
        return

    table = Table(title="Organisation Profiles", border_style="#00ff88")
    table.add_column("File", style="dim")
    table.add_column("Organisation")
    for filename, org_name in profiles:
        table.add_row(filename, org_name)
    console.print(table)


@profile.command("show")
@click.argument("name")
def profile_show(name: str) -> None:
    """Show details of an organisation profile."""
    from au_grants_agent.proposal.profiles import load_profile

    try:
        p = load_profile(name)
    except FileNotFoundError:
        console.print(f"[red]Profile '{name}' not found.[/red]")
        return

    content = f"[bold]Name:[/bold] {p.name}\n"
    if p.type:
        content += f"[bold]Type:[/bold] {p.type}\n"
    if p.state:
        content += f"[bold]State:[/bold] {p.state}\n"
    if p.description:
        content += f"[bold]Description:[/bold] {p.description}\n"
    if p.research_strengths:
        content += f"\n[bold]Research Strengths:[/bold]\n"
        for s in p.research_strengths:
            content += f"  - {s}\n"
    if p.key_personnel:
        content += f"\n[bold]Key Personnel:[/bold]\n"
        for person in p.key_personnel:
            content += f"  - {person.name} ({person.role})"
            if person.expertise:
                content += f" — {person.expertise}"
            content += "\n"
    if p.past_grants:
        content += f"\n[bold]Past Grants:[/bold]\n"
        for g in p.past_grants:
            content += f"  - {g}\n"
    if p.facilities:
        content += f"\n[bold]Facilities:[/bold]\n"
        for f in p.facilities:
            content += f"  - {f}\n"

    console.print(Panel(content, title=f"[#00ff88]Profile: {p.name}[/#00ff88]", border_style="#00ff88"))


# ── match ──────────────────────────────────────────────────────

@cli.command()
@click.argument("profile_name")
@click.option("--top", "top_n", default=10, help="Number of top matches to show")
@click.option("--min-score", default=0.1, help="Minimum match score (0.0-1.0)")
@click.option("--status", default=None, help="Filter by grant status (Open, Closed)")
@pass_ctx
def match(
    ctx: Context,
    profile_name: str,
    top_n: int,
    min_score: float,
    status: Optional[str],
) -> None:
    """Match grants to an organisation profile by relevance."""
    from au_grants_agent.database import Database
    from au_grants_agent.proposal.matcher import rank_grants
    from au_grants_agent.proposal.profiles import load_profile

    try:
        profile = load_profile(profile_name)
    except FileNotFoundError:
        console.print(f"[red]Profile '{profile_name}' not found. Run 'au-grants profile list'.[/red]")
        return

    db = Database()
    grants = db.list_grants(status=status)

    if not grants:
        console.print("[yellow]No grants found. Run 'au-grants crawl' first.[/yellow]")
        return

    results = rank_grants(grants, profile, min_score=min_score, top_n=top_n)

    if not results:
        console.print(f"[yellow]No grants match with score >= {min_score}[/yellow]")
        return

    console.print(Panel(
        f"[bold]Profile:[/bold] {profile.name}\n"
        f"[bold]Grants Analyzed:[/bold] {len(grants)}\n"
        f"[bold]Matches (score >= {min_score}):[/bold] {len(results)}",
        title="[#00ff88]Grant Matching[/#00ff88]",
        border_style="#00ff88",
    ))

    table = Table(title=f"Top {len(results)} Matches", border_style="#00ff88", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Rating", width=10)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title", max_width=40)
    table.add_column("Agency", max_width=25)
    table.add_column("Reasons", max_width=40)

    for i, m in enumerate(results, 1):
        # Color by rating
        rating_colors = {"Excellent": "green", "Good": "cyan", "Fair": "yellow", "Low": "dim"}
        color = rating_colors.get(m.rating, "white")

        score_bar = "█" * int(m.score * 10) + "░" * (10 - int(m.score * 10))
        reasons = "; ".join(m.reasons[:3]) if m.reasons else "-"

        table.add_row(
            str(i),
            f"[{color}]{m.score:.0%}[/{color}]",
            f"[{color}]{m.rating}[/{color}]",
            (m.grant.go_id or m.grant.id[:8]),
            m.grant.title[:40],
            (m.grant.agency or "")[:25],
            reasons[:40],
        )

    console.print(table)


# ── propose ─────────────────────────────────────────────────────

@cli.command()
@click.argument("grant_id")
@click.option("--org", default=None, help="Applicant organisation name")
@click.option("--profile", "profile_name", default=None, help="Organisation profile name or YAML file path")
@click.option("--focus", default=None, help="Research focus area")
@click.option("--output", "output_dir", default=None, help="Output directory")
@click.option("--format", "fmt", default="all", type=click.Choice(["all", "md", "docx", "pdf"]))
@click.option("--no-refine", is_flag=True, help="Skip multi-pass review/refine (faster, cheaper)")
@pass_ctx
def propose(
    ctx: Context,
    grant_id: str,
    org: Optional[str],
    profile_name: Optional[str],
    focus: Optional[str],
    output_dir: Optional[str],
    fmt: str,
    no_refine: bool,
) -> None:
    """Generate a proposal for a specific grant.

    By default uses 3-pass generation (draft → expert review → refined version).
    Use --no-refine to skip the review/refine passes for faster, cheaper output.
    Use --profile to load an organisation profile for tailored proposals.
    """
    from au_grants_agent.database import Database
    from au_grants_agent.proposal.exporter import ProposalExporter
    from au_grants_agent.proposal.generator import ProposalGenerator

    if not settings.has_api_key:
        key_name = "DEEPSEEK_API_KEY" if settings.llm_provider == "deepseek" else "ANTHROPIC_API_KEY"
        console.print(f"[red]{key_name} not set. Add it to .env file.[/red]")
        return

    # Load org profile if specified
    org_profile = None
    if profile_name:
        from au_grants_agent.proposal.profiles import load_profile

        try:
            org_profile = load_profile(profile_name)
            console.print(f"[#00ff88]Loaded profile: {org_profile.name}[/#00ff88]")
        except FileNotFoundError:
            console.print(f"[red]Profile '{profile_name}' not found. Run 'au-grants profile list'.[/red]")
            return

    db = Database()
    grant = db.get_grant(grant_id)

    # Support partial ID
    if not grant:
        grants = db.list_grants()
        for g in grants:
            if g.id.startswith(grant_id):
                grant = g
                break

    if not grant:
        console.print(f"[red]Grant '{grant_id}' not found.[/red]")
        return

    generator = ProposalGenerator(db=db)
    proposal = generator.generate(
        grant=grant,
        org_name=org,
        focus_area=focus,
        refine=not no_refine,
        org_profile=org_profile,
    )

    # Validate
    from au_grants_agent.proposal.validator import validate_proposal

    if proposal.content_en:
        vresult = validate_proposal(proposal.content_en)
        ref_color = "green" if vresult.reference_score >= 60 else "yellow" if vresult.reference_score >= 40 else "red"
        comp_color = "green" if vresult.completeness_score >= 80 else "yellow"
        console.print(Panel(
            f"[bold]Words:[/bold] {vresult.word_count:,}\n"
            f"[bold]Completeness:[/bold] [{comp_color}]{vresult.completeness_score:.0f}%[/{comp_color}]\n"
            f"[bold]References:[/bold] [{ref_color}]{vresult.valid_references}/{vresult.total_references} valid ({vresult.reference_score:.0f}%)[/{ref_color}]"
            + (f"\n[bold yellow]Issues:[/bold yellow] {', '.join(vresult.issues)}" if vresult.issues else ""),
            title="[#00ff88]Validation[/#00ff88]",
            border_style="dim",
        ))

    # Export
    out_dir = Path(output_dir) if output_dir else None
    exporter = ProposalExporter(output_dir=out_dir)
    paths = exporter.export_all(grant, proposal, formats=fmt)

    console.print(Panel(
        "\n".join(f"[#00ff88]{p}[/#00ff88]" for p in paths),
        title="[bold]Exported Files[/bold]",
        border_style="#00ff88",
    ))


# ── validate ───────────────────────────────────────────────────

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@pass_ctx
def validate(ctx: Context, file_path: str) -> None:
    """Validate a generated proposal file (MD format)."""
    from au_grants_agent.proposal.validator import (
        format_validation_report,
        validate_proposal,
    )

    content = Path(file_path).read_text(encoding="utf-8")

    # Strip YAML frontmatter if present
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            content = content[end + 3:].strip()

    result = validate_proposal(content)
    report = format_validation_report(result)
    console.print(Markdown(report))


# ── pipeline ────────────────────────────────────────────────────

@cli.command()
@click.option("--top", "top_n", default=3, help="Number of top grants to process")
@click.option("--format", "fmt", default="all", type=click.Choice(["all", "md", "docx", "pdf"]))
@click.option("--org", default=None, help="Applicant organisation")
@click.option("--profile", "profile_name", default=None, help="Organisation profile name or YAML file path")
@click.option("--no-refine", is_flag=True, help="Skip multi-pass review/refine")
@pass_ctx
def pipeline(ctx: Context, top_n: int, fmt: str, org: Optional[str], profile_name: Optional[str], no_refine: bool) -> None:
    """Full pipeline: crawl -> rank by deadline -> generate proposals."""
    from au_grants_agent.crawler import ARCCrawler, BusinessGovCrawler, GrantsGovCrawler, NHMRCCrawler
    from au_grants_agent.database import Database
    from au_grants_agent.proposal.exporter import ProposalExporter
    from au_grants_agent.proposal.generator import ProposalGenerator

    if not settings.has_api_key:
        key_name = "DEEPSEEK_API_KEY" if settings.llm_provider == "deepseek" else "ANTHROPIC_API_KEY"
        console.print(f"[red]{key_name} not set. Add it to .env file.[/red]")
        return

    # Load org profile if specified
    org_profile = None
    if profile_name:
        from au_grants_agent.proposal.profiles import load_profile

        try:
            org_profile = load_profile(profile_name)
            console.print(f"[#00ff88]Loaded profile: {org_profile.name}[/#00ff88]")
        except FileNotFoundError:
            console.print(f"[red]Profile '{profile_name}' not found.[/red]")
            return

    db = Database()
    db.init_db()

    # Step 1: Crawl
    console.print("[bold #00ff88]Step 1: Crawling grant sources...[/bold #00ff88]")

    async def do_crawl():
        for CrawlerClass in [GrantsGovCrawler, BusinessGovCrawler, ARCCrawler, NHMRCCrawler]:
            crawler = CrawlerClass(db=db)
            result = await crawler.crawl()
            console.print(
                f"  {result.source}: {result.grants_found} found, "
                f"{result.grants_new} new, {result.grants_updated} updated"
            )

    asyncio.run(do_crawl())

    # Step 2: Rank by closing date
    console.print(f"\n[bold #00ff88]Step 2: Selecting top {top_n} grants by closing date...[/bold #00ff88]")
    grants = db.list_grants(status="open", sort_by="closing_date")
    selected = grants[:top_n]

    if not selected:
        console.print("[yellow]No open grants found.[/yellow]")
        return

    for i, g in enumerate(selected, 1):
        console.print(f"  {i}. {g.title[:60]} (closes: {g.closing_date or 'N/A'})")

    # Step 3: Generate proposals
    console.print(f"\n[bold #00ff88]Step 3: Generating proposals...[/bold #00ff88]")
    generator = ProposalGenerator(db=db)
    exporter = ProposalExporter()

    for g in selected:
        console.rule(f"[#00ff88]{g.title[:60]}[/#00ff88]")
        proposal = generator.generate(
            grant=g, org_name=org, refine=not no_refine, org_profile=org_profile,
        )
        paths = exporter.export_all(g, proposal, formats=fmt)
        for p in paths:
            console.print(f"  [dim]{p}[/dim]")

    console.print("\n[bold #00ff88]Pipeline complete![/bold #00ff88]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
