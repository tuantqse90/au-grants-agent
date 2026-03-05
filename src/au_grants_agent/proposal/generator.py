"""Proposal generation using DeepSeek or Claude API with streaming."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from au_grants_agent.config import settings
from au_grants_agent.database import Database
from au_grants_agent.models import Grant, Proposal
from au_grants_agent.proposal.templates import (
    SYSTEM_PROMPT_EN,
    SYSTEM_PROMPT_VI,
    VIETNAMESE_SUMMARY_PROMPT,
    build_proposal_prompt,
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

    def generate(
        self,
        grant: Grant,
        org_name: Optional[str] = None,
        focus_area: Optional[str] = None,
    ) -> Proposal:
        """Generate a full bilingual proposal for a grant."""
        console.print(
            Panel(
                f"[bold]Generating proposal for:[/bold]\n{grant.title}\n"
                f"[dim]Provider: {settings.provider_display}[/dim]",
                title="[#00ff88]AU Grants Agent[/#00ff88]",
                border_style="#00ff88",
            )
        )

        # 1. Generate English proposal
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
        )

        en_text, en_tokens = self._stream_response(
            system=SYSTEM_PROMPT_EN,
            user_prompt=user_prompt,
            max_tokens=4096,
            label="Generating English Proposal",
        )

        # 2. Generate Vietnamese summary
        vi_prompt = VIETNAMESE_SUMMARY_PROMPT.format(proposal_text=en_text)
        vi_text, vi_tokens = self._stream_response(
            system=SYSTEM_PROMPT_VI,
            user_prompt=vi_prompt,
            max_tokens=1024,
            label="Generating Vietnamese Summary (Tóm tắt Tiếng Việt)",
        )

        proposal = Proposal(
            id=str(uuid.uuid4()),
            grant_id=grant.id,
            org_name=org_name,
            focus_area=focus_area,
            content_en=en_text,
            summary_vi=vi_text,
            model=f"{self.provider}:{self.model}",
            tokens_used=en_tokens + vi_tokens,
            generated_at=datetime.utcnow().isoformat(),
        )

        # Save to DB
        self.db.save_proposal(proposal)
        console.print(
            f"\n[bold #00ff88]Proposal saved![/bold #00ff88] "
            f"Provider: {self.provider} | Tokens: {proposal.tokens_used:,}"
        )

        return proposal
