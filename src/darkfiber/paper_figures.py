"""
DarkFiber MAS v5 — Figuras del manuscrito de Fase 2 (paper, technical note).

Pre-registrado en `docs/plan_fase2_paper.md` (Comanda F2.D). Genera las 4
figuras del manuscrito EXCLUSIVAMENTE desde los `figures/snr_curve_<id>.json`
congelados y las funciones ya testeadas de `series_robustness.py` -- ningún
SNR50, ρ, envolvente o cota se recalcula fuera de ese módulo; este archivo
solo dibuja lo que `series_robustness.py` ya produjo y verificó. La única
cantidad nueva acá es la correlación de Spearman OBSERVADA (ρ real, no la
cota de peor caso) entre cada proxy y los 8 SNR50 medidos, con su p-valor
EXACTO (enumeración de las 8! permutaciones, misma convención que
`derive_critical_rho_n8_two_tailed` -- Pearson sobre rangos promedio, ver
`RANK_CONVENTION`), necesaria para la Figura 2 y ausente del pre-registro
original de `series_robustness.py`.

Reproducibilidad bit a bit: matplotlib embebe un `CreationDate` en el PDF y
un `Software` en el PNG -- verificado empíricamente (no asumido) que
`metadata={'CreationDate': None}` / `metadata={'Software': None}` alcanza
para byte-identidad entre corridas, sin necesitar `SOURCE_DATE_EPOCH`. Ver
`tests/test_paper_figures.py::test_regeneration_is_bit_identical`.

Uso: python -m darkfiber.paper_figures [--out-dir figures/paper]
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from datetime import datetime, timezone

from ._cli_utf8 import ensure_utf8_stdio
from .series_robustness import (
    ARRAY_IDS,
    GEOMETRY,
    PROXIES,
    RANK_CONVENTION,
    build_report,
    derive_critical_rho_n8_two_tailed,
    load_curve_json,
    sha256_file,
    spearman_rho,
)

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "figures")

PROXY_LABELS = {
    "n_ch": "n_ch (canales)",
    "dx": "dx (espaciado, m)",
    "aperture_m": "apertura (m)",
    "fs": "fs (Hz)",
}

DISPLAY_NAMES = {
    "monterey_bay": "monterey_bay",
    "foresee": "FORESEE",
    "stanford2_sandhill": "Stanford-2",
    "valencia_submarine": "Valencia",
    "ridgecrest_north": "ridgecrest_north",
    "fossa": "FOSSA",
    "stanford1_campus": "stanford1_campus",
    "arcata": "arcata",
}

SNR_GRID = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]


def observed_proxy_correlations(point_snr50: dict[str, float]) -> dict[str, dict]:
    """ρ de Spearman OBSERVADO (no la cota de peor caso) entre cada proxy y
    los 8 SNR50 medidos, con p-valor EXACTO por enumeración de las 8!
    permutaciones -- misma convención de rangos que el resto del módulo
    (Pearson sobre rangos promedio, ver `RANK_CONVENTION`), no una
    aproximación asintótica (t de Student). Reutiliza `spearman_rho` de
    `series_robustness.py`, no reimplementa la correlación.
    """
    snr_vec = [point_snr50[a] for a in ARRAY_IDS]
    ranks_1_to_n = list(range(1, len(ARRAY_IDS) + 1))
    out: dict[str, dict] = {}
    for proxy in PROXIES:
        proxy_vec = [GEOMETRY[a][proxy] for a in ARRAY_IDS]
        rho_obs = spearman_rho(snr_vec, proxy_vec)
        total = 0
        extreme = 0
        for perm in itertools.permutations(ranks_1_to_n):
            total += 1
            rho = spearman_rho(list(perm), proxy_vec)
            if abs(rho) >= abs(rho_obs) - 1e-12:
                extreme += 1
        out[proxy] = dict(rho=rho_obs, p_exact=extreme / total, n_permutations=total)
    return out


def is_measured_point(curve: list[dict]) -> bool:
    """True si algún escalón de la curva tiene recall==0.5 EXACTO -- el
    SNR50 de ese array es un punto medido, no interpolado (hoy solo
    arcata, ver docs/plan_fase2_paper.md §2.1)."""
    return any(r["recall"] == 0.5 for r in curve)


def _safe_relpath(path: str) -> str:
    """`os.path.relpath` explota en Windows si `path` y el cwd están en
    unidades distintas (ValueError: path is on mount 'C:', start on mount
    'D:') -- un caso real (carpeta de salida fuera del repo, ej. para
    verificar reproducibilidad sin ensuciar `figures/`), no hipotético.
    Cae a la ruta absoluta en vez de reventar."""
    try:
        return os.path.relpath(path)
    except ValueError:
        return os.path.abspath(path)


def _write_sidecar(
    fig_path_base: str, script_path: str, input_files: list[str], extra: dict
) -> str:
    """Sidecar JSON con provenance completa: input_files + sha256 de cada
    uno, hash del script generador, timestamp. Un sidecar por figura."""
    entries = []
    for f in input_files:
        entries.append(dict(path=_safe_relpath(f), sha256=sha256_file(f)))
    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha256_file(script_path),
        script_path=_safe_relpath(script_path),
        input_files=entries,
        outputs={},
        **extra,
    )
    for ext in ("pdf", "png"):
        out_path = f"{fig_path_base}.{ext}"
        if os.path.exists(out_path):
            payload["outputs"][ext] = dict(
                path=_safe_relpath(out_path), sha256=sha256_file(out_path)
            )
    sidecar_path = f"{fig_path_base}.sidecar.json"
    with open(sidecar_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return sidecar_path


def _savefig(fig, path_base: str) -> None:
    fig.savefig(f"{path_base}.pdf", metadata={"CreationDate": None}, bbox_inches="tight")
    fig.savefig(f"{path_base}.png", dpi=300, metadata={"Software": None}, bbox_inches="tight")


def _viridis_colors(n: int):
    import matplotlib

    cmap = matplotlib.colormaps["viridis"]
    return [cmap(i / (n - 1)) for i in range(n)]


def fig1_recall_curves(out_dir: str, script_path: str) -> None:
    """Figura 1 -- las 8 curvas recall-vs-SNR, superpuestas, ordenadas por
    SNR50 ascendente. La figura más importante del paper: es el entregable
    del protocolo."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = build_report()
    rows = sorted(report["arrays"], key=lambda r: r["snr50_rederived"])
    colors = _viridis_colors(len(rows))
    input_files = [os.path.join(FIGURES_DIR, f"snr_curve_{r['array_id']}.json") for r in rows]

    fig, ax = plt.subplots(figsize=(8.5, 6))
    for row, color in zip(rows, colors, strict=False):
        d = load_curve_json(row["array_id"])
        curve = sorted(d["curve"], key=lambda r: r["snr"])
        snrs = [c["snr"] for c in curve]
        recalls = [c["recall"] for c in curve]
        ci_lo = [c["recall"] - c["ci_low"] for c in curve]
        ci_hi = [c["ci_high"] - c["recall"] for c in curve]
        label = DISPLAY_NAMES[row["array_id"]]
        ax.errorbar(
            snrs,
            recalls,
            yerr=[ci_lo, ci_hi],
            fmt="o-",
            color=color,
            label=f"{label} (SNR50={row['snr50_rederived']:.2f})",
            capsize=2,
            markersize=4,
            linewidth=1.2,
            elinewidth=0.8,
        )
        measured = is_measured_point(curve)
        marker = "*" if measured else "D"
        marker_size = 220 if measured else 90
        ax.scatter(
            [row["snr50_rederived"]],
            [0.5],
            marker=marker,
            s=marker_size,
            facecolor=color,
            edgecolor="black",
            linewidth=0.8,
            zorder=5,
        )
        lo, hi = row["envelope"]
        ax.plot([lo, hi], [0.5, 0.5], color=color, linewidth=3.5, alpha=0.35, zorder=3)

    ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.8, zorder=1)
    # Lineal a propósito, NO logarítmica: en log los huecos entre escalones
    # (1,1,2,3,4,8 unidades de SNR) se ven casi parejos y esconden
    # exactamente lo que hay que mostrar -- que la grilla se abre hacia
    # arriba y la precisión de SNR50 se degrada ahí (Limitaciones).
    ax.set_xticks(SNR_GRID)
    ax.set_xlim(0.3, 20.7)
    ax.set_ylim(-0.03, 1.05)
    ax.set_xlabel("SNR (lineal, adimensional)")
    ax.set_ylabel("recall")
    ax.set_title("Recall vs. SNR, 8 instalaciones — IC Wilson 95% por punto (n=20/escalón)")
    ax.legend(fontsize=7.5, loc="lower right", ncol=1, framealpha=0.9)
    ax.text(
        0.02,
        0.98,
        "★ = SNR50 medido (punto exacto, recall=50.0%) · ◆ = SNR50 interpolado\n"
        "barra horizontal = envolvente propagada (NO es un intervalo de confianza)\n"
        "grilla de SNR no uniforme (1,2,3,5,8,12,20) -- la precisión de SNR50\n"
        "se degrada hacia arriba (ver Limitaciones). Valencia y FOSSA no\n"
        "alcanzan 100% de recall dentro del rango barrido (ver Limitaciones).",
        transform=ax.transAxes,
        fontsize=6.5,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="lightgray"),
    )
    fig.tight_layout()

    path_base = os.path.join(out_dir, "fig1_recall_curves")
    _savefig(fig, path_base)
    plt.close(fig)
    _write_sidecar(
        path_base,
        script_path,
        input_files,
        extra=dict(
            figure="fig1_recall_curves",
            description="8 curvas recall-vs-SNR con IC Wilson, SNR50 y envolvente",
        ),
    )


