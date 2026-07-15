"""
DarkFiber MAS v5 — Contratos de datos (Pydantic v2).

Principio del proyecto: todo lo que viaja entre agentes es un contrato
tipado y toda decisión lleva explicaciones auditables (patrón RiskFactor).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


class ArrayGeometry(BaseModel):
    """Geometría física del arreglo DAS."""

    n_channels: int = Field(..., gt=0)
    channel_spacing_m: float = Field(8.0, gt=0, description="Separación entre canales (m)")
    fs_hz: float = Field(50.0, gt=0, description="Frecuencia de muestreo (Hz)")

    @property
    def aperture_m(self) -> float:
        """Longitud total del arreglo en metros (canal 0 al último)."""
        return (self.n_channels - 1) * self.channel_spacing_m


class Tier0Config(BaseModel):
    """Parámetros del triaje STA/LTA (Nivel 0)."""

    sta_s: float = Field(0.4, gt=0, description="Ventana corta (s)")
    lta_s: float = Field(8.0, gt=0, description="Ventana larga (s)")
    gap_s: float = Field(
        0.4, ge=0, description="Retardo del LTA para no contaminarlo con el evento"
    )
    threshold: float = Field(4.0, gt=1, description="Umbral de disparo STA/LTA")
    min_event_duration_s: float = Field(0.3, gt=0)
    merge_gap_s: float = Field(
        3.0,
        ge=0,
        description="Huecos menores a esto se fusionan en un solo evento "
        "(agrupa fases P y S de un mismo sismo local)",
    )
    split_gap_channels: int = Field(
        80,
        ge=0,
        description="Dentro de una misma ventana temporal, grupos de canales "
        "separados por un hueco mayor a esto (80 ch × 8 m = 640 m) "
        "se emiten como eventos independientes: dos fuentes "
        "simultáneas en zonas distintas de la fibra no son un solo "
        "evento. Un sismo real, aun débil, no deja 640 m sin "
        "disparar; una fuente local sí.",
    )


class CoherenceConfig(BaseModel):
    """Parámetros del motor de coherencia física (Nivel 2)."""

    # Banda sísmica (velocidad aparente a lo largo de la fibra)
    seismic_v_min_mps: float = 1500.0
    seismic_v_max_mps: float = 8000.0
    n_velocity_steps: int = 36
    seismic_min_semblance: float = 0.12
    seismic_min_coincidence: float = 0.30  # fracción de canales disparados casi a la vez
    seismic_min_span_frac: float = 0.30  # fracción del arreglo cubierta por el evento
    # Debe cubrir el moveout máximo del arreglo dentro de la banda sísmica:
    # largo_fibra / v_min = (626 canales × 8 m) / 1500 m/s ≈ 3.34 s.
    # Con 2.5 s, un sismo legítimo de v_app baja repartía sus disparos en una
    # ventana mayor y la fracción de coincidencia caía bajo el umbral.
    coincidence_window_s: float = 3.5

    # Banda de tráfico / fuentes móviles lentas
    traffic_v_min_mps: float = 2.0
    traffic_v_max_mps: float = 40.0
    traffic_min_r2: float = 0.80
    traffic_min_duration_s: float = 3.0

    # Supresión de falsos positivos locales
    max_isolated_channels: int = 3
    coherent_channel_corr: float = 0.30  # correlación mínima canal↔beam para contarlo coherente

    # Regional/lejano emergente: disparo masivo sin moveout resoluble por
    # semblanza. Con f_c o span_frac por encima de estos pisos, la supresión
    # de falso positivo local queda prohibida por construcción (energía con
    # esta extensión espacial no es un transitorio de un solo punto).
    regional_min_coincidence: float = 0.5
    regional_min_span_frac: float = 0.5
    onset_fit_min_channels: int = 30  # mínimo de canales con cruce STA/LTA para el ajuste robusto

    use_envelope: bool = True  # robusto ante cambios de polaridad en fibra real

    # Picking de fases P/S sobre el beam apilado
    pick_lookback_s: float = 12.0  # cuánto mirar hacia atrás para captar la P débil
    pick_lookahead_s: float = 3.0

    @classmethod
    def from_array_profile(cls, profile: dict | None) -> CoherenceConfig:
        """Carga umbrales desde el perfil de un arreglo (catalog.array_profiles,
        campo thresholds_json). Sin perfil o sin umbrales propuestos, quedan
        los defaults de esta clase — ningún arreglo cambia de comportamiento
        hasta que `calibrate.py --apply` escriba una propuesta con evidencia."""
        if not profile or not profile.get("thresholds_json"):
            return cls()
        return cls(**profile["thresholds_json"])


# ---------------------------------------------------------------------------
# Resultados (auditables)
# ---------------------------------------------------------------------------


class EventClass(str, Enum):
    """Veredicto físico del CoherenceAgent. Ver docs/adr/0002 para por qué
    existe REGIONAL_EMERGENT como quinta clase, no una variante de las otras
    cuatro."""

    SEISMIC_CONFIRMED = "SISMO_CONFIRMADO"
    TRAFFIC = "FUENTE_MOVIL_TRAFICO"
    INCOHERENT_LOCAL = "INCOHERENTE_LOCAL_SUPRIMIDO"
    UNKNOWN_COHERENT = "COHERENTE_DESCONOCIDO"
    REGIONAL_EMERGENT = "POSIBLE_REGIONAL_EMERGENTE"


class TriggerEvent(BaseModel):
    """Un evento candidato producido por el Nivel 0 (STA/LTA)."""

    event_id: str
    t_start_s: float
    t_end_s: float
    ch_min: int
    ch_max: int
    n_triggered_channels: int
    peak_ratio: float = Field(..., description="Máximo STA/LTA observado")


class PhaseArrivals(BaseModel):
    """Llegadas de fases sísmicas medidas sobre el beam apilado."""

    t_p_s: float | None = None
    t_s_s: float | None = None

    @property
    def ts_minus_tp_s(self) -> float | None:
        """Segundos de alerta temprana: cuánto antes llega la P que la S."""
        if self.t_p_s is None or self.t_s_s is None:
            return None
        return self.t_s_s - self.t_p_s


class CoherenceResult(BaseModel):
    """Veredicto físico del CoherenceAgent sobre un TriggerEvent.

    Todo campo numérico es una MEDICIÓN, no una etiqueta del modelo ML.
    Las `explanations` siguen el patrón RiskFactor: legibles y auditables.
    """

    event_id: str
    classification: EventClass
    apparent_velocity_mps: float | None = Field(
        None, description="Velocidad aparente a lo largo de la fibra (m/s). Signo = dirección."
    )
    semblance: float | None = Field(None, ge=0, le=1)
    coincidence_fraction: float | None = Field(None, ge=0, le=1)
    coherent_channels: int | None = None
    span_fraction: float | None = Field(None, ge=0, le=1)
    track_speed_mps: float | None = None
    track_r2: float | None = None
    phases: PhaseArrivals | None = None
    v_app_onset_mps: float | None = Field(
        None,
        description="Velocidad aparente por ajuste robusto de onsets STA/LTA "
        "(fallback cuando la semblanza de forma de onda muere en llegadas emergentes)",
    )
    onset_fit_r2: float | None = Field(None, ge=0, le=1)
    suppressed_false_positive: bool = False
    explanations: list[str] = Field(default_factory=list)


class CatalogMatch(BaseModel):
    """Resultado de comparar la firma latente de un evento contra el catálogo."""

    label: str | None = None
    similarity: float = 0.0
    is_novel: bool = True
    recurring_unknown_id: int | None = None
    recurring_count: int = 0
    suggest_naming: bool = False
    explanations: list[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    """Verdad-terreno embebida en un archivo real (p. ej. QuakeFlow DAS:
    magnitud/epicentro/origen ya vienen en los attrs del HDF5)."""

    usgs_id: str | None = None
    magnitude: float | None = None
    origin_time: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    array_id: str
    distance_km: float | None = None


class OutcomeLabel(str, Enum):
    """Resultado de comparar el veredicto del motor contra la verdad-terreno.

    HIT: sismo local real -> SISMO_CONFIRMADO.
    HONEST_UNKNOWN: evento real débil -> COHERENTE_DESCONOCIDO (no alucina).
    HONEST_REGIONAL: evento real emergente/lejano -> POSIBLE_REGIONAL_EMERGENTE.
    MISS_SUPPRESSED: hubo un evento real y el motor lo perdió (suprimido,
        mal clasificado, o Tier0 nunca disparó nada que lo cubra) — el peor
        modo de falla.
    FALSE_ALARM: SISMO_CONFIRMADO sin verdad-terreno que lo respalde.
    CORRECT_REJECTION: sin verdad-terreno y el motor correctamente no
        confirmó nada.
    """

    HIT = "HIT"
    HONEST_UNKNOWN = "HONEST_UNKNOWN"
    HONEST_REGIONAL = "HONEST_REGIONAL"
    MISS_SUPPRESSED = "MISS_SUPPRESSED"
    FALSE_ALARM = "FALSE_ALARM"
    CORRECT_REJECTION = "CORRECT_REJECTION"


class ValidationOutcome(BaseModel):
    """Une un evento real, el veredicto del motor y la etiqueta de resultado
    — la fila atómica del ledger de verdad-terreno (P2)."""

    event_file: str
    array_id: str
    ground_truth: GroundTruth | None = None
    verdict: CoherenceResult | None = None
    outcome: OutcomeLabel
    dt_detect_s: float | None = None


class SelfTestResult(BaseModel):
    """Resultado de una inyección sintética de auto-verificación."""

    injected_velocity_mps: float
    injected_t0_s: float
    injected_snr: float
    detected: bool
    classified_as: EventClass | None = None
    measured_velocity_mps: float | None = None
    latency_note: str = ""
