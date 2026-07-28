"""Tests for `snr_curve.stationarity_check` (F1.5) -- el criterio de
estacionariedad pre-registrado en F1.3 (§2/§7), implementado acá por
primera vez como código (antes solo estaba diseñado en el documento).

Usa fuentes sintéticas con un `noise` de RMS conocido (construido a
mano, no real) para poder controlar exactamente qué ratio max/min ve el
chequeo -- no depende de ningún array real descargado.
"""

from __future__ import annotations

import numpy as np
import pytest

from darkfiber.snr_curve import stationarity_check


def _source_with_rms(rms_value: float, n_ch: int = 2, n_t: int = 1000) -> dict:
    """Fuente sintética cuyo `noise_rms()` es exactamente `rms_value`
    (ruido gaussiano escalado, mismo canal repetido para RMS uniforme)."""
    rng = np.random.default_rng(hash(rms_value) % (2**31))
    base = rng.standard_normal((1, n_t)).astype(np.float32)
    base /= np.sqrt(np.mean(base**2))  # normaliza a RMS=1 exacto
    data = np.repeat(base * rms_value, n_ch, axis=0).astype(np.float32)
    return dict(path=f"fake_{rms_value}.h5", noise=data)


def test_clean_pass_when_all_within_threshold(tmp_path):
    sources = [_source_with_rms(r) for r in [1.0, 1.5, 2.0, 1.2]]  # max/min=2.0 <= 3.0
    result = stationarity_check(sources, threshold=3.0)
    assert result["passed_clean"] is True
    assert result["drift_flag"] is False
    assert result["kept_indices"] == [0, 1, 2, 3]
    assert result["overall_ratio"] == pytest.approx(2.0, rel=1e-3)


def test_subset_when_one_outlier_at_edge(tmp_path):
    # Los primeros 3 tienen max/min=2.0 (limpio); el 4to es un outlier
    # (10x) que rompe el ratio global -- debe recortar al subconjunto
    # contiguo más largo que SÍ pasa, no descartar todo.
    sources = [_source_with_rms(r) for r in [1.0, 1.5, 2.0, 20.0]]
    result = stationarity_check(sources, threshold=3.0, k_min=1)
    assert result["passed_clean"] is False
    assert result["drift_flag"] is False
    assert result["kept_indices"] == [0, 1, 2]


def test_earliest_start_wins_on_tie(tmp_path):
    # Dos subconjuntos contiguos de largo 2 pasan el umbral (índices
    # [0,1] y [3,4]); el outlier en el medio (índice 2) los separa.
    # Empate en longitud -> gana el que empieza más temprano (índice 0).
    sources = [
        _source_with_rms(1.0),
        _source_with_rms(1.5),  # ratio [0,1]=1.5, OK
        _source_with_rms(50.0),  # outlier
        _source_with_rms(1.0),
        _source_with_rms(1.8),  # ratio [3,4]=1.8, OK, mismo largo que [0,1]
    ]
    result = stationarity_check(sources, threshold=3.0, k_min=1)
    assert result["kept_indices"] == [0, 1]


def test_terminal_branch_full_pool_with_drift_flag_when_no_subset_reaches_k_min(tmp_path):
    # Ningún subconjunto contiguo de largo >= k_min=3 pasa el umbral --
    # rama terminal: pool COMPLETO con drift_flag=True, nunca recortado
    # por debajo de k_min ni declarado "inmedible".
    sources = [
        _source_with_rms(1.0),
        _source_with_rms(20.0),
        _source_with_rms(1.0),
        _source_with_rms(20.0),
        _source_with_rms(1.0),
    ]
    result = stationarity_check(sources, threshold=3.0, k_min=3)
    assert result["passed_clean"] is False
    assert result["drift_flag"] is True
    assert result["kept_indices"] == [0, 1, 2, 3, 4]  # pool completo, no recortado


def test_ratio_monotonic_shortcut_does_not_miss_a_valid_longer_window():
    # Verifica que el atajo (cortar el escaneo interno al primer `end`
    # que excede el umbral) no se salte una ventana más larga y válida
    # que empiece más tarde -- construcción donde el óptimo NO es
    # [0:n], para confirmar que el algoritmo explora todos los `start`.
    sources = [
        _source_with_rms(100.0),  # aislado, rompe cualquier ventana que lo incluya
        _source_with_rms(1.0),
        _source_with_rms(1.2),
        _source_with_rms(1.1),
        _source_with_rms(1.3),
    ]
    result = stationarity_check(sources, threshold=3.0, k_min=1)
    assert result["kept_indices"] == [1, 2, 3, 4]
