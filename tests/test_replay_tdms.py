"""Tests for `replay.load_tdms` (F1.5, FOSSA): loader nuevo para TDMS de
National Instruments (Silixa/decimator, PubDAS). Fixtures sintéticas
(`nptdms.TdmsWriter`), no el archivo real (que no está en el repo).

No toca el path de veredicto -- exclusivamente la capa de carga.
"""

from __future__ import annotations

import numpy as np
import pytest
from nptdms import ChannelObject, TdmsWriter

from darkfiber.replay import load_tdms

FS = 500.0
DX = 2.0
N_CH = 6
N_T = 30000  # 60s @ 500Hz, igual que el archivo real de FOSSA


def _write_tdms(tmp_path, dtype=np.int16, group_name="Measurement"):
    rng = np.random.default_rng(0)
    if np.issubdtype(dtype, np.integer):
        data = rng.integers(-2000, 2000, size=(N_CH, N_T)).astype(dtype)
    else:
        data = (rng.standard_normal((N_CH, N_T)) * 0.01).astype(dtype)
    path = tmp_path / "test_array.tdms"
    with TdmsWriter(str(path)) as writer:
        channels = [ChannelObject(group_name, str(i), data[i]) for i in range(N_CH)]
        writer.write_segment(channels)
    return str(path)


@pytest.fixture
def tdms_path(tmp_path):
    return _write_tdms(tmp_path)


def test_requires_explicit_fs_dx(tdms_path):
    """Sin fs/dx explícitos, falla fuerte -- el TDMS real de FOSSA no
    trae properties confiables (confirmado: properties={} en el archivo
    real, grupo y canales), nunca se asumen."""
    with pytest.raises(SystemExit):
        load_tdms(tdms_path)
    with pytest.raises(SystemExit):
        load_tdms(tdms_path, fs=FS)
    with pytest.raises(SystemExit):
        load_tdms(tdms_path, dx=DX)


def test_shape_dtype_matches_real_foresee_pattern(tdms_path):
    """Shape/dtype correctos, upcast a float32 confirmado -- mismo
    contrato que los demás loaders no-QuakeFlow de este módulo."""
    data, fs, dx, attrs = load_tdms(tdms_path, fs=FS, dx=DX)
    assert fs == FS
    assert dx == DX
    assert data.shape == (N_CH, N_T)
    assert data.dtype == np.float32
    assert attrs == {}


def test_channel_order_preserved(tmp_path):
    """Los canales se apilan en el mismo orden en que aparecen en el
    grupo TDMS (nombre '0'..'N-1', 0-indexado, confirmado contra el
    archivo real de FOSSA) -- no se reordenan por accidente."""
    rng = np.random.default_rng(1)
    known = rng.integers(-1000, 1000, size=(N_CH, N_T)).astype(np.int16)
    path = tmp_path / "ordered.tdms"
    with TdmsWriter(str(path)) as writer:
        channels = [ChannelObject("Measurement", str(i), known[i]) for i in range(N_CH)]
        writer.write_segment(channels)
    data, _, _, _ = load_tdms(str(path), fs=FS, dx=DX)
    np.testing.assert_array_equal(data, known.astype(np.float32))


def test_low_snr_injection_survives_int16_source_via_tdms(tdms_path):
    """Supervivencia a SNR=1 (el escalón más frágil) sobre datos int16
    cargados vía TDMS -- mismo chequeo ya hecho para el int16 de FOSSA
    en F1.4 (`test_snr_curve.py`), ahora contra el loader TDMS real en
    vez de un `.npz` sintético con dtype forzado."""
    from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config
    from darkfiber.selftest import inject_and_verify_sized

    data, fs, dx, _ = load_tdms(tdms_path, fs=FS, dx=DX)
    geom = ArrayGeometry(n_channels=N_CH, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config()
    coh_cfg = CoherenceConfig()
    result = inject_and_verify_sized(data, geom, t0cfg, coh_cfg, v_app_mps=3200.0, snr=1.0, seed=0)
    assert result is not None, "la ventana debería ser suficiente para esta apertura chica"


def test_injection_arithmetic_never_rounds_through_int16(tdms_path):
    """Prueba de grilla, análoga a la de float16 de FORESEE
    (`test_replay_hdf5_generic.py::test_injection_arithmetic_never_rounds_through_float16`):
    si la aritmética de inyección redondeara a través de int16 en algún
    punto, cada valor inyectado sería un entero exacto (round-trip
    int16->float32 sin cambio). Con aritmética float32 real, los valores
    inyectados son continuos y prácticamente NUNCA caen en la grilla
    entera -- una coincidencia total del 100% solo pasa si hubo
    cuantización real."""
    from darkfiber.synth import add_plane_wave, ricker, snr_to_amplitude

    data, fs, dx, _ = load_tdms(tdms_path, fs=FS, dx=DX)
    assert data.dtype == np.float32, (
        "el loader debe upcastear a float32 antes de que nada más toque el array"
    )

    before = data.copy()
    wav = ricker(6.0, fs)
    amp = snr_to_amplitude(1.0, data, wav)  # SNR=1, el escalón más frágil
    add_plane_wave(data, fs, dx, v_app_mps=3200.0, t0_s=20.0, wavelet=wav, amp=amp, seed=0)

    assert data.dtype == np.float32, "la inyección no debe cambiar el dtype del buffer"
    diff = data - before
    injected = diff[diff != 0]
    assert injected.size > 0, (
        "la inyección no tocó ninguna muestra -- t0_s mal elegido para este test"
    )

    # Si la aritmética hubiera pasado por int16 (truncamiento), TODOS los
    # valores inyectados serían enteros exactos. Con aritmética float32
    # real, la fracción que coincide exacto con su propio redondeo a
    # entero debe ser ~0 -- no una coincidencia posible con valores
    # continuos reales (a diferencia de float16, acá el chequeo es
    # contra la grilla ENTERA, no la grilla float16).
    rounded = np.round(injected)
    exact_match_fraction = np.mean(injected == rounded)
    assert exact_match_fraction < 0.05, (
        f"{exact_match_fraction:.1%} de los valores inyectados son enteros exactos -- "
        "sugiere que la aritmética de inyección pasó por int16 (truncamiento) en algún "
        "punto, no se mantuvo en float32 como debería"
    )
