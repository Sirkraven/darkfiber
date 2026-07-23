"""
DarkFiber MAS v5 — Catálogo Vivo de Firmas (open-set + few-shot por prototipo).

Extiende la tabla `event_signatures` existente (vectores latentes en SQLite):
  * match():  compara el vector latente contra prototipos conocidos (coseno).
  * Desconocidos recurrentes: firmas nuevas que se repiten en la misma zona se
    agrupan; al superar un umbral de ocurrencias, el dashboard propone
    nombrarlas ("Fuente recurrente no identificada en km 3.2 ...").
  * promote(): el operador la bautiza y se vuelve clase nueva SIN reentrenar
    (clasificación por prototipo en el espacio latente).
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time

import numpy as np

from .contracts import CatalogMatch

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prototypes (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    zone TEXT,
    array_id TEXT,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL,
    n_events INTEGER DEFAULT 1,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS unknown_clusters (
    id INTEGER PRIMARY KEY,
    zone TEXT,
    array_id TEXT,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL,
    n_events INTEGER DEFAULT 1,
    first_seen REAL,
    last_seen REAL
);
CREATE TABLE IF NOT EXISTS ledger (
    event_file TEXT NOT NULL UNIQUE,
    array_id TEXT,
    gt_json TEXT,
    verdict TEXT,
    outcome TEXT,
    dt_detect_s REAL,
    metrics_json TEXT,
    snr_observed REAL,
    ts REAL
);
CREATE TABLE IF NOT EXISTS ledger_invalidations (
    id INTEGER PRIMARY KEY,
    event_file TEXT NOT NULL,
    array_id TEXT,
    reason TEXT NOT NULL,
    prior_verdict TEXT,
    prior_outcome TEXT,
    prior_dt_detect_s REAL,
    prior_gt_json TEXT,
    prior_metrics_json TEXT,
    invalidated_at REAL
);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY,
    array_id TEXT,
    param TEXT,
    old_value REAL,
    new_value REAL,
    evidence_json TEXT,
    applied INTEGER DEFAULT 0,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS array_profiles (
    array_id TEXT NOT NULL UNIQUE,
    fs REAL,
    dx REAL,
    n_ch INTEGER,
    aperture_m REAL,
    noise_stats_json TEXT,
    thresholds_json TEXT,
    synth_recall REAL,
    recall_curve_json TEXT,
    snr50 REAL,
    updated REAL
);
CREATE TABLE IF NOT EXISTS array_profile_history (
    id INTEGER PRIMARY KEY,
    array_id TEXT NOT NULL,
    fs REAL,
    dx REAL,
    n_ch INTEGER,
    aperture_m REAL,
    noise_stats_json TEXT,
    thresholds_json TEXT,
    synth_recall REAL,
    recall_curve_json TEXT,
    snr50 REAL,
    note TEXT,
    archived_at REAL
);
CREATE TABLE IF NOT EXISTS live_verdicts (
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    array_id TEXT,
    source_file TEXT,
    t_start_s REAL,
    t_end_s REAL,
    verdict TEXT,
    explanations_json TEXT,
    metrics_json TEXT,
    ts REAL
);
"""


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / ((np.linalg.norm(a) + 1e-12) * (np.linalg.norm(b) + 1e-12)))


