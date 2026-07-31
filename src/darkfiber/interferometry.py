"""
DarkFiber MAS v5 — Interferometría de fuente virtual (experimento).

LA IDEA (la inversión conceptual de v5): el pipeline descarta el tráfico como
"no-sismo"... pero cada vehículo rastreado es una FUENTE SÍSMICA CALIBRADA
que ilumina el subsuelo gratis. Correlacionando pares de canales durante una
pasada, emerge la función de Green empírica entre ellos: un pulso que viaja
a la velocidad del MEDIO (no del vehículo). Repetido en el tiempo, eso es un
ecógrafo continuo del subsuelo urbano (Biondi & Martin demostraron la física
sobre este mismo arreglo de Stanford; acá se industrializa el circuito:
rastreo → catálogo de fuentes → gather → velocidad medida → auditable).

Pipeline estándar de interferometría de ruido (Bensen et al. 2007), mínimo:
  1. bandpass a la banda de onda superficial
  2. normalización temporal one-bit  (mata la firma determinista del motor)
  3. blanqueo espectral              (balancea la banda)
  4. correlación cruzada por ventanas, apiladas
  5. medición de la velocidad del medio sobre el gather... reutilizando el
     MISMO slant-stack del motor de coherencia. La pendiente sigue siendo
     la física; solo cambió qué física: antes v_aparente del evento, ahora
     v del subsuelo.

HONESTIDAD: este módulo se valida contra un forward model sintético donde
v_medium es verdad-terreno conocida (synth.add_moving_radiator), con control
negativo (ruido puro NO debe producir velocidad estable). La corrida sobre
las pasadas reales de Stanford queda en tu máquina (CLI abajo); 22 minutos
de datos dan un vistazo de la función de Green, no un modelo de velocidad.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .contracts import ArrayGeometry, TriggerEvent
from .synth import bandpass

# ---------------------------------------------------------------------------
# Preprocesamiento estándar
# ---------------------------------------------------------------------------


def one_bit(x: np.ndarray) -> np.ndarray:
    """Normalización temporal one-bit: conserva la fase, descarta la amplitud.

    Es el paso que evita que el espectro del motor del vehículo (determinista
    y de banda angosta) domine la correlación; queda solo la cinemática de
    propagación, que es lo que buscamos.
    """
    return np.sign(x).astype(np.float32)


def spectral_whiten(x: np.ndarray, fs: float, band: tuple[float, float]) -> np.ndarray:
    """Blanqueo espectral por canal dentro de `band` (taper coseno suave)."""
    n = x.shape[-1]
    X = np.fft.rfft(x, axis=-1)
    f = np.fft.rfftfreq(n, d=1.0 / fs)
    lo, hi = band
    edge = max(0.5, 0.1 * (hi - lo))
    w = np.zeros_like(f)
    core = (f >= lo) & (f <= hi)
    w[core] = 1.0
    ramp_lo = (f >= lo - edge) & (f < lo)
    w[ramp_lo] = 0.5 * (1 + np.cos(np.pi * (lo - f[ramp_lo]) / edge))
    ramp_hi = (f > hi) & (f <= hi + edge)
    w[ramp_hi] = 0.5 * (1 + np.cos(np.pi * (f[ramp_hi] - hi) / edge))
    Xw = w * X / (np.abs(X) + 1e-10)
    return np.fft.irfft(Xw, n=n, axis=-1).astype(np.float32)


# ---------------------------------------------------------------------------
# Correlación de fuente virtual
# ---------------------------------------------------------------------------


def virtual_source_gather(
    data: np.ndarray,
    ref_ch: int,
    fs: float,
    band: tuple[float, float] = (4.0, 16.0),
    max_lag_s: float = 2.0,
    win_s: float = 10.0,
    hop_s: float = 5.0,
    whiten: bool = True,
):
    """Gather de fuente virtual: NCF entre `ref_ch` y todos los canales.

    Correlación por ventanas (normalizadas) apiladas linealmente. Devuelve
    (lags_s, gather (n_ch, n_lags), n_windows). El canal de referencia actúa
    como 'fuente virtual': la función de correlación cruzada (NCF) estima la
    función de Green ref→canal, con llegadas en ±offset/v_medio.
    """
    x = bandpass(np.ascontiguousarray(data, dtype=np.float32), fs, *band)
    x = one_bit(x)
    if whiten:
        x = spectral_whiten(x, fs, band)

    n_ch, n_t = x.shape
    L = int(max_lag_s * fs)
    wn = int(win_s * fs)
    hp = max(1, int(hop_s * fs))
    if n_t < wn:
        raise ValueError(f"datos demasiado cortos: {n_t} muestras < ventana {wn}")

    nfft = 1
    while nfft < wn + L + 1:
        nfft *= 2

    acc = np.zeros((n_ch, 2 * L + 1), dtype=np.float64)
    n_win = 0
    for a in range(0, n_t - wn + 1, hp):
        seg = x[:, a : a + wn]
        # normalización por ventana: ninguna ventana ruidosa domina el stack
        seg = seg - seg.mean(axis=1, keepdims=True)
        nrm = np.linalg.norm(seg, axis=1, keepdims=True) + 1e-12
        seg = seg / nrm
        S = np.fft.rfft(seg, n=nfft, axis=1)
        C = S * np.conj(S[ref_ch : ref_ch + 1, :])
        cc = np.fft.irfft(C, n=nfft, axis=1)
        # lags negativos al final del array circular → reordenar a [-L..L]
        gather_w = np.concatenate([cc[:, -L:], cc[:, : L + 1]], axis=1)
        acc += gather_w
        n_win += 1

    lags = np.arange(-L, L + 1) / fs
    return lags, (acc / max(n_win, 1)).astype(np.float32), n_win


def fit_group_velocity(
    lags: np.ndarray,
    gather: np.ndarray,
    ref_ch: int,
    dx: float,
    fs: float,
    v_min: float = 100.0,
    v_max: float = 1200.0,
    min_offset_m: float = 40.0,
    max_offset_m: float = 480.0,
):
    """Mide v_medio del gather: la pendiente offset/tiempo ES la física.

    Método estándar para NCFs (velocidad de grupo por pico de envolvente):
      1. plegar causal+anticausal (la fuente pasó por ambos lados del par:
         ambas ramas están iluminadas),
      2. por cada offset, tomar el tiempo del pico de la envolvente dentro
         de la ventana físicamente admisible [offset/v_max, offset/v_min],
      3. ajustar offset = v·t por mínimos cuadrados PESADOS POR AMPLITUD y
         forzados por el origen (offset 0 ⇒ tiempo 0: no hay intercepto
         físico posible).

    La misma tesis del motor de coherencia — la pendiente es la física —
    en el plano offset-tiempo de la función de Green empírica. Devuelve
    (v_mps, r2, detalle) con detalle=(offsets_m, t_picos_s, amplitudes)
    para auditoría y figura.
    """
    from scipy.signal import hilbert

    n_ch = gather.shape[0]
    L = (gather.shape[1] - 1) // 2
    offsets = (np.arange(n_ch) - ref_ch) * dx
    sel = np.flatnonzero((np.abs(offsets) >= min_offset_m) & (np.abs(offsets) <= max_offset_m))
    if sel.size < 8:
        raise ValueError("muy pocos canales en el rango de offsets pedido")

    folded = 0.5 * (gather[:, L:] + gather[:, L::-1])  # eje t_viaje ∈ [0, L]
    env = np.abs(hilbert(folded[sel], axis=1))

    offs_list: list[float] = []
    t_pk_list: list[float] = []
    amp_list: list[float] = []
    for row, i in enumerate(sel):
        o = abs(float(offsets[i]))
        ka = int(np.floor(o / v_max * fs))
        kb = int(np.ceil(o / v_min * fs))
        ka, kb = max(0, ka), min(L, kb)
        if kb - ka < 2:
            continue
        k = ka + int(np.argmax(env[row, ka : kb + 1]))
        offs_list.append(o)
        t_pk_list.append(k / fs)
        amp_list.append(float(env[row, k]))

    offs = np.asarray(offs_list)
    t_pk = np.asarray(t_pk_list)
    w = np.asarray(amp_list)
    if offs.size < 8 or not np.any(t_pk > 0):
        raise ValueError("sin picos utilizables en la ventana física")

    # offset = v·t por el origen, pesado por amplitud del pico
    v = float((w * offs * t_pk).sum() / ((w * t_pk**2).sum() + 1e-12))
    pred = offs / max(v, 1e-9)
    ss_res = float((w * (t_pk - pred) ** 2).sum())
    mu = float((w * t_pk).sum() / w.sum())
    ss_tot = float((w * (t_pk - mu) ** 2).sum()) + 1e-12
    r2 = max(0.0, 1.0 - ss_res / ss_tot)
    return v, r2, (offs, t_pk, w)


# ---------------------------------------------------------------------------
# Puente con el pipeline: pasadas rastreadas → gather
# ---------------------------------------------------------------------------


def gather_from_tracked_event(
    data: np.ndarray,
    evt: TriggerEvent,
    geom: ArrayGeometry,
    ref_offset_channels: int = 0,
    pad_s: float = 5.0,
    **kwargs,
):
    """Cierra el círculo: un evento FUENTE_MOVIL_TRAFICO se convierte en fuente.

    Recorta la ventana temporal de la pasada (+pad) y usa como referencia el
    canal central del evento (+offset opcional). Todo lo que el pipeline
    descarta como 'no-sismo' entra por acá como iluminación del subsuelo.
    """
    fs = geom.fs_hz
    a = max(0, int((evt.t_start_s - pad_s) * fs))
    b = min(data.shape[1], int((evt.t_end_s + pad_s) * fs))
    ref = min(max(0, (evt.ch_min + evt.ch_max) // 2 + ref_offset_channels), data.shape[0] - 1)
    lags, gather, n_win = virtual_source_gather(data[:, a:b], ref, fs, **kwargs)
    return lags, gather, n_win, ref


# ---------------------------------------------------------------------------
# Experimento validado (verdad-terreno + control negativo + ganancia de stack)
# ---------------------------------------------------------------------------


def _gather_snr(
    lags: np.ndarray,
    gather: np.ndarray,
    ref_ch: int,
    dx: float,
    v_true: float,
    off_lo: float,
    off_hi: float,
) -> float:
    """SNR del gather: energía en la llegada física esperada vs cola tardía."""
    offsets = np.abs((np.arange(gather.shape[0]) - ref_ch) * dx)
    sel = np.flatnonzero((offsets >= off_lo) & (offsets <= off_hi))
    L = (gather.shape[1] - 1) // 2
    fs = 1.0 / (lags[1] - lags[0])
    sig, noi = [], []
    for i in sel:
        t_arr = offsets[i] / v_true
        k = L + int(round(t_arr * fs))
        w = int(0.15 * fs)
        if k + w >= gather.shape[1]:
            continue
        fold = 0.5 * (gather[i, L:] + gather[i, L::-1])
        ka = k - L
        sig.append(np.abs(fold[max(0, ka - w) : ka + w + 1]).max())
        tail = fold[int(len(fold) * 0.7) :]
        noi.append(np.sqrt(np.mean(tail**2)) + 1e-12)
    return float(np.mean(np.array(sig) / np.array(noi)))


def run_demo(make_figs: bool = False, out_dir: str = "figures") -> int:
    """Experimento sintético completo (1 pasada, 2 pasadas, control negativo)
    contra verdad-terreno conocida. Devuelve 0 si las 4 verificaciones pasan."""
    from .synth import add_moving_radiator, make_noise

    print("=" * 74)
    print("INTERFEROMETRÍA DE FUENTE VIRTUAL — experimento con verdad-terreno")
    print("=" * 74)

    fs, dx, n_ch = 50.0, 8.0, 200
    dur_s = 240.0
    v_medium = 400.0  # verdad-terreno: velocidad del medio (onda sup.)
    v_vehiculo = 12.0
    ref = 100
    rng_seeds = (21, 22)

    def build(seed, with_source=True, two_passes=False):
        d = make_noise(n_ch, int(dur_s * fs), fs, seed=seed)
        if with_source:
            add_moving_radiator(
                d,
                fs,
                dx,
                v_vehiculo,
                v_medium,
                x_start_m=-150.0,
                t_start_s=2.0,
                t_end_s=dur_s - 2,
                amp=40.0,
                seed=seed + 100,
            )
            if two_passes:
                add_moving_radiator(
                    d,
                    fs,
                    dx,
                    -v_vehiculo,
                    v_medium,
                    x_start_m=(n_ch - 1) * dx + 150.0,
                    t_start_s=4.0,
                    t_end_s=dur_s - 2,
                    amp=40.0,
                    seed=seed + 200,
                )
        return d

    # Wrappers en vez de **kw/**off sobre un dict: mismos parámetros
    # reutilizados en las 3 pasadas, pero con tipos explícitos (un dict
    # dict(band=(...), max_lag_s=...) se infiere como dict[str, object] y
    # el unpacking pierde la información de tipo por argumento).
    def _gather(d: np.ndarray):
        return virtual_source_gather(
            d, ref, fs, band=(4.0, 16.0), max_lag_s=2.0, win_s=10.0, hop_s=5.0
        )

    def _fit(lags_: np.ndarray, g: np.ndarray):
        return fit_group_velocity(lags_, g, ref, dx, fs, min_offset_m=40.0, max_offset_m=480.0)

    # --- 1 pasada -----------------------------------------------------------
    d1 = build(rng_seeds[0], two_passes=False)
    lags, g1, nw = _gather(d1)
    v1, r2_1, det1 = _fit(lags, g1)
    err1 = abs(v1 - v_medium) / v_medium * 100
    print(
        f"\n1 pasada  ({nw} ventanas): v_medio medida = {v1:.0f} m/s "
        f"(real {v_medium:.0f}, error {err1:.1f}%), R² = {r2_1:.3f}"
    )

    # --- 2 pasadas (stack) ---------------------------------------------------
    d2 = build(rng_seeds[0], two_passes=True)
    _, g2, _ = _gather(d2)
    v2, r2_2, _ = _fit(lags, g2)
    snr1 = _gather_snr(lags, g1, ref, dx, v_medium, off_lo=40, off_hi=480)
    snr2 = _gather_snr(lags, g2, ref, dx, v_medium, off_lo=40, off_hi=480)
    print(
        f"2 pasadas : v = {v2:.0f} m/s, R² = {r2_2:.3f} | "
        f"SNR del gather {snr1:.1f} → {snr2:.1f} (el stack mejora la imagen)"
    )

    # --- control negativo: ruido puro ----------------------------------------
    d0 = build(rng_seeds[1], with_source=False)
    _, g0, _ = _gather(d0)
    try:
        _, r2_0, _ = _fit(lags, g0)
    except ValueError:
        r2_0 = 0.0
    print(
        f"control negativo (sin fuente): R² = {r2_0:.3f} vs {r2_1:.3f} con fuente "
        f"— sin fuente, los picos son aleatorios y el ajuste lineal colapsa"
    )

    checks = [
        (f"v_medio recuperada con error {err1:.1f}% ≤ 10%", err1 <= 10),
        (f"ajuste físico con fuente: R² {r2_1:.2f} ≥ 0.90", r2_1 >= 0.90),
        (f"control negativo: R² {r2_0:.2f} ≤ 0.5 (no alucina velocidad)", r2_0 <= 0.5),
        (f"ganancia de stack: SNR {snr2:.1f} ≥ {snr1:.1f} con 2ª pasada", snr2 >= snr1),
    ]
    print()
    passed = 0
    for msg, ok in checks:
        print(f"  [{'OK ' if ok else 'FALLA'}] {msg}")
        passed += ok
    print(f"\n  RESULTADO: {passed}/{len(checks)} verificaciones del experimento")

    if make_figs:
        _make_fig(lags, g1, det1, ref, dx, v_medium, v1, r2_1, out_dir)

    return 0 if passed == len(checks) else 1


def _make_fig(lags, gather, detail, ref, dx, v_true, v_meas, r2, out_dir):
    import os

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    offsets = (np.arange(gather.shape[0]) - ref) * dx
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5), gridspec_kw={"width_ratios": [1.5, 1]})
    v = np.percentile(np.abs(gather), 99.5) + 1e-12
    ax1.imshow(
        gather,
        aspect="auto",
        cmap="RdBu_r",
        vmin=-v,
        vmax=v,
        extent=[lags[0], lags[-1], offsets[-1], offsets[0]],
    )
    tt = np.linspace(0, max(abs(offsets)) / v_true, 50)
    ax1.plot(tt, tt * v_true, "k--", lw=1.2, label=f"±offset/v_real ({v_true:.0f} m/s)")
    ax1.plot(-tt, tt * v_true, "k--", lw=1.2)
    ax1.plot(tt, -tt * v_true, "k--", lw=1.2)
    ax1.plot(-tt, -tt * v_true, "k--", lw=1.2)
    ax1.set_xlabel("lag (s)")
    ax1.set_ylabel("offset desde la fuente virtual (m)")
    ax1.set_title(
        "Gather de fuente virtual (NCF por canal)\nla 'V' es la función de Green empírica"
    )
    ax1.legend(loc="upper right", fontsize=8)

    offs, t_pk, w = detail
    ax2.scatter(
        t_pk,
        offs,
        s=18 + 60 * (w / (w.max() + 1e-12)),
        alpha=0.65,
        c="steelblue",
        edgecolors="k",
        linewidths=0.4,
        label="pico de envolvente por canal",
    )
    tt2 = np.linspace(0, t_pk.max() * 1.05, 20)
    ax2.plot(tt2, v_meas * tt2, "k--", label=f"ajuste: v = {v_meas:.0f} m/s (R²={r2:.2f})")
    ax2.plot(tt2, v_true * tt2, ":", color="crimson", label=f"real: {v_true:.0f} m/s")
    ax2.set_xlabel("tiempo del pico (s)")
    ax2.set_ylabel("offset (m)")
    ax2.set_title("La pendiente es la física — otra vez:\noffset/tiempo = v del subsuelo")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    path = os.path.join(out_dir, "fig4_interferometria.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"Figura guardada: {path}")


# ---------------------------------------------------------------------------
# CLI para datos reales
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI de interferometry.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--demo",
        action="store_true",
        help="Experimento sintético con verdad-terreno y control negativo",
    )
    ap.add_argument("--figs", action="store_true", help="Generar figura del demo")
    ap.add_argument("--npz", help="Matriz real (canales×tiempo) para gather")
    ap.add_argument("--key", default="data")
    ap.add_argument("--fs", type=float, default=50.0)
    ap.add_argument("--dx", type=float, default=8.0)
    ap.add_argument("--ref-ch", type=int, default=None, help="Canal fuente virtual")
    ap.add_argument("--band", type=float, nargs=2, default=(4.0, 16.0))
    ap.add_argument("--max-lag", type=float, default=2.0)
    ap.add_argument("--out", default="gather_interferometria.npz")
    args = ap.parse_args()

    if args.demo:
        sys.exit(run_demo(make_figs=args.figs))

    if not args.npz:
        ap.error("indicá --demo o --npz")
    with np.load(args.npz) as z:
        data = np.asarray(z[args.key], dtype=np.float32)
    ref = args.ref_ch if args.ref_ch is not None else data.shape[0] // 2
    lags, gather, n_win = virtual_source_gather(
        data, ref, args.fs, band=tuple(args.band), max_lag_s=args.max_lag
    )
    np.savez(args.out, lags=lags, gather=gather, ref_ch=ref, n_windows=n_win)
    print(
        f"Gather ({n_win} ventanas) guardado en {args.out}. "
        f"Nota honesta: con pocos minutos de datos esperá un VISTAZO de la "
        f"función de Green, no un modelo de velocidad."
    )


if __name__ == "__main__":
    main()
