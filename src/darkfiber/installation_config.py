"""
DarkFiber MAS v5 — installation_config.py (C3): un `installation.yaml`
por instalación selecciona TODO lo que `pipeline_daemon.py` necesita
(geometría del arreglo, umbrales calibrados, rutas de datos/ledger,
logging, healthcheck, backup) -- cero constantes hardcodeadas en el
daemon mismo, per PLAN_v5.2 §C3.

Requiere el extra opcional `pyyaml` (`pip install darkfiber[ops]`) --
igual que `dashboard`/`figs`, no es una dependencia del núcleo.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .contracts import ArrayGeometry, CoherenceConfig, Tier0Config


class DataSourceConfig(BaseModel):
    """De dónde vienen los chunks. Hoy solo existe el modo `replay_loop`
    -- lee un archivo (o los archivos de un directorio, en orden, en
    loop) con `replay.py`, porque no existe todavía un adaptador de
    ingesta en vivo contra el protocolo real de un interrogador (ver
    `docs/pilot_kit.md`, "qué necesita el dueño de la fibra" -- deuda
    declarada, no escondida). Cuando exista un adaptador real, este
    modelo gana un modo nuevo (p. ej. `live_socket`); `replay_loop` sigue
    sirviendo para demos y para el propio soak test de 24h de C3."""

    mode: str = Field("replay_loop", description="Hoy solo 'replay_loop' existe")
    path: str = Field(..., description="Archivo .h5/.npz, o directorio con varios")
    speed: float | None = Field(
        1.0, description="1.0=tiempo real, None/<=0=sin pacing, N=acelerado"
    )
    chunk_s: float = 1.0
    fs_hz: float | None = None  # solo hace falta para .npz sin attrs embebidos
    dx_m: float | None = None  # ídem


class LoggingConfig(BaseModel):
    path: str = "darkfiber_pipeline.log"
    level: str = "INFO"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


class HealthcheckConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    stale_after_s: float = 30.0


class BackupConfig(BaseModel):
    enabled: bool = True
    dir: str = "backups"
    interval_s: float = 3600.0
    keep_last: int = 24


class InstallationConfig(BaseModel):
    """Todo lo que una instalación real necesita declarar. `array_id`
    entra directo a `SignatureCatalog`/`live_verdicts` (aísla perfiles y
    veredictos por instalación, mismo criterio que el resto del
    proyecto desde P3)."""

    array_id: str
    geometry: ArrayGeometry
    tier0: Tier0Config = Field(default_factory=Tier0Config)
    coherence: CoherenceConfig = Field(default_factory=CoherenceConfig)
    data_source: DataSourceConfig
    ledger_db_path: str = "quakeflow_ledger.db"
    analysis_interval_s: float = 10.0
    no_filter: bool = False
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    healthcheck: HealthcheckConfig = Field(default_factory=HealthcheckConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)


def load_installation_config(path: str) -> InstallationConfig:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SystemExit(
            "Falta pyyaml -- instalá el extra 'ops': pip install 'darkfiber[ops]'"
        ) from exc
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return InstallationConfig.model_validate(raw)
