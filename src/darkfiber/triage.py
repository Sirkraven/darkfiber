"""
DarkFiber MAS v5 — Nivel 0 del triaje jerárquico (Tier 0).

STA/LTA clásico (estándar sismológico) totalmente vectorizado con NumPy
sobre la matriz completa canales×tiempo. Es la compuerta que decide qué
fracción minúscula del stream merece inferencia ML y análisis de coherencia.

Diseño clave:
  * Medias móviles TRAILING exactas vía cumsum (no filtros centrados):
    el LTA solo mira el pasado, con un 'gap' para no contaminarse con
    el propio evento.
  * Devuelve el raster binario de disparos: la materia prima geométrica
    del CoherenceAgent (la pendiente en ese raster ES la física).
"""

from __future__ import annotations

import numpy as np

from .contracts import ArrayGeometry, Tier0Config, TriggerEvent


def _trailing_mean(p: np.ndarray, w: int) -> np.ndarray:
    """Media móvil de los últimos `w` muestras, exacta, por filas."""
    n = p.shape[-1]
    w = min(max(1, w), n)
    c = np.cumsum(p, axis=-1, dtype=np.float64)
    out = np.empty_like(c)
    out[..., :w] = c[..., :w] / np.arange(1, w + 1)
    if n > w:
        out[..., w:] = (c[..., w:] - c[..., :-w]) / w
    return out


def _sta_lta_ratio_block(data: np.ndarray, fs: float, cfg: Tier0Config) -> np.ndarray:
    """Cuerpo real de sta_lta_ratio, sobre UN bloque de canales. Ver esa
    función para la garantía de calentamiento y la nota sobre por qué
    bloquear por canal no cambia el resultado."""
    sta_n = max(1, int(cfg.sta_s * fs))
    lta_n = max(sta_n + 1, int(cfg.lta_s * fs))
    gap_n = int(cfg.gap_s * fs)

    # Inmunidad al overflow SIN pagar float64: el ratio STA/LTA es invariante
    # a la escala, así que normalizamos por el máximo absoluto (|d|≤1 ⇒ el
    # cuadrado float32 no puede desbordar) y elevamos al cuadrado in-place.
    # La exactitud del promedio la garantiza el cumsum en float64 de
    # _trailing_mean.
    m = float(np.abs(data).max())
    if m == 0.0 or not np.isfinite(m):
        return np.ones_like(data, dtype=np.float32)
    d = data * np.float32(1.0 / m)
    p = np.square(d, out=d)
    sta = _trailing_mean(p, sta_n)
    lta = _trailing_mean(p, lta_n)
    # LTA retardado: en t usamos el LTA que terminaba en t - sta_n - gap_n
    shift = sta_n + gap_n
    lta_delayed = np.empty_like(lta)
    lta_delayed[..., shift:] = lta[..., :-shift]
    lta_delayed[..., :shift] = lta[..., :1]
    ratio = sta / (lta_delayed + 1e-12)
    # Zona de calentamiento del LTA: sin disparos válidos
    warm = lta_n + shift
    ratio[..., :warm] = 1.0
    return ratio.astype(np.float32)


_BLOCK_MEMORY_BUDGET_BYTES = 256 * 1024 * 1024  # pico aprox. por array float64 intermedio


