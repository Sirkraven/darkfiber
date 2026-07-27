"""Tests for `replay.load_hdf5_generic` (F1.4, Fase 1 de la extensión de
SNR50): loader nuevo para HDF5 no-QuakeFlow (FORESEE, Valencia, PubDAS en
general), a propósito SEPARADO de `load_quakeflow_h5` -- ese loader
defaultea `dt_s`/`dx_m` en silencio si faltan los attrs (correcto para
QuakeFlow, que sí trae esa convención; peligroso acá, donde no hay
ninguna garantía de attrs -- confirmado en el archivo real de FORESEE,
que no trae NINGÚN attr ni en el archivo ni en el dataset).

No toca el path de veredicto -- exclusivamente la capa de carga.
"""

from __future__ import annotations

import h5py
import numpy as np
import pytest

from darkfiber.replay import load_hdf5_generic

FS = 125.0
DX = 2.0
N_CH = 6
N_T = 6000


def _write_hdf5(tmp_path, dataset_name="raw", with_attrs=False, dtype=np.float16):
    rng = np.random.default_rng(0)
    data = (rng.standard_normal((N_CH, N_T)) * 0.01).astype(dtype)
    path = tmp_path / "test_array.hdf5"
    with h5py.File(path, "w") as fh:
        ds = fh.create_dataset(dataset_name, data=data)
        if with_attrs:
            # attrs con nombres DISTINTOS a la convención QuakeFlow --
            # simula que un HDF5 no-QuakeFlow puede traer attrs propios,
            # pero este loader los ignora a propósito (nunca los lee).
            ds.attrs["sampling_rate_hz"] = FS
    return str(path)


@pytest.fixture
def hdf5_path(tmp_path):
    return _write_hdf5(tmp_path)


def test_requires_explicit_fs_dx(hdf5_path):
    """Sin fs/dx explícitos, debe fallar fuerte (`SystemExit`) -- nunca
    asumir un default como hace `load_quakeflow_h5` con `dt_s`/`dx_m`."""
    with pytest.raises(SystemExit):
        load_hdf5_generic(hdf5_path)
    with pytest.raises(SystemExit):
        load_hdf5_generic(hdf5_path, fs=FS)  # falta dx
    with pytest.raises(SystemExit):
        load_hdf5_generic(hdf5_path, dx=DX)  # falta fs


def test_ignores_attrs_even_if_present(tmp_path):
    """Aunque el HDF5 traiga attrs (con cualquier nombre), este loader
    nunca los lee -- fs/dx SIEMPRE vienen del argumento explícito, no
    hay una convención de attrs de la que este loader dependa."""
    path = _write_hdf5(tmp_path, with_attrs=True)
    data, fs, dx, attrs = load_hdf5_generic(path, fs=FS, dx=DX)
    assert fs == FS
    assert dx == DX
    assert attrs == {}


def test_shape_dtype_via_default_raw_key(hdf5_path):
    """Sin `key` explícito, prueba `"raw"` primero (convención real de
    FORESEE) -- y el resultado siempre se upcastea a float32, sin
    importar el dtype de origen (acá float16, igual que el archivo real
    de FORESEE)."""
    data, fs, dx, attrs = load_hdf5_generic(hdf5_path, fs=FS, dx=DX)
    assert fs == FS
    assert dx == DX
    assert data.shape == (N_CH, N_T)
    assert data.dtype == np.float32


def test_key_fallback_to_first_2d_dataset(tmp_path):
    """Si no existe `"raw"` y no se pasa `key`, cae al primer dataset 2D
    que encuentre -- mismo comportamiento defensivo que
    `load_quakeflow_h5` para `.npz`/`.h5` sin la clave por default."""
    path = _write_hdf5(tmp_path, dataset_name="strain_rate")
    data, fs, dx, attrs = load_hdf5_generic(path, fs=FS, dx=DX)
    assert data.shape == (N_CH, N_T)
    assert data.dtype == np.float32


def test_explicit_key_wrong_name_fails_loud(hdf5_path):
    """Un `key` explícito que no existe en el archivo falla fuerte, no
    cae en silencio al fallback de primer-dataset-2D -- si el usuario
    pidió una clave específica, un typo no debe resolverse solo."""
    with pytest.raises(SystemExit):
        load_hdf5_generic(hdf5_path, fs=FS, dx=DX, key="no_existe")


def test_low_snr_injection_survives_float16_source(hdf5_path):
    """FORESEE real es float16 (no float32/int16 -- un tercer dtype de
    origen distinto a todo lo visto hasta ahora). Verifica que, tras el
    upcast a float32 de este loader, una inyección a SNR=1 (el escalón
    más frágil) sobrevive sin degradarse -- el mismo tipo de chequeo que
    ya se hizo para el int16 de FOSSA, ahora para float16."""
    from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config
    from darkfiber.selftest import inject_and_verify_sized

    data, fs, dx, _ = load_hdf5_generic(hdf5_path, fs=FS, dx=DX)
    geom = ArrayGeometry(n_channels=N_CH, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config()
    coh_cfg = CoherenceConfig()
    # Ventana de ruido más larga que el piso de esta apertura minúscula
    # (N_CH=6, dx=2 -> apertura=10m, piso trivial) -- alcanza con N_T.
    result = inject_and_verify_sized(data, geom, t0cfg, coh_cfg, v_app_mps=3200.0, snr=1.0, seed=0)
    assert result is not None, "la ventana debería ser suficiente para esta apertura chica"
