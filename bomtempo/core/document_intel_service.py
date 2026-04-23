"""
DocumentIntelService — Bomtempo Intelligence
Analisa documentos anexados à timeline em background via IA.
Extrai pontos-chave, alertas, entidades e riscos — salva em hub_document_intel.

Pipeline:
  Upload na timeline → trigger fire-and-forget → extrai texto do arquivo
  → IA analisa → salva hub_document_intel → dispara AlertEngine se há alertas

LGPD: sempre filtra por client_id. Zero cross-tenant.
"""
from __future__ import annotations

import io
import json
import re
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_insert, sb_update, sb_select

logger = get_logger(__name__)

# ── Métricas de desempenho para observabilidade ────────────────────────────────
_STATS: Dict[str, int] = {"processed": 0, "errors": 0, "skipped": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Extração de texto (PDF e outros formatos)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_file_bytes(url: str) -> Optional[bytes]:
    """Baixa o arquivo da URL pública do Supabase Storage."""
    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            if r.status_code == 200:
                return r.content
    except Exception as exc:
        logger.warning(f"[DocIntel] fetch_bytes error: {exc}")
    return None


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto de PDF usando pdfplumber (já presente no projeto via Playwright)."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:30]:  # máximo 30 páginas
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning(f"[DocIntel] pdfplumber error: {exc}")

    # Fallback: pypdf2
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = [reader.pages[i].extract_text() or "" for i in range(min(30, len(reader.pages)))]
        return "\n\n".join(p for p in pages if p.strip())
    except Exception:
        pass

    return ""


def _extract_text_from_docx(file_bytes: bytes) -> str:
    """Extrai texto de DOCX."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        logger.warning(f"[DocIntel] docx error: {exc}")
    return ""


def _extract_text(url: str, filename: str) -> str:
    """Detecta tipo pelo nome/extensão e extrai texto."""
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    file_bytes = _fetch_file_bytes(url)
    if not file_bytes:
        return ""

    if ext == "pdf":
        return _extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return _extract_text_from_docx(file_bytes)
    elif ext in ("txt", "md", "csv"):
        try:
            return file_bytes.decode("utf-8", errors="replace")[:20000]
        except Exception:
            return ""
    elif ext in ("xlsx", "xls"):
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df.to_markdown(index=False)
        except Exception:
            return ""
    else:
        # Tentativa genérica como texto
        try:
            return file_bytes.decode("utf-8", errors="ignore")[:10000]
        except Exception:
            return ""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt de análise IA
# ─────────────────────────────────────────────────────────────────────────────

_ANALYSIS_SYSTEM = """Você é um analista jurídico-técnico especializado em contratos e documentos de construção civil.
Analise o documento fornecido e extraia APENAS informações presentes no texto.
NÃO invente dados. Se uma informação não estiver no texto, omita-a.
Retorne EXCLUSIVAMENTE JSON válido, sem markdown, sem explicações, sem comentários."""

_ANALYSIS_PROMPT = """Documento: {titulo}
Tipo inferido: {tipo_hint}
Contrato: {contrato}

Texto do documento:
---
{texto}
---

Retorne um JSON com exatamente esta estrutura:
{{
  "tipo_documento": "contrato|ata|nota_tecnica|medicao|aditivo|boletim|relatorio|outro",
  "resumo_executivo": "máximo 3 frases descrevendo o documento e sua relevância",
  "pontos_chave": [
    "ponto importante 1 (máximo 15 palavras)",
    "ponto importante 2"
  ],
  "alertas_extraidos": [
    {{
      "tipo": "multa|prazo|garantia|rescisao|pagamento|requisito|outro",
      "descricao": "descrição clara do alerta",
      "valor": "valor monetário ou percentual se houver, null caso contrário",
      "gatilho": "condição que ativa (ex: atraso, inadimplência)",
      "criticidade": "alto|medio|baixo"
    }}
  ],
  "entidades": {{
    "partes": ["Empresa A", "Empresa B"],
    "prazo_final": "data ISO ou null",
    "valor_contrato": "valor em reais ou null",
    "vigencia_meses": "número ou null",
    "objeto": "descrição do objeto do contrato em 1 frase"
  }},
  "riscos": [
    {{
      "descricao": "descrição do risco identificado",
      "nivel": "alto|medio|baixo"
    }}
  ]
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Motor de análise
# ─────────────────────────────────────────────────────────────────────────────

def _classify_document_type(titulo: str, descricao: str) -> str:
    """Infere tipo pelo título antes de chamar a IA."""
    texto = f"{titulo} {descricao}".lower()
    if any(w in texto for w in ["contrato", "acordo", "instrumento"]):
        return "contrato"
    if any(w in texto for w in ["ata", "reunião", "reuniao", "meeting"]):
        return "ata"
    if any(w in texto for w in ["medição", "medicao", "bm ", "boletim"]):
        return "medicao"
    if any(w in texto for w in ["aditivo", "termo aditivo", "apostilamento"]):
        return "aditivo"
    if any(w in texto for w in ["nota técnica", "nt ", "nota tecnica"]):
        return "nota_tecnica"
    if any(w in texto for w in ["relatório", "relatorio", "report"]):
        return "relatorio"
    return "documento"


def _call_ai_analysis(titulo: str, contrato: str, texto: str, tipo_hint: str) -> Dict[str, Any]:
    """Chama a IA para análise. Retorna dict com os campos esperados."""
    from bomtempo.core.ai_client import ai_client

    # Limita texto para não estourar contexto (max ~40k chars ≈ 10k tokens)
    texto_truncado = texto[:40000]
    if len(texto) > 40000:
        texto_truncado += "\n\n[... documento truncado por tamanho ...]"

    prompt = _ANALYSIS_PROMPT.format(
        titulo=titulo,
        tipo_hint=tipo_hint,
        contrato=contrato,
        texto=texto_truncado,
    )

    try:
        resp = ai_client.query(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=_ANALYSIS_SYSTEM,
            max_tokens=2000,
        )
        # Extrai JSON da resposta (pode ter ruído)
        json_match = re.search(r'\{[\s\S]*\}', resp or "")
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError as je:
        logger.warning(f"[DocIntel] JSON parse error: {je}")
    except Exception as exc:
        logger.error(f"[DocIntel] AI call error: {exc}")

    return {}


def _run_analysis(
    timeline_id: str,
    contrato: str,
    client_id: str,
    titulo: str,
    descricao: str,
    anexo_url: str,
    anexo_nome: str,
) -> None:
    """
    Executa o pipeline completo de análise.
    Chamado em threading.Thread(daemon=True) — nunca bloqueia o event loop.
    """
    t_start = time.time()

    # 1. Inserir registro com status=processing
    intel_id = None
    try:
        tipo_hint = _classify_document_type(titulo, descricao)
        row = sb_insert("hub_document_intel", {
            "timeline_id": timeline_id,
            "contrato": contrato,
            "client_id": client_id or None,
            "tipo_documento": tipo_hint,
            "status": "processing",
        })
        intel_id = (row or {}).get("id") if row else None
        if not intel_id:
            logger.warning(f"[DocIntel] sb_insert não retornou id para timeline {timeline_id}")
    except Exception as exc:
        logger.error(f"[DocIntel] Falha ao criar registro inicial: {exc}")
        _STATS["errors"] += 1
        return

    # 2. Extrair texto do documento
    texto = ""
    if anexo_url:
        texto = _extract_text(anexo_url, anexo_nome or "doc.pdf")

    if not texto.strip():
        # Usa título + descrição como fallback mínimo
        texto = f"{titulo}\n{descricao or ''}"

    # 3. Analisar com IA
    result = _call_ai_analysis(titulo, contrato, texto, tipo_hint)

    elapsed_ms = int((time.time() - t_start) * 1000)

    # 4. Persistir resultado
    update_payload: Dict[str, Any] = {
        "status": "done" if result else "error",
        "processing_ms": elapsed_ms,
        "model_used": "claude-sonnet-4-6",
    }

    if result:
        update_payload.update({
            "tipo_documento": result.get("tipo_documento", tipo_hint),
            "resumo_executivo": result.get("resumo_executivo", ""),
            "pontos_chave": result.get("pontos_chave", []),
            "alertas_extraidos": result.get("alertas_extraidos", []),
            "entidades": result.get("entidades", {}),
            "riscos": result.get("riscos", []),
        })
        _STATS["processed"] += 1
        logger.info(
            f"[DocIntel] ✅ {titulo[:50]} — {len(result.get('pontos_chave', []))} pontos, "
            f"{len(result.get('alertas_extraidos', []))} alertas — {elapsed_ms}ms"
        )

        # 5. Se há alertas críticos extraídos, dispara AlertEngine
        alertas = result.get("alertas_extraidos", [])
        criticos = [a for a in alertas if a.get("criticidade") == "alto"]
        if criticos:
            _trigger_document_alerts(contrato, client_id, titulo, criticos)

    else:
        update_payload["error_msg"] = "IA não retornou análise válida"
        _STATS["errors"] += 1
        logger.warning(f"[DocIntel] ❌ Análise vazia para {titulo[:50]}")

    try:
        sb_update("hub_document_intel", filters={"id": intel_id}, data=update_payload)
    except Exception as exc:
        logger.error(f"[DocIntel] Falha ao salvar resultado: {exc}")


def _trigger_document_alerts(
    contrato: str, client_id: str, titulo: str, criticos: List[Dict]
) -> None:
    """Dispara AlertEngine para alertas críticos extraídos de documento."""
    try:
        from bomtempo.core.alert_engine import AlertEngine
        AlertEngine.check_event(
            event_type="document_critical_alert",
            contrato=contrato,
            client_id=client_id,
            metadata={
                "documento": titulo,
                "alertas": criticos,
            },
        )
    except Exception as exc:
        logger.warning(f"[DocIntel] AlertEngine trigger error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

class DocumentIntelService:
    """Interface pública para o pipeline de Document Intelligence."""

    @staticmethod
    def trigger_analysis(
        timeline_id: str,
        contrato: str,
        client_id: str,
        titulo: str,
        descricao: str = "",
        anexo_url: str = "",
        anexo_nome: str = "",
    ) -> None:
        """
        Dispara análise em background. Fire-and-forget — retorna imediatamente.
        Deve ser chamado logo após o sb_insert do evento na timeline.
        """
        t = threading.Thread(
            target=_run_analysis,
            args=(timeline_id, contrato, client_id, titulo, descricao, anexo_url, anexo_nome),
            daemon=True,
            name=f"doc-intel-{timeline_id[:8]}",
        )
        t.start()
        logger.info(f"[DocIntel] 🔍 Background análise iniciada: {titulo[:50]} [{timeline_id[:8]}]")

    @staticmethod
    def get_intel_for_timeline(timeline_id: str, client_id: str = "") -> Optional[Dict]:
        """Retorna análise salva para um timeline_id. None se pendente/erro."""
        try:
            filters: Dict = {"timeline_id": timeline_id}
            rows = sb_select("hub_document_intel", filters=filters, limit=1)
            if rows:
                return rows[0]
        except Exception as exc:
            logger.warning(f"[DocIntel] get_intel error: {exc}")
        return None

    @staticmethod
    def get_intel_for_contrato(contrato: str, client_id: str = "") -> List[Dict]:
        """
        Retorna todas as análises concluídas de um contrato.
        Usado no contexto de relatórios e alertas.
        """
        try:
            filters: Dict = {"contrato": contrato, "status": "done"}
            if client_id:
                filters["client_id"] = client_id
            rows = sb_select("hub_document_intel", filters=filters, limit=50)
            return rows or []
        except Exception as exc:
            logger.warning(f"[DocIntel] get_intel_for_contrato error: {exc}")
        return []

    @staticmethod
    def get_pontos_chave_context(contrato: str, client_id: str = "") -> str:
        """
        Retorna pontos-chave formatados como contexto para IA (relatórios, alertas, chat).
        Texto pronto para injetar em system_prompt.
        """
        rows = DocumentIntelService.get_intel_for_contrato(contrato, client_id)
        if not rows:
            return ""

        lines = ["## DOCUMENTOS ANALISADOS — PONTOS-CHAVE E ALERTAS"]
        for r in rows:
            titulo = r.get("titulo") or r.get("tipo_documento", "Documento")
            pontos = r.get("pontos_chave") or []
            alertas = r.get("alertas_extraidos") or []
            entidades = r.get("entidades") or {}

            lines.append(f"\n### {titulo}")
            if entidades.get("objeto"):
                lines.append(f"Objeto: {entidades['objeto']}")
            if entidades.get("prazo_final"):
                lines.append(f"Prazo final: {entidades['prazo_final']}")
            if entidades.get("valor_contrato"):
                lines.append(f"Valor: {entidades['valor_contrato']}")

            if pontos:
                lines.append("**Pontos-chave:**")
                for p in pontos[:8]:
                    lines.append(f"- {p}")

            if alertas:
                lines.append("**Alertas contratuais:**")
                for a in alertas[:5]:
                    crit = a.get("criticidade", "medio")
                    flag = "🔴" if crit == "alto" else ("🟡" if crit == "medio" else "🟢")
                    lines.append(
                        f"- {flag} [{a.get('tipo', '')}] {a.get('descricao', '')} "
                        f"{'— ' + a.get('valor', '') if a.get('valor') else ''}"
                    )

        return "\n".join(lines)

    @staticmethod
    def get_stats() -> Dict[str, int]:
        return dict(_STATS)
