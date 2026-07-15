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
    ts REAL
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
    updated REAL
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
    ) -> None:
        """UPSERT por `event_file`: correr el arnés de nuevo sobre el mismo
        archivo actualiza la fila en vez de duplicarla."""
        with self._lock:
            self.db.execute(
                """
                INSERT INTO ledger (event_file, array_id, gt_json, verdict, outcome,
                                     dt_detect_s, metrics_json, ts)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(event_file) DO UPDATE SET
                    array_id=excluded.array_id, gt_json=excluded.gt_json,
                    verdict=excluded.verdict, outcome=excluded.outcome,
                    dt_detect_s=excluded.dt_detect_s, metrics_json=excluded.metrics_json,
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
                    time.time(),
                ),
            )
            self.db.commit()

    def ledger_rows(self, array_id: str | None = None) -> list[dict]:
        """Filas del ledger (todas, o filtradas por `array_id`), con
        `gt_json`/`metrics_json` ya deserializados."""
        q = "SELECT event_file, array_id, gt_json, verdict, outcome, dt_detect_s, metrics_json, ts FROM ledger"
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
    ) -> None:
        """UPSERT del perfil de un arreglo. `synth_recall=None` conserva el
        valor previo (COALESCE) — llamar sin recall no lo borra."""
        with self._lock:
            self.db.execute(
                """
                INSERT INTO array_profiles (array_id, fs, dx, n_ch, aperture_m,
                                             noise_stats_json, thresholds_json,
                                             synth_recall, updated)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(array_id) DO UPDATE SET
                    fs=excluded.fs, dx=excluded.dx, n_ch=excluded.n_ch,
                    aperture_m=excluded.aperture_m,
                    noise_stats_json=excluded.noise_stats_json,
                    thresholds_json=excluded.thresholds_json,
                    synth_recall=COALESCE(excluded.synth_recall, array_profiles.synth_recall),
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
                    time.time(),
                ),
            )
            self.db.commit()

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
            "synth_recall, updated FROM array_profiles WHERE array_id=?",
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
            "updated",
        ]
        d = dict(zip(cols, row, strict=True))
        d["noise_stats_json"] = json.loads(d["noise_stats_json"]) if d["noise_stats_json"] else None
        d["thresholds_json"] = json.loads(d["thresholds_json"]) if d["thresholds_json"] else None
        return d
