"""
DarkFiber MAS v5 — dashboard.py (C2): panel de operador (Streamlit).

Vistas:
  - **Vivo (demo)**: corre `replay.py` -> `StreamRunner` de punta a punta
    sobre un archivo real ya descargado, y muestra el waterfall
    canal-tiempo del tramo final del buffer con los eventos finalizados
    marcados, más el feed de veredictos con sus `explanations` completas
    -- el veredicto auditable ES el producto, se muestra entero, no un
    resumen.
  - **Catálogo de firmas**: prototipos y desconocidos recurrentes ya
    guardados en el catálogo (`prototypes`/`unknown_clusters`), con el
    flujo de bautizo (`promote()`). El catálogo real todavía está VACÍO
    (`match()`/`promote()` están implementados y testeados pero no están
    conectados a `run_on_quakeflow.py` -- ver CHANGELOG) -- esta vista lo
    dice de forma honesta en vez de simular contenido, y ofrece un
    sembrado de demo EXPLÍCITAMENTE marcado como tal (mismo patrón que
    `run_validation.py`) para poder ejercitar el flujo de bautizo en la
    UI.
  - **Latido**: último auto-test (`synth_recall`), SNR50 y curva
    recall-vs-SNR por arreglo, desde `array_profiles`.
  - **Scoreboard**: matriz de outcomes con IC de Wilson, calculada en
    vivo desde `ledger_rows()` (no parseando el markdown).

Diseño deliberado de la pestaña "Vivo": corre-hasta-el-final (bloqueante,
con spinner), no actualización incremental con hilo de fondo. Streamlit
+ `st.session_state` mutado desde un hilo asyncio en background es un
patrón común pero no oficialmente soportado (carreras de datos posibles);
para una demo -- no un panel de producción de 24h -- correr hasta el
final es más simple y más robusto, y de todas formas ejercita el mismo
pipeline real de punta a punta. Actualización incremental de verdad
queda anotada en `docs/observaciones.md` como mejora futura, no
escondida.

Uso: `darkfiber-dashboard -- --db <ledger.db>` o
`streamlit run src/darkfiber/dashboard.py -- --db <ledger.db>`.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# Imports absolutos a propósito, no relativos: `streamlit run dashboard.py`
# ejecuta este archivo como script standalone (__main__, sin paquete
# padre) -- `from .catalog import ...` revienta con "attempted relative
# import with no known parent package" en ese modo, aunque funcione bien
# corrido como módulo (`python -m darkfiber.dashboard`). Absoluto funciona
# en los dos casos siempre que el paquete esté instalado
# (`pip install -e .`). Encontrado por el propio smoke test
# (`tests/test_dashboard.py`, vía `streamlit.testing.v1.AppTest`, que
# ejecuta el archivo tal como streamlit lo haría) antes de correrlo a mano.
from darkfiber.catalog import SignatureCatalog
from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config
from darkfiber.replay import load_file, replay
from darkfiber.run_on_stanford import sanitize
from darkfiber.stream_runner import StreamRunner

DEFAULT_DB = "quakeflow_ledger.db"

_OUTCOME_ORDER = [
    "HIT",
    "HONEST_UNKNOWN",
    "HONEST_REGIONAL",
    "MISS_SUPPRESSED",
    "MISS_BELOW_FLOOR",
    "CORRECT_REJECTION",
    "FALSE_ALARM",
]


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    args, _unknown = ap.parse_known_args(sys.argv[1:])
    return args


def _wilson_ci(k: int, n: int) -> tuple[float, float]:
    from darkfiber.snr_curve import wilson_ci

    return wilson_ci(k, n)


# --------------------------------------------------------------------
# Vista: Vivo (demo contra replay.py)
# --------------------------------------------------------------------
def _run_replay_demo(path: str, speed: float | None, analysis_interval_s: float) -> dict:
    """Corre replay()->StreamRunner de punta a punta (bloqueante). Devuelve
    un dict con el buffer final, los eventos finalizados, y timing --
    nada de esto toca el ledger (SignatureCatalog no se instancia acá)."""
    data, fs, dx, _attrs = load_file(path)
    data = sanitize(data)
    n_ch = data.shape[0]
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config()
    coh_cfg = CoherenceConfig()

    async def _drive():
        runner = StreamRunner(geom, t0cfg, coh_cfg, analysis_interval_s=analysis_interval_s)
        events = []
        t0 = time.perf_counter()
        async for chunk in replay(data, fs, chunk_s=1.0, speed=speed):
            events.extend(await runner.feed(chunk))
        events.extend(await runner.finish())
        elapsed = time.perf_counter() - t0
        snap = runner.snapshot(tail_s=120.0)
        return events, elapsed, snap

    events, elapsed, snap = asyncio.run(_drive())
    return {
        "path": path,
        "fs": fs,
        "dx": dx,
        "n_channels": n_ch,
        "duration_s": data.shape[1] / fs,
        "events": events,
        "elapsed_s": elapsed,
        "snapshot": snap,
    }


def _waterfall_figure(snapshot: dict, events: list):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    buf = snapshot["buffer"]
    fs = snapshot["fs_hz"]
    if buf is None or buf.size == 0:
        return None
    n_ch, n_t = buf.shape
    # Downsample para que el render no sea gigante en archivos largos.
    stride_t = max(1, n_t // 1500)
    stride_ch = max(1, n_ch // 800)
    view = buf[::stride_ch, ::stride_t]
    t_offset_s = snapshot["duration_s"] - n_t / fs  # inicio del tramo mostrado

    fig, ax = plt.subplots(figsize=(9, 4.5))
    vmax = np.percentile(np.abs(view), 99) or 1.0
    extent = (t_offset_s, snapshot["duration_s"], 0, n_ch)
    ax.imshow(
        view, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-vmax, vmax=vmax, extent=extent
    )
    for evt, _res in events:
        if evt.t_start_s >= t_offset_s:
            ax.axvline(evt.t_start_s, color="black", lw=0.8, alpha=0.7)
    ax.set_xlabel("tiempo (s)")
    ax.set_ylabel("canal")
    ax.set_title(
        f"Waterfall en vivo (último tramo, {n_t / fs:.0f}s) — eventos finalizados marcados"
    )
    fig.tight_layout()
    return fig


def view_vivo() -> None:
    import streamlit as st

    st.subheader("Vivo — demo contra replay.py")
    st.caption(
        "Corre el pipeline real (Nivel 0 + coherencia) en modo streaming sobre un "
        "archivo .h5/.npz ya descargado, exactamente igual que stream_runner.py. "
        "No toca el ledger."
    )
    path = st.text_input(
        "Archivo (.h5 de QuakeFlow o .npz)",
        value=st.session_state.get("vivo_path", ""),
        help=r"Ej: D:\darkfiber\data\quakeflow\ridgecrest_north\ci39493944.h5",
    )
    col1, col2 = st.columns(2)
    speed = col1.number_input("Speed (0 = sin pacing, máxima velocidad)", value=0.0, min_value=0.0)
    interval = col2.number_input("Intervalo de análisis (s)", value=10.0, min_value=1.0)

    if st.button("▶ Correr replay", disabled=not path):
        st.session_state["vivo_path"] = path
        try:
            with st.spinner("Corriendo replay + StreamRunner sobre el archivo completo…"):
                demo_result = _run_replay_demo(path, speed or None, interval)
            st.session_state["vivo_result"] = demo_result
        except Exception as exc:  # noqa: BLE001 -- mostrar el error en la UI, no tumbar la app
            st.error(f"Falló: {exc}")
            st.session_state.pop("vivo_result", None)

    result: dict | None = st.session_state.get("vivo_result")
    if not result:
        st.info("Sin corrida todavía. Indicá un archivo y apretá ▶.")
        return

    n_ev = len(result["events"])
    speedup = (
        result["duration_s"] / result["elapsed_s"] if result["elapsed_s"] > 0 else float("inf")
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Canales", result["n_channels"])
    c2.metric("Duración del archivo", f"{result['duration_s']:.0f}s")
    c3.metric("Eventos finalizados", n_ev)
    c4.metric("Tiempo real / tiempo de archivo", f"{speedup:.1f}×")

    fig = _waterfall_figure(result["snapshot"], result["events"])
    if fig is not None:
        st.pyplot(fig)

    st.markdown("#### Feed de veredictos")
    if not result["events"]:
        st.caption("Ningún evento finalizado en este archivo.")
    for evt, res in sorted(result["events"], key=lambda er: er[0].t_start_s):
        with st.expander(
            f"{evt.event_id} — [{evt.t_start_s:.1f}s, {evt.t_end_s:.1f}s] — {res.classification.value}"
        ):
            for line in res.explanations:
                st.markdown(f"- {line}")
            if not res.explanations:
                st.caption("(sin explanations)")


# --------------------------------------------------------------------
# Vista: Catálogo de firmas
# --------------------------------------------------------------------
def view_catalogo(cat: SignatureCatalog) -> None:
    import streamlit as st

    st.subheader("Catálogo de firmas")
    protos = cat.db.execute(
        "SELECT id, label, zone, array_id, n_events FROM prototypes ORDER BY label"
    ).fetchall()
    unknowns = cat.db.execute(
        "SELECT id, zone, array_id, n_events FROM unknown_clusters ORDER BY n_events DESC"
    ).fetchall()

    if not protos and not unknowns:
        st.info(
            "El catálogo de este ledger está vacío. `catalog.match()`/`promote()` están "
            "implementados y testeados (`tests/test_catalog.py`) pero todavía no están "
            "conectados al pipeline real (`run_on_quakeflow.py` solo usa el catálogo para "
            "el ledger de verdad-terreno y los perfiles de arreglo, no para firmas) -- "
            "ningún evento `COHERENTE_DESCONOCIDO` real llegó a pasar por `match()` "
            "todavía. No es un bug de esta vista; es el estado real del proyecto."
        )
    else:
        st.markdown("#### Prototipos nombrados")
        if protos:
            st.table(
                [
                    {"label": p[1], "zona": p[2], "arreglo": p[3], "ocurrencias": p[4]}
                    for p in protos
                ]
            )
        else:
            st.caption("Ninguno todavía.")

        st.markdown("#### Desconocidos recurrentes")
        if unknowns:
            st.table(
                [{"id": u[0], "zona": u[1], "arreglo": u[2], "ocurrencias": u[3]} for u in unknowns]
            )
            candidate = max(unknowns, key=lambda u: u[3])
            with st.form("bautizo"):
                st.write(
                    f"Bautizar cluster #{candidate[0]} ({candidate[3]} ocurrencias, "
                    f"arreglo {candidate[2]}):"
                )
                label = st.text_input("Nombre nuevo")
                if st.form_submit_button("Bautizar") and label:
                    try:
                        cat.promote(candidate[0], label)
                        st.success(f"'{label}' promovido a prototipo. Recargá la página.")
                    except (KeyError, ValueError) as exc:
                        st.error(str(exc))
        else:
            st.caption("Ninguno todavía.")

    st.divider()
    st.caption(
        "Demo (vectores sintéticos, mismo patrón que `run_validation.py` -- NO usa "
        "datos reales ni toca el ledger de verdad-terreno):"
    )
    if st.button("Sembrar demo de bautizo"):
        rng = np.random.default_rng(0)
        proto_vec = rng.standard_normal(64).astype(np.float32)
        match = None
        for _ in range(4):
            vec = proto_vec + 0.05 * rng.standard_normal(64).astype(np.float32)
            match = cat.match(vec, zone="demo_dashboard", array_id="demo")
        assert match is not None  # range(4) siempre itera al menos una vez
        st.success(
            f"Sembrado: cluster #{match.recurring_unknown_id}, "
            f"{match.recurring_count} ocurrencias, sugerir_nombre={match.suggest_naming}. "
            "Recargá la página para verlo arriba."
        )


# --------------------------------------------------------------------
# Vista: Latido
# --------------------------------------------------------------------
def view_latido(cat: SignatureCatalog) -> None:
    import streamlit as st

    st.subheader("Latido — auto-test y detectabilidad por arreglo")
    rows = cat.db.execute(
        "SELECT array_id, synth_recall, snr50, recall_curve_json, updated, thresholds_json "
        "FROM array_profiles ORDER BY array_id"
    ).fetchall()
    if not rows:
        st.info("Sin perfiles de arreglo en este ledger todavía.")
        return

    for array_id, synth_recall, snr50, recall_curve_json, updated, thresholds_json in rows:
        with st.container(border=True):
            st.markdown(f"**{array_id}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("SNR50", f"{snr50:.2f}" if snr50 is not None else "—")
            c2.metric(
                "synth_recall (auto-test legado)",
                f"{synth_recall * 100:.0f}%" if synth_recall is not None else "—",
            )
            age_s = (time.time() - updated) if updated else None
            c3.metric("Última actualización", f"hace {age_s / 3600:.1f}h" if age_s else "—")
            if thresholds_json:
                st.caption(f"Umbrales: `{thresholds_json}`")
            if recall_curve_json:
                import json

                curve = json.loads(recall_curve_json)
                st.line_chart(
                    {
                        "SNR": [c["snr"] for c in curve],
                        "recall": [c["recall"] * 100 for c in curve],
                    },
                    x="SNR",
                    y="recall",
                )


# --------------------------------------------------------------------
# Vista: Scoreboard
# --------------------------------------------------------------------
def view_scoreboard(cat: SignatureCatalog) -> None:
    import streamlit as st

    st.subheader("Scoreboard — matriz de outcomes (IC 95% Wilson)")
    rows = cat.ledger_rows()
    if not rows:
        st.info("Ledger vacío.")
        return

    gt_rows = [r for r in rows if r["gt_json"] is not None]
    non_gt_rows = [r for r in rows if r["gt_json"] is None]
    n = len(gt_rows)
    counts = {k: 0 for k in _OUTCOME_ORDER}
    for r in gt_rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    n_neg = len(non_gt_rows)
    cr = sum(1 for r in non_gt_rows if r["outcome"] == "CORRECT_REJECTION")
    fa = sum(1 for r in non_gt_rows if r["outcome"] == "FALSE_ALARM")

    table = []
    for outcome in (
        "HIT",
        "HONEST_UNKNOWN",
        "HONEST_REGIONAL",
        "MISS_SUPPRESSED",
        "MISS_BELOW_FLOOR",
    ):
        k = counts.get(outcome, 0)
        lo, hi = _wilson_ci(k, n) if n else (0.0, 0.0)
        table.append(
            {
                "outcome": outcome,
                "n/N": f"{k}/{n}",
                "tasa": f"{k / n * 100:.1f}%" if n else "—",
                "IC 95%": f"[{lo * 100:.1f}%, {hi * 100:.1f}%]" if n else "—",
            }
        )
    st.table(table)
    if n_neg:
        lo_cr, hi_cr = _wilson_ci(cr, n_neg)
        lo_fa, hi_fa = _wilson_ci(fa, n_neg)
        st.markdown(
            f"Archivos sin catálogo: **{cr}/{n_neg}** CORRECT_REJECTION "
            f"(IC [{lo_cr * 100:.1f}%, {hi_cr * 100:.1f}%]), **{fa}/{n_neg}** FALSE_ALARM "
            f"(IC [{lo_fa * 100:.1f}%, {hi_fa * 100:.1f}%])."
        )

    st.markdown("#### Por arreglo")
    by_array: dict[str, list] = {}
    for r in rows:
        by_array.setdefault(r["array_id"], []).append(r)
    for array_id, arows in sorted(by_array.items()):
        with st.expander(f"{array_id} ({len(arows)} archivos)"):
            st.table(
                [
                    {
                        "archivo": r["event_file"],
                        # Columna forzada a texto a propósito: mezclar
                        # float (magnitud real) con "—" (sin verdad-terreno)
                        # en la misma columna rompe la conversión a Arrow
                        # de Streamlit (encontrado corriendo esto contra el
                        # ledger real -- st.table lo "arregla" solo pero en
                        # silencio, mejor no depender de eso).
                        "magnitud": (
                            f"{m:.2f}"
                            if isinstance(m := (r["gt_json"] or {}).get("magnitude"), int | float)
                            else "—"
                        ),
                        "veredicto": r["verdict"] or "—",
                        "outcome": r["outcome"],
                    }
                    for r in sorted(arows, key=lambda r: r["event_file"])
                ]
            )


# --------------------------------------------------------------------
def main() -> None:
    """Punto de entrada del console script: relanza vía `streamlit run`
    (una app Streamlit no se ejecuta como un script Python normal)."""
    args = sys.argv[1:]
    cmd = [sys.executable, "-m", "streamlit", "run", __file__]
    if args:
        cmd += ["--"] + args
    subprocess.run(cmd, check=True)


def _streamlit_app() -> None:
    import streamlit as st

    st.set_page_config(page_title="DarkFiber — Panel de Operador", layout="wide", page_icon="🛰️")
    args = _parse_args()
    db_exists = Path(args.db).exists()
    st.title("🛰️ DarkFiber — Panel de Operador")
    if not db_exists:
        st.warning(
            f"No se encontró `{args.db}`. Corré con `--db <ruta>`, o esta demo va a crear "
            "un ledger vacío nuevo ahí -- ninguna de las vistas de abajo va a tener datos "
            "reales hasta que apuntes al ledger correcto."
        )
    cat = SignatureCatalog(args.db)

    tab_vivo, tab_catalogo, tab_latido, tab_scoreboard = st.tabs(
        ["Vivo (demo)", "Catálogo de firmas", "Latido", "Scoreboard"]
    )
    with tab_vivo:
        view_vivo()
    with tab_catalogo:
        view_catalogo(cat)
    with tab_latido:
        view_latido(cat)
    with tab_scoreboard:
        view_scoreboard(cat)


if __name__ == "__main__":
    # `streamlit run dashboard.py` importa este archivo como __main__ y lo
    # ejecuta de punta a punta -- por eso la app real vive en
    # _streamlit_app(), no en main() (que es el entry point del console
    # script, y relanza esto vía subprocess).
    _streamlit_app()
