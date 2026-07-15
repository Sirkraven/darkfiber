"""
DarkFiber MAS v5 — Caracterización del límite apertura/distancia (P1).

El caso real M5.8 de Ridgecrest (ver validacion_real/NOTES.md) dejó una
pregunta abierta: ¿por qué un sismo real y fuerte no deja moveout resoluble
en una apertura de ~9 km? Dos barridos sintéticos, con verdad-terreno
conocida, cierran esa pregunta en vez de descubrirla caso por caso:

  1. Barrido de GEOMETRÍA: onda plana coherente (impulsiva) a distintas
     v_app sobre distintas aperturas -> error de velocidad medida vs
     verdadera. Muestra el límite por MUESTREO (cuántas muestras de retardo
     total hay para resolver la pendiente).
  2. Barrido de COHERENCIA: a v_app fija, transición impulsivo -> emergente
     (tiempo de subida 0->10s, mezclando una onda plana coherente con un
     tren de banda angosta decorrelado canal a canal) -> semblanza y R² del
     ajuste de onsets. Muestra el límite por DECORRELACIÓN DE FORMA DE ONDA,
     independiente del muestreo -- este es el que explica el caso M5.8: el
     problema no es cuántas muestras hay, es que la forma de onda ya no es
     la misma canal a canal.

Uso: python characterize_aperture.py [--figs]
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .coherence import fit_onset_velocity, slant_stack_semblance, v_app_max_resoluble
from .contracts import ArrayGeometry, CoherenceConfig, Tier0Config, TriggerEvent
from .synth import add_emergent_regional, add_plane_wave, make_noise, ricker
from .triage import sta_lta_ratio

FS = 50.0
DX = 8.0
K_SAMPLES = 3
APERTURES_KM = [2.0, 5.0, 9.2, 40.0]  # 9.2 km = apertura real de Ridgecrest North
RIDGECREST_APERTURE_KM = 9.2
RIDGECREST_FS = 100.0


def measure_v_app(
    data: np.ndarray,
    dx: float,
    fs: float,
    v_min: float = 1000.0,
    v_max: float = 200_000.0,
    n_steps: int = 48,
):
    """Mide v_app por slant-stack sobre TODO el arreglo, con grilla de
    velocidad ancha (no acotada a la banda sísmica del clasificador): acá
    se diagnostica la capacidad de MEDICIÓN cruda, no la decisión de negocio.
    """
    n_ch, n_t = data.shape
    x = np.arange(n_ch, dtype=np.float64) * dx
    v = np.geomspace(v_min, v_max, n_steps)
    p = 1.0 / v
    slownesses = np.concatenate([-p[::-1], p])
    margin = int(np.ceil(np.abs(slownesses).max() * x.max() * fs)) + int(1 * fs)
    # Mismo clamp de seguridad que _extract_window en coherence.py: sin esto,
    # el margen requerido por la velocidad más lenta de la grilla puede
    # exceder la ventana disponible y el "core" para semblanza queda vacío
    # o inválido (medía basura -> v_meas pegado al piso de la grilla).
    margin = max(1, min(margin, (n_t - int(0.5 * fs)) // 2))
    sem, _ = slant_stack_semblance(data, x, fs, slownesses, margin, use_envelope=True)
    k = int(np.argmax(sem))
    p_best = slownesses[k]
    v_best = 1.0 / p_best if p_best != 0 else float("inf")
    return float(v_best), float(min(1.0, max(0.0, sem[k])))


def sweep1_geometry():
    """Onda plana coherente a distintas v_app sobre distintas aperturas.

    La duración de la ventana se dimensiona por combinación (L_km, v_true):
    el moveout total (L/v_true) debe caber completo, si no los canales más
    lejanos nunca reciben el frente y la medición queda sesgada por
    truncamiento, no por el límite físico que queremos medir.
    """
    # El límite geométrico depende de la apertura TOTAL y de fs, no de cuántos
    # canales caben adentro (eso es SNR, otro eje). Usar pocos canales (64)
    # cubriendo la misma apertura real da el mismo resultado físico y corre
    # órdenes de magnitud más rápido, lo que permite dimensionar ventanas
    # generosas sin que el barrido completo se vuelva impago en tiempo.
    n_ch_diag = 64
    results = []
    v_true_list = np.geomspace(1500.0, 2_000_000.0, 18)
    for L_km in APERTURES_KM:
        aperture_m = L_km * 1000.0
        dx_diag = aperture_m / (n_ch_diag - 1)
        for v_true in v_true_list:
            v_min_grid = v_true / 3.0
            v_max_grid = v_true * 3.0
            margin_s = aperture_m / v_min_grid
            core_s = 3.0
            dur_s = 2 * margin_s + core_s
            n_t = int(dur_s * FS)
            t0 = margin_s + 0.5
            data = make_noise(n_ch_diag, n_t, FS, seed=1)
            add_plane_wave(
                data,
                FS,
                dx_diag,
                float(v_true),
                t0,
                ricker(4.0, FS, 1.0),
                amp=6.0,
                amp_jitter=0.0,
                seed=2,
            )
            v_meas, sem = measure_v_app(data, dx_diag, FS, v_min=v_min_grid, v_max=v_max_grid)
            err_pct = abs(abs(v_meas) - v_true) / v_true * 100.0
            v_max_geo = v_app_max_resoluble(aperture_m, FS, K_SAMPLES)
            results.append(
                dict(
                    L_km=L_km,
                    v_true_mps=float(v_true),
                    v_meas_mps=v_meas,
                    semblance=sem,
                    err_pct=float(err_pct),
                    v_max_geometrico_mps=v_max_geo,
                )
            )
    return results


def sweep2_coherence():
    """A v_app fija, transición impulsivo (onda plana coherente) -> emergente
    (tren decorrelado canal a canal), variando el tiempo de subida 0->10s.
    alpha=rise_s/10 pesa la mezcla: alpha=0 puro impulsivo, alpha=1 puro
    emergente.

    La ventana de medición se recorta al tramo relevante (t_start-1s hasta
    duración máxima de la señal +2s): medir sobre 20s completos diluye una
    señal de 1-8s en ruido de fondo y la semblanza queda artificialmente
    baja incluso en el caso puramente impulsivo.
    """
    aperture_m = RIDGECREST_APERTURE_KM * 1000.0
    n_ch_diag = 64
    dx_diag = aperture_m / (n_ch_diag - 1)
    v_fixed = 5000.0
    rise_values = np.linspace(0.0, 10.0, 11)
    geom = ArrayGeometry(n_channels=n_ch_diag, channel_spacing_m=dx_diag, fs_hz=FS)
    cfg = CoherenceConfig()
    t0cfg = Tier0Config()

    v_min_grid, v_max_grid = v_fixed / 3.0, v_fixed * 3.0
    margin_s = aperture_m / v_min_grid
    core_s = 12.0  # generoso: cubre la duración del tren emergente (8s) + margen
    t_start = margin_s + 1.0
    dur_s = 2 * margin_s + core_s
    n_t = int(dur_s * FS)

    results = []
    for rise_s in rise_values:
        alpha = rise_s / 10.0
        data = make_noise(n_ch_diag, n_t, FS, seed=3)
        amp_coherent = (1.0 - alpha) * 10.0 + 0.05
        add_plane_wave(
            data,
            FS,
            dx_diag,
            v_fixed,
            t_start,
            ricker(4.0, FS, 1.0),
            amp=amp_coherent,
            amp_jitter=0.0,
            seed=4,
        )
        if alpha > 0:
            add_emergent_regional(
                data,
                FS,
                dx_diag,
                t_start_s=t_start,
                duration_s=8.0,
                amp=alpha * 10.0,
                v_app_mps=v_fixed,
                rise_s=max(rise_s, 0.5),
                seed=5,
            )

        v_meas, sem = measure_v_app(data, dx_diag, FS, v_min=v_min_grid, v_max=v_max_grid)

        ratio = sta_lta_ratio(data, geom, t0cfg)
        evt = TriggerEvent(
            event_id="sweep2",
            t_start_s=0.0,
            t_end_s=dur_s,
            ch_min=0,
            ch_max=n_ch_diag - 1,
            n_triggered_channels=n_ch_diag,
            peak_ratio=t0cfg.threshold * 2,
        )
        v_onset, r2_onset = fit_onset_velocity(ratio, evt, geom, cfg, t0cfg.threshold)
        results.append(
            dict(
                rise_s=float(rise_s),
                alpha=float(alpha),
                semblance=sem,
                v_meas_mps=v_meas,
                v_onset_mps=v_onset,
                r2_onset=r2_onset,
            )
        )
    return results


def make_figures(res1, res2, out_dir="figures"):
    """Genera fig5 (límite por geometría + límite por coherencia)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8))

    for L_km in APERTURES_KM:
        rows = [r for r in res1 if r["L_km"] == L_km]
        v_true = [r["v_true_mps"] for r in rows]
        err = [r["err_pct"] for r in rows]
        ax1.semilogx(v_true, err, "o-", label=f"L={L_km:g} km")
    ax1.axhline(10, color="crimson", ls=":", label="10% error")
    ax1.set_xlabel("v_app verdadera (m/s)")
    ax1.set_ylabel("error de medición (%)")
    ax1.set_title("Barrido 1 — límite por GEOMETRÍA\n(onda plana coherente, distintas aperturas)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    rise = [r["rise_s"] for r in res2]
    sem = [r["semblance"] for r in res2]
    r2 = [r["r2_onset"] if r["r2_onset"] is not None else 0.0 for r in res2]
    ax2.plot(rise, sem, "o-", color="#1a355e", label="semblanza (slant-stack)")
    ax2.plot(rise, r2, "s--", color="crimson", label="R² (ajuste de onsets)")
    ax2.axhline(
        CoherenceConfig().seismic_min_semblance,
        color="#1a355e",
        ls=":",
        alpha=0.6,
        label="umbral semblanza sísmica",
    )
    ax2.set_xlabel("tiempo de subida (s): 0=impulsivo, 10=emergente")
    ax2.set_ylabel("semblanza / R²")
    ax2.set_title(
        f"Barrido 2 — límite por COHERENCIA\n"
        f"(v_app=5,000 m/s fija, apertura Ridgecrest {RIDGECREST_APERTURE_KM} km)"
    )
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    path = os.path.join(out_dir, "fig5_limite_apertura.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"Figura guardada: {path}")


def main(make_figs: bool):
    t0 = time.perf_counter()
    print("=" * 74)
    print("CARACTERIZACIÓN DEL LÍMITE APERTURA/DISTANCIA (P1)")
    print("=" * 74)

    print(
        "\nBarrido 1 (geometría): onda plana coherente, v_app 1.5-100 km/s, "
        f"aperturas {APERTURES_KM} km..."
    )
    res1 = sweep1_geometry()
    for L_km in APERTURES_KM:
        rows = [r for r in res1 if r["L_km"] == L_km]
        first_bad = next((r for r in rows if r["err_pct"] > 10.0), None)
        v_max_geo = v_app_max_resoluble(L_km * 1000.0, FS, K_SAMPLES)
        msg = (
            f"  L={L_km:5.1f} km: v_app_max_geométrico(k=3)={v_max_geo:,.0f} m/s | "
            f"error > 10% a partir de v_app≈"
            f"{first_bad['v_true_mps']:,.0f} m/s"
            if first_bad
            else f"  L={L_km:5.1f} km: v_app_max_geométrico(k=3)={v_max_geo:,.0f} m/s | "
            f"error nunca supera 10% en el rango barrido"
        )
        print(msg)

    print(
        f"\nBarrido 2 (coherencia): v_app=5,000 m/s fija, apertura Ridgecrest "
        f"{RIDGECREST_APERTURE_KM} km, tiempo de subida 0->10s..."
    )
    res2 = sweep2_coherence()
    cfg = CoherenceConfig()
    dies_at = next((r for r in res2 if r["semblance"] < cfg.seismic_min_semblance), None)
    if dies_at:
        print(
            f"  La semblanza cae bajo el umbral sísmico ({cfg.seismic_min_semblance:.2f}) "
            f"a partir de tiempo de subida ≈ {dies_at['rise_s']:.1f} s"
        )
    for r in res2:
        v_onset_s = (
            f"{r['v_onset_mps']:,.0f}" if r["v_onset_mps"] not in (None, float("inf")) else "—"
        )
        print(
            f"    subida={r['rise_s']:4.1f}s  semblanza={r['semblance']:.3f}  "
            f"v_onset={v_onset_s} m/s  R²_onset={r['r2_onset'] or 0:.2f}"
        )

    dt = time.perf_counter() - t0
    print(f"\nTiempo total: {dt:.1f} s")

    # Mismo bug que en run_validation.py: este write corre antes de que
    # make_figures() cree figures/, incluso con --figs. Ver CHANGELOG.md.
    os.makedirs("figures", exist_ok=True)
    with open("figures/limite_apertura.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "sweep1_geometria": res1,
                "sweep2_coherencia": res2,
                "k_muestras": K_SAMPLES,
                "runtime_s": dt,
            },
            fh,
            indent=2,
            default=str,
        )
    print("Tabla guardada en figures/limite_apertura.json")

    if make_figs:
        make_figures(res1, res2)


def main_cli() -> None:
    """Entry point for the `darkfiber-aperture` console script."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--figs", action="store_true")
    main(ap.parse_args().figs)


if __name__ == "__main__":
    main_cli()
