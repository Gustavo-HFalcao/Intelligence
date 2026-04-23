"""
PDF utilities — HTML-to-PDF via Playwright/Edge in an isolated subprocess.

ARCHITECTURE NOTE — WHY subprocess isolation matters:
  The previous Playwright/Chromium implementation ran inside the main Reflex
  process. On the Fly.io 1 GB container, one PDF call could push the process
  past the OOM limit → the kernel killed the entire Python process → ALL
  WebSocket connections dropped → every user saw "Reconectando" simultaneously.

  This implementation spawns a SEPARATE PROCESS for each PDF job via
  multiprocessing.Process(context="spawn"). If that worker crashes or OOMs,
  ONLY the subprocess dies. The main Reflex server process and every active
  user connection remain alive. The calling code gets a RuntimeError and can
  show the user an error message instead of bringing down the platform.

  Edge/Chromium peak RAM per call: ~300–500 MB — contained inside the worker.
  Worker is killed after 120s timeout; proc.kill() ensures no zombie processes.

  CDN blocking: Google Fonts, Tailwind CDN, etc. are aborted inside the worker
  so `wait_until="domcontentloaded"` never hangs waiting for external resources.
"""
from __future__ import annotations

import multiprocessing
import sys
import time
from pathlib import Path

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# Minimum free RAM required before spawning the PDF subprocess.
# If the system is already under memory pressure, fail fast here rather than
# spawning and causing an OOM kill that would disconnect all users.
_MIN_FREE_MB = 150


# ─── Public API ───────────────────────────────────────────────────────────────

