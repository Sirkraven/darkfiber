"""
DarkFiber MAS v5 — Motor de calibración (P3).

Lee el ledger + perfil de un arreglo y PROPONE un ajuste de `seismic_min_semblance`
(el umbral que separa SISMO_CONFIRMADO de POSIBLE_REGIONAL_EMERGENTE /
COHERENTE_DESCONOCIDO), re-evaluando OFFLINE los eventos ya en el ledger con
cada valor candidato. La re-evaluación usa las MÉTRICAS YA CACHEADAS
(coincidencia, span, semblanza, v_app) del ledger — no hace falta releer
los .h5 crudos, así que corre instantáneo aunque el archivo original ya no
esté a mano.

A6 agrega un SEGUNDO modo (`--dir` + `--param tier0_threshold`): propone un
ajuste de `Tier0Config.threshold` (STA/LTA, Nivel 0) con evidencia de la
evidencia real de piso de ruido de un arreglo (encontrada en A5: Ridgecrest
dispara de forma sostenida en cientos de canales a la vez, más de lo que
este umbral anticipa). A diferencia del modo de semblanza, éste SÍ necesita
releer los .h5 crudos (Tier0 no deja métricas cacheadas reutilizables en el
ledger) y corre además un chequeo SINTÉTICO (`synthetic_sanity_check`)
contra `run_validation.py` para no proponer un umbral que rompa el recall
ya validado.

El sistema PROPONE con evidencia (qué caso cambia, de qué a qué); un
humano decide. Nada se aplica sin `--apply` explícito, y la propuesta
(aplicada o no) queda registrada en la tabla `proposals` con su evidencia.

Uso:
    python calibrate.py --array-id ridgecrest_north --db quakeflow_ledger.db
    python calibrate.py --array-id ridgecrest_north --db quakeflow_ledger.db --apply --value 0.15
    python calibrate.py --array-id ridgecrest_north --param tier0_threshold --dir ../../das_data/ridgecrest
"""

from __future__ import annotations

import argparse
import glob
import os

from ._cli_utf8 import ensure_utf8_stdio
from .catalog import SignatureCatalog
from .contracts import ArrayGeometry, CoherenceConfig, EventClass, OutcomeLabel, Tier0Config


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


# ---------------------------------------------------------------------------
# A6: calibración de Tier0Config.threshold (STA/LTA, Nivel 0) por evidencia
# real de piso de ruido de un arreglo. A diferencia de evaluate_candidate()
# arriba, esto SÍ necesita releer los .h5 crudos: el ledger no cachea nada
# de Tier0 (raster, ratio) que permita re-evaluar un threshold distinto
# offline.
# ---------------------------------------------------------------------------


def simulate_file_at_threshold(
    path: str, array_id: str, threshold: float
) -> tuple[str | None, str]:
    """Corre Tier0 + coherencia sobre UN .h5 crudo a un `threshold`
    candidato, SIN escribir al ledger (dry-run). Delega en
    `run_on_quakeflow.decide_outcome` -- la MISMA lógica de decisión que
    `process_file` usa en producción (A8: antes de esto había una réplica
    acá que nunca se enteró del fallback de A7 para archivos sin
    `event_time_index`, así que sistemáticamente devolvía "N/A" para
    Arcata y nunca evaluaba los archivos sin verdad-terreno de Monterey
    Bay -- exactamente los dos casos que la calibración simétrica de A8
    necesita)."""
    from .coherence import CoherenceAgent
    from .run_on_quakeflow import (
        build_ground_truth,
        decide_outcome,
        load_quakeflow_h5,
        valid_event_index,
    )
    from .run_on_stanford import sanitize
    from .synth import bandpass
    from .triage import extract_events, sta_lta_ratio, trigger_raster

    data, fs, dx, attrs = load_quakeflow_h5(path)
    n_ch = data.shape[0]
    data = sanitize(data)
    data = bandpass(data, fs)
    gt = build_ground_truth(attrs, array_id)
    idx = valid_event_index(attrs)
    origin_s = float(idx) / fs if idx is not None else None

    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config(threshold=threshold)
    agent = CoherenceAgent(geom, CoherenceConfig(), tier0_threshold=threshold)
    ratio = sta_lta_ratio(data, geom, t0cfg)
    raster = trigger_raster(ratio, t0cfg)
    events = extract_events(raster, ratio, geom, t0cfg)

    dec = decide_outcome(data, ratio, raster, events, gt, origin_s, None, agent)
    classification = dec.best_res.classification.value if dec.best_res is not None else None
    return classification, dec.outcome.value


