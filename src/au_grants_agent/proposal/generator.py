"""Proposal generation using DeepSeek or Claude API with streaming."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from au_grants_agent.proposal.profiles import OrgProfile

from rich.console import Console
from rich.panel import Panel

from au_grants_agent.config import settings
from au_grants_agent.database import Database
from au_grants_agent.models import Grant, Proposal
from au_grants_agent.proposal.templates import (
    REFINE_SYSTEM_PROMPT,
    REFINE_USER_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_PROMPT,
    SYSTEM_PROMPT_VI,
    VIETNAMESE_SUMMARY_PROMPT,
    build_proposal_prompt,
    get_system_prompt,
)
from au_grants_agent.utils.logger import get_logger

logger = get_logger()
console = Console()


class ProposalGenerator:
    """Generate grant proposals using DeepSeek or Claude API with streaming output."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()
        self.provider = settings.llm_provider
        self.model = settings.default_model

        if self.provider == "deepseek":
            from openai import OpenAI

            self.openai_client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            self._anthropic_client = None
        else:
            import anthropic

            self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self.openai_client = None

    def _stream_deepseek(
        self, system: str, user_prompt: str, max_tokens: int, label: str
    ) -> tuple[str, int]:
        """Stream a DeepSeek response to terminal. Returns (text, token_count)."""
        full_text = ""
        total_tokens = 0

        console.print(f"\n[bold #00ff88]>>> {label} [DeepSeek][/bold #00ff88]\n")

        stream = self.openai_client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.7,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_text += text
                console.print(text, end="", highlight=False)

            # Capture usage from final chunk
            if chunk.usage:
                total_tokens = chunk.usage.total_tokens

        # If usage wasn't in stream, estimate
        if total_tokens == 0:
            total_tokens = len(full_text) // 4  # rough estimate

        console.print()
        return full_text, total_tokens

    def _stream_anthropic(
        self, system: str, user_prompt: str, max_tokens: int, label: str
    ) -> tuple[str, int]:
        """Stream a Claude response to terminal. Returns (text, token_count)."""
        full_text = ""
        total_tokens = 0

        console.print(f"\n[bold #00ff88]>>> {label} [Claude][/bold #00ff88]\n")

        with self._anthropic_client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.7,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                full_text += text
                console.print(text, end="", highlight=False)

        final = stream.get_final_message()
        total_tokens = final.usage.input_tokens + final.usage.output_tokens

        console.print()
        return full_text, total_tokens

    def _stream_response(
        self, system: str, user_prompt: str, max_tokens: int, label: str
    ) -> tuple[str, int]:
        """Route to the active provider's streaming method."""
        if self.provider == "deepseek":
            return self._stream_deepseek(system, user_prompt, max_tokens, label)
        return self._stream_anthropic(system, user_prompt, max_tokens, label)

    def _build_funding_range(self, grant: Grant) -> str:
        """Format funding range string for prompts."""
        if grant.amount_min and grant.amount_max:
            return f"${grant.amount_min:,.0f} – ${grant.amount_max:,.0f}"
        elif grant.amount_min:
            return f"${grant.amount_min:,.0f}"
        return "Not specified"

    def _review_draft(self, grant: Grant, draft_text: str) -> tuple[str, int]:
        """Pass 2: Review the draft proposal and produce feedback."""
        review_prompt = REVIEW_USER_PROMPT.format(
            title=grant.title,
            agency=grant.agency or "Australian Government",
            funding_range=self._build_funding_range(grant),
            draft_text=draft_text,
        )
        return self._stream_response(
            system=REVIEW_SYSTEM_PROMPT,
            user_prompt=review_prompt,
            max_tokens=2048,
            label="Pass 2/3: Reviewing Draft (Expert Assessment)",
        )

    def _refine_draft(
        self, grant: Grant, draft_text: str, review_text: str
    ) -> tuple[str, int]:
        """Pass 3: Refine the draft based on reviewer feedback."""
        refine_prompt = REFINE_USER_PROMPT.format(
            title=grant.title,
            agency=grant.agency or "Australian Government",
            draft_text=draft_text,
            review_text=review_text,
        )
        return self._stream_response(
            system=REFINE_SYSTEM_PROMPT,
            user_prompt=refine_prompt,
            max_tokens=4096,
            label="Pass 3/3: Refining Proposal (Final Version)",
        )

    def generate(
        self,
        grant: Grant,
        org_name: Optional[str] = None,
        focus_area: Optional[str] = None,
        refine: bool = True,
        org_profile: Optional["OrgProfile"] = None,
    ) -> Proposal:
        """Generate a full bilingual proposal for a grant.

        Args:
            grant: The grant to write a proposal for.
            org_name: Applicant organisation name.
            focus_area: Research focus area.
            refine: If True, use 3-pass generation (draft → review → refine).
                    If False, use single-pass generation.
            org_profile: Rich organisation profile for tailored proposals.
        """
        # Use profile name if no org_name given
        if org_profile and not org_name:
            org_name = org_profile.name

        mode_label = "3-Pass (Draft → Review → Refine)" if refine else "Single-Pass"
        profile_label = f" | Profile: {org_profile.name}" if org_profile else ""
        console.print(
            Panel(
                f"[bold]Generating proposal for:[/bold]\n{grant.title}\n"
                f"[dim]Provider: {settings.provider_display} | Mode: {mode_label}{profile_label}[/dim]",
                title="[#00ff88]AU Grants Agent[/#00ff88]",
                border_style="#00ff88",
            )
        )

        total_tokens = 0

        # Build org profile section for prompt
        org_profile_section = org_profile.to_prompt_section() if org_profile else None

        # Pass 1: Generate English draft
        user_prompt = build_proposal_prompt(
            title=grant.title,
            agency=grant.agency,
            category=grant.category,
            amount_min=grant.amount_min,
            amount_max=grant.amount_max,
            closing_date=grant.closing_date,
            eligibility=grant.eligibility,
            description=grant.description,
            org_name=org_name,
            focus_area=focus_area,
            org_profile_section=org_profile_section,
        )

        # Select category-specific system prompt
        system_prompt = get_system_prompt(grant.category)

        draft_label = "Pass 1/3: Generating Draft" if refine else "Generating English Proposal"
        if grant.category:
            draft_label += f" [{grant.category}]"
        en_text, en_tokens = self._stream_response(
            system=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            label=draft_label,
        )
        total_tokens += en_tokens

        # Pass 2 & 3: Review and refine (if enabled)
        if refine:
            console.print("\n[dim]─── Starting expert review... ───[/dim]\n")

            review_text, review_tokens = self._review_draft(grant, en_text)
            total_tokens += review_tokens

            console.print("\n[dim]─── Refining based on feedback... ───[/dim]\n")

            en_text, refine_tokens = self._refine_draft(grant, en_text, review_text)
            total_tokens += refine_tokens

            console.print(
                f"\n[#00ff88]Multi-pass complete![/#00ff88] "
                f"Draft → Review → Refined ({total_tokens:,} tokens so far)"
            )

        # Generate Vietnamese summary (from final version)
        vi_prompt = VIETNAMESE_SUMMARY_PROMPT.format(proposal_text=en_text)
        vi_text, vi_tokens = self._stream_response(
            system=SYSTEM_PROMPT_VI,
            user_prompt=vi_prompt,
            max_tokens=1024,
            label="Generating Vietnamese Summary (Tóm tắt Tiếng Việt)",
        )
        total_tokens += vi_tokens

        proposal = Proposal(
            id=str(uuid.uuid4()),
            grant_id=grant.id,
            org_name=org_name,
            focus_area=focus_area,
            content_en=en_text,
            summary_vi=vi_text,
            model=f"{self.provider}:{self.model}",
            tokens_used=total_tokens,
            generated_at=datetime.utcnow().isoformat(),
        )

        # Save to DB
        self.db.save_proposal(proposal)
        console.print(
            f"\n[bold #00ff88]Proposal saved![/bold #00ff88] "
            f"Provider: {self.provider} | Mode: {mode_label} | Tokens: {proposal.tokens_used:,}"
        )

        return proposal
