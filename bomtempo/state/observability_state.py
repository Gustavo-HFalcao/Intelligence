"""
LLM Observability State — Token usage, costs, and tool error tracking.
Página: /admin/observabilidade — apenas Administrador.
"""

import reflex as rx

from bomtempo.core.supabase_client import sb_select_paginated, sb_select
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

_MODEL_COLORS = {
    "gpt-4o":      "#C98B2A",
    "gpt-4o-mini": "#2A9D8F",
    "gpt-4-turbo": "#3B82F6",
    "gpt-4":       "#EF4444",
    "gpt-3.5-turbo": "#8B5CF6",
    "whisper-1":   "#F59E0B",
    "tts-1":       "#EC4899",
}


def _fmt_cost(usd: float) -> str:
    if usd == 0:
        return "—"
    if usd < 0.001:
        return f"$0.000{int(usd * 10000)}"
    return f"${usd:.4f}"


def _normalize_row(r: dict) -> dict:
    tools = r.get("tool_names") or []
    tools_str = ", ".join(tools) if tools else "—"
    model = r.get("model") or "—"
    cost = r.get("cost_usd") or 0
    error = r.get("error") or ""
    created_raw = r.get("created_at") or ""
    # Format timestamp
    ts = created_raw[:19].replace("T", " ") if created_raw else "—"
    return {
        "id": str(r.get("id") or ""),
        "model": model,
        "username": str(r.get("username") or "—"),
        "call_type": str(r.get("call_type") or "—"),
        "prompt_tokens": str(r.get("prompt_tokens") or 0),
        "completion_tokens": str(r.get("completion_tokens") or 0),
        "total_tokens": str(r.get("total_tokens") or 0),
        "cost_usd": _fmt_cost(cost),
        "cost_raw": str(round(cost, 8)),
        "tool_names": tools_str,
        "duration_ms": str(r.get("duration_ms") or 0),
        "error": error[:120] if error else "",
        "has_error": "true" if error else "false",
        "created_at": ts,
        "model_color": _MODEL_COLORS.get(model, "#889999"),
    }


class ObservabilityState(rx.State):
    # ── List view ────────────────────────────────────────────────
    rows: list[dict] = []
    page: int = 1
    per_page: int = 50
    total: int = 0
    filter_model: str = ""
    filter_username: str = ""
    filter_call_type: str = ""
    filter_errors_only: bool = False
    is_loading: bool = False

    # ── Summary stats ────────────────────────────────────────────
    stat_total_calls: int = 0
    stat_total_tokens: int = 0
    stat_total_cost: str = "—"
    stat_errors: int = 0
    stat_avg_duration: int = 0

    # ── Per-model breakdown ──────────────────────────────────────
    model_breakdown: list[dict] = []

    # ── Detail panel ─────────────────────────────────────────────
    selected_row: dict = {}
    show_detail: bool = False

    @rx.var
    def total_pages(self) -> int:
        if self.per_page == 0:
            return 1
        import math
        return max(1, math.ceil(self.total / self.per_page))

    @rx.var
    def has_prev(self) -> bool:
        return self.page > 1

    @rx.var
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @rx.var
    def page_info(self) -> str:
        return f"Página {self.page} / {self.total_pages}"

    @rx.event(background=True)
    async def load_page(self):
        async with self:
            self.is_loading = True

        # ── Summary stats from full dataset (no pagination) ───────
        all_rows = sb_select(
            "llm_observability",
            order="created_at.desc",
            limit=5000,
        )
        total_calls = len(all_rows)
        total_tokens = sum(r.get("total_tokens") or 0 for r in all_rows)
        total_cost = sum(r.get("cost_usd") or 0 for r in all_rows)
        errors = sum(1 for r in all_rows if r.get("error"))
        durations = [r.get("duration_ms") or 0 for r in all_rows if r.get("duration_ms")]
        avg_dur = int(sum(durations) / len(durations)) if durations else 0

        # Per-model breakdown
        model_map: dict = {}
        for r in all_rows:
            m = r.get("model") or "—"
            if m not in model_map:
                model_map[m] = {"calls": 0, "tokens": 0, "cost": 0.0}
            model_map[m]["calls"] += 1
            model_map[m]["tokens"] += r.get("total_tokens") or 0
            model_map[m]["cost"] += r.get("cost_usd") or 0

        breakdown = [
            {
                "model": m,
                "calls": str(v["calls"]),
                "tokens": f"{v['tokens']:,}",
                "cost": _fmt_cost(v["cost"]),
                "color": _MODEL_COLORS.get(m, "#889999"),
            }
            for m, v in sorted(model_map.items(), key=lambda x: -x[1]["cost"])
        ]

        async with self:
            self.stat_total_calls = total_calls
            self.stat_total_tokens = total_tokens
            self.stat_total_cost = _fmt_cost(total_cost)
            self.stat_errors = errors
            self.stat_avg_duration = avg_dur
            self.model_breakdown = breakdown

        # ── Paginated table ───────────────────────────────────────
        await self._fetch_page()

    async def _fetch_page(self):
        async with self:
            page = self.page
            per_page = self.per_page
            filter_model = self.filter_model
            filter_username = self.filter_username
            filter_call_type = self.filter_call_type
            filter_errors_only = self.filter_errors_only

        filters = {}
        if filter_model:
            filters["model"] = filter_model
        if filter_username:
            filters["username"] = filter_username
        if filter_call_type:
            filters["call_type"] = filter_call_type

        raw, total = sb_select_paginated(
            "llm_observability",
            page=page,
            limit=per_page,
            filters=filters,
            order="created_at.desc",
        )
        normalized = [_normalize_row(r) for r in raw]
        if filter_errors_only:
            rows = [r for r in normalized if r["has_error"] == "true"]
            total = len(rows)
        else:
            rows = normalized

        async with self:
            self.rows = rows
            self.total = total
            self.is_loading = False

    async def set_filter_model(self, val: str):
        self.filter_model = "" if val == "__all__" else val
        self.page = 1
        await self._fetch_page()

    async def set_filter_username(self, val: str):
        self.filter_username = "" if val == "__all__" else val
        self.page = 1
        await self._fetch_page()

    async def set_filter_call_type(self, val: str):
        self.filter_call_type = "" if val == "__all__" else val
        self.page = 1
        await self._fetch_page()

    async def toggle_errors_only(self):
        self.filter_errors_only = not self.filter_errors_only
        self.page = 1
        await self._fetch_page()

    @rx.event(background=True)
    async def prev_page(self):
        async with self:
            if self.page > 1:
                self.page -= 1
        await self._fetch_page()

    @rx.event(background=True)
    async def next_page(self):
        async with self:
            if self.page < self.total_pages:
                self.page += 1
        await self._fetch_page()

    def open_detail(self, row: dict):
        self.selected_row = row
        self.show_detail = True

    def close_detail(self):
        self.show_detail = False
        self.selected_row = {}
