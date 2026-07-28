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


def _write_hdf5_3d_febus(tmp_path, n_blocks=4, samples_per_block=250, n_ch=5, nested=True):
    """Simula el layout real de Valencia: dataset 3D
    `(n_bloques, muestras_por_bloque, n_canales)`, anidado bajo grupos
    (mismo patrón que el archivo real:
    `fa1-<id>/Source1/Zone1/SR_Valencia`)."""
    rng = np.random.default_rng(0)
    data = rng.standard_normal((n_blocks, samples_per_block, n_ch)).astype(np.float32)
    path = tmp_path / "test_valencia_like.hdf5"
    with h5py.File(path, "w") as fh:
        if nested:
            grp = fh.create_group("fa1-test/Source1/Zone1")
            grp.create_dataset("SR_Valencia", data=data)
        else:
            fh.create_dataset("SR_Valencia", data=data)
    return str(path), data


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


def test_injection_arithmetic_never_rounds_through_float16(hdf5_path):
    """Prueba más estricta que la anterior: no solo que la detección
    sobreviva, sino que la ARITMÉTICA de inyección (wavelet + suma con
    ruido) nunca pasa por float16 en ningún punto intermedio -- pedido
    explícito tras el hallazgo de float16 en FORESEE (misma preocupación
    que el int16 de FOSSA, pero por REDONDEO en vez de truncamiento a
    cero: float16 tiene ~3 dígitos de precisión y rango dinámico chico).

    Método: si algún paso de `add_plane_wave` redondeara internamente a
    float16, cada valor inyectado caería EXACTO en la grilla discreta de
    float16 (round-trip float16->float32 sin cambio). Con aritmética
    real en float32 (o superior, como usa `noise_rms`/`wavelet_rms` en
    float64), los valores inyectados son continuos y prácticamente NUNCA
    caen justo en esa grilla -- una coincidencia exacta en el 100% de
    las muestras solo pasa si hubo cuantización real, no por azar."""
    from darkfiber.synth import add_plane_wave, ricker, snr_to_amplitude

    data, fs, dx, _ = load_hdf5_generic(hdf5_path, fs=FS, dx=DX)
    assert data.dtype == np.float32, (
        "el loader debe upcastear a float32 antes de que nada más toque el array"
    )

    before = data.copy()
    wav = ricker(6.0, fs)  # 6.0 = frecuencia central, dur_s=0.8 default
    # RMS de ruido/wavelet ya se calculan en float64 dentro de synth.py
    # (noise_rms/wavelet_rms hacen .astype(np.float64) explícito) --
    # confirmado leyendo el código, no asumido; acá solo se ejercita.
    amp = snr_to_amplitude(1.0, data, wav)  # SNR=1, el escalón más frágil
    add_plane_wave(data, fs, dx, v_app_mps=3200.0, t0_s=20.0, wavelet=wav, amp=amp, seed=0)

    assert data.dtype == np.float32, "la inyección no debe cambiar el dtype del buffer"
    diff = data - before
    injected = diff[diff != 0]
    assert injected.size > 0, (
        "la inyección no tocó ninguna muestra -- t0_s/ventana mal elegidos para este test"
    )

    # Si la aritmética hubiera pasado por float16 en algún punto, TODOS
    # los valores inyectados serían un punto fijo de ida-y-vuelta por
    # float16 (por definición: ya estarían en esa grilla). Con
    # aritmética float32 real, la fracción que coincide exacto debe ser
    # ~0 -- no una coincidencia posible con valores continuos reales.
    roundtrip_f16 = injected.astype(np.float16).astype(np.float32)
    exact_match_fraction = np.mean(injected == roundtrip_f16)
    assert exact_match_fraction < 0.05, (
        f"{exact_match_fraction:.1%} de los valores inyectados caen exactos en la "
        "grilla de float16 -- sugiere que la aritmética de inyección pasó por "
        "float16 en algún punto, no se mantuvo en float32 como debería"
    )


def test_3d_febus_layout_reshapes_correctly(tmp_path):
    """Layout real de Valencia: dataset 3D `(bloques, muestras/bloque,
    canales)`, anidado bajo grupos, accedido con una ruta `key`
    (h5py soporta indexado con `/` nativo). Verifica el reordenamiento
    exacto a `(canales, tiempo)` contra los datos escritos, no solo el
    shape final."""
    n_blocks, samples_per_block, n_ch = 4, 250, 5
    path, written = _write_hdf5_3d_febus(tmp_path, n_blocks, samples_per_block, n_ch)
    data, fs, dx, attrs = load_hdf5_generic(
        path, fs=250.0, dx=16.8, key="fa1-test/Source1/Zone1/SR_Valencia"
    )
    assert data.shape == (n_ch, n_blocks * samples_per_block)
    assert data.dtype == np.float32
    # Reconstruye a mano lo mismo que debería hacer el loader y compara
    # exacto -- no solo el shape, el REORDENAMIENTO real de valores.
    expected = written.transpose(2, 0, 1).reshape(n_ch, n_blocks * samples_per_block)
    np.testing.assert_array_equal(data, expected)
    # Canal 0, primeros `samples_per_block` valores == bloque 0 del canal 0
    np.testing.assert_array_equal(data[0, :samples_per_block], written[0, :, 0])


def test_3d_layout_rejects_mismatched_fs(tmp_path):
    """Si la dimensión del medio del dataset 3D NO coincide con `fs`
    (`round(fs)`), el layout (bloques, muestras/bloque, canales) NO se
    asume a ciegas -- falla fuerte en vez de reordenar mal en silencio."""
    path, _ = _write_hdf5_3d_febus(tmp_path, n_blocks=4, samples_per_block=250, n_ch=5)
    with pytest.raises(SystemExit):
        load_hdf5_generic(path, fs=125.0, dx=16.8, key="fa1-test/Source1/Zone1/SR_Valencia")


def test_nested_group_path_key_works(tmp_path):
    """`key` acepta una ruta anidada completa (`grupo/subgrupo/dataset`)
    -- necesario porque Valencia real anida el dataset 3 niveles bajo
    grupos (`fa1-<id>/Source1/Zone1/SR_Valencia`), no en la raíz del
    archivo como FORESEE."""
    path, written = _write_hdf5_3d_febus(tmp_path, n_blocks=2, samples_per_block=250, n_ch=3)
    data, fs, dx, _ = load_hdf5_generic(
        path, fs=250.0, dx=16.8, key="fa1-test/Source1/Zone1/SR_Valencia"
    )
    assert data.shape == (3, 500)
