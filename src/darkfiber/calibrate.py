"""
DarkFiber MAS v5 — Motor de calibración (P3).

Lee el ledger + perfil de un arreglo y PROPONE un ajuste de `seismic_min_semblance`
(el umbral que separa SISMO_CONFIRMADO de POSIBLE_REGIONAL_EMERGENTE /
COHERENTE_DESCONOCIDO), re-evaluando OFFLINE los eventos ya en el ledger con
cada valor candidato. La re-evaluación usa las MÉTRICAS YA CACHEADAS
(coincidencia, span, semblanza, v_app) del ledger — no hace falta releer
los .h5 crudos, así que corre instantáneo aunque el archivo original ya no
esté a mano.

El sistema PROPONE con evidencia (qué caso cambia, de qué a qué); un
humano decide. Nada se aplica sin `--apply` explícito, y la propuesta
(aplicada o no) queda registrada en la tabla `proposals` con su evidencia.

Uso:
    python calibrate.py --array-id ridgecrest_north --db quakeflow_ledger.db
    python calibrate.py --array-id ridgecrest_north --db quakeflow_ledger.db --apply --value 0.15
"""

from __future__ import annotations

import argparse

from ._cli_utf8 import ensure_utf8_stdio
from .catalog import SignatureCatalog
from .contracts import CoherenceConfig


def reclassify(f_c, span_frac, s_best, v_best, cfg: CoherenceConfig) -> str | None:
    """Réplica simplificada del árbol de decisión de coherence.py usando
    solo las métricas cacheadas en el ledger (f_c, span_frac, semblanza,
    v_app). No reproduce las ramas de tráfico/supresión por canales
    aislados (esas necesitan el TriggerEvent original) — alcanza para
    explorar el umbral de semblanza, que es el parámetro que este script
    calibra.
    """
    if None in (f_c, span_frac, s_best, v_best):
        return None
    is_seismic = (
        f_c >= cfg.seismic_min_coincidence
        and span_frac >= cfg.seismic_min_span_frac
        and s_best >= cfg.seismic_min_semblance
        and cfg.seismic_v_min_mps <= abs(v_best) <= cfg.seismic_v_max_mps
    )
    if is_seismic:
        return "SISMO_CONFIRMADO"
    if f_c >= cfg.regional_min_coincidence and span_frac >= cfg.regional_min_span_frac:
        return "POSIBLE_REGIONAL_EMERGENTE"
    return "COHERENTE_DESCONOCIDO"


def evaluate_candidate(rows: list[dict], candidate: float) -> list[dict]:
    """Reclasifica cada fila del ledger con `candidate` como umbral y
    devuelve solo las que cambiarían de veredicto."""
    cfg = CoherenceConfig(seismic_min_semblance=candidate)
    changes = []
    for r in rows:
        m = r.get("metrics_json") or {}
        new_verdict = reclassify(
            m.get("coincidence_fraction"),
            m.get("span_fraction"),
            m.get("semblance"),
            m.get("apparent_velocity_mps"),
            cfg,
        )
        old_verdict = r["verdict"]
        if new_verdict is not None and new_verdict != old_verdict:
            changes.append(
                dict(
                    event_file=r["event_file"],
                    old=old_verdict,
                    new=new_verdict,
                    magnitude=(r["gt_json"] or {}).get("magnitude"),
                )
            )
    return changes


def main() -> None:
    """CLI de calibrate.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--array-id", required=True)
    ap.add_argument("--db", default="quakeflow_ledger.db")
    ap.add_argument(
        "--candidates", type=float, nargs="+", default=[0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Escribe el valor propuesto en el perfil del arreglo "
        "(thresholds_json). Sin esto, solo se reporta evidencia.",
    )
    ap.add_argument(
        "--value",
        type=float,
        default=None,
        help="Con --apply, el valor exacto a aplicar (si no se da, "
        "se aplica el primer candidato que no rompe ningún HIT existente)",
    )
    args = ap.parse_args()

    cat = SignatureCatalog(args.db)
    rows = cat.ledger_rows(args.array_id)
    if not rows:
        raise SystemExit(f"no hay filas en el ledger para array_id='{args.array_id}'")

    current = CoherenceConfig().seismic_min_semblance
    print(f"Umbral actual seismic_min_semblance = {current}")
    print(
        f"Evaluando {len(rows)} evento(s) del ledger para '{args.array_id}' contra "
        f"{len(args.candidates)} candidatos (offline, con métricas cacheadas)...\n"
    )

    best_candidate = None
    for c in args.candidates:
        changes = evaluate_candidate(rows, c)
        breaks_a_hit = any(ch["old"] == "SISMO_CONFIRMADO" for ch in changes)
        tag = " (rompería un HIT existente)" if breaks_a_hit else ""
        print(f"  candidato={c:.3f}{tag}")
        for ch in changes:
            print(f"      {ch['event_file']} (M{ch['magnitude']}): {ch['old']} -> {ch['new']}")
        if not changes:
            print("      sin cambios respecto al veredicto ya registrado")
        if best_candidate is None and not breaks_a_hit and changes:
            best_candidate = c

    evidence = {
        "candidates_evaluated": args.candidates,
        "n_ledger_rows": len(rows),
        "changes_per_candidate": {str(c): evaluate_candidate(rows, c) for c in args.candidates},
    }

    if not args.apply:
        proposal_value = args.value if args.value is not None else best_candidate
        if proposal_value is None:
            print(
                "\nNinguna propuesta: ningún candidato cambia algo sin romper un HIT. "
                "Nada que registrar."
            )
            return
        pid = cat.add_proposal(
            args.array_id, "seismic_min_semblance", current, proposal_value, evidence
        )
        print(
            f"\nPropuesta #{pid} registrada (NO aplicada): "
            f"seismic_min_semblance {current} -> {proposal_value}. "
            f"Corré de nuevo con --apply --value {proposal_value} para aplicarla."
        )
        return

    value = args.value if args.value is not None else best_candidate
    if value is None:
        raise SystemExit("--apply requiere --value (o que haya un candidato sin romper HITs)")

    profile = cat.get_array_profile(args.array_id) or {}
    thresholds = dict(profile.get("thresholds_json") or {})
    thresholds["seismic_min_semblance"] = value
    cat.upsert_array_profile(
        args.array_id,
        fs=profile.get("fs") or 0.0,
        dx=profile.get("dx") or 0.0,
        n_ch=profile.get("n_ch") or 0,
        aperture_m=profile.get("aperture_m") or 0.0,
        noise_stats=profile.get("noise_stats_json"),
        thresholds=thresholds,
        synth_recall=profile.get("synth_recall"),
    )
    pid = cat.add_proposal(args.array_id, "seismic_min_semblance", current, value, evidence)
    cat.mark_proposal_applied(pid)
    print(
        f"\nAplicado: seismic_min_semblance = {value} para '{args.array_id}' "
        f"(propuesta #{pid}, con evidencia registrada)."
    )


if __name__ == "__main__":
    main()
