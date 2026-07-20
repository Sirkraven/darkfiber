"""
DarkFiber MAS v5 — Validación de punta a punta (números medidos, no prometidos).

Genera tres escenarios sintéticos FÍSICAMENTE correctos sobre la geometría del
arreglo de Stanford (626 canales, 8 m, 50 Hz) y verifica que el pipeline
Tier0 → Coherencia mida y clasifique lo que la física dicta:

  A) Sismo: fase P débil (v_app 5500 m/s) + fase S fuerte (3000 m/s, +3.4 s)
  B) Vehículo a 12 m/s recorriendo la fibra
  C) Ruido + transitorio fuerte en UN solo canal (el falso positivo de v4)

Además: benchmark de throughput del Tier 0, demo del catálogo vivo y una
ronda de auto-verificación por inyección sintética.

Uso:  python run_validation.py [--figs]
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, EventClass, Tier0Config
from .selftest import inject_and_verify, recall_gauge
from .synth import (
    add_emergent_regional,
    add_local_spike,
    add_moving_source,
    add_plane_wave,
    make_noise,
    ricker,
)
from .triage import extract_events, reduction_stats, sta_lta_ratio, trigger_raster

GEOM = ArrayGeometry(n_channels=626, channel_spacing_m=8.0, fs_hz=50.0)
T0 = Tier0Config()
COH = CoherenceConfig()

DUR_S = 60.0
N_T = int(DUR_S * GEOM.fs_hz)

# Verdad-terreno del escenario sísmico
V_P, V_S = 5500.0, 3000.0
T0_P, T0_S = 25.0, 28.4  # origen de cada fase en canal 0
AMP_P, AMP_S = 3.0, 8.0
# tS-tP verdadero varía a lo largo de la fibra por el moveout diferencial:
TRUE_TS_TP_MIN = T0_S - T0_P  # en x = 0
TRUE_TS_TP_MAX = TRUE_TS_TP_MIN + GEOM.aperture_m * (1 / V_S - 1 / V_P)

VEH_SPEED = 12.0  # m/s
SPIKE_CH = 300
DUAL_SPIKE_CH = 450  # bien lejos de la franja del vehículo

# F: dos sismos locales genuinamente separados en el tiempo, sobre el MISMO
# rango de canales, con chatter ambiental disperso (clics de UN canal, muy
# por debajo del piso de densidad) llenando el hueco entre ambos -- el
# escenario sintético de regresión de A5. Buffer propio, más largo que el
# resto (los clics necesitan lugar para acumular > max_merged_block_s entre
# quake y quake sin llegar a ser, cada uno, un evento propio).
F_DUR_S = 80.0
F_N_T = int(F_DUR_S * GEOM.fs_hz)
F_T0_P1, F_T0_S1 = 12.0, 15.4
F_T0_P2, F_T0_S2 = 60.0, 63.4
F_CHATTER_T0, F_CHATTER_T1 = 19.0, 58.0
F_CHATTER_STEP_S = 2.2
F_CHATTER_DUR_S = 0.6
F_CHATTER_AMP = 20.0

# G: arribo coherente cuya velocidad aparente verdadera está EN el borde de
# la banda resoluble (v_app=seismic_v_max_mps) -- semblanza alta (>0.12,
# confirmaría sin la guarda) pero el argmax cae exactamente en el extremo
# de la grilla de búsqueda (A9). Reproduce la patología real del M5.8 de
# Ridgecrest: incidencia casi vertical / apertura insuficiente para
# resolver el moveout, no ruido ni decorrelación.
G_V_APP_TRUE = 8000.0  # == seismic_v_max_mps: el propio borde de la banda
G_T0 = 25.0

# H: sismo local legítimo, LENTO pero bien DENTRO de la banda (cerca del
# extremo inferior sin tocarlo) -- pico de semblanza interior real. La
# guarda de borde NO puede matar esto: un sismo lento verdadero con pico
# interior tiene que seguir confirmando.
H_V_APP_TRUE = 2000.0
H_T0 = 25.0

# I: arribo verdaderamente lejano/rápido (v_app_true muy por encima de
# seismic_v_max_mps) cuyo argmax de semblanza NO cae en el borde exacto de
# la grilla (boundary_pinned=False -- un paso adentro, ver A10 CHANGELOG) y
# por eso antes "confirmaba" con una velocidad de semblanza espuria
# (~1573 m/s) sin relación con la real. El ajuste de onsets (Theil-Sen)
# SÍ recupera la velocidad real (decenas de miles de m/s) -- la
# concordancia cruzada (A10) es la segunda capa que atrapa lo que la
# guarda de borde por sí sola no atrapaba.
I_V_APP_TRUE = 100_000.0
I_T0 = 25.0


def build_scenarios():
    """Construye los escenarios sintéticos (A-I) con verdad-terreno conocida."""
    fs, dx = GEOM.fs_hz, GEOM.channel_spacing_m
    base = make_noise(GEOM.n_channels, N_T, fs, seed=42)

    seis = base.copy()
    add_plane_wave(seis, fs, dx, V_P, T0_P, ricker(8.0, fs, 0.6), AMP_P, seed=11)
    add_plane_wave(seis, fs, dx, V_S, T0_S, ricker(4.0, fs, 1.2), AMP_S, seed=12)

    veh = base.copy()
    add_moving_source(
        veh, fs, dx, VEH_SPEED, x_start_m=800.0, t_start_s=15.0, t_end_s=45.0, amp=6.0
    )

    fp = base.copy()
    add_local_spike(fp, fs, SPIKE_CH, t0_s=25.0, dur_s=0.6, amp=30.0)

    # D: dos fuentes SIMULTÁNEAS en zonas disjuntas de la fibra. Antes de la
    # auditoría, la proyección temporal las fusionaba en un solo evento de
    # física mixta; ahora la separación por hueco de canales las emite como
    # eventos independientes con veredictos independientes.
    dual = base.copy()
    add_moving_source(
        dual, fs, dx, VEH_SPEED, x_start_m=800.0, t_start_s=15.0, t_end_s=45.0, amp=6.0
    )
    add_local_spike(dual, fs, DUAL_SPIKE_CH, t0_s=28.0, dur_s=0.6, amp=30.0)

    # E: evento regional/lejano emergente — llegada cuasi-simultánea a todo el
    # arreglo (jitter ±1 muestra), banda angosta 1-6 Hz, subida lenta (9s).
    # Reproduce la física real del caso M5.8 de Ridgecrest / Pawnee: disparo
    # masivo sin moveout resoluble por semblanza. Nunca debe suprimirse como
    # falso positivo local (span/coincidencia son altos por construcción).
    reg = base.copy()
    add_emergent_regional(
        reg, fs, dx, t_start_s=20.0, duration_s=40.0, amp=10.0, v_app_mps=None, rise_s=9.0, seed=13
    )

    # F: dos sismos separados en el tiempo (A5, regresión permanente). Ver
    # constantes F_* arriba. Reproduce el hallazgo real de Ridgecrest: con
    # "algún canal disparado" como criterio de fusión, clics ambientales de
    # un solo canal cada 2.2s (huecos « merge_gap_s=3.0) encadenan el sismo
    # 1 con el sismo 2 en un solo bloque de decenas de segundos, mezclando
    # la física de ambos. Antes de A5 esto fusionaba en un único veredicto;
    # ahora max_merged_block_s dispara la re-segmentación por densidad y
    # cada sismo se mide y clasifica por separado.
    dual_time = make_noise(GEOM.n_channels, F_N_T, fs, seed=43)
    add_plane_wave(dual_time, fs, dx, V_P, F_T0_P1, ricker(8.0, fs, 0.6), AMP_P, seed=21)
    add_plane_wave(dual_time, fs, dx, V_S, F_T0_S1, ricker(4.0, fs, 1.2), AMP_S, seed=22)
    add_plane_wave(dual_time, fs, dx, V_P, F_T0_P2, ricker(8.0, fs, 0.6), AMP_P, seed=23)
    add_plane_wave(dual_time, fs, dx, V_S, F_T0_S2, ricker(4.0, fs, 1.2), AMP_S, seed=24)
    chatter_rng = np.random.default_rng(99)
    t = F_CHATTER_T0
    k = 0
    while t < F_CHATTER_T1:
        ch = int(chatter_rng.integers(0, GEOM.n_channels))
        add_local_spike(
            dual_time, fs, ch, t0_s=t, dur_s=F_CHATTER_DUR_S, amp=F_CHATTER_AMP, seed=1000 + k
        )
        t += F_CHATTER_STEP_S
        k += 1

    # G: arribo coherente en el BORDE de la banda resoluble (A9, regresión
    # permanente de la guarda de solución de borde). Sin la guarda, esto
    # confirmaría SISMO_CONFIRMADO (semblanza alta, v_app dentro de banda
    # por estar exactamente en su extremo) -- con la guarda, el argmax cae
    # en el límite de la grilla y debe caer a POSIBLE_REGIONAL_EMERGENTE.
    borde = base.copy()
    add_plane_wave(borde, fs, dx, G_V_APP_TRUE, G_T0, ricker(6.0, fs, 1.0), amp=6.0, seed=31)

    # H: sismo lento pero bien DENTRO de la banda -- pico de semblanza
    # INTERIOR real (A9, regresión permanente: la guarda de borde no puede
    # matar esto). Semilla de ruido distinta de G para que no compartan
    # base y esto quede como control independiente, no una variación del
    # mismo ruido.
    lento = make_noise(GEOM.n_channels, N_T, fs, seed=45)
    add_plane_wave(lento, fs, dx, H_V_APP_TRUE, H_T0, ricker(6.0, fs, 1.0), amp=6.0, seed=32)

    # I: arribo lejano/rápido cuyo pico de semblanza NO cae en el borde
    # exacto (A10, regresión permanente de la concordancia cruzada) -- la
    # guarda de borde (A9) sola no lo atrapa; el ajuste de onsets sí
    # recupera la velocidad real y debe discrepar lo suficiente para
    # bloquear la confirmación.
    lejano = make_noise(GEOM.n_channels, N_T, fs, seed=47)
    add_plane_wave(lejano, fs, dx, I_V_APP_TRUE, I_T0, ricker(6.0, fs, 1.0), amp=6.0, seed=33)

    return {
        "A_sismo": seis,
        "B_vehiculo": veh,
        "C_falso_positivo_local": fp,
        "D_simultaneos": dual,
        "E_regional_emergente": reg,
        "F_dos_sismos_separados": dual_time,
        "G_borde_velocidad": borde,
        "H_sismo_lento_interior": lento,
        "I_lejano_concordancia": lejano,
    }, base


def run_tier0(data):
    """Corre STA/LTA + raster + extracción de eventos sobre `data`."""
    t0 = time.perf_counter()
    ratio = sta_lta_ratio(data, GEOM, T0)
    raster = trigger_raster(ratio, T0)
    events = extract_events(raster, ratio, GEOM, T0)
    dt = time.perf_counter() - t0
    return ratio, raster, events, dt


def benchmark_tier0(minutes: float = 10.0):
    """Mide el throughput de Tier0 sobre `minutes` de ruido puro."""
    n_t = int(minutes * 60 * GEOM.fs_hz)
    data = make_noise(GEOM.n_channels, n_t, GEOM.fs_hz, seed=7)
    t0 = time.perf_counter()
    ratio = sta_lta_ratio(data, GEOM, T0)
    raster = trigger_raster(ratio, T0)
    dt = time.perf_counter() - t0
    stats = reduction_stats(raster)
    rtf = (minutes * 60) / dt
    return dt, rtf, stats, data.nbytes / 1e6


def main(make_figs: bool):
    """Corre los escenarios sintéticos, verifica contra verdad-terreno,
    benchmarkea Tier0, hace una demo del catálogo y corre auto-verificación."""
    print("=" * 74)
    print("DarkFiber MAS v5 — VALIDACIÓN DE PUNTA A PUNTA (escenarios sintéticos")
    print("físicamente correctos; geometría Stanford: 626 ch × 8 m @ 50 Hz)")
    print("=" * 74)

    scenarios, base = build_scenarios()
    agent = CoherenceAgent(GEOM, COH)
    summary = {}
    keep_for_figs = {}

    for name, data in scenarios.items():
        print(f"\n--- Escenario {name} " + "-" * (50 - len(name)))
        ratio, raster, events, dt = run_tier0(data)
        stats = reduction_stats(raster)
        print(
            f"Tier0: {len(events)} evento(s) candidato(s) en {dt * 1000:.0f} ms | "
            f"celdas marcadas: {stats['cell_flag_fraction'] * 100:.3f}% | "
            f"tiempo con actividad: {stats['time_flag_fraction'] * 100:.1f}%"
        )
        results = []
        for evt in events:
            t1 = time.perf_counter()
            res = agent.analyze(data, ratio, raster, evt)
            dt2 = (time.perf_counter() - t1) * 1000
            results.append(res)
            print(
                f"\n  Evento {evt.event_id}  [{evt.t_start_s:.1f}s–{evt.t_end_s:.1f}s]"
                f"  canales {evt.ch_min}–{evt.ch_max} ({evt.n_triggered_channels} disparados)"
            )
            print(f"  → {res.classification.value}   (coherencia analizada en {dt2:.0f} ms)")
            for e in res.explanations:
                print(f"     · {e}")
        summary[name] = [r.model_dump(mode="json") for r in results]
        keep_for_figs[name] = (data, ratio, raster, events, results)

    # ---------------- verificación contra verdad-terreno -----------------
    print("\n" + "=" * 74)
    print("VERIFICACIÓN CONTRA VERDAD-TERRENO")
    print("=" * 74)
    checks = []

    res_a = [r for r in keep_for_figs["A_sismo"][4]]
    seis = [r for r in res_a if r.classification == EventClass.SEISMIC_CONFIRMED]
    ok = len(seis) == 1
    checks.append(("Sismo clasificado como SISMO_CONFIRMADO", ok))
    if seis:
        r = seis[0]
        assert r.apparent_velocity_mps is not None  # garantizado por la rama SISMO_CONFIRMADO
        v_err = abs(abs(r.apparent_velocity_mps) - V_S) / V_S * 100
        checks.append(
            (
                f"v_app medida {abs(r.apparent_velocity_mps):,.0f} m/s vs {V_S:,.0f} "
                f"(error {v_err:.1f}% ≤ 8%)",
                v_err <= 8,
            )
        )
        if r.phases and r.phases.ts_minus_tp_s is not None:
            m = r.phases.ts_minus_tp_s
            lo, hi = TRUE_TS_TP_MIN - 0.4, TRUE_TS_TP_MAX + 0.4
            checks.append(
                (
                    f"tS−tP medido {m:.2f} s dentro del rango físico "
                    f"verdadero [{TRUE_TS_TP_MIN:.2f}–{TRUE_TS_TP_MAX:.2f}] s (±0.4)",
                    lo <= m <= hi,
                )
            )
        else:
            checks.append(("tS−tP medido sobre el beam", False))
        if r.v_app_onset_mps is not None:
            onset_err = abs(abs(r.v_app_onset_mps) - V_S) / V_S * 100
            checks.append(
                (
                    f"v_app_onset (fallback de onsets) {abs(r.v_app_onset_mps):,.0f} m/s "
                    f"vs {V_S:,.0f} (error {onset_err:.1f}% ≤ 15%)",
                    onset_err <= 15,
                )
            )
        else:
            checks.append(("v_app_onset medido sobre escenario A", False))

    res_e = keep_for_figs["E_regional_emergente"][4]
    reg_ok = len(res_e) >= 1 and all(
        r.classification == EventClass.REGIONAL_EMERGENT for r in res_e
    )
    no_supp_e = not any(r.classification == EventClass.INCOHERENT_LOCAL for r in res_e)
    checks.append(
        (f"Regional emergente: {len(res_e)} evento(s), todos POSIBLE_REGIONAL_EMERGENTE", reg_ok)
    )
    checks.append(("Regional emergente: NUNCA suprimido como falso positivo local", no_supp_e))

    res_b = keep_for_figs["B_vehiculo"][4]
    traf = [r for r in res_b if r.classification == EventClass.TRAFFIC]
    checks.append(("Vehículo clasificado como FUENTE_MOVIL_TRAFICO", len(traf) >= 1))
    if traf:
        assert traf[0].track_speed_mps is not None  # garantizado por la rama FUENTE_MOVIL_TRAFICO
        sp_err = abs(abs(traf[0].track_speed_mps) - VEH_SPEED)
        checks.append(
            (
                f"velocidad medida {abs(traf[0].track_speed_mps):.1f} m/s vs "
                f"{VEH_SPEED:.1f} (err {sp_err:.1f} ≤ 2 m/s)",
                sp_err <= 2,
            )
        )

    res_d = keep_for_figs["D_simultaneos"][4]
    d_traf = [r for r in res_d if r.classification == EventClass.TRAFFIC]
    d_supp = [r for r in res_d if r.suppressed_false_positive]
    d_seis = [r for r in res_d if r.classification == EventClass.SEISMIC_CONFIRMED]
    checks.append(
        (f"Simultáneos separados: {len(res_d)} eventos independientes (≥2)", len(res_d) >= 2)
    )
    checks.append(
        (
            "Simultáneos: vehículo TRAFICO y golpe SUPRIMIDO, sin falso sismo",
            len(d_traf) >= 1 and len(d_supp) >= 1 and len(d_seis) == 0,
        )
    )

    # ---------------- F: dos sismos separados en el tiempo (A5) -----------
    evt_f, res_f = (
        keep_for_figs["F_dos_sismos_separados"][3],
        keep_for_figs["F_dos_sismos_separados"][4],
    )
    seis_f = [
        (e, r)
        for e, r in zip(evt_f, res_f, strict=False)
        if r.classification == EventClass.SEISMIC_CONFIRMED
    ]
    checks.append(
        (
            f"Dos sismos separados en el tiempo: {len(seis_f)} veredicto(s) "
            f"SISMO_CONFIRMADO independientes (=2, no fusionados por el chatter "
            f"ambiental entre medio)",
            len(seis_f) == 2,
        )
    )
    if len(seis_f) == 2:
        seis_f.sort(key=lambda er: er[0].t_start_s)
        (e1, r1), (e2, r2) = seis_f
        checks.append(
            (
                f"Sismo 1 (t_start={e1.t_start_s:.1f}s) y sismo 2 (t_start={e2.t_start_s:.1f}s) "
                f"NO se solapan en el tiempo",
                e1.t_end_s <= e2.t_start_s,
            )
        )
        v1_err = (
            abs(abs(r1.apparent_velocity_mps) - V_S) / V_S * 100
            if r1.apparent_velocity_mps
            else 100.0
        )
        v2_err = (
            abs(abs(r2.apparent_velocity_mps) - V_S) / V_S * 100
            if r2.apparent_velocity_mps
            else 100.0
        )
        checks.append(
            (
                f"v_app de ambos sismos dentro de tolerancia de la S verdadera "
                f"({V_S:,.0f} m/s): sismo1 err={v1_err:.1f}%, sismo2 err={v2_err:.1f}% (≤8%)",
                v1_err <= 8 and v2_err <= 8,
            )
        )

    # ---------------- G: guarda de solución de borde (A9) ------------------
    # Sin la guarda esto confirmaría (semblanza alta, v_app en el extremo de
    # la banda) -- el M5.8 real de Ridgecrest tenía exactamente este patrón
    # (semblanza 0.503, argmax pinchado en seismic_v_min_mps).
    res_g = keep_for_figs["G_borde_velocidad"][4]
    g_regional = [r for r in res_g if r.classification == EventClass.REGIONAL_EMERGENT]
    g_seismic = [r for r in res_g if r.classification == EventClass.SEISMIC_CONFIRMED]
    g_boundary_flagged = [r for r in res_g if r.boundary_pinned]
    checks.append(
        (
            f"Borde de velocidad: {len(res_g)} evento(s), NINGUNO confirma SISMO "
            f"(argmax en el borde de la grilla = no-medición)",
            len(g_seismic) == 0,
        )
    )
    checks.append(
        (
            f"Borde de velocidad: cae a POSIBLE_REGIONAL_EMERGENTE "
            f"({len(g_regional)}/{len(res_g)})",
            len(res_g) >= 1 and len(g_regional) == len(res_g),
        )
    )
    checks.append(
        (
            f"Borde de velocidad: boundary_pinned=True registrado para auditoría "
            f"({len(g_boundary_flagged)}/{len(res_g)})",
            len(res_g) >= 1 and len(g_boundary_flagged) == len(res_g),
        )
    )

    # ---------------- H: sismo lento con pico interior real (A9) -----------
    # Control negativo de G: la guarda NO puede matar un pico interior
    # genuino solo por estar cerca del extremo inferior de la banda.
    res_h = keep_for_figs["H_sismo_lento_interior"][4]
    h_seismic = [r for r in res_h if r.classification == EventClass.SEISMIC_CONFIRMED]
    checks.append(
        (
            f"Sismo lento interior ({H_V_APP_TRUE:,.0f} m/s): "
            f"{len(h_seismic)} evento(s) SISMO_CONFIRMADO (la guarda no mata picos "
            f"interiores reales)",
            len(h_seismic) >= 1,
        )
    )
    if h_seismic:
        rh = h_seismic[0]
        assert rh.apparent_velocity_mps is not None  # garantizado por la rama SISMO_CONFIRMADO
        h_err = abs(abs(rh.apparent_velocity_mps) - H_V_APP_TRUE) / H_V_APP_TRUE * 100
        checks.append(
            (
                f"Sismo lento interior: v_app medida {abs(rh.apparent_velocity_mps):,.0f} "
                f"m/s vs {H_V_APP_TRUE:,.0f} (error {h_err:.1f}% ≤ 8%), "
                f"boundary_pinned={rh.boundary_pinned}",
                h_err <= 8 and not rh.boundary_pinned,
            )
        )
        checks.append(
            (
                f"Sismo lento interior: v_app_onset ({rh.v_app_onset_mps:,.0f} m/s) "
                f"CONCUERDA con la semblanza (A10, la concordancia no mata "
                f"confirmaciones sanas)",
                rh.v_app_onset_mps is not None
                and abs(abs(rh.v_app_onset_mps) - abs(rh.apparent_velocity_mps))
                / ((abs(rh.v_app_onset_mps) + abs(rh.apparent_velocity_mps)) / 2)
                <= COH.onset_agreement_tol_frac,
            )
        )

    # ---------------- I: concordancia cruzada atrapa lo que el borde no (A10) -
    # v_app_true=100,000 m/s: el argmax de semblanza NO cae en el borde
    # exacto (boundary_pinned=False) y antes "confirmaba" con una velocidad
    # espuria (~1573 m/s). El ajuste de onsets recupera la velocidad real y
    # debe discrepar lo suficiente para bloquear la confirmación.
    res_i = keep_for_figs["I_lejano_concordancia"][4]
    i_seismic = [r for r in res_i if r.classification == EventClass.SEISMIC_CONFIRMED]
    checks.append(
        (
            f"Lejano/rápido ({I_V_APP_TRUE:,.0f} m/s verdadero, pico de semblanza NO en "
            f"el borde): {len(i_seismic)} evento(s) SISMO_CONFIRMADO (=0 -- la "
            f"concordancia cruzada debe bloquear esto aunque boundary_pinned=False)",
            len(i_seismic) == 0,
        )
    )
    if res_i:
        ri = max(res_i, key=lambda r: r.coincidence_fraction or 0)
        checks.append(
            (
                f"Lejano/rápido: boundary_pinned={ri.boundary_pinned} (debe ser False -- "
                "esto prueba que la guarda de borde SOLA no alcanza, hace falta la "
                "concordancia)",
                ri.boundary_pinned is False,
            )
        )
        if ri.v_app_onset_mps is not None and ri.apparent_velocity_mps:
            rel_diff = abs(ri.v_app_onset_mps - ri.apparent_velocity_mps) / (
                (abs(ri.v_app_onset_mps) + abs(ri.apparent_velocity_mps)) / 2
            )
            checks.append(
                (
                    f"Lejano/rápido: v_app_onset ({ri.v_app_onset_mps:,.0f} m/s, recupera "
                    f"la velocidad real) DISCREPA de la semblanza espuria "
                    f"({ri.apparent_velocity_mps:,.0f} m/s) — diferencia {rel_diff * 100:.0f}% "
                    f"> tolerancia {COH.onset_agreement_tol_frac * 100:.0f}%",
                    rel_diff > COH.onset_agreement_tol_frac,
                )
            )

    res_c = keep_for_figs["C_falso_positivo_local"][4]
    supp = [r for r in res_c if r.suppressed_false_positive]
    fake_seis = [r for r in res_c if r.classification == EventClass.SEISMIC_CONFIRMED]
    checks.append(("Falso positivo local SUPRIMIDO (el 5% de v4)", len(supp) >= 1))
    checks.append(("Ningún falso 'sismo' en escenario C", len(fake_seis) == 0))

    # ---------------- garantía de calentamiento del STA/LTA (A2/T1d) ------
    # Encontrado en A2 (Monterey Bay): un archivo recortado que arranca casi
    # en el evento real hizo que la PRIMERA muestra visible tras el
    # calentamiento coincidiera con esa energía real. La garantía de fondo
    # (ratio==1.0, sin disparos posibles, para t < cfg.warmup_s) ya existía
    # de forma incidental (threshold>1 por contrato); acá se prueba
    # explícitamente para que no pueda romperse en silencio.
    warm_ok = True
    for seed in (0, 1, 2):
        noise = make_noise(GEOM.n_channels, int(15 * GEOM.fs_hz), GEOM.fs_hz, seed=seed)
        warm_ratio = sta_lta_ratio(noise, GEOM, T0)
        raster = trigger_raster(warm_ratio, T0)
        warm_n = int(T0.warmup_s * GEOM.fs_hz)
        if raster[:, :warm_n].any():
            warm_ok = False
    checks.append(
        (
            f"Calentamiento STA/LTA ({T0.warmup_s:.1f}s): cero disparos posibles antes, "
            "en 3 semillas de ruido puro",
            warm_ok,
        )
    )

    # ---------------- equivalencia numérica del bloqueo por canal (A2/T3a) -
    # sta_lta_ratio ahora puede procesar en bloques de canales (para no
    # agotar RAM en arreglos densos como Arcata, 7,550 canales). El bloqueo
    # no debería cambiar el resultado (cada canal es independiente) más
    # allá de redondeo de punto flotante -- se prueba con datos sintéticos
    # que incluyen un sismo real para que el raster tenga estructura, no
    # solo ruido.
    seis_data = keep_for_figs["A_sismo"][0]
    r_full = sta_lta_ratio(seis_data, GEOM, T0, channel_block=GEOM.n_channels)
    r_blocked = sta_lta_ratio(seis_data, GEOM, T0, channel_block=64)
    block_diff = float(np.abs(r_full.astype(np.float64) - r_blocked.astype(np.float64)).max())
    raster_full = trigger_raster(r_full, T0)
    raster_blocked = trigger_raster(r_blocked, T0)
    same_triggers = bool(np.array_equal(raster_full, raster_blocked))
    checks.append(
        (
            f"Bloqueo por canal en sta_lta_ratio: mismo raster de disparo, "
            f"diff máx de ratio={block_diff:.2e} (tolerancia float)",
            same_triggers,
        )
    )

    # ---------------- aislamiento de firmas entre arreglos (A2/T5a) -------
    # catalog.match()/promote() documentan que "lo aprendido en Ridgecrest
    # no contamina Monterey" (array_id aísla la búsqueda) -- esto lo prueba
    # como test permanente, no solo como comentario.
    import os as _os
    import tempfile as _tempfile

    from .catalog import SignatureCatalog as _SignatureCatalog

    iso_db = _os.path.join(_tempfile.gettempdir(), "df_isolation_test.db")
    if _os.path.exists(iso_db):
        _os.remove(iso_db)
    iso_cat = _SignatureCatalog(iso_db, naming_threshold=2)
    iso_rng = np.random.default_rng(7)
    proto_vec = iso_rng.standard_normal(64).astype(np.float32)
    for _ in range(2):
        m_a = iso_cat.match(
            proto_vec + 0.02 * iso_rng.standard_normal(64).astype(np.float32),
            zone="zona_A",
            array_id="ridgecrest_north",
        )
    assert m_a.recurring_unknown_id is not None
    iso_cat.promote(m_a.recurring_unknown_id, "fuente_recurrente_ridgecrest")
    same_vec_other_array = iso_cat.match(proto_vec, zone="zona_A", array_id="monterey_bay")
    same_vec_same_array = iso_cat.match(proto_vec, zone="zona_A", array_id="ridgecrest_north")
    isolated_ok = (
        same_vec_other_array.is_novel is True
        and same_vec_other_array.label is None
        and same_vec_same_array.is_novel is False
        and same_vec_same_array.label == "fuente_recurrente_ridgecrest"
    )
    checks.append(
        (
            "Aislamiento de firmas: una firma de ridgecrest_north NO matchea "
            "en monterey_bay (mismo vector, array_id distinto)",
            isolated_ok,
        )
    )

    # ---------------- Tier0Config.from_array_profile se consume de verdad (A7) -
    # calibrate.py --param tier0_threshold --apply escribe thresholds_json en
    # array_profiles; no alcanza con que el dataclass cargue el valor -- el
    # PIPELINE tiene que cambiar de comportamiento con él. Se prueba con una
    # señal débil (misma receta que la fase P del escenario A) que dispara al
    # threshold default (4.0) y deja de disparar bajo un threshold alto
    # cargado desde un perfil de prueba (proxy de una propuesta aplicada).
    profile_db = _os.path.join(_tempfile.gettempdir(), "df_tier0_profile_test.db")
    if _os.path.exists(profile_db):
        _os.remove(profile_db)
    profile_cat = _SignatureCatalog(profile_db, naming_threshold=2)
    HIGH_THRESHOLD = 15.0
    profile_cat.upsert_array_profile(
        "test_array_alto_umbral",
        fs=GEOM.fs_hz,
        dx=GEOM.channel_spacing_m,
        n_ch=GEOM.n_channels,
        aperture_m=GEOM.aperture_m,
        thresholds={"threshold": HIGH_THRESHOLD},
    )
    loaded_t0 = Tier0Config.from_array_profile(
        profile_cat.get_array_profile("test_array_alto_umbral")
    )
    loaded_ok = loaded_t0.threshold == HIGH_THRESHOLD

    weak_base = make_noise(GEOM.n_channels, int(20 * GEOM.fs_hz), GEOM.fs_hz, seed=55)
    weak_seis = weak_base.copy()
    add_plane_wave(
        weak_seis,
        GEOM.fs_hz,
        GEOM.channel_spacing_m,
        5000.0,
        8.0,
        ricker(6.0, GEOM.fs_hz, 0.6),
        amp=3.0,
        seed=56,
    )
    raster_default = trigger_raster(sta_lta_ratio(weak_seis, GEOM, T0), T0)
    raster_loaded = trigger_raster(sta_lta_ratio(weak_seis, GEOM, loaded_t0), loaded_t0)
    consumption_ok = bool(raster_default.any()) and not bool(raster_loaded.any())

    checks.append(
        (
            f"Tier0Config.from_array_profile: carga thresholds_json['threshold']="
            f"{HIGH_THRESHOLD} Y el pipeline lo consume de verdad (señal débil dispara "
            "al default, deja de disparar bajo el perfil)",
            loaded_ok and consumption_ok,
        )
    )

    # ---------------- upsert_array_profile no pisa thresholds_json en silencio (A8) -
    # Bug real encontrado en A8: `run_array_selftest` llama a
    # `upsert_array_profile` sin pasar `thresholds=` (solo actualiza ruido/
    # synth_recall) -- pero `thresholds_json` NO estaba en la lista COALESCE
    # del UPDATE (a diferencia de synth_recall/recall_curve_json/snr50, que
    # el propio docstring de la función ya prometía preservar). Resultado:
    # cada corrida de `run_on_quakeflow.py --dir ...` sobre un arreglo YA
    # calibrado (calibrate.py --apply) borraba threshold=8.0 de vuelta a
    # None en el paso final (el self-test), silenciosamente -- ridgecrest_
    # north perdió su calibración así en medio de A8. Corregido
    # (COALESCE en thresholds_json); se prueba acá que un upsert SIN
    # thresholds= no borra un threshold ya guardado.
    coalesce_db = _os.path.join(_tempfile.gettempdir(), "df_thresholds_coalesce_test.db")
    if _os.path.exists(coalesce_db):
        _os.remove(coalesce_db)
    coalesce_cat = _SignatureCatalog(coalesce_db, naming_threshold=2)
    coalesce_cat.upsert_array_profile(
        "test_array_coalesce",
        fs=100.0,
        dx=8.0,
        n_ch=100,
        aperture_m=800.0,
        thresholds={"threshold": 8.0},
    )
    # Réplica exacta del patrón de llamada de run_array_selftest: sin thresholds=.
    coalesce_cat.upsert_array_profile(
        "test_array_coalesce",
        fs=100.0,
        dx=8.0,
        n_ch=100,
        aperture_m=800.0,
        noise_stats={"rms_mean": 0.1},
        synth_recall=1.0,
    )
    survived = (coalesce_cat.get_array_profile("test_array_coalesce") or {}).get("thresholds_json")
    checks.append(
        (
            "upsert_array_profile: un upsert sin thresholds= NO borra un threshold "
            "ya guardado (COALESCE, no overwrite ciego)",
            survived == {"threshold": 8.0},
        )
    )

    passed = 0
    for msg, ok in checks:
        print(f"  [{'OK ' if ok else 'FALLA'}] {msg}")
        passed += ok
    print(f"\n  RESULTADO: {passed}/{len(checks)} verificaciones superadas")

    # ---------------- benchmark Tier 0 -----------------------------------
    print("\n" + "=" * 74)
    print("BENCHMARK TIER 0 (matriz completa, solo ruido)")
    print("=" * 74)
    dt, rtf, stats, mb = benchmark_tier0(10.0)
    print(
        f"  10.0 min de arreglo completo ({mb:.0f} MB) triados en {dt * 1000:.0f} ms "
        f"→ factor tiempo-real {rtf:,.0f}×"
    )
    print(
        f"  Silencio filtrado (nada pasa a ML): {stats['silence_filtered_fraction'] * 100:.2f}% "
        f"del tiempo | celdas canal-tiempo marcadas: {stats['cell_flag_fraction'] * 100:.4f}%"
    )
    bench = {"tier0_10min_ms": dt * 1000, "real_time_factor": rtf, **stats}

    # ---------------- catálogo vivo (demo funcional) ----------------------
    print("\n" + "=" * 74)
    print("CATÁLOGO VIVO DE FIRMAS (demo funcional sobre SQLite)")
    print("=" * 74)
    import tempfile

    from .catalog import SignatureCatalog

    db = os.path.join(tempfile.gettempdir(), "df_sig_demo.db")
    if os.path.exists(db):
        os.remove(db)
    cat = SignatureCatalog(db, naming_threshold=3)
    rng = np.random.default_rng(0)
    proto_bomba = rng.standard_normal(64).astype(np.float32)
    for i in range(4):
        vec = proto_bomba + 0.05 * rng.standard_normal(64).astype(np.float32)
        catmatch = cat.match(vec, zone="km_3.2")
        print(
            f"  Evento desconocido #{i + 1}: recurrente_id={catmatch.recurring_unknown_id} "
            f"ocurrencias={catmatch.recurring_count} sugerir_nombre={catmatch.suggest_naming}"
        )
    assert catmatch.recurring_unknown_id is not None
    cat.promote(catmatch.recurring_unknown_id, "bomba_de_agua_km3.2")
    catmatch2 = cat.match(
        proto_bomba + 0.05 * rng.standard_normal(64).astype(np.float32), zone="km_3.2"
    )
    print(
        f"  Tras bautizarla: etiqueta='{catmatch2.label}' similitud={catmatch2.similarity:.2f} "
        f"(clase nueva SIN reentrenar)"
    )

    # ---------------- auto-verificación ------------------------------------
    print("\n" + "=" * 74)
    print("AUTO-VERIFICACIÓN POR INYECCIÓN SINTÉTICA (gauge de SLA)")
    print("=" * 74)
    st_results = []
    for k, (v, snr) in enumerate([(2500, 4), (3200, 3), (4500, 5), (6000, 4), (3500, 2.5)]):
        st_res = inject_and_verify(base, GEOM, T0, COH, v_app_mps=v, snr=snr, seed=100 + k)
        st_results.append(st_res)
        vm = f"{abs(st_res.measured_velocity_mps):,.0f}" if st_res.measured_velocity_mps else "—"
        print(
            f"  Inyección v={v:,} m/s SNR={snr}: detectado={st_res.detected} "
            f"clase={st_res.classified_as.value if st_res.classified_as else '—'} v_medida={vm} m/s"
        )
    gauge = recall_gauge(st_results)
    print(f"\n  GAUGE 'recall sintético': {gauge * 100:.0f}% ({len(st_results)} inyecciones)")

    # figures/ solo se creaba dentro de make_figures(), y solo con --figs — un
    # checkout limpio sin esa carpeta rompía este write incluso cuando se pasaba
    # --figs, porque este bloque corre ANTES de la llamada a make_figures() más
    # abajo. Encontrado en la prueba de clean-room (ver CHANGELOG.md).
    os.makedirs("figures", exist_ok=True)
    with open("figures/validation_summary.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "scenarios": summary,
                "benchmark": bench,
                "selftest_recall": gauge,
                "checks_passed": f"{passed}/{len(checks)}",
            },
            fh,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    if make_figs:
        make_figures(keep_for_figs)
    print("\nListo. Resumen en figures/validation_summary.json")


def make_figures(keep):
    """Genera fig1-fig3 (pendiente/semblanza/beam) a partir de los resultados."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fs = GEOM.fs_hz
    t = np.arange(N_T) / fs

    # ---- Figura 1: la pendiente es la física (3 paneles) -----------------
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), sharey=True)
    titles = {
        "A_sismo": "A) Sismo real\n(frente a km/s: casi vertical)",
        "B_vehiculo": "B) Vehículo a 12 m/s\n(franja diagonal lenta)",
        "C_falso_positivo_local": "C) Falso positivo local\n(un solo canal: sin pendiente)",
    }
    for ax, name in zip(axes, titles, strict=False):
        data = keep[name][0]
        env = np.abs(data)
        vmax = np.percentile(env, 99.7)
        ax.imshow(
            env,
            aspect="auto",
            origin="lower",
            cmap="magma",
            extent=[t[0], t[-1], 0, GEOM.n_channels],
            vmin=0,
            vmax=vmax,
            interpolation="nearest",
        )
        ax.set_title(titles[name], fontsize=10)
        ax.set_xlabel("tiempo (s)")
        ax.set_xlim(10, 55)
    axes[0].set_ylabel("canal de fibra (× 8 m)")
    fig.suptitle("DarkFiber v5 — «La pendiente es la física»: plano canal-tiempo", y=1.02)
    fig.tight_layout()
    fig.savefig("figures/fig1_pendiente_es_fisica.png", dpi=150, bbox_inches="tight")

    # ---- Figura 2: curva de semblanza -------------------------------------
    from .coherence import slant_stack_semblance, slowness_grid

    data, ratio, raster, events, results = keep["A_sismo"]
    evt = [
        e
        for e, r in zip(events, results, strict=False)
        if r.classification == EventClass.SEISMIC_CONFIRMED
    ][0]
    agent = CoherenceAgent(GEOM, COH)
    win, x, margin, _ = agent._extract_window(data, evt)
    grid = slowness_grid(COH)
    sem, _ = slant_stack_semblance(win, x, fs, grid, margin, COH.use_envelope)
    v_axis = 1.0 / grid
    pos = grid > 0
    fig2, ax = plt.subplots(figsize=(7, 4))
    ax.semilogx(np.abs(v_axis[pos]), sem[pos], "o-", label="dirección canal 0→N")
    ax.semilogx(np.abs(v_axis[~pos]), sem[~pos], "s--", alpha=0.6, label="dirección canal N→0")
    ax.axvline(V_S, color="crimson", ls=":", label=f"verdad-terreno S: {V_S:,.0f} m/s")
    ax.axvspan(
        COH.seismic_v_min_mps,
        COH.seismic_v_max_mps,
        alpha=0.08,
        color="green",
        label="banda sísmica",
    )
    ax.set_xlabel("velocidad aparente |v| (m/s)")
    ax.set_ylabel("semblanza")
    ax.set_title("Escaneo slant-stack: el pico revela la velocidad del frente de onda")
    ax.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig("figures/fig2_semblanza.png", dpi=150, bbox_inches="tight")

    # ---- Figura 3: beam con fases P y S ------------------------------------
    from .coherence import pick_phases_on_beam

    sem_k = int(np.argmax(sem))
    p_best = float(grid[sem_k])
    beam, t0_abs = agent.beamform_wide(data, evt, p_best)
    phases = pick_phases_on_beam(beam, fs)
    tb = np.arange(beam.size) / fs + t0_abs
    fig3, ax = plt.subplots(figsize=(8, 3.4))
    ax.plot(tb, beam, lw=0.9, color="#1a355e")
    if phases.t_p_s:
        tp = phases.t_p_s + t0_abs
        ax.axvline(tp, color="orange", ls="--", label=f"P @ {tp:.2f}s")
    if phases.t_s_s:
        ts = phases.t_s_s + t0_abs
        ax.axvline(ts, color="crimson", ls="--", label=f"S @ {ts:.2f}s")
    if phases.ts_minus_tp_s:
        ax.set_title(
            f"Beam apilado (SNR ×√626): tS−tP = {phases.ts_minus_tp_s:.2f} s "
            "= segundos de alerta temprana"
        )
    ax.set_xlabel("tiempo (s)")
    ax.set_ylabel("envolvente apilada")
    ax.legend()
    fig3.tight_layout()
    fig3.savefig("figures/fig3_beam_fases_PS.png", dpi=150, bbox_inches="tight")
    print("Figuras guardadas en figures/")


def main_cli() -> None:
    """Entry point for the `darkfiber-validate` console script."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--figs", action="store_true")
    main(ap.parse_args().figs)


if __name__ == "__main__":
    main_cli()
