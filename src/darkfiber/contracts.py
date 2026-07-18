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
    max_merged_block_s: float = Field(
        20.0,
        gt=0,
        description="Techo de duración para un bloque fusionado por "
        "merge_gap_s ANTES de que extract_events lo re-examine "
        "con la compuerta de densidad (A5). Muy por encima de la "
        "duración esperable de un sismo local real de esta "
        "banda (P-a-S + coda estructurada: ~3-10 s en la verdad-"
        "terreno sintética y en el M5.8 real de Ridgecrest antes "
        "de decaer a chatter de baja densidad) y muy por debajo "
        "de la patología real encontrada en A5 (Ridgecrest: "
        "bloques de 79-111 s = casi el archivo entero). Bloques "
        "más cortos que esto NUNCA tocan la compuerta de "
        "densidad — preserva sin cambios el comportamiento "
        "histórico (p. ej. que una fase P débil pero real se "
        "siga fusionando con la S fuerte que la sigue).",
    )
    dense_coincidence_frac: float = Field(
        0.01,
        ge=0,
        le=1,
        description="Compuerta de densidad usada SOLO al re-segmentar un "
        "bloque que superó max_merged_block_s (A5): dentro de "
        "ese bloque, un instante cuenta como parte de una ráfaga "
        "real si al menos esta fracción de canales dispara A LA "
        "VEZ, no con solo 'algún' canal disparado — encontrado "
        "en A5 sobre datos reales de Ridgecrest (1150 canales): "
        "con esa definición más laxa, la probabilidad de que "
        "TODOS los canales estén simultáneamente por debajo del "
        "umbral en una muestra dada es casi nula por pura "
        "estadística de ruido ambiental disperso. Un sismo real "
        "ilumina una fracción sustancial del arreglo A LA VEZ "
        "(ver seismic_min_coincidence=0.30 y "
        "regional_min_coincidence=0.5 en CoherenceConfig); este "
        "piso de Tier0 es deliberadamente mucho más bajo — es un "
        "filtro grueso para separar ráfagas densas de chatter "
        "ambiental disperso (1-5 canales) dentro de un bloque ya "
        "sospechoso por su duración, no una réplica de esa "
        "física.",
    )
    dense_min_channels_floor: int = Field(
        4,
        ge=1,
        description="Piso absoluto de dense_coincidence_frac para arreglos "
        "chicos, donde la fracción sola redondearía a muy pocos "
        "canales.",
    )

    @property
    def warmup_s(self) -> float:
        """Tiempo mínimo de buffer antes de que el LTA termine de calentar
        y el disparo deje de estar forzado a "nunca dispara" (ver
        triage.sta_lta_ratio). Única fuente de esta cuenta en el proyecto —
        antes de A2 se recalculaba ad hoc en más de un módulo (snr_curve.py)
        y en el propio triage.py, con el riesgo de que diverjan.
        """
        return self.lta_s + self.gap_s + self.sta_s

    @classmethod
    def from_array_profile(cls, profile: dict | None) -> Tier0Config:
        """Carga `threshold` (STA/LTA, Nivel 0) desde el perfil de un
        arreglo (catalog.array_profiles, campo thresholds_json) — análogo a
        `CoherenceConfig.from_array_profile` (A7). Sin perfil o sin
        `threshold` propuesto, quedan los defaults de esta clase
        (threshold=4.0 global) — ningún arreglo cambia de comportamiento
        hasta que `calibrate.py --param tier0_threshold --apply` escriba una
        propuesta con evidencia real + sintética. `thresholds_json` puede
        traer también campos de `CoherenceConfig` (p. ej.
        seismic_min_semblance, escritos por el otro modo de calibrate.py);
        Pydantic v2 ignora por default los campos extra que no son de esta
        clase, así que compartir el mismo blob entre ambos modos es seguro."""
        if not profile or not profile.get("thresholds_json"):
            return cls()
        return cls(**profile["thresholds_json"])


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

    # A10, "ninguna confirmación sísmica se sostiene en un solo estimador de
    # velocidad": SISMO_CONFIRMADO exige que el ajuste de onsets (Theil-Sen,
    # independiente del slant-stack) CORROBORE, no solo exista. Encontrado en
    # A9: el M5.8 real ya tenía v_app_onset=-10,282 m/s vs v_semblance=-1,500
    # m/s (discrepancia >200%) -- el guard de borde lo atrapó por otro lado,
    # pero la concordancia lo habría atrapado igual, de forma independiente
    # (defensa en capas, no redundancia inútil).
    # 40%: run_validation.py ya valida cada estimador CONTRA LA VERDAD-TERRENO
    # por separado con tolerancias propias (slant-stack ≤8%, onset ≤15%,
    # escenario A sintético) -- si ambos están dentro de su propio margen
    # pero en direcciones opuestas del valor real, pueden diferir ENTRE SÍ
    # hasta ~23% (suma) en el peor caso incluso siendo ambos "correctos".
    # 40% deja margen extra para ruido real (los sintéticos que fijan 8%/15%
    # son limpios por construcción) sin diluirse hasta el punto de aceptar
    # una discrepancia real como la del M5.8 (>200%, ver A9/A10).
    onset_agreement_tol_frac: float = (
        0.40  # diferencia relativa máxima entre |v_semblance| y |v_onset|
    )
    # Sin piso de R² para la concordancia (probado y descartado en A10): un
    # primer intento con onset_agreement_min_r2=0.15 tiraba abajo
    # confirmaciones sanas sobre ruido REAL de Ridgecrest (inyecciones con
    # v_onset a 1% de la verdad-terreno pero R²=0.03) -- Theil-Sen es un
    # estimador ROBUSTO específicamente porque tolera picks ruidosos canal a
    # canal sin que la PENDIENTE se rompa; un R² bajo mide dispersión
    # alrededor de la recta, no si la pendiente es confiable. El criterio de
    # corroboración es la concordancia de VELOCIDAD (onset_agreement_tol_frac),
    # no la forma de la recta -- ver coherence.analyze() para el detalle.

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
    boundary_pinned: bool = Field(
        False,
        description="A9: el argmax de semblanza cae en el borde de su rama de "
        "la grilla de velocidades (o no es un pico interior estricto) "
        "-- el óptimo real puede estar fuera del rango barrido, así "
        "que apparent_velocity_mps NO es una medición resuelta, y no "
        "puede sostener SISMO_CONFIRMADO por sí sola (ver "
        "coherence._velocity_peak_is_boundary).",
    )
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
    MISS_SUPPRESSED: Tier0 SÍ disparó un candidato causal (dentro de la
        ventana [origen, origen+margen], ver A6) sobre el origen real, y el
        motor lo perdió igual (suprimido por incoherencia local, o
        clasificado tráfico) — el modo de falla malo: el sistema vio algo y
        lo descartó mal.
    MISS_BELOW_FLOOR (A6): hubo un evento real pero NINGÚN candidato Tier0
        cae dentro de la ventana causal [origen, origen+margen] — no es que
        el motor haya visto algo y lo haya tirado, es que Tier0 nunca
        disparó nada ahí. Físicamente distinto de MISS_SUPPRESSED: es lo
        que la curva recall-vs-SNR predice para eventos bajo el piso de
        detección, no un bug de clasificación. Antes de A6 ambos casos
        caían indistintos en MISS_SUPPRESSED.
    FALSE_ALARM: SISMO_CONFIRMADO sin verdad-terreno que lo respalde.
    CORRECT_REJECTION: sin verdad-terreno y el motor correctamente no
        confirmó nada.
    """

    HIT = "HIT"
    HONEST_UNKNOWN = "HONEST_UNKNOWN"
    HONEST_REGIONAL = "HONEST_REGIONAL"
    MISS_SUPPRESSED = "MISS_SUPPRESSED"
    MISS_BELOW_FLOOR = "MISS_BELOW_FLOOR"
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