def html_to_pdf(
    html: str,
    path: Path,
    margin: dict | None = None,
    display_header_footer: bool = True,
    header_template: str | None = None,
    footer_template: str | None = None,
) -> None:
    """
    Render an HTML string to a PDF file using Playwright (Edge on Windows,
    Chromium on Linux) running in an isolated subprocess.

    Runs in an isolated subprocess — a crash or OOM in the worker cannot
    affect the main server process or other users' connections.

    Args:
        html: Full HTML document string (UTF-8).
        path: Destination Path for the PDF file.
        margin: Optional dict with top/right/bottom/left keys.
                Defaults to {"top":"1.8cm","right":"1.4cm","bottom":"1.8cm","left":"1.4cm"}.
        display_header_footer: Whether to inject the BOMTEMPO header/footer on each page.
        header_template: Override header HTML (Playwright template). Ignored when
                         display_header_footer=False.
        footer_template: Override footer HTML (Playwright template). Ignored when
                         display_header_footer=False.

    Raises:
        RuntimeError: On timeout, worker crash, or Playwright errors.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # ── Pre-flight: memory pressure check ────────────────────────────────────
    try:
        import psutil
        available_mb = psutil.virtual_memory().available // (1024 * 1024)
        if available_mb < _MIN_FREE_MB:
            raise RuntimeError(
                f"Memória insuficiente para gerar PDF "
                f"(disponível: {available_mb} MB, mínimo: {_MIN_FREE_MB} MB). "
                f"O RDO foi salvo — tente gerar o PDF novamente em alguns minutos."
            )
        logger.debug(f"pdf_utils: pre-flight OK — {available_mb} MB disponível")
    except ImportError:
        pass  # psutil not available — skip check, proceed

    _m = margin or {"top": "1.8cm", "right": "1.4cm", "bottom": "1.8cm", "left": "1.4cm"}

    # Build header/footer templates for Playwright
    _default_header = (
        '<div style="width:100%;box-sizing:border-box;padding:0 48px;'
        'font-family:Arial,sans-serif;font-size:8px;color:#9CA3AF;'
        'display:flex;justify-content:space-between;align-items:center;'
        'border-bottom:1px solid #E5E7EB;padding-bottom:6px;">'
        '<span style="font-weight:700;color:#C98B2A;letter-spacing:0.12em;">'
        'BOMTEMPO INTELLIGENCE</span>'
        '<span>Relatório Executivo · Confidencial</span>'
        '</div>'
    )
    _default_footer = (
        '<div style="width:100%;box-sizing:border-box;padding:0 48px;'
        'font-family:Arial,sans-serif;font-size:8px;color:#9CA3AF;'
        'display:flex;justify-content:space-between;align-items:center;'
        'border-top:1px solid #E5E7EB;padding-top:6px;">'
        '<span>Documento Confidencial — Uso Interno</span>'
        '<span>Página <span class="pageNumber"></span> '
        'de <span class="totalPages"></span></span>'
        '</div>'
    )

    hdr = header_template if header_template is not None else _default_header
    ftr = footer_template if footer_template is not None else _default_footer

    # "spawn" starts a fresh Python interpreter — safe from asyncio/threading
    # inheritance issues (unlike "fork"). ~1-2s startup overhead is acceptable.
    ctx = multiprocessing.get_context("spawn")
    q: multiprocessing.Queue = ctx.Queue()

    proc = ctx.Process(
        target=_playwright_worker,
        args=(html, str(path), _m, display_header_footer, hdr, ftr, q),
        daemon=True,
    )

    try:
        import psutil
        _vm = psutil.virtual_memory()
        logger.info(
            f"pdf_utils: spawning worker | RAM {_vm.used // (1024*1024)}MB used / "
            f"{_vm.total // (1024*1024)}MB total / "
            f"{_vm.available // (1024*1024)}MB available"
        )
    except Exception:
        pass

    t0 = time.monotonic()
    proc.start()
    proc.join(timeout=120)
    elapsed = time.monotonic() - t0

    if proc.is_alive():
        proc.kill()
        proc.join(timeout=5)
        raise RuntimeError("PDF generation timed out after 120s")

    if proc.exitcode not in (0, None):
        # exitcode -9 (Linux SIGKILL) = OOM killer do kernel matou o subprocess.
        # Acontece quando o container não tem RAM suficiente para o Chromium (~300-500MB).
        # O servidor principal NÃO cai — apenas este worker morreu.
        _oom = proc.exitcode in (-9, -11) or proc.exitcode == 137  # 137 = 128 + SIGKILL em shells
        _oom_hint = " — provável OOM (falta de RAM no container)" if _oom else ""
        try:
            import psutil
            vm = psutil.virtual_memory()
            _mem_info = (
                f" | RAM: {vm.used // (1024*1024)}MB usados / "
                f"{vm.total // (1024*1024)}MB total / "
                f"{vm.available // (1024*1024)}MB disponível"
            )
        except Exception:
            _mem_info = ""
        logger.error(
            f"PDF worker crashed (exitcode={proc.exitcode}){_oom_hint}{_mem_info}"
        )
        raise RuntimeError(
            f"PDF worker process crashed (exitcode={proc.exitcode}){_oom_hint}"
        )

    # Check for application-level error reported by the worker
    try:
        err = q.get_nowait()
    except Exception:
        err = None

    if err:
        raise RuntimeError(f"PDF generation failed: {err}")

    if not path.exists() or path.stat().st_size < 100:
        raise RuntimeError("PDF file was not created or is suspiciously small")

    logger.debug(f"pdf_utils: PDF written → {path.name} ({elapsed:.1f}s)")


# ─── Worker function (executes inside isolated subprocess) ───────────────────

def _playwright_worker(
    html: str,
    path_str: str,
    margin: dict,
    display_header_footer: bool,
    header_template: str,
    footer_template: str,
    result_queue: "multiprocessing.Queue",
) -> None:
    """
    Playwright PDF renderer — runs in a completely isolated subprocess.

    Any exception or OOM here only kills this worker; the parent Reflex
    server process and all active WebSocket connections are unaffected.

    OS-level memory cap (Linux/Fly.io):
      resource.setrlimit(RLIMIT_AS, 400 MB) is applied at startup.
      If Chromium tries to allocate beyond this, the OS raises MemoryError
      inside THIS process only — not OOM-killing the parent.
    """
    # ── OS-enforced memory cap — Linux only (Fly.io, Docker) ─────────────────
    try:
        import resource  # noqa: PLC0415 — stdlib, Linux only
        _400MB = 400 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (_400MB, _400MB))
        except (ValueError, OSError, resource.error):  # type: ignore[attr-defined]
            pass  # insufficient privileges or unsupported — skip
    except ImportError:
        pass  # Windows / macOS — module does not exist, skip silently

    try:
        import asyncio

        async def _render() -> None:
            from playwright.async_api import async_playwright

            # Flags que reduzem RAM do Chromium em ~40-50% no Linux.
            # --single-process: renderer roda no mesmo processo do browser (~150MB vs ~400MB).
            # --disable-dev-shm-usage: evita esgotar /dev/shm (64MB no Docker/Fly.io).
            # Demais flags desligam features desnecessárias para geração de PDF.
            _LEAN_ARGS = [
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--single-process",
            ]

            async def _launch(p):
                """Launch browser: Edge on Windows (sem single-process), Chromium+lean no Linux."""
                if sys.platform == "win32":
                    # Edge no Windows não suporta --single-process — usa sem a flag
                    win_args = [a for a in _LEAN_ARGS if a != "--single-process" and a != "--no-sandbox"]
                    try:
                        return await p.chromium.launch(channel="msedge", args=win_args)
                    except Exception:
                        return await p.chromium.launch(args=win_args)
                else:
                    # Linux (Fly.io): --single-process é o maior redutor de RAM
                    try:
                        return await p.chromium.launch(args=_LEAN_ARGS)
                    except Exception as launch_err:
                        if "Executable doesn't exist" in str(launch_err) or "executable" in str(launch_err).lower():
                            import subprocess as sp
                            sp.run(
                                [sys.executable, "-m", "playwright", "install", "chromium"],
                                check=False, capture_output=True, timeout=300,
                            )
                            return await p.chromium.launch(args=_LEAN_ARGS)
                        raise

            _BLOCKED_HOSTS = (
                "fonts.googleapis.com",
                "fonts.gstatic.com",
                "cdn.tailwindcss.com",
                "unpkg.com",
                "jsdelivr.net",
                "cdnjs.cloudflare.com",
            )

            async with async_playwright() as p:
                browser = await _launch(p)
                try:
                    page = await browser.new_page()

                    async def _block_external(route):
                        if any(h in route.request.url for h in _BLOCKED_HOSTS):
                            await route.abort()
                        else:
                            await route.continue_()

                    await page.route("**/*", _block_external)
                    await page.set_content(html, wait_until="domcontentloaded", timeout=15000)
                    await page.pdf(
                        path=path_str,
                        format="A4",
                        print_background=True,
                        margin=margin,
                        display_header_footer=display_header_footer,
                        header_template=header_template,
                        footer_template=footer_template,
                    )
                finally:
                    await browser.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_render())
        finally:
            loop.close()

        result_queue.put(None)  # None = success sentinel

    except MemoryError:
        result_queue.put("PDF worker atingiu limite de memória — documento muito grande?")
    except Exception as exc:  # noqa: BLE001
        result_queue.put(str(exc))
