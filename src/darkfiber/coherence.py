"""
DarkFiber MAS v5 — Motor de Coherencia Física (CoherenceAgent).

Tesis central de v5: en el plano canal-tiempo, LA PENDIENTE DE UN EVENTO ES
SU FÍSICA.
  * Sismo real  -> frente de onda que cruza cientos de canales a km/s
                   (moveout casi vertical + disparo masivo cuasi-simultáneo).
  * Vehículo    -> mancha localizada que se desplaza a ~2-40 m/s
                   (franja diagonal lenta).
  * Falso positivo por canal -> energía sin coherencia espacial
                   (1-3 canales aislados). Se suprime.

Tres mediciones independientes, todas físicas y auditables:
  1. coincidence_fraction : fracción de canales disparados dentro de una
     ventana corta. Robusta a la geometría real de la fibra (lazos, curvas):
     un sismo golpea TODO el arreglo casi a la vez, sin importar el trazado.
  2. slant-stack + semblanza : escaneo de velocidades aparentes; el pico de
     semblanza entrega v_app (magnitud y dirección). Sobre fibra con trazado
     no rectilíneo conviene medirlo en el sub-tramo más lineal (configurable).
  3. regresión de trayectoria : ajuste lineal del centroide de energía
     (canal vs tiempo) para fuentes móviles lentas -> velocidad del vehículo
     y sentido de circulación.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import hilbert
from scipy.stats import theilslopes

from .contracts import (
    ArrayGeometry,
    CoherenceConfig,
    CoherenceResult,
    EventClass,
    PhaseArrivals,
    TriggerEvent,
)

# ---------------------------------------------------------------------------
# Núcleo: slant-stack con semblanza
# ---------------------------------------------------------------------------


def v_app_max_resoluble(aperture_m: float, fs_hz: float, k: int = 3) -> float:
    """Límite geométrico: la apertura solo resuelve un v_app si el retardo

    total a lo largo del arreglo cruza al menos `k` muestras (k=3 por
    defecto). Con menos, el corrimiento entre canal 0 y N es sub-muestra y
    el slant-stack no puede distinguir esa velocidad de "infinita" (moveout
    plano). Reutilizado por P0 (rama REGIONAL_EMERGENT) y por
    `characterize_aperture.py` (P1) para el barrido de geometría.
    """
    return aperture_m * fs_hz / k


def slowness_grid(cfg: CoherenceConfig) -> np.ndarray:
    """Lentitudes (s/m) en ambas direcciones para la banda sísmica."""
    v = np.geomspace(cfg.seismic_v_min_mps, cfg.seismic_v_max_mps, cfg.n_velocity_steps)
    p = 1.0 / v
    return np.concatenate([-p[::-1], p])


def _velocity_peak_is_boundary(sem: np.ndarray, k: int, n_velocity_steps: int) -> bool:
    """A9: True si el argmax de semblanza (índice `k`) NO es un pico
    interior genuino dentro de su propia RAMA de dirección.

    `slowness_grid` concatena dos rangos [-p_max..-p_min, p_min..p_max]
    (dirección negativa: índices [0, n_velocity_steps-1]; positiva:
    [n_velocity_steps, 2*n_velocity_steps-1]). Las dos ramas son
    DISCONTINUAS entre sí en velocidad física -- saltan el hueco alrededor
    de v≈±∞ (p≈0) -- así que un pico en el extremo de SU rama es un
    límite real de la búsqueda, aunque el índice matemáticamente
    "vecino" exista en el array (pertenece a la otra dirección, no es
    comparable físicamente).

    Encontrado en A8/A9 sobre el M5.8 real de Ridgecrest: la semblanza
    subía monótonamente de 0.296 (en -8000 m/s) a 0.503 exactamente en
    -1500 m/s = seismic_v_min_mps, el borde de la rama negativa, sin
    ningún pico interior -- el clasificador lo leyó como "velocidad
    medida 1500 m/s" cuando en realidad el óptimo real está fuera del
    rango barrido (moveout aún más lento, esencialmente instantáneo:
    consistente con un arribo regional/emergente, no con un sismo local
    de moveout resoluble).

    También cuenta como no resuelto un pico interior que no es
    ESTRICTAMENTE mayor que ambos vecinos (empate/meseta): el argmax
    garantiza `sem[k] >= vecinos`, así que la única forma de fallar la
    igualdad estricta es una meseta, que tampoco es una medición
    resuelta.
    """
    if k < n_velocity_steps:
        branch_lo, branch_hi = 0, n_velocity_steps - 1
    else:
        branch_lo, branch_hi = n_velocity_steps, 2 * n_velocity_steps - 1
    if k in (branch_lo, branch_hi):
        return True
    return not (sem[k] > sem[k - 1] and sem[k] > sem[k + 1])


def slant_stack_semblance(
    window: np.ndarray,
    x_m: np.ndarray,
    fs: float,
    slownesses: np.ndarray,
    margin: int,
    use_envelope: bool = True,
):
    """Semblanza S(p) = Σ_t (Σ_ch g)² / (N Σ_t Σ_ch g²) para cada lentitud p.

    `window` debe venir con `margin` muestras extra a cada lado para que los
    corrimientos no introduzcan coherencia artificial en los bordes; la
    semblanza se evalúa solo sobre la región central válida.

    Devuelve (semblanzas, beams_central) donde beams_central[k] es el beam
    apilado tras alinear con la lentitud k (útil para picking de fases).
    """
    if use_envelope:
        sig = np.abs(hilbert(window, axis=1)).astype(np.float32)
    else:
        sig = window.astype(np.float32)

    n_ch, n_t = sig.shape
    core = slice(margin, n_t - margin)
    n_core = n_t - 2 * margin
    t_idx = np.arange(margin, n_t - margin)

    # Semblanza sobre señal de MEDIA CERO: la envolvente es siempre positiva
    # y su componente DC apila coherentemente para CUALQUIER lentitud,
    # regalando un piso de ~0.6 que vuelve decorativo cualquier umbral.
    # Removida la media, el piso incoherente cae a ~1/n_ch y el umbral
    # seismic_min_semblance vuelve a significar algo físico.
    sig = sig - sig[:, core].mean(axis=1, keepdims=True)

    sem = np.empty(len(slownesses), dtype=np.float64)
    beams = np.empty((len(slownesses), n_core), dtype=np.float32)
    for k, p in enumerate(slownesses):
        shifts = np.rint(p * x_m * fs).astype(np.int64)
        idx = t_idx[None, :] + shifts[:, None]
        np.clip(idx, 0, n_t - 1, out=idx)
        g = np.take_along_axis(sig, idx, axis=1)
        s = g.sum(axis=0)
        num = float((s * s).sum())
        den = n_ch * float((g * g).sum()) + 1e-20
        sem[k] = num / den
        beams[k] = s / n_ch
    return sem, beams


def coherent_channel_count(
    window: np.ndarray,
    x_m: np.ndarray,
    fs: float,
    p_best: float,
    margin: int,
    corr_min: float,
    use_envelope: bool = True,
) -> int:
    """Cuenta canales cuya traza alineada correlaciona con el beam."""
    sig = np.abs(hilbert(window, axis=1)).astype(np.float32) if use_envelope else window
    n_ch, n_t = sig.shape
    t_idx = np.arange(margin, n_t - margin)
    shifts = np.rint(p_best * x_m * fs).astype(np.int64)
    idx = t_idx[None, :] + shifts[:, None]
    np.clip(idx, 0, n_t - 1, out=idx)
    g = np.take_along_axis(sig, idx, axis=1)
    g = g - g.mean(axis=1, keepdims=True)
    beam = g.mean(axis=0)
    bn = np.linalg.norm(beam) + 1e-12
    gn = np.linalg.norm(g, axis=1) + 1e-12
    corr = (g @ beam) / (gn * bn)
    return int((corr > corr_min).sum())


# ---------------------------------------------------------------------------
# Coincidencia masiva (independiente de la geometría de la fibra)
# ---------------------------------------------------------------------------


def coincidence_fraction(
    raster: np.ndarray, evt: TriggerEvent, geom: ArrayGeometry, cfg: CoherenceConfig
) -> float:
    """Máxima fracción de canales disparados dentro de una ventana corta."""
    fs = geom.fs_hz
    a, b = int(evt.t_start_s * fs), int(evt.t_end_s * fs)
    sub = raster[:, a:b]
    if sub.size == 0:
        return 0.0
    w = max(1, int(cfg.coincidence_window_s * fs))
    first = np.where(sub.any(axis=1), sub.argmax(axis=1), -1)
    fired = first[first >= 0]
    if fired.size == 0:
        return 0.0
    fired.sort()
    best = 0
    j = 0
    for i in range(fired.size):
        while fired[i] - fired[j] > w:
            j += 1
        best = max(best, i - j + 1)
    # Normalizamos por los canales DISPARADOS, no por el arreglo entero:
    # un sismo débil dispara menos canales (eso es SNR, y lo vigila
    # span_frac), pero los que dispara lo hacen casi a la vez — esa
    # simultaneidad es la física que esta métrica debe medir.
    # Piso explícito: con menos del 5% del arreglo disparado no hay
    # evidencia de "disparo masivo", por muy juntos que caigan.
    min_fired = max(10, int(0.05 * geom.n_channels))
    return best / max(fired.size, min_fired)


# ---------------------------------------------------------------------------
# Regresión de trayectoria (fuentes móviles lentas)
# ---------------------------------------------------------------------------


def track_speed(ratio: np.ndarray, evt: TriggerEvent, geom: ArrayGeometry, threshold: float):
    """Ajusta canal_centroide(t) = m·t + b sobre el evento.

    Devuelve (velocidad_mps_con_signo, r2, duracion_s) o (None, 0, 0).
    """
    fs = geom.fs_hz
    a, b = int(evt.t_start_s * fs), int(evt.t_end_s * fs)
    # Restringimos a los canales del evento (+margen): con los 626 canales el
    # ruido residual de ~600 canales silenciosos arrastra el centroide y el
    # ajuste lineal pierde sentido (R² ~0.1 en la validación previa).
    margin = 5
    c0 = max(0, evt.ch_min - margin)
    c1 = min(ratio.shape[0], evt.ch_max + 1 + margin)
    sub = np.maximum(ratio[c0:c1, a:b] - threshold, 0.0)
    energy_t = sub.sum(axis=0)
    valid = energy_t > 0
    if valid.sum() < 5:
        return None, 0.0, 0.0
    ch_idx = np.arange(c0, c1, dtype=np.float64)
    cent = (ch_idx[:, None] * sub[:, valid]).sum(axis=0) / energy_t[valid]
    t = np.flatnonzero(valid) / fs
    w = energy_t[valid]
    m, c = np.polyfit(t, cent, 1, w=w)
    pred = m * t + c
    ss_res = float((w * (cent - pred) ** 2).sum())
    mu = float((w * cent).sum() / w.sum())
    ss_tot = float((w * (cent - mu) ** 2).sum()) + 1e-12
    r2 = max(0.0, 1.0 - ss_res / ss_tot)
    speed = m * geom.channel_spacing_m  # m/s con signo (sentido de circulación)
    duration = float(t[-1] - t[0])
    return float(speed), float(r2), duration


# ---------------------------------------------------------------------------
# Fallback de moveout por onsets (llegadas emergentes: la semblanza de forma
# de onda muere cuando el frente no es coherente muestra a muestra, pero el
# tiempo de PRIMER cruce STA/LTA por canal todavía traza el moveout grueso).
# ---------------------------------------------------------------------------


def fit_onset_velocity(
    ratio: np.ndarray,
    evt: TriggerEvent,
    geom: ArrayGeometry,
    cfg: CoherenceConfig,
    thr: float,
):
    """Ajusta t_onset(canal) = x/v + t0 con Theil-Sen (mediana repetida de
    pendientes por pares), robusto a onsets espurios canal a canal.

    Devuelve (v_app_onset_mps, r2) o (None, None) si no hay evidencia
    suficiente (menos de `cfg.onset_fit_min_channels` canales con cruce).
    """
    fs, dx = geom.fs_hz, geom.channel_spacing_m
    a, b = int(evt.t_start_s * fs), int(evt.t_end_s * fs)
    ch0, ch1 = evt.ch_min, evt.ch_max
    sub = ratio[ch0 : ch1 + 1, a:b]
    if sub.shape[1] == 0:
        return None, None

    fired = sub > thr
    has_onset = fired.any(axis=1)
    if has_onset.sum() < cfg.onset_fit_min_channels:
        return None, None

    onset_idx = np.argmax(fired, axis=1).astype(np.float64)
    xs = np.arange(sub.shape[0], dtype=np.float64)[has_onset] * dx
    ts = onset_idx[has_onset] / fs

    slope, intercept, _, _ = theilslopes(ts, xs)
    pred = slope * xs + intercept
    ss_res = float(((ts - pred) ** 2).sum())
    ss_tot = float(((ts - ts.mean()) ** 2).sum()) + 1e-12
    r2 = max(0.0, 1.0 - ss_res / ss_tot)

    if abs(slope) < 1e-9:
        return float("inf"), float(r2)
    return float(1.0 / slope), float(r2)


# ---------------------------------------------------------------------------
# Picking de fases P/S sobre el beam apilado
# ---------------------------------------------------------------------------


def pick_phases_on_beam(beam: np.ndarray, fs: float, thr: float = 3.5) -> PhaseArrivals:
    """Picking P/S sobre el beam apilado, anclado en picos.

    El apilado coherente multiplica el SNR ~√N y vuelve visible la P débil.
    Estrategia (robusta a los dos modos de fallo observados en validación):

    1. La envolvente apilada tiene un pedestal DC (ruido promediado que nunca
       baja a cero): se resta la mediana y se recorta a ≥0.
    2. En zonas silenciosas, cociente diminuto/diminuto dispara STA/LTA de
       forma espuria → el denominador se regulariza con un piso de ruido
       robusto (percentil 75 del beam²).
    3. La S se ancla en el MÁXIMO global de energía (fase dominante) y su
       onset se obtiene caminando hacia atrás hasta el 5% del pico — esto
       elimina el sesgo de rampa de wavelets anchas.
    4. La P se busca ANTES de la S con el ratio regularizado (detector de
       transitorios); su onset también por walk-back al 10% de su pico local.
    """
    from .triage import _trailing_mean

    b = beam.astype(np.float64)
    b -= np.median(b)
    np.clip(b, 0.0, None, out=b)
    p = b**2
    n = p.size
    if n < int(6 * fs):
        return PhaseArrivals()

    floor = float(np.percentile(p, 75)) + 1e-12

    w_sm = max(1, int(0.2 * fs))
    sm = np.convolve(p, np.ones(w_sm) / w_sm, mode="same")

    valid_from = int(4.0 * fs)  # estadísticas del beam pobladas
    if n <= valid_from + int(1.0 * fs):
        return PhaseArrivals()

    # --- S: máximo global de energía --------------------------------------
    i_peak = valid_from + int(np.argmax(sm[valid_from:]))
    peak = float(sm[i_peak])
    if peak < 8.0 * floor:  # ni la fase dominante sobresale del piso
        return PhaseArrivals()
    j = i_peak
    lim = max(valid_from, i_peak - int(6.0 * fs))
    while j > lim and sm[j] > 0.05 * peak:
        j -= 1
    s_onset = j

    # --- P: transitorio previo a la S con ratio regularizado --------------
    sta = _trailing_mean(p[None, :], max(1, int(0.2 * fs)))[0]
    lta = _trailing_mean(p[None, :], max(2, int(3.0 * fs)))[0]
    shift = int(0.4 * fs)
    lta_d = np.empty_like(lta)
    lta_d[shift:] = lta[:-shift]
    lta_d[:shift] = lta[0]
    r = sta / (lta_d + 0.5 * floor)

    p_onset = None
    p_end = s_onset - int(0.6 * fs)
    if p_end - valid_from > int(0.5 * fs):
        seg = r[valid_from:p_end]
        i2 = valid_from + int(np.argmax(seg))
        if float(r[i2]) > thr:
            pk2 = float(sm[valid_from:p_end].max()) + 1e-12
            j = i2
            lim2 = max(valid_from, i2 - int(6.0 * fs))
            while j > lim2 and sm[j] > 0.10 * pk2:
                j -= 1
            p_onset = j

    if p_onset is None:
        return PhaseArrivals(t_p_s=s_onset / fs)  # una sola llegada detectable
    return PhaseArrivals(t_p_s=p_onset / fs, t_s_s=s_onset / fs)


# ---------------------------------------------------------------------------
# El agente
# ---------------------------------------------------------------------------


class CoherenceAgent:
    """Nivel 2 del triaje: veredicto físico sobre cada TriggerEvent.

    Uso: `await asyncio.to_thread(agent.analyze, data, ratio, raster, evt)`
    para no bloquear el event loop (regla del proyecto).
    """

    def __init__(
        self,
        geom: ArrayGeometry,
        cfg: CoherenceConfig | None = None,
        tier0_threshold: float = 4.0,
    ):
        self.geom = geom
        self.cfg = cfg or CoherenceConfig()
        # Mismo umbral que disparó el Nivel 0: el rastreo de fuentes móviles
        # debe mirar la misma evidencia que generó el evento, no ruido sub-umbral.
        self.tier0_thr = tier0_threshold
        self._p_grid = slowness_grid(self.cfg)

    # ---- utilidades internas -------------------------------------------
    def _extract_window(self, data: np.ndarray, evt: TriggerEvent):
        fs = self.geom.fs_hz
        dx = self.geom.channel_spacing_m
        ch0, ch1 = evt.ch_min, evt.ch_max
        x = (np.arange(ch0, ch1 + 1) - ch0) * dx
        p_max = float(np.abs(self._p_grid).max())
        margin = int(np.ceil(p_max * x.max() * fs)) + int(1.0 * fs)
        a = max(0, int(evt.t_start_s * fs) - margin)
        b = min(data.shape[1], int(evt.t_end_s * fs) + margin)
        win = data[ch0 : ch1 + 1, a:b]
        eff_margin = min(margin, (win.shape[1] - int(0.5 * fs)) // 2)
        return win, x, max(1, eff_margin), a

    def beamform_wide(self, data: np.ndarray, evt: TriggerEvent, p_best: float):
        """Beam apilado sobre una ventana extendida hacia atrás.

        Clave de la alerta temprana: la fase P suele ser demasiado débil para
        disparar canales individuales, pero el apilado coherente de cientos de
        canales multiplica el SNR ~√N y la vuelve visible en el beam.

        Devuelve (beam, t0_abs_s): beam y el tiempo absoluto de su muestra 0.
        """
        cfg, geom = self.cfg, self.geom
        fs, dx = geom.fs_hz, geom.channel_spacing_m
        ch0, ch1 = evt.ch_min, evt.ch_max
        x = (np.arange(ch0, ch1 + 1) - ch0) * dx
        max_shift = int(np.ceil(abs(p_best) * x.max() * fs)) + 1
        a = max(0, int((evt.t_start_s - cfg.pick_lookback_s) * fs) - max_shift)
        b = min(data.shape[1], int((evt.t_end_s + cfg.pick_lookahead_s) * fs) + max_shift)
        win = data[ch0 : ch1 + 1, a:b]
        env = np.abs(hilbert(win, axis=1)).astype(np.float32)
        n_t = env.shape[1]
        core0, core1 = max_shift, n_t - max_shift
        if core1 - core0 < int(2 * fs):
            core0, core1 = 0, n_t
        t_idx = np.arange(core0, core1)
        shifts = np.rint(p_best * x * fs).astype(np.int64)
        idx = t_idx[None, :] + shifts[:, None]
        np.clip(idx, 0, n_t - 1, out=idx)
        beam = np.take_along_axis(env, idx, axis=1).mean(axis=0)
        return beam, (a + core0) / fs

    # ---- API principal ---------------------------------------------------
    def analyze(
        self,
        data: np.ndarray,
        ratio: np.ndarray,
        raster: np.ndarray,
        evt: TriggerEvent,
        pick_phases: bool = True,
    ) -> CoherenceResult:
        """Veredicto físico sobre un TriggerEvent (el árbol de decisión central
        del proyecto). Orden de las ramas, en este orden estricto:

          1. Canales aislados (`n_triggered_channels <= max_isolated_channels`)
             -> supresión inmediata, sin coherencia espacial posible.
          2. Banda sísmica (semblanza + coincidencia + span + v_app en rango)
             -> SISMO_CONFIRMADO, con picking de fases P/S sobre el beam.
          3. Banda de tráfico (regresión de trayectoria del centroide)
             -> FUENTE_MOVIL_TRAFICO.
          4. Disparo masivo (`f_c`/`span_frac` altos) sin moveout resoluble
             -> POSIBLE_REGIONAL_EMERGENTE (nunca supresión: ver docs/adr/0002).
          5. Todo lo demás con evidencia débil y extensión chica -> supresión
             final; si no, COHERENTE_DESCONOCIDO al catálogo de firmas.

        Cada rama escribe su razonamiento en `explanations` (patrón RiskFactor):
        el veredicto es auditable sin releer el código.
        """
        cfg, geom = self.cfg, self.geom
        expl: list[str] = []

        span_frac = (evt.ch_max - evt.ch_min + 1) / geom.n_channels
        f_c = coincidence_fraction(raster, evt, geom, cfg)
        expl.append(
            f"Coincidencia: {f_c * 100:.1f}% de los canales disparados dentro de "
            f"{cfg.coincidence_window_s:.1f}s (extensión del evento: {span_frac * 100:.1f}% del arreglo)."
        )

        # --- Supresión inmediata de transitorios locales ------------------
        if evt.n_triggered_channels <= cfg.max_isolated_channels:
            expl.append(
                f"Solo {evt.n_triggered_channels} canal(es) disparado(s): sin coherencia "
                f"espacial. Un evento físico real no puede existir en un único punto de la fibra."
            )
            return CoherenceResult(
                event_id=evt.event_id,
                classification=EventClass.INCOHERENT_LOCAL,
                coincidence_fraction=f_c,
                span_fraction=span_frac,
                suppressed_false_positive=True,
                explanations=expl,
            )

        # Fallback de onsets: se calcula temprano y viaja en TODO resultado
        # posterior (incluido SISMO_CONFIRMADO) para poder validarlo contra
        # verdad-terreno donde el moveout por semblanza también existe.
        v_onset, r2_onset = fit_onset_velocity(ratio, evt, geom, cfg, self.tier0_thr)

        # --- Banda sísmica: slant-stack + semblanza ------------------------
        win, x, margin, _ = self._extract_window(data, evt)
        sem, beams = slant_stack_semblance(
            win, x, geom.fs_hz, self._p_grid, margin, cfg.use_envelope
        )
        k = int(np.argmax(sem))
        p_best = float(self._p_grid[k])
        v_best = 1.0 / p_best if p_best != 0 else float("inf")
        # Clamp: Cauchy-Schwarz garantiza ≤1 en exacto, el float no.
        s_best = float(min(1.0, max(0.0, sem[k])))
        n_coh = coherent_channel_count(
            win, x, geom.fs_hz, p_best, margin, cfg.coherent_channel_corr, cfg.use_envelope
        )
        direction = "canal 0 → N" if v_best > 0 else "canal N → 0"
        expl.append(
            f"Slant-stack: pico de semblanza {s_best:.3f} en v_app = {abs(v_best):,.0f} m/s "
            f"({direction}); {n_coh} canales coherentes con el beam."
        )

        # A9: guarda de solución de borde -- un argmax que no es un pico
        # interior estricto de su rama no es una velocidad RESUELTA, así
        # que no puede sostener SISMO_CONFIRMADO (ver
        # _velocity_peak_is_boundary). El evento sigue el árbol de
        # decisión existente con esta info sumada, no se descarta.
        boundary_pinned = _velocity_peak_is_boundary(sem, k, cfg.n_velocity_steps)
        if boundary_pinned:
            expl.append(
                "Máximo en borde de búsqueda: no-medición. El pico de semblanza no es "
                "interior a la grilla de velocidades -- el óptimo real puede estar fuera "
                "del rango barrido (moveout aún más lento/rápido, o esencialmente "
                "instantáneo). La velocidad aparente reportada NO sostiene SISMO_CONFIRMADO."
            )

        # A10, regla permanente: ninguna confirmación sísmica se sostiene en
        # un solo estimador de velocidad. v_onset (Theil-Sen sobre cruces
        # STA/LTA, independiente del slant-stack) tiene que CORROBORAR -- no
        # solo existir -- dentro de onset_agreement_tol_frac. Encontrado en
        # A9: el M5.8 real tenía v_onset=-10,282 m/s vs v_semblanza=-1,500
        # m/s (>200% de diferencia) -- la guarda de borde ya lo atrapaba,
        # pero la concordancia es una segunda capa independiente que no
        # depende de que el pico caiga exactamente en el borde de la grilla.
        #
        # NO se exige un R² mínimo del ajuste de onsets (a diferencia de un
        # primer intento en A10): Theil-Sen es un estimador ROBUSTO
        # (mediana repetida de pendientes por pares) específicamente porque
        # tolera picks ruidosos canal a canal sin que la PENDIENTE se rompa
        # -- un R² bajo mide dispersión alrededor de la recta, no si la
        # pendiente es confiable. Verificado sobre ruido real de Ridgecrest
        # (A10): inyecciones sintéticas con v_onset a 1% de v_semblanza (y
        # de la verdad-terreno) con R²=0.03 -- exigir R² alto ahí tiraba
        # abajo confirmaciones sanas por el motivo equivocado. El criterio
        # real es la CONCORDANCIA de velocidad, no la forma de la recta.
        onset_agrees = False
        if v_onset is not None and r2_onset is not None and v_best != 0:
            rel_diff = abs(v_onset - v_best) / ((abs(v_onset) + abs(v_best)) / 2.0)
            onset_agrees = rel_diff <= cfg.onset_agreement_tol_frac
            expl.append(
                f"Corroboración cruzada: v_app_onset (Theil-Sen) = {v_onset:,.0f} m/s "
                f"(R²={r2_onset:.2f}, informativo -- no se exige un piso: Theil-Sen es "
                f"robusto a picks ruidosos, un R² bajo no invalida la pendiente) vs "
                f"v_app_semblanza = {v_best:,.0f} m/s -- diferencia relativa {rel_diff * 100:.0f}% "
                f"({'CONCUERDA' if onset_agrees else 'DISCREPA'}, tolerancia "
                f"{cfg.onset_agreement_tol_frac * 100:.0f}%)."
            )
        else:
            expl.append(
                "Corroboración cruzada: sin ajuste de onsets disponible (menos de "
                f"{cfg.onset_fit_min_channels} canales con cruce STA/LTA) -- sin segundo "
                "estimador, no hay corroboración posible."
            )

        is_seismic = (
            f_c >= cfg.seismic_min_coincidence
            and span_frac >= cfg.seismic_min_span_frac
            and not boundary_pinned
            and s_best >= cfg.seismic_min_semblance
            and cfg.seismic_v_min_mps <= abs(v_best) <= cfg.seismic_v_max_mps
            and onset_agrees
        )
        if is_seismic:
            phases = None
            if pick_phases:
                beam, t0_abs = self.beamform_wide(data, evt, p_best)
                rel = pick_phases_on_beam(beam, geom.fs_hz)
                phases = PhaseArrivals(
                    t_p_s=None if rel.t_p_s is None else rel.t_p_s + t0_abs,
                    t_s_s=None if rel.t_s_s is None else rel.t_s_s + t0_abs,
                )
                if phases.ts_minus_tp_s is not None:
                    expl.append(
                        f"Fases sobre el beam: tS−tP = {phases.ts_minus_tp_s:.2f} s "
                        f"(la P llega antes: esos son los segundos de alerta temprana)."
                    )
            expl.append(
                "Veredicto: SISMO CONFIRMADO por física de propagación "
                f"(velocidad aparente en rango sísmico [{cfg.seismic_v_min_mps:,.0f}–"
                f"{cfg.seismic_v_max_mps:,.0f}] m/s + disparo masivo cuasi-simultáneo)."
            )
            return CoherenceResult(
                event_id=evt.event_id,
                classification=EventClass.SEISMIC_CONFIRMED,
                apparent_velocity_mps=v_best,
                semblance=s_best,
                coincidence_fraction=f_c,
                coherent_channels=n_coh,
                span_fraction=span_frac,
                phases=phases,
                v_app_onset_mps=v_onset,
                onset_fit_r2=r2_onset,
                boundary_pinned=boundary_pinned,
                explanations=expl,
            )

        # --- Banda de tráfico: regresión de trayectoria --------------------
        speed, r2, dur = track_speed(ratio, evt, geom, threshold=self.tier0_thr)
        if speed is not None:
            expl.append(
                f"Trayectoria del centroide: {abs(speed):.1f} m/s "
                f"({'km↑' if speed > 0 else 'km↓'}), R²={r2:.2f}, duración {dur:.1f}s."
            )
        if (
            speed is not None
            and cfg.traffic_v_min_mps <= abs(speed) <= cfg.traffic_v_max_mps
            and r2 >= cfg.traffic_min_r2
            and dur >= cfg.traffic_min_duration_s
        ):
            expl.append(
                "Veredicto: FUENTE MÓVIL (tráfico). Velocidad en rango vehicular y "
                "trayectoria lineal sostenida a lo largo de la fibra."
            )
            return CoherenceResult(
                event_id=evt.event_id,
                classification=EventClass.TRAFFIC,
                apparent_velocity_mps=v_best,
                coincidence_fraction=f_c,
                span_fraction=span_frac,
                semblance=s_best,
                coherent_channels=n_coh,
                track_speed_mps=speed,
                track_r2=r2,
                v_app_onset_mps=v_onset,
                onset_fit_r2=r2_onset,
                boundary_pinned=boundary_pinned,
                explanations=expl,
            )

        # --- Regional/lejano emergente: disparo masivo sin moveout resoluble
        # por semblanza. f_c o span_frac altos son, por sí solos, evidencia de
        # extensión espacial real: la supresión de falso positivo local queda
        # prohibida acá por construcción (nunca se llega a ese branch abajo).
        if f_c >= cfg.regional_min_coincidence and span_frac >= cfg.regional_min_span_frac:
            aperture_km = geom.aperture_m / 1000.0
            v_max_geo = v_app_max_resoluble(geom.aperture_m, geom.fs_hz)
            expl.append(
                f"Disparo masivo ({f_c * 100:.1f}% de los canales disparados, "
                f"{span_frac * 100:.1f}% del arreglo) sin moveout resoluble por semblanza "
                f"(pico {s_best:.3f} < umbral {cfg.seismic_min_semblance:.2f}): consistente "
                f"con evento regional/lejano cuya llegada emergente excede la resolución "
                f"de esta apertura (L={aperture_km:.2f} km, v_app_max_geométrico≈"
                f"{v_max_geo:,.0f} m/s con k=3 muestras). Escalar para verificación "
                f"externa (USGS/red regional)."
            )
            # Nota física adicional además de la corroboración cruzada ya
            # citada arriba (siempre): pendiente ≈0 tiene una lectura propia
            # (moveout plano) que la línea genérica de corroboración no dice.
            if v_onset is not None and abs(v_onset) > 20_000:
                expl.append(
                    f"Pendiente de onsets ≈0 (v_app_onset={v_onset:,.0f} m/s) — moveout "
                    f"plano: incidencia casi vertical u origen fuera de la resolución de "
                    f"esta apertura."
                )
            return CoherenceResult(
                event_id=evt.event_id,
                classification=EventClass.REGIONAL_EMERGENT,
                apparent_velocity_mps=v_best,
                semblance=s_best,
                coincidence_fraction=f_c,
                coherent_channels=n_coh,
                span_fraction=span_frac,
                track_speed_mps=speed,
                track_r2=r2,
                v_app_onset_mps=v_onset,
                onset_fit_r2=r2_onset,
                suppressed_false_positive=False,
                boundary_pinned=boundary_pinned,
                explanations=expl,
            )

        # --- Ni sismo, ni vehículo, ni regional: transitorio local ---------
        # f_c y span_frac ya están garantizados bajos acá (la rama regional de
        # arriba capturó el caso alto y retornó antes); se deja la condición
        # explícita para que la regla quede legible sin depender del orden.
        if (
            n_coh <= cfg.max_isolated_channels
            and s_best < cfg.seismic_min_semblance
            and f_c < cfg.regional_min_coincidence
            and span_frac < cfg.regional_min_span_frac
        ):
            expl.append(
                "Veredicto: energía sin estructura espacial coherente. Suprimido como "
                "falso positivo local."
            )
            return CoherenceResult(
                event_id=evt.event_id,
                classification=EventClass.INCOHERENT_LOCAL,
                coincidence_fraction=f_c,
                span_fraction=span_frac,
                semblance=s_best,
                coherent_channels=n_coh,
                v_app_onset_mps=v_onset,
                onset_fit_r2=r2_onset,
                suppressed_false_positive=True,
                boundary_pinned=boundary_pinned,
                explanations=expl,
            )

        expl.append(
            "Veredicto: coherente pero fuera de las bandas físicas conocidas. "
            "Se envía al catálogo de firmas para identificación."
        )
        return CoherenceResult(
            event_id=evt.event_id,
            classification=EventClass.UNKNOWN_COHERENT,
            apparent_velocity_mps=v_best,
            semblance=s_best,
            coincidence_fraction=f_c,
            coherent_channels=n_coh,
            span_fraction=span_frac,
            track_speed_mps=speed,
            track_r2=r2,
            v_app_onset_mps=v_onset,
            onset_fit_r2=r2_onset,
            boundary_pinned=boundary_pinned,
            explanations=expl,
        )
