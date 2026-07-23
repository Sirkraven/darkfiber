"""
DarkFiber MAS v5 — pipeline_daemon.py (C3): operación continua.

Consume el(los) archivo(s) que declare `installation.yaml` a través de
`replay.py` -> `StreamRunner` (streaming real, con paridad batch/stream y
eviction real -- ver `stream_runner.py`), y persiste cada veredicto
finalizado en `SignatureCatalog.insert_live_verdict` (tabla operacional
`live_verdicts`, deliberadamente separada del `ledger` de verdad-terreno
-- ver ese método). Expone un healthcheck HTTP simple (`/healthz`,
`/status`) para que un orquestador (Docker, systemd, lo que sea) sepa si
el proceso sigue vivo y procesando, no solo si el proceso existe.

Fuente de datos HOY: solo archivo(s) locales en loop (`replay_loop` en
`installation_config.py`) -- no existe todavía un adaptador de ingesta en
vivo contra el protocolo real de un interrogador (ver
`docs/pilot_kit.md`). Este mismo modo es el que se usa para el soak test
de 24h de C3 (repetir el mismo archivo real en loop y verificar que la
memoria/latencia no crecen).

Uso:
    darkfiber-pipeline --config installation.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import glob
import json
import logging
import logging.handlers
import os
import signal
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ._cli_utf8 import ensure_utf8_stdio
from .catalog import SignatureCatalog
from .installation_config import InstallationConfig, load_installation_config
from .replay import load_file, replay
from .run_on_stanford import sanitize
from .stream_runner import StreamRunner

log = logging.getLogger("darkfiber.pipeline")


class _HealthState:
    """Estado compartido entre el loop principal (asyncio) y el thread
    del healthcheck HTTP -- solo escalares simples, protegidos por un
    lock trivial (no es una ruta caliente: se actualiza una vez por
    chunk, se lee una vez por request HTTP)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.last_chunk_at: float | None = None
        self.files_processed = 0
        self.chunks_processed = 0
        self.verdicts_written = 0
        self.current_file: str | None = None
        self.last_error: str | None = None

    def touch(self, current_file: str) -> None:
        with self._lock:
            self.last_chunk_at = time.time()
            self.chunks_processed += 1
            self.current_file = current_file

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "started_at": self.started_at,
                "uptime_s": time.time() - self.started_at,
                "last_chunk_at": self.last_chunk_at,
                "seconds_since_last_chunk": (
                    None if self.last_chunk_at is None else time.time() - self.last_chunk_at
                ),
                "files_processed": self.files_processed,
                "chunks_processed": self.chunks_processed,
                "verdicts_written": self.verdicts_written,
                "current_file": self.current_file,
                "last_error": self.last_error,
            }


def _make_health_handler(state: _HealthState, stale_after_s: float):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A002
            log.debug("healthcheck: " + fmt, *args)

        def do_GET(self) -> None:  # noqa: N802
            snap = state.snapshot()
            age = snap["seconds_since_last_chunk"]
            healthy = age is not None and age < stale_after_s
            if self.path == "/status":
                body = json.dumps(snap).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            # /healthz (default): 200 vivo y procesando, 503 si no.
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok" if healthy else b"stale")

    return Handler


def _start_healthcheck_server(state: _HealthState, cfg) -> ThreadingHTTPServer:
    handler = _make_health_handler(state, cfg.stale_after_s)
    server = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="healthcheck")
    thread.start()
    log.info(f"healthcheck escuchando en http://{cfg.host}:{cfg.port}/healthz")
    return server


