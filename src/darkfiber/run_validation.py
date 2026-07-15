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


def build_scenarios():
    """Construye los 5 escenarios sintéticos (A-E) con verdad-terreno conocida."""
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

    return {
        "A_sismo": seis,
        "B_vehiculo": veh,
        "C_falso_positivo_local": fp,
        "D_simultaneos": dual,
        "E_regional_emergente": reg,
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
    """Corre los 5 escenarios sintéticos, verifica contra verdad-terreno,
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
            ts_tp = r.phases.ts_minus_tp_s
            lo, hi = TRUE_TS_TP_MIN - 0.4, TRUE_TS_TP_MAX + 0.4
            checks.append(
                (
                    f"tS−tP medido {ts_tp:.2f} s dentro del rango físico "
                    f"verdadero [{TRUE_TS_TP_MIN:.2f}–{TRUE_TS_TP_MAX:.2f}] s (±0.4)",
                    lo <= ts_tp <= hi,
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

    res_c = keep_for_figs["C_falso_positivo_local"][4]
    supp = [r for r in res_c if r.suppressed_false_positive]
    fake_seis = [r for r in res_c if r.classification == EventClass.SEISMIC_CONFIRMED]
    checks.append(("Falso positivo local SUPRIMIDO (el 5% de v4)", len(supp) >= 1))
    checks.append(("Ningún falso 'sismo' en escenario C", len(fake_seis) == 0))

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
    import os
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
    for ax, name in zip(axes, titles, strict=True):
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
        for e, r in zip(events, results, strict=True)
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
