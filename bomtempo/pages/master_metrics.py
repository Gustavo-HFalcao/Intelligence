"""Master Metrics — placeholder (em desenvolvimento)."""
import reflex as rx
from bomtempo.core import styles as S
from bomtempo.state.master_state import MasterState


def _metrics_tenant_row(t: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(t["client_name"], color="white", font_size="13px")),
        rx.table.cell(rx.text("R$ ", t["ai_budget"], color=S.COPPER, font_size="13px")),
        rx.table.cell(rx.text(t["session_count"], color=S.TEXT_MUTED, font_size="13px")),
        rx.table.cell(
            rx.badge(
                t["status"],
                color_scheme=rx.cond(t["status"] == "active", "green", "red"),
                variant="soft",
                size="1",
            ),
        ),
    )


def master_metrics_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="bar-chart-big", size=20, color=S.COPPER),
                rx.text(
                    "CUSTOS & UTILIZAÇÃO",
                    font_size="20px",
                    font_weight="800",
                    color="white",
                    letter_spacing="0.1em",
                    font_family=S.FONT_TECH,
                ),
                spacing="3",
                align="center",
            ),
            rx.text(
                "Métricas de uso de IA e custos por tenant — em desenvolvimento.",
                font_size="13px",
                color=S.TEXT_MUTED,
            ),
            rx.separator(width="100%", color_scheme="amber", opacity="0.2"),

            # Tabela de budget por tenant
            rx.cond(
                MasterState.is_loading,
                rx.spinner(size="3", color=S.COPPER),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("TENANT"),
                            rx.table.column_header_cell("BUDGET IA"),
                            rx.table.column_header_cell("SESSÕES"),
                            rx.table.column_header_cell("STATUS"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(MasterState.tenants, _metrics_tenant_row)
                    ),
                    width="100%",
                    variant="surface",
                ),
            ),
            spacing="5",
            width="100%",
            align="start",
        ),
        padding="32px",
        width="100%",
        min_height="100vh",
    )