class SignatureCatalog:
    """Backing store SQLite del proyecto: catálogo de firmas (prototipos +
    desconocidos recurrentes, aislados por `array_id` desde P3), ledger de
    verdad-terreno (P2) y perfiles/propuestas de calibración por arreglo
    (P3). Una sola conexión, thread-safe vía lock propio — ver el comentario
    en `__init__` sobre por qué `check_same_thread=False`."""

    def __init__(
        self,
        db_path: str = "signatures.db",
        tau_known: float = 0.85,
        tau_cluster: float = 0.90,
        naming_threshold: int = 5,
    ):
        # check_same_thread=False + lock propio: la regla del proyecto es
        # llamar código CPU-bound vía asyncio.to_thread, que puede aterrizar
        # en CUALQUIER hilo del pool. El default de sqlite3 (True) crasharía
        # en el primer match() fuera del hilo creador. WAL: lectores no
        # bloquean al escritor (mismo patrón que el feature store de v4).
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(_SCHEMA)
        # Migración defensiva: bases creadas antes de P3 no tienen array_id.
        for table in ("prototypes", "unknown_clusters"):
            with contextlib.suppress(sqlite3.OperationalError):  # columna ya existe
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN array_id TEXT")
        # Migración defensiva: bases creadas antes de A1 no tienen la curva
        # recall-vs-SNR ni el SNR50 resumen (ver snr_curve.py).
        for col in ("recall_curve_json TEXT", "snr50 REAL"):
            with contextlib.suppress(sqlite3.OperationalError):  # columna ya existe
                self.db.execute(f"ALTER TABLE array_profiles ADD COLUMN {col}")
        # Migración defensiva: bases creadas antes de A2 (Tarea 7) no tienen
        # el SNR observado por evento del ledger.
        with contextlib.suppress(sqlite3.OperationalError):  # columna ya existe
            self.db.execute("ALTER TABLE ledger ADD COLUMN snr_observed REAL")
        self._lock = threading.Lock()
        self.tau_known = tau_known
        self.tau_cluster = tau_cluster
        self.naming_threshold = naming_threshold

    # ------------------------------------------------------------------
    def match(
        self, vec: np.ndarray, zone: str | None = None, array_id: str | None = None
    ) -> CatalogMatch:
        """`array_id`, si se da, aísla la búsqueda a firmas de ESE arreglo
        (lo aprendido en Ridgecrest no contamina Monterey). Sin `array_id`
        (default), busca globalmente — compatibilidad con llamadas previas
        a P3 (p. ej. la demo de run_validation.py)."""
        with self._lock:
            return self._match_locked(vec, zone, array_id)

    def _match_locked(
        self, vec: np.ndarray, zone: str | None, array_id: str | None = None
    ) -> CatalogMatch:
        vec = np.asarray(vec, dtype=np.float32)
        expl: list[str] = []

        if array_id is not None:
            proto_rows = self.db.execute(
                "SELECT label, vec FROM prototypes WHERE array_id = ?", (array_id,)
            )
        else:
            proto_rows = self.db.execute("SELECT label, vec FROM prototypes")

        best_label, best_sim = None, -1.0
        for label, blob in proto_rows:
            proto = np.frombuffer(blob, dtype=np.float32)
            s = _cos(vec, proto)
            if s > best_sim:
                best_label, best_sim = label, s

        if best_label is not None and best_sim >= self.tau_known:
            expl.append(f"Firma reconocida como '{best_label}' (similitud {best_sim:.2f}).")
            self.db.execute(
                "UPDATE prototypes SET n_events = n_events + 1, updated_at = ? WHERE label = ?",
                (time.time(), best_label),
            )
            self.db.commit()
            return CatalogMatch(
                label=best_label, similarity=best_sim, is_novel=False, explanations=expl
            )

        # Desconocido: ¿coincide con un cluster de desconocidos recurrentes?
        expl.append(
            f"Firma no reconocida (mejor similitud {max(best_sim, 0):.2f} < τ={self.tau_known})."
        )
        if array_id is not None:
            rows = self.db.execute(
                "SELECT id, vec, n_events FROM unknown_clusters "
                "WHERE array_id = ? AND (zone IS ? OR zone = ?)",
                (array_id, zone, zone),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, vec, n_events FROM unknown_clusters WHERE zone IS ? OR zone = ?",
                (zone, zone),
            ).fetchall()
        for cid, blob, n in rows:
            proto = np.frombuffer(blob, dtype=np.float32)
            if _cos(vec, proto) >= self.tau_cluster:
                n_new = n + 1
                # media incremental exacta del prototipo del cluster
                # (peso 1/n al nuevo vector; NO es una EMA)
                merged = (proto * n + vec) / n_new
                self.db.execute(
                    "UPDATE unknown_clusters SET vec=?, n_events=?, last_seen=? WHERE id=?",
                    (merged.astype(np.float32).tobytes(), n_new, time.time(), cid),
                )
                self.db.commit()
                suggest = n_new >= self.naming_threshold
                if suggest:
                    expl.append(
                        f"Fuente recurrente no identificada (#{cid}) en zona '{zone}': "
                        f"{n_new} ocurrencias. Se sugiere nombrarla."
                    )
                return CatalogMatch(
                    is_novel=True,
                    similarity=max(best_sim, 0.0),
                    recurring_unknown_id=cid,
                    recurring_count=n_new,
                    suggest_naming=suggest,
                    explanations=expl,
                )

        cur = self.db.execute(
            "INSERT INTO unknown_clusters (zone, array_id, dim, vec, n_events, first_seen, last_seen)"
            " VALUES (?,?,?,?,1,?,?)",
            (zone, array_id, vec.size, vec.tobytes(), time.time(), time.time()),
        )
        self.db.commit()
        expl.append("Nueva firma desconocida registrada para seguimiento.")
        return CatalogMatch(
            is_novel=True,
            similarity=max(best_sim, 0.0),
            recurring_unknown_id=cur.lastrowid,
            recurring_count=1,
            explanations=expl,
        )

    # ------------------------------------------------------------------
    def promote(self, cluster_id: int, label: str) -> None:
        """El operador bautiza un desconocido recurrente: nace una clase nueva.

        Lanza KeyError si el cluster no existe y ValueError si la etiqueta
        ya está tomada (labels son únicos por contrato del catálogo).
        """
        with self._lock:
            self._promote_locked(cluster_id, label)

    def _promote_locked(self, cluster_id: int, label: str) -> None:
        row = self.db.execute(
            "SELECT zone, array_id, dim, vec, n_events FROM unknown_clusters WHERE id=?",
            (cluster_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"cluster {cluster_id} no existe")
        zone, array_id, dim, vec, n = row
        try:
            self.db.execute(
                "INSERT INTO prototypes (label, zone, array_id, dim, vec, n_events, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (label, zone, array_id, dim, vec, n, time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"la etiqueta '{label}' ya existe en el catálogo") from exc
        self.db.execute("DELETE FROM unknown_clusters WHERE id=?", (cluster_id,))
        self.db.commit()

    # ------------------------------------------------------------------
    # Ledger de verdad-terreno (P2): una fila por archivo de evento,
    # UPSERT por event_file para que corridas repetidas no dupliquen.
    # ------------------------------------------------------------------
    def upsert_ledger(
        self,
        event_file: str,
        array_id: str,
        gt_json: dict | None,
        verdict: str | None,
        outcome: str,
        dt_detect_s: float | None,
        metrics_json: dict | None,
        snr_observed: float | None = None,
    ) -> None:
        """UPSERT por `event_file`: correr el arnés de nuevo sobre el mismo
        archivo actualiza la fila en vez de duplicarla."""
        with self._lock:
            self.db.execute(
                """
                INSERT INTO ledger (event_file, array_id, gt_json, verdict, outcome,
                                     dt_detect_s, metrics_json, snr_observed, ts)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(event_file) DO UPDATE SET
                    array_id=excluded.array_id, gt_json=excluded.gt_json,
                    verdict=excluded.verdict, outcome=excluded.outcome,
                    dt_detect_s=excluded.dt_detect_s, metrics_json=excluded.metrics_json,
                    snr_observed=excluded.snr_observed,
                    ts=excluded.ts
                """,
                (
                    event_file,
                    array_id,
                    json.dumps(gt_json, default=str) if gt_json is not None else None,
                    verdict,
                    outcome,
                    dt_detect_s,
                    json.dumps(metrics_json, default=str) if metrics_json is not None else None,
                    snr_observed,
                    time.time(),
                ),
            )
            self.db.commit()

    # ------------------------------------------------------------------
    # Veredictos en vivo (C3): registro operacional de una corrida real
    # (pipeline_daemon.py), SIN verdad-terreno -- deliberadamente en una
    # tabla propia, no en `ledger`, para no mezclar "validado contra
    # catálogo público" (lo que `ledger`/`validacion_real/scoreboard.md`
    # significan en todo el resto del proyecto) con "esto es lo que el
    # sistema dijo en producción, todavía sin comparar contra nada" (ver
    # docs/pilot_kit.md, la comparación es un paso posterior y explícito,
    # no algo que este método decida).
    # ------------------------------------------------------------------
    def insert_live_verdict(
        self,
        event_id: str,
        array_id: str,
        source_file: str,
        t_start_s: float,
        t_end_s: float,
        verdict: str | None,
        explanations: list[str] | None,
        metrics_json: dict | None,
    ) -> None:
        """INSERT simple (no upsert): cada `event_id` de una corrida en
        vivo es único por construcción (`StreamRunner`, ver ese módulo),
        así que no hay "re-correr el mismo archivo" que deba pisar una
        fila anterior como en `upsert_ledger`."""
        with self._lock:
            self.db.execute(
                """
                INSERT INTO live_verdicts (event_id, array_id, source_file, t_start_s,
                                            t_end_s, verdict, explanations_json, metrics_json, ts)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    array_id,
                    source_file,
                    t_start_s,
                    t_end_s,
                    verdict,
                    json.dumps(explanations, default=str) if explanations is not None else None,
                    json.dumps(metrics_json, default=str) if metrics_json is not None else None,
                    time.time(),
                ),
            )
            self.db.commit()

    def invalidate_ledger_rows(self, array_id: str, reason: str) -> int:
        """Marca como inválidas (NO borra) todas las filas actuales del
        ledger para `array_id`: copia su estado ANTES de la corrección a
        `ledger_invalidations` (con motivo y timestamp) para que quede un
        rastro auditable permanente de qué decía el ledger antes del fix,
        aunque la fila de `ledger` misma se sobrescriba después con el
        re-run correcto (mismo event_file, UPSERT). Devuelve cuántas filas
        se invalidaron."""
        with self._lock:
            rows = self.db.execute(
                "SELECT event_file, array_id, verdict, outcome, dt_detect_s, gt_json, metrics_json "
                "FROM ledger WHERE array_id = ?",
                (array_id,),
            ).fetchall()
            now = time.time()
            for event_file, arr, verdict, outcome, dt_detect_s, gt_json, metrics_json in rows:
                self.db.execute(
                    "INSERT INTO ledger_invalidations (event_file, array_id, reason, prior_verdict, "
                    "prior_outcome, prior_dt_detect_s, prior_gt_json, prior_metrics_json, invalidated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        event_file,
                        arr,
                        reason,
                        verdict,
                        outcome,
                        dt_detect_s,
                        gt_json,
                        metrics_json,
                        now,
                    ),
                )
            self.db.commit()
            return len(rows)

    def list_invalidations(self, array_id: str | None = None) -> list[dict]:
        q = (
            "SELECT event_file, array_id, reason, prior_verdict, prior_outcome, "
            "prior_dt_detect_s, prior_gt_json, prior_metrics_json, invalidated_at "
            "FROM ledger_invalidations"
        )
        params: tuple = ()
        if array_id is not None:
            q += " WHERE array_id = ?"
            params = (array_id,)
        cols = [
            "event_file",
            "array_id",
            "reason",
            "prior_verdict",
            "prior_outcome",
            "prior_dt_detect_s",
            "prior_gt_json",
            "prior_metrics_json",
            "invalidated_at",
        ]
        out = []
        for row in self.db.execute(q, params).fetchall():
            d = dict(zip(cols, row, strict=True))
            d["prior_gt_json"] = json.loads(d["prior_gt_json"]) if d["prior_gt_json"] else None
            d["prior_metrics_json"] = (
                json.loads(d["prior_metrics_json"]) if d["prior_metrics_json"] else None
            )
            out.append(d)
        return out

    def ledger_rows(self, array_id: str | None = None) -> list[dict]:
        """Filas del ledger (todas, o filtradas por `array_id`), con
        `gt_json`/`metrics_json` ya deserializados."""
        q = (
            "SELECT event_file, array_id, gt_json, verdict, outcome, dt_detect_s, "
            "metrics_json, snr_observed, ts FROM ledger"
        )
        params: tuple = ()
        if array_id is not None:
            q += " WHERE array_id = ?"
            params = (array_id,)
        rows = self.db.execute(q, params).fetchall()
        cols = [
            "event_file",
            "array_id",
            "gt_json",
            "verdict",
            "outcome",
            "dt_detect_s",
            "metrics_json",
            "snr_observed",
            "ts",
        ]
        out = []
        for row in rows:
            d = dict(zip(cols, row, strict=True))
            d["gt_json"] = json.loads(d["gt_json"]) if d["gt_json"] else None
            d["metrics_json"] = json.loads(d["metrics_json"]) if d["metrics_json"] else None
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Perfil por arreglo (P3, expuesto ya en P2 para que el ledger pueda
    # citarlo): ruido/geometría/umbrales medidos por instalación.
    # ------------------------------------------------------------------
    def upsert_array_profile(
        self,
        array_id: str,
        fs: float,
        dx: float,
        n_ch: int,
        aperture_m: float,
        noise_stats: dict | None = None,
        thresholds: dict | None = None,
        synth_recall: float | None = None,
        recall_curve: list[dict] | None = None,
        snr50: float | None = None,
    ) -> None:
        """`recall_curve`: lista de escalones {snr, recall, ci_low, ci_high,
        n, hits} (ver snr_curve.py, A1). `snr50`: SNR interpolado al que la
        curva cruza recall=0.5 (None si no se observó en el rango barrido).
        Como con `synth_recall`, un upsert sin estos campos NO borra lo ya
        guardado (COALESCE) — p.ej. `run_on_quakeflow.run_array_selftest`
        sigue actualizando ruido/geometría sin pisar la curva."""
        with self._lock:
            self.db.execute(
                """
                INSERT INTO array_profiles (array_id, fs, dx, n_ch, aperture_m,
                                             noise_stats_json, thresholds_json,
                                             synth_recall, recall_curve_json, snr50, updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(array_id) DO UPDATE SET
                    fs=excluded.fs, dx=excluded.dx, n_ch=excluded.n_ch,
                    aperture_m=excluded.aperture_m,
                    noise_stats_json=excluded.noise_stats_json,
                    thresholds_json=COALESCE(excluded.thresholds_json, array_profiles.thresholds_json),
                    synth_recall=COALESCE(excluded.synth_recall, array_profiles.synth_recall),
                    recall_curve_json=COALESCE(excluded.recall_curve_json, array_profiles.recall_curve_json),
                    snr50=COALESCE(excluded.snr50, array_profiles.snr50),
                    updated=excluded.updated
                """,
                (
                    array_id,
                    fs,
                    dx,
                    n_ch,
                    aperture_m,
                    json.dumps(noise_stats, default=str) if noise_stats is not None else None,
                    json.dumps(thresholds, default=str) if thresholds is not None else None,
                    synth_recall,
                    json.dumps(recall_curve, default=str) if recall_curve is not None else None,
                    snr50,
                    time.time(),
                ),
            )
            self.db.commit()

    def archive_array_profile(self, array_id: str, note: str) -> bool:
        """Antes de sobrescribir `recall_curve_json`/`snr50` con una
        medición nueva (A7): la curva recall-vs-SNR es propiedad de
        INSTALACIÓN+CONFIG, no solo de la instalación — cambiar
        `Tier0Config.threshold` la vuelve obsoleta, no incorrecta.
        Copia el estado ACTUAL completo del perfil a
        `array_profile_history` con una nota, antes de que
        `upsert_array_profile` lo reemplace. Devuelve False (no archiva
        nada) si no había perfil previo o no tenía curva medida todavía —
        no tiene sentido archivar un perfil vacío."""
        with self._lock:
            row = self.db.execute(
                "SELECT array_id, fs, dx, n_ch, aperture_m, noise_stats_json, thresholds_json, "
                "synth_recall, recall_curve_json, snr50 FROM array_profiles WHERE array_id=?",
                (array_id,),
            ).fetchone()
            if row is None or row[8] is None:  # sin recall_curve_json: nada que archivar
                return False
            self.db.execute(
                "INSERT INTO array_profile_history (array_id, fs, dx, n_ch, aperture_m, "
                "noise_stats_json, thresholds_json, synth_recall, recall_curve_json, snr50, "
                "note, archived_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (*row, note, time.time()),
            )
            self.db.commit()
            return True

    def list_array_profile_history(self, array_id: str | None = None) -> list[dict]:
        q = (
            "SELECT array_id, fs, dx, n_ch, aperture_m, noise_stats_json, thresholds_json, "
            "synth_recall, recall_curve_json, snr50, note, archived_at FROM array_profile_history"
        )
        params: tuple = ()
        if array_id is not None:
            q += " WHERE array_id = ?"
            params = (array_id,)
        cols = [
            "array_id",
            "fs",
            "dx",
            "n_ch",
            "aperture_m",
            "noise_stats_json",
            "thresholds_json",
            "synth_recall",
            "recall_curve_json",
            "snr50",
            "note",
            "archived_at",
        ]
        out = []
        for row in self.db.execute(q, params).fetchall():
            d = dict(zip(cols, row, strict=True))
            d["noise_stats_json"] = (
                json.loads(d["noise_stats_json"]) if d["noise_stats_json"] else None
            )
            d["thresholds_json"] = (
                json.loads(d["thresholds_json"]) if d["thresholds_json"] else None
            )
            d["recall_curve_json"] = (
                json.loads(d["recall_curve_json"]) if d["recall_curve_json"] else None
            )
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Propuestas de calibración (P3): el sistema PROPONE con evidencia, un
    # humano aplica. Nunca se auto-modifica un umbral en producción.
    # ------------------------------------------------------------------
    def add_proposal(
        self, array_id: str, param: str, old_value: float, new_value: float, evidence: dict
    ) -> int:
        """Registra una propuesta de calibración con su evidencia; devuelve
        el id. No la aplica — ver `mark_proposal_applied`."""
        with self._lock:
            cur = self.db.execute(
                "INSERT INTO proposals (array_id, param, old_value, new_value, "
                "evidence_json, applied, created_at) VALUES (?,?,?,?,?,0,?)",
                (
                    array_id,
                    param,
                    old_value,
                    new_value,
                    json.dumps(evidence, default=str),
                    time.time(),
                ),
            )
            self.db.commit()
            assert cur.lastrowid is not None  # garantizado tras un INSERT exitoso
            return cur.lastrowid

    def list_proposals(self, array_id: str | None = None) -> list[dict]:
        """Propuestas de calibración (todas, o filtradas por `array_id`),
        aplicadas o no."""
        q = "SELECT id, array_id, param, old_value, new_value, evidence_json, applied, created_at FROM proposals"
        params: tuple = ()
        if array_id is not None:
            q += " WHERE array_id = ?"
            params = (array_id,)
        cols = [
            "id",
            "array_id",
            "param",
            "old_value",
            "new_value",
            "evidence_json",
            "applied",
            "created_at",
        ]
        out = []
        for row in self.db.execute(q, params).fetchall():
            d = dict(zip(cols, row, strict=True))
            d["evidence_json"] = json.loads(d["evidence_json"]) if d["evidence_json"] else None
            out.append(d)
        return out

    def mark_proposal_applied(self, proposal_id: int) -> None:
        """Marca una propuesta como aplicada (llamar tras escribirla en
        `array_profiles.thresholds_json` — no lo hace automáticamente)."""
        with self._lock:
            self.db.execute("UPDATE proposals SET applied=1 WHERE id=?", (proposal_id,))
            self.db.commit()

    def get_array_profile(self, array_id: str) -> dict | None:
        """Perfil de un arreglo, o `None` si todavía no se le corrió el
        auto-test (`run_array_selftest` en run_on_quakeflow.py)."""
        row = self.db.execute(
            "SELECT array_id, fs, dx, n_ch, aperture_m, noise_stats_json, thresholds_json, "
            "synth_recall, recall_curve_json, snr50, updated FROM array_profiles WHERE array_id=?",
            (array_id,),
        ).fetchone()
        if row is None:
            return None
        cols = [
            "array_id",
            "fs",
            "dx",
            "n_ch",
            "aperture_m",
            "noise_stats_json",
            "thresholds_json",
            "synth_recall",
            "recall_curve_json",
            "snr50",
            "updated",
        ]
        d = dict(zip(cols, row, strict=True))
        d["noise_stats_json"] = json.loads(d["noise_stats_json"]) if d["noise_stats_json"] else None
        d["thresholds_json"] = json.loads(d["thresholds_json"]) if d["thresholds_json"] else None
        d["recall_curve_json"] = (
            json.loads(d["recall_curve_json"]) if d["recall_curve_json"] else None
        )
        return d
