"""Test para `convert_stanford_sgy.read_segy` confirmando que se puede
reusar TAL CUAL para Stanford-2 (F1.4, Fase 1 de la extensión de SNR50) --
no hace falta un loader nuevo. `read_segy` ya es genérico: lee
`sample_interval_us`/`samples_per_trace`/`data_format_code` del header
binario SEG-Y real, nunca asume nada de un array/formato específico.

Verificado además contra el archivo real de Stanford-2
(`cbt_processed_20200301_065859.550+0000.sgy`, descargado en Ola 1):
1250 canales, fs=250Hz, 60.0s exactos, format_code=5 -- coincide con lo
esperado de Tabla 1/FDSN, sin cambios de código. Este test hermético usa
una fixture sintética (no el archivo real, que no está en el repo) con
los mismos parámetros (1250 canales, fs=250Hz) para que corra en CI.

No toca el path de veredicto -- exclusivamente la capa de carga.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from darkfiber.convert_stanford_sgy import read_binary_header, read_segy

TXT_HEADER, BIN_HEADER, TRACE_HEADER = 3200, 400, 240

# Parámetros reales de Stanford-2 (confirmados contra el archivo
# descargado en Ola 1): 1250 canales, sample_interval=4000us (fs=250Hz).
N_CH_REAL = 1250
FS_REAL = 250.0
N_SAMPLES_SMALL = 100  # chico a propósito -- el test no necesita 60s reales


def _write_segy(
    path: Path, n_ch: int, samples_per_trace: int, sample_interval_us: int, format_code: int = 5
) -> np.ndarray:
    """Escribe un SEG-Y sintético mínimo pero real (header binario real,
    datos IEEE float32 big-endian por traza) y devuelve los datos
    escritos para comparar."""
    rng = np.random.default_rng(0)
    data = rng.standard_normal((n_ch, samples_per_trace)).astype(np.float32) * 1000.0

    with open(path, "wb") as fh:
        fh.write(b"\x00" * TXT_HEADER)
        binh = bytearray(BIN_HEADER)
        binh[16:18] = struct.pack(">h", sample_interval_us)
        binh[20:22] = struct.pack(">h", samples_per_trace)
        binh[24:26] = struct.pack(">h", format_code)
        fh.write(bytes(binh))
        for ch in range(n_ch):
            fh.write(b"\x00" * TRACE_HEADER)
            fh.write(data[ch].astype(">f4").tobytes())
    return data


def test_read_binary_header_reflects_stanford2_real_params(tmp_path):
    """Confirma que el header binario se lee del archivo, no se asume --
    con los parámetros reales de Stanford-2 (1250 canales, fs=250Hz,
    sample_interval=4000us)."""
    path = tmp_path / "stanford2_like.sgy"
    _write_segy(path, n_ch=N_CH_REAL, samples_per_trace=N_SAMPLES_SMALL, sample_interval_us=4000)
    with open(path, "rb") as fh:
        si_us, spt, fmt = read_binary_header(fh)
    assert si_us == 4000
    assert spt == N_SAMPLES_SMALL
    assert fmt == 5


def test_read_segy_shape_dtype_fs_matches_written_data(tmp_path):
    """`read_segy` (sin ningún cambio) reproduce exactamente shape/fs/
    valores para un SEG-Y con los parámetros reales de Stanford-2 --
    confirma que reusarlo tal cual es seguro, no hace falta loader nuevo."""
    path = tmp_path / "stanford2_like.sgy"
    written = _write_segy(
        path, n_ch=N_CH_REAL, samples_per_trace=N_SAMPLES_SMALL, sample_interval_us=4000
    )
    data, fs = read_segy(path)
    assert data.shape == (N_CH_REAL, N_SAMPLES_SMALL)
    assert data.dtype == np.float32
    assert fs == FS_REAL
    np.testing.assert_allclose(data, written, rtol=1e-5)


def test_read_segy_rejects_unsupported_format_code(tmp_path):
    """Nunca asume el formato de datos -- si `data_format_code != 5`
    (IEEE float32), falla fuerte en vez de intentar interpretar bytes
    con el formato equivocado en silencio."""
    path = tmp_path / "wrong_format.sgy"
    _write_segy(path, n_ch=2, samples_per_trace=10, sample_interval_us=4000, format_code=1)
    with pytest.raises(ValueError):
        read_segy(path)


def test_read_segy_fs_derived_from_header_not_hardcoded(tmp_path):
    """`fs` sale de `sample_interval_us` del header real, no de una
    constante -- confirmado con un sample_interval distinto al de
    Stanford-2 (Pawnee/Stanford-1 usaron otras tasas históricamente,
    ver `validacion_real/NOTES.md`: 50Hz en 2016, 100Hz en 2017)."""
    path = tmp_path / "different_fs.sgy"
    _write_segy(path, n_ch=3, samples_per_trace=20, sample_interval_us=10000)  # 100Hz
    _, fs = read_segy(path)
    assert fs == 100.0