def sta_lta_ratio(
    data: np.ndarray, geom: ArrayGeometry, cfg: Tier0Config, channel_block: int | None = None
) -> np.ndarray:
    """Razón STA/LTA por canal y muestra. data: (n_ch, n_t) float32.

    GARANTÍA (probada en run_validation.py, escenario de calentamiento):
    para toda muestra t < cfg.warmup_s (en tiempo real, `lta_s+gap_s+sta_s`),
    ratio[..., t] == 1.0 exactamente, y como Tier0Config.threshold exige
    gt=1, ningún disparo puede originarse ahí — el LTA no tuvo tiempo de
    madurar y cualquier disparo sería una medición sin base de comparación
    real, no una detección. Encontrado en A2 (Monterey Bay): un archivo
    recortado que arranca casi en el evento de interés hace que la PRIMERA
    muestra visible después del calentamiento coincida con esa energía real
    — el buffer corto no le da al Tier0 la posibilidad de ver antes, no es
    un artefacto numérico de la ventana. Downstream (run_on_quakeflow,
    scoreboard) debe tratar con sospecha cualquier evento cuyo t_start_s
    caiga muy cerca de warmup_s (ver check de anomalía de dt_detect_s
    repetido en write_scoreboard).

    `channel_block`: procesa los canales de a bloques de este tamaño en vez
    de la matriz completa de una sola pasada. El Tier0 es matemáticamente
    independiente por canal (`_trailing_mean` no mezcla filas, y la
    normalización por máximo absoluto es invariante de escala dentro de
    cada canal) — bloquear no es una aproximación, da el mismo resultado
    (hasta redondeo de punto flotante) con un pico de memoria muchísimo
    menor. Default None: se calcula automáticamente para que el cumsum
    float64 de cada bloque no supere ~256 MB. Encontrado en A2: Arcata
    (7,550 canales) agotaba la RAM de esta máquina procesando todo de una
    vez (¡861 MiB de un solo array intermedio, y hay varios vivos a la vez!).
    """
    n_ch, n_t = data.shape
    if channel_block is None:
        channel_block = max(1, min(n_ch, int(_BLOCK_MEMORY_BUDGET_BYTES / max(1, n_t * 8))))
    if channel_block >= n_ch:
        return _sta_lta_ratio_block(data, geom.fs_hz, cfg)

    out = np.empty((n_ch, n_t), dtype=np.float32)
    for c0 in range(0, n_ch, channel_block):
        c1 = min(n_ch, c0 + channel_block)
        out[c0:c1] = _sta_lta_ratio_block(data[c0:c1], geom.fs_hz, cfg)
    return out


def trigger_raster(ratio: np.ndarray, cfg: Tier0Config) -> np.ndarray:
    """Raster binario canales×tiempo (True = canal disparado)."""
    return ratio > cfg.threshold