def evaluate_tier0_candidates(files: list[str], array_id: str, candidates: list[float]) -> dict:
    """Evidencia real: para cada threshold candidato, el (verdict, outcome)
    de cada archivo. current=threshold actual (4.0) siempre incluido para
    que la comparación sea contra la línea de base, no entre candidatos."""
    all_thresholds = sorted(set(candidates) | {Tier0Config().threshold})
    out = {}
    for thr in all_thresholds:
        out[thr] = {
            os.path.basename(f): simulate_file_at_threshold(f, array_id, thr) for f in files
        }
    return out


def synthetic_sanity_check(threshold: float) -> dict:
    """Chequeo sintético OBLIGATORIO antes de proponer un threshold real
    (A6, "sintéticos incluidos"): recall del battery de 5 inyecciones de
    `run_validation.py` (mismo ruido/semillas) a este threshold, más tres
    invariantes estructurales que un threshold más alto podría romper sin
    que el recall solo lo muestre:
      - escenario A: la fase P débil debe seguir uniéndose a la S en UN
        solo veredicto SISMO_CONFIRMADO (no fragmentarse ni dejar de
        disparar del todo).
      - escenario C: el falso positivo de un canal (el arquetipo de v4)
        debe seguir generando un candidato Tier0 Y seguir suprimido -- no
        desaparecer en silencio.
      - escenario F: los dos sismos separados en el tiempo (A5) deben
        seguir dando 2 veredictos SISMO_CONFIRMADO independientes.
    No reemplaza a `run_validation.py` -- es la evidencia mínima que este
    script necesita ANTES de proponer un threshold real."""
    from . import run_validation as rv
    from .coherence import CoherenceAgent
    from .selftest import inject_and_verify, recall_gauge
    from .triage import extract_events, sta_lta_ratio, trigger_raster

    t0cfg = Tier0Config(threshold=threshold)
    coh_cfg = CoherenceConfig()
    scenarios, base = rv.build_scenarios()
    agent = CoherenceAgent(rv.GEOM, coh_cfg, tier0_threshold=threshold)

    results = []
    for k, (v, snr) in enumerate([(2500, 4), (3200, 3), (4500, 5), (6000, 4), (3500, 2.5)]):
        r = inject_and_verify(base, rv.GEOM, t0cfg, coh_cfg, v_app_mps=v, snr=snr, seed=100 + k)
        results.append(r)
    recall = recall_gauge(results)

    def _events(name):
        data = scenarios[name]
        ratio = sta_lta_ratio(data, rv.GEOM, t0cfg)
        raster = trigger_raster(ratio, t0cfg)
        events = extract_events(raster, ratio, rv.GEOM, t0cfg)
        return data, ratio, raster, [agent.analyze(data, ratio, raster, e) for e in events]

    _, _, _, res_a = _events("A_sismo")
    a_ok = sum(1 for r in res_a if r.classification == EventClass.SEISMIC_CONFIRMED) == 1

    _, _, _, res_c = _events("C_falso_positivo_local")
    c_ok = any(r.suppressed_false_positive for r in res_c)

    _, _, _, res_f = _events("F_dos_sismos_separados")
    f_ok = sum(1 for r in res_f if r.classification == EventClass.SEISMIC_CONFIRMED) == 2

    return {
        "threshold": threshold,
        "recall_5inj": recall,
        "scenario_A_ok": a_ok,
        "scenario_C_ok": c_ok,
        "scenario_F_ok": f_ok,
        "all_ok": a_ok and c_ok and f_ok,
    }