def fig2_proxy_scatter(out_dir: str, script_path: str) -> None:
    """Figura 2 -- 4 paneles SNR50 vs. cada proxy, con ρ de Spearman
    observado + p exacto + umbral crítico marcado."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = build_report()
    rows = sorted(report["arrays"], key=lambda r: r["snr50_rederived"])
    colors = _viridis_colors(len(rows))
    point_snr50 = {r["array_id"]: r["snr50_rederived"] for r in rows}
    correlations = observed_proxy_correlations(point_snr50)
    critical = derive_critical_rho_n8_two_tailed()
    critical_rho = critical["critical_rho"]
    input_files = [os.path.join(FIGURES_DIR, f"snr_curve_{r['array_id']}.json") for r in rows]

    fig, axes = plt.subplots(2, 2, figsize=(9, 7.5))
    for ax, proxy in zip(axes.flat, PROXIES, strict=False):
        xs = [GEOMETRY[r["array_id"]][proxy] for r in rows]
        ys = [r["snr50_rederived"] for r in rows]
        for x, y, color in zip(xs, ys, colors, strict=False):
            ax.scatter([x], [y], color=color, s=60, edgecolor="black", linewidth=0.5, zorder=3)
        corr = correlations[proxy]
        ax.set_xlabel(PROXY_LABELS[proxy])
        ax.set_ylabel("SNR50")
        crosses = "SÍ cruza" if abs(corr["rho"]) >= critical_rho else "no cruza"
        ax.set_title(
            f"ρ = {corr['rho']:+.4f}, p = {corr['p_exact']:.4f} ({crosses} |ρ|≥{critical_rho:.4f})",
            fontsize=9,
        )
        if proxy in ("n_ch", "aperture_m", "fs"):
            ax.set_xscale("log")
        ax.grid(True, alpha=0.25, linewidth=0.5)

    fig.suptitle(
        f"SNR50 vs. proxies de geometría/adquisición — umbral crítico |ρ| = {critical_rho:.4f} "
        f"(n=8, dos colas, α={critical['alpha']})",
        fontsize=10,
    )
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=c,
            markeredgecolor="black",
            markersize=7,
            label=DISPLAY_NAMES[r["array_id"]],
        )
        for r, c in zip(rows, colors, strict=False)
    ]
    fig.legend(
        handles=handles, loc="lower center", ncol=4, fontsize=7.5, bbox_to_anchor=(0.5, -0.02)
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))

    path_base = os.path.join(out_dir, "fig2_proxy_scatter")
    _savefig(fig, path_base)
    plt.close(fig)
    _write_sidecar(
        path_base,
        script_path,
        input_files,
        extra=dict(
            figure="fig2_proxy_scatter",
            description="4 paneles SNR50 vs n_ch/dx/aperture_m/fs con rho observado y p exacto",
            rank_convention=RANK_CONVENTION,
            observed_correlations=correlations,
            critical_rho_n8_two_tailed=critical,
        ),
    )


def fig3_ordered_series(out_dir: str, script_path: str) -> None:
    """Figura 3 -- los 8 SNR50 ordenados con su envolvente propagada."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = build_report()
    rows = sorted(report["arrays"], key=lambda r: r["snr50_rederived"])
    colors = _viridis_colors(len(rows))
    input_files = [os.path.join(FIGURES_DIR, f"snr_curve_{r['array_id']}.json") for r in rows]

    fig, ax = plt.subplots(figsize=(7, 5))
    ypos = list(range(len(rows)))
    for y, row, color in zip(ypos, rows, colors, strict=False):
        lo, hi = row["envelope"]
        ax.plot([lo, hi], [y, y], color=color, linewidth=6, alpha=0.35, zorder=1, label=None)
        ax.scatter(
            [row["snr50_rederived"]],
            [y],
            color=color,
            s=90,
            edgecolor="black",
            linewidth=0.7,
            zorder=3,
        )
        ax.text(
            hi + 0.15,
            y,
            f"{DISPLAY_NAMES[row['array_id']]}  {row['snr50_rederived']:.2f}",
            va="center",
            fontsize=8.5,
        )

    lo_min = min(r["snr50_rederived"] for r in rows)
    hi_max = max(r["snr50_rederived"] for r in rows)
    ax.set_yticks([])
    ax.set_xlabel("SNR50")
    ax.set_xlim(0, hi_max * 1.9)
    ax.set_title(
        f"Serie SNR50 ordenada — rango {lo_min:.2f}–{hi_max:.2f}, "
        f"cociente entre extremos {hi_max / lo_min:.2f}×"
    )
    ax.text(
        0.98,
        0.02,
        "barra = envolvente propagada (NO es un intervalo de confianza)",
        transform=ax.transAxes,
        fontsize=7,
        ha="right",
        va="bottom",
        style="italic",
    )
    fig.tight_layout()

    path_base = os.path.join(out_dir, "fig3_ordered_series")
    _savefig(fig, path_base)
    plt.close(fig)
    _write_sidecar(
        path_base,
        script_path,
        input_files,
        extra=dict(
            figure="fig3_ordered_series",
            description="8 SNR50 ordenados con envolvente propagada",
            point_spread=hi_max / lo_min,
        ),
    )