def _setup_logging(cfg) -> None:
    root = logging.getLogger("darkfiber")
    root.setLevel(cfg.level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    if cfg.path:
        os.makedirs(os.path.dirname(os.path.abspath(cfg.path)) or ".", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            cfg.path, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)


def _discover_files(path: str) -> list[str]:
    if os.path.isdir(path):
        files = sorted(
            f
            for f in glob.glob(os.path.join(path, "*"))
            if f.lower().endswith((".h5", ".hdf5", ".npz"))
        )
        if not files:
            raise SystemExit(f"{path}: directorio sin .h5/.hdf5/.npz")
        return files
    if not os.path.isfile(path):
        raise SystemExit(f"{path}: no existe")
    return [path]


async def _backup_loop(db_path: str, cfg, stop: asyncio.Event) -> None:
    """Backup periódico vía la API nativa de SQLite (`Connection.backup`,
    segura contra escrituras concurrentes -- no es una copia de archivo a
    ciegas, que podría capturar la base a mitad de una transacción)."""
    if not cfg.enabled:
        return
    os.makedirs(cfg.dir, exist_ok=True)
    while not stop.is_set():
        try:
            await asyncio.sleep(cfg.interval_s)
        except asyncio.CancelledError:
            return
        if stop.is_set():
            return
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        dest_path = os.path.join(cfg.dir, f"backup_{ts}.db")

        def _do_backup(dest_path: str = dest_path) -> None:
            src = sqlite3.connect(db_path)
            try:
                dest = sqlite3.connect(dest_path)
                try:
                    src.backup(dest)
                finally:
                    dest.close()
            finally:
                src.close()

        try:
            await asyncio.to_thread(_do_backup)
            log.info(f"backup: {dest_path}")
        except Exception:
            log.exception("backup falló (no fatal, se reintenta en el próximo ciclo)")
            continue
        # Poda: conservar solo los últimos `keep_last`.
        backups = sorted(glob.glob(os.path.join(cfg.dir, "backup_*.db")))
        for stale in backups[: -cfg.keep_last] if cfg.keep_last > 0 else []:
            with contextlib.suppress(OSError):
                os.remove(stale)


async def _run_file(
    path: str,
    cfg: InstallationConfig,
    cat: SignatureCatalog,
    state: _HealthState,
    shutdown: asyncio.Event,
) -> None:
    data, fs, dx, _attrs = load_file(path, fs=cfg.data_source.fs_hz, dx=cfg.data_source.dx_m)
    data = sanitize(data)
    geom = cfg.geometry.model_copy(update={"fs_hz": fs, "channel_spacing_m": dx})
    runner = StreamRunner(
        geom,
        cfg.tier0,
        cfg.coherence,
        no_filter=cfg.no_filter,
        analysis_interval_s=cfg.analysis_interval_s,
    )
    event_file = os.path.basename(path)

    async def _persist(pairs) -> None:
        for evt, res in pairs:
            cat.insert_live_verdict(
                event_id=evt.event_id,
                array_id=cfg.array_id,
                source_file=event_file,
                t_start_s=evt.t_start_s,
                t_end_s=evt.t_end_s,
                verdict=res.classification.value,
                explanations=res.explanations,
                metrics_json={
                    "apparent_velocity_mps": res.apparent_velocity_mps,
                    "semblance": res.semblance,
                    "coincidence_fraction": res.coincidence_fraction,
                    "span_fraction": res.span_fraction,
                },
            )
            state.verdicts_written += 1
            log.info(f"{event_file} {evt.event_id}: {res.classification.value}")

    stopped_early = False
    async for chunk in replay(
        data, fs, chunk_s=cfg.data_source.chunk_s, speed=cfg.data_source.speed
    ):
        if shutdown.is_set():
            # Corta de CONSUMIR chunks nuevos -- no espera el resto del
            # archivo (que a `speed` real podría tardar minutos) -- pero
            # todavía no sale de la función: el `finish()` de abajo sigue
            # corriendo siempre, para drenar lo que ya está bufferizado
            # en `runner` en vez de tirarlo. "Drenar antes de cortar", no
            # cortar en seco.
            stopped_early = True
            break
        finalized = await runner.feed(chunk)
        state.touch(event_file)
        if finalized:
            await _persist(finalized)
    await _persist(await runner.finish())
    if not stopped_early:
        state.files_processed += 1


async def run_forever(
    cfg: InstallationConfig, state: _HealthState, shutdown: asyncio.Event
) -> None:
    cat = SignatureCatalog(cfg.ledger_db_path)
    files = _discover_files(cfg.data_source.path)
    log.info(f"array_id={cfg.array_id}: {len(files)} archivo(s), loop continuo")
    stop = asyncio.Event()  # señal interna, solo para _backup_loop -- ver más abajo
    backup_task = asyncio.create_task(_backup_loop(cfg.ledger_db_path, cfg.backup, stop))
    try:
        i = 0
        while not shutdown.is_set():
            path = files[i % len(files)]
            i += 1
            try:
                await _run_file(path, cfg, cat, state, shutdown)
            except Exception as exc:  # noqa: BLE001 -- un archivo roto no debe tumbar el daemon
                state.last_error = f"{path}: {exc}"
                log.exception(f"error procesando {path} -- se sigue con el próximo archivo")
    finally:
        # Orden importa: `_run_file` (arriba) ya drenó el archivo en curso
        # (incluye `runner.finish()`) antes de que el `while` revisara
        # `shutdown` y saliera -- acá solo queda apagar el backup loop
        # (esperando su cancelación real, no solo pedida, para que no
        # siga leyendo el .db mientras `cat.close()` lo checkpointea) y
        # cerrar el ledger.
        log.info("cerrando: apagando backup loop y checkpointeando el ledger")
        stop.set()
        backup_task.cancel()
        await asyncio.gather(backup_task, return_exceptions=True)
        cat.close()
        log.info("shutdown limpio completo")


def main() -> None:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, help="Ruta a installation.yaml")
    args = ap.parse_args()

    cfg = load_installation_config(args.config)
    _setup_logging(cfg.logging)
    state = _HealthState()
    _start_healthcheck_server(state, cfg.healthcheck)
    log.info(f"darkfiber-pipeline arrancando: array_id={cfg.array_id}")
    try:
        asyncio.run(_main_async(cfg, state))
    except KeyboardInterrupt:
        # Red de seguridad, no la ruta principal: en Linux/Docker,
        # _main_async ya instala un handler de SIGINT que apaga
        # ordenadamente vía `shutdown` -- esto solo cubre una plataforma
        # donde `add_signal_handler` no esté disponible (ver ahí).
        log.info("interrumpido por el usuario, cerrando")


async def _main_async(cfg: InstallationConfig, state: _HealthState) -> None:
    """Registra SIGTERM/SIGINT vía `loop.add_signal_handler`, no
    `signal.signal`: sus callbacks corren DENTRO del event loop (no en un
    contexto de señal restringido), así que pueden tocar primitivas de
    asyncio (`shutdown.set()`) de forma segura -- `signal.signal` no lo
    garantiza para código async. `add_signal_handler` necesita un loop
    YA corriendo, por eso esto vive en una corrutina separada en vez de
    antes de `asyncio.run()`. `docker stop` manda SIGTERM (con
    `stop_grace_period` de margen antes de un SIGKILL forzado, ver
    docker-compose.yml) -- sin este handler, Python lo mata sin ningún
    cleanup. En Windows (`add_signal_handler` no soportado,
    `NotImplementedError`) cae al `except KeyboardInterrupt` de `main()`,
    que sigue cubriendo Ctrl+C -- Docker, donde esto corre de verdad,
    siempre es Linux."""
    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown.set)
        except NotImplementedError:
            log.warning(f"add_signal_handler no soportado para {sig.name} en esta plataforma")
    await run_forever(cfg, state, shutdown)


if __name__ == "__main__":
    main()