def _merge_runs(mask: np.ndarray, merge_n: int) -> list[tuple[int, int]]:
    """Funde en segmentos los tramos contiguos True de `mask`, fusionando
    huecos False de hasta `merge_n` muestras.

    `k - prev` es la DISTANCIA entre índices consecutivos activos; el hueco
    real de muestras False entre ellos es `k - prev - 1` (dos muestras
    inmediatamente adyacentes, k - prev == 1, tienen hueco CERO). Con
    merge_n=0 (pasada dispersa) esto importa: `k - prev > 0` partía en
    átomos de una sola muestra una racha perfectamente contigua.
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    segs = []
    start = idx[0]
    prev = idx[0]
    for k in idx[1:]:
        if k - prev - 1 > merge_n:
            segs.append((start, prev))
            start = k
        prev = k
    segs.append((start, prev))
    return segs


def _density_resegment(
    raster: np.ndarray, a: int, b: int, merge_n: int, dense_min: int
) -> list[tuple[int, int]]:
    """Re-segmenta temporalmente un bloque [a,b] YA fusionado que resultó
    demasiado largo (A5), buscando dentro de él tramos de alta densidad de
    coincidencia (`n_canales_disparados(t) >= dense_min`) separados por
    tramos de baja densidad. Es el análogo TEMPORAL de split_gap_channels:
    éste corta por huecos en el eje ESPACIAL dentro de una ventana fija de
    tiempo; ésta corta por huecos en la densidad de coincidencia dentro de
    un bloque ya fusionado en el eje temporal.

    Devuelve los límites de CADA tramo denso encontrado, aunque sea uno
    solo -- un bloque de 45 s con un único sismo de 3 s en un extremo y
    chatter ambiental disperso llenando el resto SIGUE siendo "un solo
    tramo denso" (nada que partir en dos), pero ese tramo denso es angosto:
    hay que recortar el bloque a sus límites, no devolver el bloque entero
    sin tocar (encontrado al validar el escenario F: devolver (a,b) sin
    cambios cuando `len(dense_segs) == 1` dejaba pasar intacto un bloque
    entero de 44.9 s en vez de recortarlo a los ~3 s reales del sismo).
    Solo si NO hay ningún tramo denso (caso límite: el bloque entero es
    disperso pese a superar max_merged_block_s) se devuelve (a, b) sin
    cambios, como red de seguridad."""
    sub = raster[:, a : b + 1]
    n_active = sub.sum(axis=0)
    dense = n_active >= dense_min
    dense_segs = _merge_runs(dense, merge_n)
    if not dense_segs:
        return [(a, b)]
    return [(a + lo, a + hi) for lo, hi in dense_segs]


def extract_segments(raster: np.ndarray, cfg: Tier0Config, fs: float) -> list[tuple[int, int]]:
    """La lista de segmentos (post re-segmentación por densidad, A5),
    ordenada por inicio, que `extract_events` convierte en eventos --
    factorizada aparte para que `StreamRunner` (C3) pueda calcular cuántos
    segmentos hay antes de un punto de corte de eviction propuesto, sin
    duplicar esta lógica. `n` en `evt_{n:04d}_...` (`extract_events`) es
    exactamente la posición 0-indexada de un segmento en esta lista."""
    n_ch = raster.shape[0]
    any_ch: np.ndarray = np.asarray(raster.any(axis=0))
    if not any_ch.any():
        return []
    merge_n = int(cfg.merge_gap_s * fs)
    raw_segs = _merge_runs(any_ch, merge_n)
    max_block_n = int(cfg.max_merged_block_s * fs)
    dense_min = max(cfg.dense_min_channels_floor, int(round(cfg.dense_coincidence_frac * n_ch)))
    segs: list[tuple[int, int]] = []
    for a, b in raw_segs:
        if (b - a + 1) > max_block_n:
            segs.extend(_density_resegment(raster, a, b, merge_n, dense_min))
        else:
            segs.append((a, b))
    segs.sort()
    return segs


def extract_events(
    raster: np.ndarray,
    ratio: np.ndarray,
    geom: ArrayGeometry,
    cfg: Tier0Config,
    *,
    seg_numbers: list[int] | None = None,
    sample_offset: int = 0,
) -> list[TriggerEvent]:
    """Agrupa el raster en eventos temporales contiguos (fusiona huecos cortos).

    `seg_numbers`/`sample_offset` (default `None`/0, sin efecto sobre
    ningún llamador existente -- batch incluido): permiten que un
    llamador que solo ve una VENTANA de `raster` (no el archivo completo,
    p. ej. `StreamRunner` con eviction real, C3) reconstruya los mismos
    `event_id`/`t_start_s`/`t_end_s` ABSOLUTOS que produciría el batch
    sobre el archivo completo. `sample_offset` es el índice de muestra
    ABSOLUTO del primer sample de `raster` (0 si `raster` ya es el
    archivo completo, como en batch). `seg_numbers`, si se da, reemplaza
    la posición 0-indexada por defecto (`enumerate(segs)`) por un `n`
    explícito por segmento, en el mismo orden que `extract_segments`
    devuelve -- necesario porque, con eviction real, la posición LOCAL de
    un segmento en la lista de ESTA ventana puede no ser estable pasada a
    pasada (un segmento vecino puede dejar de ser detectable si cae en la
    zona de calentamiento de Tier0 cerca del borde de la ventana, sin que
    el segmento en sí haya cambiado) -- `StreamRunner` mantiene la
    numeración `n` real de forma persistente por posición ABSOLUTA de
    inicio, no re-derivada de la posición local en cada pasada (bug real,
    encontrado corriendo el test de stream largo con eviction: el mismo
    segmento terminaba con `event_id` distinto entre pasadas). Con ambos
    en su default, el comportamiento es idéntico al de antes de que
    existieran estos parámetros.

    A5: un bloque fusionado que excede `max_merged_block_s` se re-examina
    con una compuerta de DENSIDAD de coincidencia (ver `_density_resegment`)
    y se recorta a los límites de cada ráfaga densa que encuentra adentro
    (una o varias -- incluso una sola ráfaga corta al principio de un
    bloque largo se recorta a su propio tamaño, descartando el resto como
    chatter disperso). Bloques de duración normal (la enorme mayoría -- un
    sismo
    local real, con su fase P débil y su fase S fuerte, dura segundos, no
    decenas de segundos) NUNCA tocan esta lógica y se comportan exactamente
    como antes: se preserva por ejemplo que una fase P débil pero real siga
    fusionándose con la S fuerte que la sigue (la coincidencia espacial de
    la S llena los huecos de canal de la P dispersa; partir por densidad
    ANTES de esa unión fragmenta la P en grupos sin sentido -- encontrado
    al validar este fix contra el escenario A). El síntoma real que motivó
    esto (Ridgecrest, 12 archivos reales, ver CHANGELOG A5): con cientos o
    miles de canales, "algún canal disparado" (`raster.any(axis=0)`) casi
    nunca tiene un hueco de verdad -- ruido ambiental disperso alcanza para
    que siempre haya ALGÚN canal por encima del umbral en algún instante, y
    merge_gap_s nunca encuentra un hueco que fusionar: el archivo entero
    (menos calentamiento) queda como un solo "evento" de decenas a > cien
    segundos, mezclando cualquier sismo real con ruido de fondo ajeno.
    """
    fs = geom.fs_hz
    min_n = int(cfg.min_event_duration_s * fs)
    segs = extract_segments(raster, cfg, fs)
    if not segs:
        return []
    if seg_numbers is None:
        seg_numbers = list(range(len(segs)))
    elif len(seg_numbers) != len(segs):
        raise ValueError(
            f"seg_numbers debe tener un elemento por segmento: {len(seg_numbers)} vs {len(segs)}"
        )

    events: list[TriggerEvent] = []
    for n, (a, b) in zip(seg_numbers, segs, strict=True):
        if (b - a + 1) < min_n:
            continue
        sub = raster[:, a : b + 1]
        chans = np.flatnonzero(sub.any(axis=1))
        # --- Separación espacial: dos fuentes simultáneas en zonas -------
        # disjuntas de la fibra no son un solo evento. Cortamos donde el
        # hueco entre canales disparados supera split_gap_channels.
        if cfg.split_gap_channels > 0 and chans.size > 1:
            cut = np.flatnonzero(np.diff(chans) > cfg.split_gap_channels)
            groups = np.split(chans, cut + 1)
        else:
            groups = [chans]
        for g_i, grp in enumerate(groups):
            gsub = sub[grp, :]
            t_any = gsub.any(axis=0)
            t_loc = np.flatnonzero(t_any)
            ga, gb = a + int(t_loc[0]), a + int(t_loc[-1])
            if (gb - ga + 1) < min_n:
                continue
            suffix = f"_{g_i}" if len(groups) > 1 else ""
            events.append(
                TriggerEvent(
                    event_id=f"evt_{n:04d}_{a + sample_offset}{suffix}",
                    t_start_s=(ga + sample_offset) / fs,
                    t_end_s=(gb + sample_offset + 1) / fs,
                    ch_min=int(grp.min()),
                    ch_max=int(grp.max()),
                    n_triggered_channels=int(grp.size),
                    peak_ratio=float(ratio[grp, ga : gb + 1].max()),
                )
            )
    return events


def reduction_stats(raster: np.ndarray) -> dict:
    """Métricas de reducción de datos del Nivel 0."""
    cells = raster.size
    flagged = int(raster.sum())
    t_any = raster.any(axis=0)
    return {
        "cell_flag_fraction": flagged / cells,
        "time_flag_fraction": float(t_any.mean()),
        "silence_filtered_fraction": 1.0 - float(t_any.mean()),
    }