def fig4_protocol_schema(out_dir: str, script_path: str) -> None:
    """Figura 4 -- esquema del protocolo, sin datos. Primera que se recorta
    si hace falta espacio."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrow, FancyBboxPatch

    steps = [
        "Ruido real\ndel sitio",
        "Inyección sintética\na SNR conocido",
        "Pipeline de\ndetección completo\n(Tier0 + Coherencia)",
        "Curva de\nrecall vs. SNR",
        "SNR50",
    ]

    fig, ax = plt.subplots(figsize=(11, 2.6))
    n = len(steps)
    box_w, box_h = 1.7, 1.1
    gap = 0.55
    total_w = n * box_w + (n - 1) * gap
    x0 = -total_w / 2
    xs = []
    for i, label in enumerate(steps):
        x = x0 + i * (box_w + gap)
        xs.append(x)
        box = FancyBboxPatch(
            (x, -box_h / 2),
            box_w,
            box_h,
            boxstyle="round,pad=0.08",
            facecolor="#dde6f0",
            edgecolor="#1a355e",
            linewidth=1.2,
        )
        ax.add_patch(box)
        ax.text(x + box_w / 2, 0, label, ha="center", va="center", fontsize=8.5)
        if i < n - 1:
            arrow_x0 = x + box_w + 0.05
            arrow_len = gap - 0.10
            ax.add_patch(
                FancyArrow(
                    arrow_x0,
                    0,
                    arrow_len,
                    0,
                    width=0.02,
                    head_width=0.18,
                    head_length=0.12,
                    length_includes_head=True,
                    facecolor="#1a355e",
                    edgecolor="none",
                )
            )

    ax.set_xlim(x0 - 0.3, xs[-1] + box_w + 0.3)
    ax.set_ylim(-1.1, 1.1)
    ax.axis("off")
    ax.set_title("Protocolo de aceptación de sitio: de ruido real a SNR50", fontsize=10)
    fig.tight_layout()

    path_base = os.path.join(out_dir, "fig4_protocol_schema")
    _savefig(fig, path_base)
    plt.close(fig)
    _write_sidecar(
        path_base,
        script_path,
        input_files=[],
        extra=dict(
            figure="fig4_protocol_schema",
            description="Esquema del protocolo, sin datos (no lee ningún JSON de entrada)",
        ),
    )


def generate_all(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    script_path = os.path.abspath(__file__)
    fig1_recall_curves(out_dir, script_path)
    fig2_proxy_scatter(out_dir, script_path)
    fig3_ordered_series(out_dir, script_path)
    fig4_protocol_schema(out_dir, script_path)


def main() -> None:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--out-dir",
        default=os.path.join(FIGURES_DIR, "paper"),
        help="Carpeta de salida (default: figures/paper)",
    )
    args = ap.parse_args()
    generate_all(args.out_dir)
    print(f"4 figuras + 4 sidecars escritas en {_safe_relpath(args.out_dir)}")


if __name__ == "__main__":
    main()