def run_tier0_calibration(
    cat: SignatureCatalog,
    array_id: str,
    files: list[str],
    candidates: list[float],
    apply_value: float | None,
    do_apply: bool,
) -> None:
    print(
        f"Evaluando threshold de Tier0 sobre {len(files)} archivo(s) crudo(s) de '{array_id}' "
        f"(evidencia real) + chequeo sintético contra run_validation.py...\n"
    )

    current = Tier0Config().threshold
    real_evidence = evaluate_tier0_candidates(files, array_id, candidates)

    print("=== Evidencia real (por archivo, verdict -> outcome) ===")
    for thr in sorted(real_evidence):
        tag = " (actual)" if thr == current else ""
        print(f"\n  threshold={thr}{tag}")
        for fname, (verdict, outcome) in sorted(real_evidence[thr].items()):
            print(f"    {fname}: {verdict} -> {outcome}")

    print("\n=== Chequeo sintético (obligatorio antes de proponer) ===")
    synth_evidence = {}
    for thr in sorted(set(candidates) | {current}):
        s = synthetic_sanity_check(thr)
        synth_evidence[thr] = s
        tag = " (actual)" if thr == current else ""
        status = "OK" if s["all_ok"] else "ROMPE invariante sintético"
        print(
            f"  threshold={thr}{tag}: recall_5inj={s['recall_5inj'] * 100:.0f}% "
            f"escenA={s['scenario_A_ok']} escenC={s['scenario_C_ok']} escenF={s['scenario_F_ok']} [{status}]"
        )

    print(f"\n=== Comparación contra la línea de base (threshold actual = {current}) ===")
    baseline = real_evidence[current]
    _HONEST = {
        OutcomeLabel.HIT.value,
        OutcomeLabel.HONEST_UNKNOWN.value,
        OutcomeLabel.HONEST_REGIONAL.value,
    }
    _BAD = {OutcomeLabel.MISS_SUPPRESSED.value, OutcomeLabel.FALSE_ALARM.value}
    best_candidate, best_net = None, None
    for thr in sorted(c for c in real_evidence if c != current):
        changes = []
        for fname, (_verdict, outcome) in sorted(real_evidence[thr].items()):
            old_v, old_o = baseline.get(fname, (None, None))
            if outcome != old_o:
                changes.append((fname, old_o, outcome))
        improves = sum(
            1 for _, o, n in changes if o == OutcomeLabel.MISS_BELOW_FLOOR.value and n in _HONEST
        )
        worsens = sum(1 for _, o, n in changes if n in _BAD and o not in _BAD)
        # Downgrade más suave que "worsens": perder una lectura honesta
        # (algo se detectó y se leyó bien) y quedarse sin candidato del
        # todo no es tan malo como una mala clasificación, pero sigue
        # siendo una pérdida de información -- se pesa la mitad.
        downgrades = sum(
            1 for _, o, n in changes if o in _HONEST and n == OutcomeLabel.MISS_BELOW_FLOOR.value
        )
        net = improves - 2 * worsens - 0.5 * downgrades
        synth_ok = synth_evidence[thr]["all_ok"]
        print(
            f"\n  threshold={thr}: {len(changes)} archivo(s) cambian de outcome "
            f"({improves} mejoran desde MISS_BELOW_FLOOR, {worsens} empeoran a "
            f"suprimido/falsa alarma, {downgrades} pierden una lectura honesta), "
            f"neto={net:+.1f}, sintético {'OK' if synth_ok else 'ROTO'}"
        )
        for fname, old_o, new_o in changes:
            print(f"      {fname}: {old_o} -> {new_o}")
        if synth_ok and worsens == 0 and net > 0 and (best_net is None or net > best_net):
            best_candidate, best_net = thr, net

    evidence = {
        "real_evidence": {str(k): v for k, v in real_evidence.items()},
        "synthetic_evidence": {str(k): v for k, v in synth_evidence.items()},
        "files_evaluated": [os.path.basename(f) for f in files],
    }

    if not do_apply:
        proposal_value = apply_value if apply_value is not None else best_candidate
        if proposal_value is None:
            # A8: "sin evidencia de descalibración" también es un resultado
            # -- se documenta explícito en el perfil (para que
            # `Tier0Config.from_array_profile` y quien lea el perfil sepan
            # que el default fue EVALUADO, no simplemente nunca tocado) y
            # queda una fila en `proposals` (old_value == new_value) con la
            # evidencia completa del barrido, no solo un print que se
            # pierde.
            note = (
                f"A8: barrido threshold {sorted(real_evidence.keys())} evaluado contra "
                f"{len(files)} archivo(s) crudo(s) + chequeo sintético -- ningún candidato "
                f"mejora un outcome sin romper otro (real o sintético). Default retenido, "
                f"sin evidencia de descalibración."
            )
            profile = cat.get_array_profile(array_id) or {}
            thresholds = dict(profile.get("thresholds_json") or {})
            thresholds["threshold"] = current
            thresholds["tier0_threshold_calibration_note"] = note
            cat.upsert_array_profile(
                array_id,
                fs=profile.get("fs") or 0.0,
                dx=profile.get("dx") or 0.0,
                n_ch=profile.get("n_ch") or 0,
                aperture_m=profile.get("aperture_m") or 0.0,
                noise_stats=profile.get("noise_stats_json"),
                thresholds=thresholds,
                synth_recall=profile.get("synth_recall"),
            )
            pid = cat.add_proposal(array_id, "tier0_threshold", current, current, evidence)
            print(
                f"\nNinguna propuesta (registrado #{pid}, old==new==({current}), con evidencia): "
                f"ningún candidato mejora sin romper algo (real o sintético). {note}"
            )
            return
        pid = cat.add_proposal(array_id, "tier0_threshold", current, proposal_value, evidence)
        print(
            f"\nPropuesta #{pid} registrada (NO aplicada): tier0_threshold {current} -> "
            f"{proposal_value}. Corré de nuevo con --param tier0_threshold --apply "
            f"--value {proposal_value} para aplicarla."
        )
        return

    value = apply_value if apply_value is not None else best_candidate
    if value is None:
        raise SystemExit("--apply requiere --value (o que haya un candidato sin romper nada)")
    profile = cat.get_array_profile(array_id) or {}
    thresholds = dict(profile.get("thresholds_json") or {})
    thresholds["threshold"] = value  # Tier0Config.threshold
    cat.upsert_array_profile(
        array_id,
        fs=profile.get("fs") or 0.0,
        dx=profile.get("dx") or 0.0,
        n_ch=profile.get("n_ch") or 0,
        aperture_m=profile.get("aperture_m") or 0.0,
        noise_stats=profile.get("noise_stats_json"),
        thresholds=thresholds,
        synth_recall=profile.get("synth_recall"),
    )
    pid = cat.add_proposal(array_id, "tier0_threshold", current, value, evidence)
    cat.mark_proposal_applied(pid)
    print(
        f"\nAplicado: tier0_threshold = {value} para '{array_id}' (propuesta #{pid}, "
        "con evidencia real + sintética registrada)."
    )


