"""Tests for `snr_curve.gather_noise_sources`'s extension to `.npz` (F1.1,
Fase 1 de la extensión de SNR50 a más instalaciones): el loader genérico
(`replay.load_file`) y la ventana de exclusión manual (`--exclude-s`),
necesaria para formatos sin `event_time_index` embebido (Stanford y
cualquier otro `.npz` sin convención de attrs propia, a diferencia de
QuakeFlow `.h5`).

No toca el path de veredicto (Tier0 -> coherencia -> supervisor) -- esto
es exclusivamente la capa de carga/selección de ruido de `snr_curve.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from darkfiber.snr_curve import gather_noise_sources

FS = 50.0
DX = 8.0
N_CH = 6
N_T = 6000  # 120s @ 50Hz -- bien por encima del piso de 10s por segmento


def _write_npz(tmp_path, marker_range: tuple[int, int] | None = None, marker_value=999.0):
    rng = np.random.default_rng(0)
    data = (rng.standard_normal((N_CH, N_T)).astype(np.float32)) * 0.01
    if marker_range is not None:
        a, b = marker_range
        data[:, a:b] = marker_value
    path = tmp_path / "test_array.npz"
    np.savez(path, data=data)
    return str(path)


@pytest.fixture
def npz_path(tmp_path):
    return _write_npz(tmp_path)


def test_npz_requires_explicit_fs_dx(npz_path):
    """`replay.load_file` (el loader que usa `gather_noise_sources`) exige
    fs/dx explícitos para `.npz` -- nunca los asume (regla del proyecto,
    ver `replay.py`). Sin overrides, debe fallar fuerte (`SystemExit`),
    no inventar un default ni omitir la fuente en silencio."""
    with pytest.raises(SystemExit):
        gather_noise_sources([npz_path])  # sin fs_override/dx_override


def test_npz_loader_shape_dtype_fs_dx(npz_path):
    """Con fs/dx explícitos: la fuente resultante trae exactamente el
    fs/dx pasados (nunca leídos/asumidos del archivo, que no los trae),
    la forma correcta, y el mismo dtype (float32) que produce
    `replay.load_file` para `.npz` -- verificado, no asumido (ver
    `synth.bandpass`/`run_on_stanford.sanitize`, ambos preservan
    float32 en la práctica)."""
    sources = gather_noise_sources([npz_path], fs_override=FS, dx_override=DX)
    assert (
        len(sources) == 1
    )  # sin event_time_index ni exclusión manual -> archivo completo, 1 tramo
    src = sources[0]
    assert src["fs"] == FS
    assert src["dx"] == DX
    assert src["n_ch"] == N_CH
    assert src["noise"].dtype == np.float32
    assert src["noise"].shape == (N_CH, N_T)
    assert src["exclusion_kind"] == "none (archivo completo, sin verdad-terreno)"


def test_manual_exclude_window_not_in_noise_pool(tmp_path):
    """La ventana pasada por `manual_exclude_s` no debe aparecer en NINGÚN
    tramo de ruido devuelto -- verificado de dos formas independientes:
    (1) los rangos de muestra devueltos (`segment_s`) no se solapan con
    la ventana excluida, y (2) un valor marca (999.0, imposible en ruido
    real/sintético normal) escrito exactamente en esa ventana no aparece
    en ningún array `noise` devuelto."""
    exclude_start_s, exclude_end_s = 40.0, 60.0  # [2000, 3000) muestras a fs=50
    marker_a, marker_b = int(exclude_start_s * FS), int(exclude_end_s * FS)
    path = _write_npz(tmp_path, marker_range=(marker_a, marker_b))

    sources = gather_noise_sources(
        [path], fs_override=FS, dx_override=DX, manual_exclude_s=(exclude_start_s, exclude_end_s)
    )

    assert len(sources) == 2, "se esperan 2 tramos: antes y después de la ventana excluida"
    for src in sources:
        assert src["exclusion_kind"] == "manual (--exclude-s)"
        seg_start_s, seg_end_s = src["segment_s"]
        # (1) sin solape con la ventana excluida
        assert seg_end_s <= exclude_start_s or seg_start_s >= exclude_end_s, (
            f"tramo [{seg_start_s},{seg_end_s}] se solapa con la exclusión "
            f"[{exclude_start_s},{exclude_end_s}]"
        )
        # (2) el valor marca de la ventana excluida no aparece en el ruido devuelto
        assert not np.any(src["noise"] == 999.0), "la ventana excluida apareció en el pool de ruido"

    # Verdad-terreno directa: el primer tramo termina antes del inicio de
    # la exclusión, el segundo empieza después de su fin.
    segs = sorted(s["segment_s"] for s in sources)
    assert segs[0][1] <= exclude_start_s
    assert segs[1][0] >= exclude_end_s


def test_manual_exclude_ignored_when_no_files_have_it_but_still_bounds_correctly(npz_path):
    """Sin `manual_exclude_s`, el comportamiento es el de siempre (archivo
    completo como ruido) -- el parámetro nuevo no cambia nada por default."""
    sources = gather_noise_sources([npz_path], fs_override=FS, dx_override=DX)
    assert len(sources) == 1
    assert sources[0]["segment_s"] == (0.0, N_T / FS)
