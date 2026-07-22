"""Smoke test for dashboard.py (C2): the app must at least import and
render without exceptions against an empty ledger -- CI-safe, no real
data, no network (matches this project's synthetic-only CI policy; the
dashboard's own real-data-shaped demo tab, the "Vivo" replay run, needs a
real local file and is exercised by hand, not here).

Uses `streamlit.testing.v1.AppTest`, which actually executes the script
(not just imports it) and lets us inspect the rendered element tree --
catches real rendering bugs (e.g. a bad st.table() argument), not just
import errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

DASHBOARD_PATH = str(Path(__file__).resolve().parents[1] / "src" / "darkfiber" / "dashboard.py")


def test_dashboard_renders_against_empty_ledger(tmp_path, monkeypatch):
    # El default de dashboard.py es la ruta relativa "quakeflow_ledger.db"
    # -- correr con cwd en un tmp_path aislado ejercita exactamente ese
    # default (SignatureCatalog lo crea vacío) sin tocar el ledger real.
    monkeypatch.chdir(tmp_path)

    at = AppTest.from_file(DASHBOARD_PATH, default_timeout=30)
    at.run()

    assert not at.exception, f"la app tiró una excepción: {at.exception}"
    assert len(at.tabs) == 4, f"se esperaban 4 pestañas, hubo {len(at.tabs)}"
    # Con el ledger vacío, catálogo y scoreboard deben mostrar su mensaje
    # de "sin datos" honesto, no una tabla vacía silenciosa ni un error.
    all_text = " ".join(m.value for m in at.get("markdown") + at.get("caption") + at.get("info"))
    assert "vacío" in all_text or "Sin corrida" in all_text or "vacía" in all_text
