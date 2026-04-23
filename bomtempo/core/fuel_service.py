"""
Fuel Reimbursement Service — PDF, Supabase, IA Vision, Validação
Padrão idêntico ao rdo_service.py (benchmark)
"""

import base64
import html as _html_mod
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from bomtempo.core.ai_client import ai_client
from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.pdf_utils import html_to_pdf
from bomtempo.core.supabase_client import (
    sb_delete,
    sb_insert,
    sb_select,
    sb_storage_upload,
    sb_update,
)

logger = get_logger(__name__)

# Table name
_TABLE = "fuel_reimbursements"


def _to_float(val, default: float = 0.0) -> float:
    try:
        return float(str(val).strip().replace(",", "."))
    except (ValueError, TypeError):
        return default


def _user_uuid(username: str) -> str:
    """Gera UUID determinístico a partir do username (consistente entre sessões)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bomtempo-{username.lower()}"))


_FR_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>COMPROVANTE DE REEMBOLSO - ___PROTOCOLO___</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script id="tailwind-config">
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          "copper": "#C98B2A",
          "patina": "#2A9D8F",
          "ink": "#081210",
          "paper": "#ffffff"
        },
        fontFamily: {
          "headline": ["Rajdhani", "sans-serif"],
          "body": ["Plus Jakarta Sans", "sans-serif"],
          "label": ["JetBrains Mono", "monospace"]
        }
      }
    }
  }
</script>
<style>
  @page { size: A4; margin: 0; }
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; background-color: #f3f4f6; }
  @media print { body { background-color: white !important; } .no-print { display: none !important; } }
  .material-symbols-outlined {
    font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    vertical-align: middle; line-height: 1;
  }
  .section-title {
    display: flex; align-items: center; gap: 0.5rem;
    font-family: 'Rajdhani', sans-serif; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; color: #081210;
    border-bottom: 2px solid #e4e4e7; padding-bottom: 0.5rem; margin-bottom: 1rem;
    font-size: 14px;
  }
</style>
</head>
<body class="font-body text-ink">

<!-- Main Document Canvas -->
<main style="width:210mm;min-height:297mm;margin:1.5rem auto;background:white;padding:16mm 20mm;box-shadow:0 10px 25px -5px rgba(0,0,0,0.1);">

<!-- 1. HEADER -->
<header class="flex justify-between items-start mb-10 pb-6" style="border-bottom:4px solid #C98B2A;">
  <div class="flex flex-col">
    <div class="font-headline text-2xl font-bold tracking-tighter text-copper leading-none">BOMTEMPO</div>
    <div class="font-headline text-2xl font-bold tracking-tighter text-ink leading-none -mt-1">ENGENHARIA</div>
    <div class="font-label text-[9px] text-zinc-500 uppercase tracking-[0.2em] mt-2">Sistema de Gestão de Campo</div>
    <div class="inline-block mt-2 px-2 py-0.5" style="background:#C98B2A18;border:1px solid #C98B2A40;">
      <span class="font-label text-[9px] font-bold text-copper">___BADGE_TEXT___</span>
    </div>
  </div>
  <div class="text-right">
    <h1 class="font-headline text-3xl font-bold text-ink leading-none mb-2">COMPROVANTE DE DESPESA</h1>
    <p class="font-headline text-base font-medium text-zinc-500 tracking-widest uppercase">Reembolso de Combustível</p>
    <div class="inline-block bg-copper/10 border border-copper/20 px-3 py-1 mt-2">
      <span class="font-label text-xs font-bold text-copper">PROTOCOLO #___PROTOCOLO___</span>
    </div>
  </div>
</header>

<!-- 2. DADOS DO COLABORADOR -->
<section class="mb-8">
  <h2 class="section-title">
    <span class="material-symbols-outlined text-copper">person</span>
    Dados do Colaborador
  </h2>
  <div class="grid grid-cols-3 gap-6 bg-zinc-50 p-5 rounded-lg border border-zinc-200">
    <div>
      <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">Nome Completo</label>
      <p class="font-semibold text-sm">___NOME___</p>
    </div>
    <div>
      <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">Finalidade da Viagem</label>
      <p class="font-semibold text-sm">___FINALIDADE___</p>
    </div>
    <div>
      <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">Data do Abastecimento</label>
      <p class="font-label font-bold text-sm">___DATA_ABAST___</p>
    </div>
  </div>
</section>

<!-- 3. DETALHES DO ABASTECIMENTO -->
<section class="mb-8">
  <h2 class="section-title">
    <span class="material-symbols-outlined text-copper">local_gas_station</span>
    Detalhes do Abastecimento
  </h2>
  <div class="overflow-hidden border border-zinc-200 rounded-lg">
    <table class="w-full text-left">
      <thead>
        <tr style="background:#081210;">
          <th class="px-5 py-3 font-headline text-[10px] uppercase tracking-widest text-white border-r border-white/10">Combustível</th>
          <th class="px-5 py-3 font-headline text-[10px] uppercase tracking-widest text-white border-r border-white/10">Litros</th>
          <th class="px-5 py-3 font-headline text-[10px] uppercase tracking-widest text-white border-r border-white/10">Preço / Litro</th>
          <th class="px-5 py-3 font-headline text-[10px] uppercase tracking-widest text-white text-right">Valor Total</th>
        </tr>
      </thead>
      <tbody>
        <tr class="border-b border-zinc-100">
          <td class="px-5 py-4 text-sm font-medium">___COMBUSTIVEL___</td>
          <td class="px-5 py-4 text-sm font-label">___LITROS___ L</td>
          <td class="px-5 py-4 text-sm font-label">R$ ___VALOR_LITRO___</td>
          <td class="px-5 py-4 text-xl font-bold text-right text-copper font-label">R$ ___VALOR_TOTAL___</td>
        </tr>
      </tbody>
    </table>
  </div>
</section>

<!-- 4. KPI BAR -->
<section class="mb-8">
  <div class="grid grid-cols-5 rounded-sm overflow-hidden" style="background:#081210;">
    <div class="flex flex-col items-center py-4 border-r border-white/10">
      <span class="font-label text-lg font-bold text-copper">___LITROS___ L</span>
      <span class="font-headline text-[8px] text-white/50 uppercase tracking-widest mt-1">Litros</span>
    </div>
    <div class="flex flex-col items-center py-4 border-r border-white/10">
      <span class="font-label text-lg font-bold text-copper">R$ ___VALOR_LITRO___</span>
      <span class="font-headline text-[8px] text-white/50 uppercase tracking-widest mt-1">Preço/Litro</span>
    </div>
    <div class="flex flex-col items-center py-4 border-r border-white/10">
      <span class="font-label text-lg font-bold text-copper">___KM_DRIVEN___ km</span>
      <span class="font-headline text-[8px] text-white/50 uppercase tracking-widest mt-1">KM Rodados</span>
    </div>
    <div class="flex flex-col items-center py-4 border-r border-white/10">
      <span class="font-label text-lg font-bold text-copper">___KM_PER_LITER___ km/L</span>
      <span class="font-headline text-[8px] text-white/50 uppercase tracking-widest mt-1">Eficiência</span>
    </div>
    <div class="flex flex-col items-center py-4">
      <span class="font-label text-lg font-bold text-copper">R$ ___COST_PER_KM___</span>
      <span class="font-headline text-[8px] text-white/50 uppercase tracking-widest mt-1">Custo/KM</span>
    </div>
  </div>
</section>

<!-- 5. LOCALIZAÇÃO E ROTA -->
<section class="mb-8">
  <h2 class="section-title">
    <span class="material-symbols-outlined text-copper">route</span>
    Localização e Rota
  </h2>
  <div class="grid grid-cols-2 gap-6">
    <div class="space-y-3">
      <div class="flex gap-3 p-4 border border-zinc-200 rounded-lg">
        <span class="material-symbols-outlined text-zinc-400">location_on</span>
        <div>
          <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">Localização</label>
          <p class="text-sm font-semibold">___CIDADE___, ___ESTADO___</p>
        </div>
      </div>
      <div class="p-4 border border-zinc-200 rounded-lg">
        <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">Rota</label>
        <p class="text-sm italic text-zinc-600">___ROTA___</p>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div class="p-4 bg-zinc-50 border border-zinc-200 rounded-lg">
        <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">KM Inicial</label>
        <p class="text-xl font-label font-bold">___KM_INICIAL___</p>
      </div>
      <div class="p-4 bg-zinc-50 border border-zinc-200 rounded-lg">
        <label class="font-label text-[9px] uppercase text-zinc-500 block mb-1">KM Final</label>
        <p class="text-xl font-label font-bold">___KM_FINAL___</p>
      </div>
      <div class="col-span-2 p-4 rounded-lg flex items-center justify-between" style="background:#C98B2A0d;border:1px solid #C98B2A33;">
        <label class="font-label text-[10px] uppercase font-bold text-copper">Distância Percorrida</label>
        <p class="text-2xl font-label font-bold text-copper">___KM_DRIVEN___ KM</p>
      </div>
    </div>
  </div>
</section>

<!-- 6. AI SECTION (conditional) -->
___AI_SECTION___

<!-- 7. ASSINATURAS -->
<section class="mt-14">
  <div class="grid grid-cols-2 gap-16">
    <div class="text-center">
      <div class="h-16 mb-4 flex items-end justify-center" style="border-bottom:1px solid #d4d4d8;">
        <span class="font-headline text-[10px] text-zinc-400 italic uppercase tracking-widest">Assinado Digitalmente</span>
      </div>
      <p class="font-headline font-bold text-xs uppercase tracking-[0.2em] mb-1">Solicitante</p>
      <p class="font-label text-[9px] text-zinc-500 uppercase">___NOME___</p>
    </div>
    <div class="text-center">
      <div class="h-16 mb-4" style="border-bottom:1px solid #d4d4d8;"></div>
      <p class="font-headline font-bold text-xs uppercase tracking-[0.2em] mb-1">Aprovador Financeiro</p>
      <p class="font-label text-[9px] text-zinc-500 uppercase">Gestão de Operações de Campo</p>
    </div>
  </div>
</section>

<!-- FOOTER -->
<footer class="mt-10 pt-5 flex justify-between items-center" style="border-top:2px solid #C98B2A;">
  <span class="font-headline text-[9px] font-bold text-copper uppercase tracking-widest">BOMTEMPO ENGENHARIA</span>
  <span class="font-label text-[8px] text-zinc-400 uppercase tracking-tighter">___FOOTER_CONTENT___</span>
  <span class="font-label text-[8px] text-zinc-400">Página 01 / 01</span>
</footer>

</main>
</body>
</html>"""