def main() -> None:
    """CLI de calibrate.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--array-id", required=True)
    ap.add_argument("--db", default="quakeflow_ledger.db")
    ap.add_argument(
        "--param",
        default="seismic_min_semblance",
        choices=["seismic_min_semblance", "tier0_threshold"],
        help="Qué parámetro calibrar. 'tier0_threshold' (A6) necesita --dir "
        "(relee .h5 crudos) y corre un chequeo sintético obligatorio.",
    )
    ap.add_argument(
        "--dir", default=None, help="Carpeta con .h5 crudos (solo --param tier0_threshold)"
    )
    ap.add_argument(
        "--candidates",
        type=float,
        nargs="+",
        default=None,
        help="Candidatos a evaluar (default: escalones de semblanza si "
        "--param seismic_min_semblance, escalones de threshold STA/LTA "
        "si --param tier0_threshold)",
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
        "se aplica el primer candidato que no rompe nada)",
    )
    args = ap.parse_args()

    cat = SignatureCatalog(args.db)

    if args.param == "tier0_threshold":
        if not args.dir:
            raise SystemExit(
                "--param tier0_threshold necesita --dir con los .h5 crudos del arreglo"
            )
        files = sorted(glob.glob(os.path.join(args.dir, "*.h5")))
        if not files:
            raise SystemExit(f"no se encontraron .h5 en {args.dir}")
        candidates = args.candidates or [4.5, 5.0, 5.5, 6.0, 7.0]
        run_tier0_calibration(cat, args.array_id, files, candidates, args.value, args.apply)
        return

    args.candidates = args.candidates or [0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
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