class FuelService:
    """Serviço centralizado para o módulo de Reembolso de Combustível."""

    # ── IA Vision ─────────────────────────────────────────────────────────────

    @staticmethod
    def analyze_receipt_image(image_b64: str, mime: str = "image/jpeg") -> dict:
        """
        Chama gpt-4o Vision para extrair dados da nota fiscal.
        Retorna dict com campos extraídos ou {} em caso de erro.
        """
        return ai_client.analyze_receipt_image(image_b64, mime)

    # ── Validação ─────────────────────────────────────────────────────────────

    @staticmethod
    def validate_data(user_data: dict, ai_data: dict) -> dict:
        """
        Compara dados digitados pelo usuário com os extraídos pela IA.
        Tolerância ±R$0,50 no total. Verifica consistência litros×preço≈total.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...], "ai_verified": bool}
        """
        errors = []
        warnings = []
        ai_verified = False

        if not ai_data:
            warnings.append("IA não conseguiu extrair dados da imagem. Verifique manualmente.")
            return {"valid": True, "errors": errors, "warnings": warnings, "ai_verified": False}

        ai_total = _to_float(ai_data.get("total"))
        user_total = _to_float(user_data.get("valor_total"))

        # Validar valor total vs NF
        if ai_total > 0 and user_total > 0:
            diff = abs(ai_total - user_total)
            if diff > 0.50:
                errors.append(
                    f"Valor total diverge: você digitou R${user_total:.2f}, "
                    f"a nota fiscal indica R${ai_total:.2f} (diferença: R${diff:.2f})"
                )
            else:
                ai_verified = True

        # Consistência interna: litros × preço ≈ total
        ai_litros = _to_float(ai_data.get("liters"))
        ai_preco = _to_float(ai_data.get("price_per_liter"))
        if ai_litros > 0 and ai_preco > 0:
            expected = round(ai_litros * ai_preco, 2)
            if abs(expected - ai_total) > 1.00:
                warnings.append(
                    f"Inconsistência interna na NF: {ai_litros:.3f}L × R${ai_preco:.3f} "
                    f"= R${expected:.2f}, mas total informado é R${ai_total:.2f}"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "ai_verified": ai_verified and len(errors) == 0,
        }

    # ── Métricas ──────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_metrics(data: dict) -> dict:
        """Calcula km_per_liter, cost_per_km e km_driven."""
        km_start = _to_float(data.get("km_inicial"))
        km_end = _to_float(data.get("km_final"))
        litros = _to_float(data.get("litros"))
        total = _to_float(data.get("valor_total"))

        km_driven = max(0.0, km_end - km_start)
        km_per_liter = round(km_driven / litros, 2) if litros > 0 else 0.0
        cost_per_km = round(total / km_driven, 4) if km_driven > 0 else 0.0

        return {
            "km_driven": km_driven,
            "km_per_liter": km_per_liter,
            "cost_per_km": cost_per_km,
        }

    # ── Desvios (para anomalia) ────────────────────────────────────────────────

    @staticmethod
    def calculate_deviations(user_uuid: str, km_per_liter: float) -> dict:
        """
        Calcula desvio vs média do próprio usuário e vs frota.
        Retorna {"deviation_from_user_avg": float|None, "deviation_from_fleet_avg": float|None}
        """
        try:
            all_records = sb_select(_TABLE, limit=500) or []
            user_records = sb_select(_TABLE, filters={"user_id": user_uuid}, limit=500) or []

            def _avg(records: list) -> Optional[float]:
                vals = [_to_float(r.get("km_per_liter")) for r in records if r.get("km_per_liter")]
                vals = [v for v in vals if v > 0]
                return round(sum(vals) / len(vals), 2) if vals else None

            user_avg = _avg(user_records)
            fleet_avg = _avg(all_records)

            dev_user = round((km_per_liter - user_avg) / user_avg * 100, 1) if user_avg else None
            dev_fleet = (
                round((km_per_liter - fleet_avg) / fleet_avg * 100, 1) if fleet_avg else None
            )

            return {"deviation_from_user_avg": dev_user, "deviation_from_fleet_avg": dev_fleet}
        except Exception as e:
            logger.warning(f"⚠️ Erro ao calcular desvios: {e}")
            return {"deviation_from_user_avg": None, "deviation_from_fleet_avg": None}

    # ── PDF ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_fuel_html(data: dict, id_fr: str) -> str:
        """Builds the HTML document used for PDF rendering."""

        def e(s) -> str:
            return _html_mod.escape(str(s) if s is not None else "—")

        submitted_by = e(data.get("submitted_by") or "—")
        combustivel  = e(data.get("combustivel") or "—")
        litros       = _to_float(data.get("litros"))
        valor_litro  = _to_float(data.get("valor_litro"))
        valor_total  = _to_float(data.get("valor_total"))
        km_inicial   = _to_float(data.get("km_inicial"))
        km_final     = _to_float(data.get("km_final"))
        km_driven    = _to_float(data.get("km_driven"))
        km_per_liter = _to_float(data.get("km_per_liter"))
        cost_per_km  = _to_float(data.get("cost_per_km"))
        rota         = e(data.get("rota") or "—")
        finalidade   = e(data.get("finalidade") or "—")
        cidade       = e(data.get("cidade") or "—")
        estado       = e(data.get("estado") or "—")
        data_abast   = e(data.get("data_abastecimento") or datetime.now().strftime("%Y-%m-%d"))
        ai_insight   = (data.get("ai_insight_text") or "").strip()
        ai_verified  = bool(data.get("ai_verified", False))
        id_label     = e(id_fr) if id_fr else ""
        emissao      = datetime.now().strftime("%d/%m/%Y às %H:%M")

        badge_color = "#27AE60" if ai_verified else "#888888"
        badge_text  = "NF VERIFICADA ✓ IA" if ai_verified else "NF NÃO VERIFICADA"

        # AI section (conditional)
        if ai_insight:
            ai_section = (
                '<section class="mb-8">'
                '<h2 class="section-title">'
                f'<span class="material-symbols-outlined" style="color:{badge_color};">smart_toy</span>'
                'Análise da Nota Fiscal (IA)'
                '</h2>'
                f'<div style="background:#fafafa;border:1px solid #e4e4e7;border-radius:4px;padding:14px 16px;border-left:3px solid {badge_color};">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
                f'<div style="width:22px;height:22px;border-radius:50%;background:{badge_color};display:flex;align-items:center;justify-content:center;color:white;font-size:9px;font-weight:700;">IA</div>'
                f'<span style="font-family:\'Rajdhani\',sans-serif;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:{badge_color};">{badge_text}</span>'
                '</div>'
                f'<p style="font-family:\'Plus Jakarta Sans\',sans-serif;font-size:12px;color:#3f3f46;line-height:1.7;">{e(ai_insight)}</p>'
                '</div></section>'
            )
        else:
            ai_section = ""

        footer_content = (
            f"Reembolso Combustível · {id_label} · " if id_label else "Reembolso Combustível · "
        ) + f"{submitted_by} · {data_abast} · Emitido em {emissao}"

        replacements = {
            "___PROTOCOLO___":    id_label or "—",
            "___BADGE_TEXT___":   badge_text,
            "___NOME___":         submitted_by,
            "___FINALIDADE___":   finalidade,
            "___DATA_ABAST___":   data_abast,
            "___COMBUSTIVEL___":  combustivel,
            "___LITROS___":       f"{litros:.2f}",
            "___VALOR_LITRO___":  f"{valor_litro:.3f}",
            "___VALOR_TOTAL___":  f"{valor_total:.2f}",
            "___KM_DRIVEN___":    f"{km_driven:.0f}",
            "___KM_PER_LITER___": f"{km_per_liter:.2f}",
            "___COST_PER_KM___":  f"{cost_per_km:.3f}",
            "___KM_INICIAL___":   f"{km_inicial:,.0f}",
            "___KM_FINAL___":     f"{km_final:,.0f}",
            "___CIDADE___":       cidade,
            "___ESTADO___":       estado,
            "___ROTA___":         rota,
            "___AI_SECTION___":   ai_section,
            "___FOOTER_CONTENT___": footer_content,
        }
        html = _FR_HTML_TEMPLATE
        for key, val in replacements.items():
            html = html.replace(key, str(val) if val is not None else "")
        return html

    @staticmethod
    def generate_pdf(data: dict, id_fr: str = "") -> tuple:
        """
        Gera PDF do Reembolso de Combustível via HTML → Playwright (Edge).

        Returns: (pdf_path: str, pdf_url: str)
        """
        try:
            Config.FR_PDF_DIR.mkdir(parents=True, exist_ok=True)

            data_prefix = (
                data.get("data_abastecimento", datetime.now().strftime("%Y-%m-%d"))
                .replace("-", "")
            )
            filename = (
                f"Reembolso_{data_prefix}_{id_fr}.pdf"
                if id_fr
                else f"Reembolso_PREVIEW_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            pdf_path = Config.FR_PDF_DIR / filename

            html = FuelService._build_fuel_html(data, id_fr)
            html_to_pdf(
                html, pdf_path,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                display_header_footer=False,
            )

            logger.info(f"✅ FR PDF gerado: {pdf_path.name}")
            return str(pdf_path), ""

        except Exception as e:
            logger.error(f"❌ Erro ao gerar PDF FR: {e}")
            return "", ""

    # ── Banco de dados ─────────────────────────────────────────────────────────

    @staticmethod
    def save_to_database(data: dict, submitted_by: str = "", client_id: str = "") -> Optional[str]:
        """
        Salva reembolso no Supabase (fuel_reimbursements).
        Retorna id_fr (string) ou None se falhar.

        Mapeamento de campos:
        - submitted_by → user_id (UUID determinístico via uuid5)
        - combustivel   → fuel_type
        - litros        → liters
        - valor_litro   → price_per_liter
        - valor_total   → total_value
        - data_abastecimento → created_at
        - cidade        → city
        - estado        → state
        - km_inicial    → km_start
        - km_final      → km_end
        - km_driven     → km_driven
        - rota          → route_description
        - finalidade    → purpose
        """
        try:
            metrics = FuelService.calculate_metrics(data)
            user_uuid = _user_uuid(submitted_by or "anonimo")
            deviations = FuelService.calculate_deviations(user_uuid, metrics["km_per_liter"])

            now = datetime.now().isoformat()

            record = {
                "user_id": user_uuid,
                "created_at": data.get("data_abastecimento") or now,
                "status": "pendente",
                "submitted_at": now,
                "fuel_type": data.get("combustivel", ""),
                "liters": _to_float(data.get("litros")) or None,
                "price_per_liter": _to_float(data.get("valor_litro")) or None,
                "total_value": _to_float(data.get("valor_total")) or None,
                "km_start": _to_float(data.get("km_inicial")) or None,
                "km_end": _to_float(data.get("km_final")) or None,
                "km_driven": metrics["km_driven"] or None,
                "route_description": data.get("rota", ""),
                "purpose": data.get("finalidade", ""),
                "city": data.get("cidade", ""),
                "state": data.get("estado", ""),
                "km_per_liter": metrics["km_per_liter"] or None,
                "cost_per_km": metrics["cost_per_km"] or None,
                "ai_verified": bool(data.get("ai_verified", False)),
                "ai_confidence_score": _to_float(data.get("ai_confidence_score")) or None,
                "ai_extracted_value": _to_float(data.get("ai_extracted_value")) or None,
                "ai_insight_text": data.get("ai_insight_text", "") or None,
                "deviation_from_user_avg": deviations.get("deviation_from_user_avg"),
                "deviation_from_fleet_avg": deviations.get("deviation_from_fleet_avg"),
                # ── Novos campos ──────────────────────────────────────────────
                "ai_score":            int(data["ai_score"]) if data.get("ai_score") is not None else None,
                "centro_custo":        data.get("centro_custo") or None,
                "image_hash":          data.get("image_hash") or None,
                "signature_b64":       data.get("signature_b64") or None,
                "capacidade_tanque":   data.get("capacidade_tanque"),
                "tank_overflow_alert": bool(data.get("tank_overflow_alert", False)),
                # GPS check-in
                "checkin_lat":             data.get("checkin_lat"),
                "checkin_lng":             data.get("checkin_lng"),
                "checkin_endereco":        data.get("checkin_endereco") or None,
                "checkin_timestamp":       data.get("checkin_timestamp") or None,
                "checkin_distancia_posto": data.get("checkin_distancia_posto"),
                # receipt_image_url e pdf_report_url atualizados via UPDATE após upload
                "client_id": client_id or None,
            }

            result = sb_insert(_TABLE, record)
            if result is None:
                logger.error("❌ Falha ao inserir fuel_reimbursements no Supabase")
                return None

            id_fr = str(result.get("id", ""))
            logger.info(f"✅ FR salvo no Supabase: id={id_fr}")
            return id_fr

        except Exception as e:
            logger.error(f"❌ Erro ao salvar FR: {e}")
            return None

    @staticmethod
    def upload_image_to_storage(image_b64: str, id_fr: str, mime: str = "image/jpeg") -> str:
        """
        Faz upload da imagem da NF para o Supabase Storage.
        Aceita base64 string (sem o prefixo data:...).
        Retorna URL pública ou "".
        """
        try:
            ext = mime.split("/")[-1].replace("jpeg", "jpg")
            data_prefix = datetime.now().strftime("%Y%m%d")
            storage_path = f"Reembolso_{data_prefix}_{id_fr}_nota.{ext}"
            image_bytes = base64.b64decode(image_b64)
            url = sb_storage_upload(Config.FR_BUCKET_NF, storage_path, image_bytes, mime)
            if url:
                sb_update(_TABLE, {"id": id_fr}, {"receipt_image_url": url})
                logger.info(f"✅ FR image uploaded: {url}")
            return url or ""
        except Exception as e:
            logger.error(f"❌ Erro ao fazer upload da imagem FR: {e}")
            return ""

    @staticmethod
    def upload_pdf_to_storage(pdf_path: str, id_fr: str) -> str:
        """
        Faz upload do PDF para o Supabase Storage.
        Retorna URL pública permanente ou "".
        """
        try:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
            data_prefix = datetime.now().strftime("%Y%m%d")
            storage_path = f"Reembolso_{data_prefix}_{id_fr}.pdf"
            url = sb_storage_upload(
                Config.FR_BUCKET_PDF, storage_path, file_bytes, "application/pdf"
            )
            if url:
                sb_update(_TABLE, {"id": id_fr}, {"pdf_report_url": url})
                logger.info(f"✅ FR PDF uploaded: {url}")
            return url or ""
        except Exception as e:
            logger.error(f"❌ Erro ao fazer upload do PDF FR: {e}")
            return ""

    # ── Duplicidade ───────────────────────────────────────────────────────────

    @staticmethod
    def check_duplicate_hash(image_hash: str) -> Optional[str]:
        """
        Verifica se já existe reembolso com o mesmo hash MD5 da imagem.
        Retorna o ID do reembolso duplicado ou None.
        """
        if not image_hash:
            return None
        try:
            rows = sb_select(_TABLE, filters={"image_hash": image_hash}, limit=1)
            if rows:
                return str(rows[0].get("id", ""))
            return None
        except Exception as e:
            logger.warning(f"check_duplicate_hash: {e}")
            return None

    # ── Queries ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_all_reimbursements(limit: int = 200) -> List[Dict[str, Any]]:
        """Busca todos os reembolsos (admin)."""
        return sb_select(_TABLE, order="id.desc", limit=limit) or []

    @staticmethod
    def get_reimbursements_by_user(username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Busca reembolsos de um usuário específico."""
        user_uuid = _user_uuid(username)
        return sb_select(_TABLE, filters={"user_id": user_uuid}, order="id.desc", limit=limit) or []

    # ── Email de notificação ───────────────────────────────────────────────────

    @staticmethod
    def get_notification_emails(client_id: str = "") -> List[str]:
        """Retorna lista de emails (strings) para notificação de reembolso — filtrado por tenant."""
        try:
            filters: dict = {"module": "reembolso"}
            if client_id:
                filters["client_id"] = client_id
            records = sb_select("email_sender", filters=filters) or []
            return [str(r.get("email", "")).strip() for r in records if r.get("email")]
        except Exception as e:
            logger.warning(f"⚠️ get_notification_emails: {e}")
            return []

    @staticmethod
    def get_email_records(client_id: str = "") -> List[Dict[str, Any]]:
        """Retorna registros completos de email para display no dashboard — filtrado por tenant."""
        try:
            filters: dict = {"module": "reembolso"}
            if client_id:
                filters["client_id"] = client_id
            return sb_select("email_sender", filters=filters, order="updated_date.desc") or []
        except Exception as e:
            logger.warning(f"⚠️ get_email_records: {e}")
            return []

    @staticmethod
    def add_notification_email(contract: str, email: str, created_by: str = "admin") -> bool:
        """Adiciona email de notificação para um contrato."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record = {
                "contract": contract,
                "email": email,
                "module": "reembolso",
                "created_by": created_by,
                "updated_date": now,
            }
            result = sb_insert("email_sender", record)
            return result is not None
        except Exception as e:
            logger.error(f"❌ add_notification_email: {e}")
            return False

    @staticmethod
    def delete_notification_email(contract: str, email: str) -> bool:
        """Remove email de notificação pelo par (contract, email)."""
        try:
            return sb_delete("email_sender", {"contract": contract, "email": email})
        except Exception as e:
            logger.error(f"❌ delete_notification_email: {e}")
            return False
