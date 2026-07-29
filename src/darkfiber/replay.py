"""
DarkFiber MAS v5 — replay.py (C1): simulador de interrogador.

Lee un H5 (QuakeFlow DAS) o NPZ ya descargado/convertido y lo emite como
un flujo de chunks paced en tiempo real (o acelerado con `--speed N`),
exactamente como lo haría un interrogador en vivo. Es la fuente de verdad
para desarrollar y probar `stream_runner.py` sin hardware.

Uso como librería (lo que consume `stream_runner.py` y el test de
paridad): `replay(data, fs, chunk_s, speed)` es un generador async puro,
sin tocar disco -- separado de `load_file`, que sí lee del disco. Uso
como CLI: solo demuestra el pacing (imprime progreso); no corre el
pipeline -- para eso, `stream_runner.py` importa `replay()` directamente
en el mismo proceso en vez de leer un pipe de stdout. Serializar chunks
numpy entre dos procesos por un pipe de shell literal quedó fuera de
alcance de C1 (no lo pide la aceptación: paridad de veredictos + sin
lag a --speed 10, ambas alcanzables en-proceso) -- deuda declarada para
cuando haya hardware real hablando un protocolo de verdad.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import AsyncIterator, Iterator

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .run_on_quakeflow import load_quakeflow_h5

DEFAULT_CHUNK_S = 1.0


def load_file(
    path: str, key: str = "data", fs: float | None = None, dx: float | None = None
) -> tuple[np.ndarray, float, float, dict]:
    """Carga un H5 de QuakeFlow o un NPZ real. Devuelve (data[canales,
    muestras] float32, fs, dx, attrs).

    H5: fs/dx se leen de los attrs embebidos (ver `load_quakeflow_h5`),
    `fs`/`dx` acá son overrides opcionales por si hace falta forzarlos.
    NPZ: sin convención de attrs estandarizada en el proyecto (a
    diferencia de QuakeFlow) -- `fs` y `dx` son OBLIGATORIOS, mismo
    contrato que `run_on_stanford.py --fs --dx`.
    """
    lower = path.lower()
    if lower.endswith((".h5", ".hdf5")):
        data, file_fs, file_dx, attrs = load_quakeflow_h5(path, key=key)
        return data, (fs if fs is not None else file_fs), (dx if dx is not None else file_dx), attrs
    if lower.endswith(".npz"):
        if fs is None or dx is None:
            raise SystemExit("Para NPZ hacen falta --fs y --dx explícitos (sin attrs embebidos).")
        with np.load(path) as z:
            if key not in z:
                candidates = [k for k in z if np.asarray(z[k]).ndim == 2]
                if not candidates:
                    raise SystemExit(
                        f"{path}: no se encontró un array 2D (claves: {list(z.keys())})"
                    )
                key = candidates[0]
            data = np.asarray(z[key], dtype=np.float32)
        return data, fs, dx, {}
    raise SystemExit(f"{path}: extensión no soportada (se espera .h5/.hdf5/.npz)")


def load_hdf5_generic(
    path: str, fs: float | None = None, dx: float | None = None, key: str | None = None
) -> tuple[np.ndarray, float, float, dict]:
    """Carga un HDF5 genérico -- NO QuakeFlow (ej. FORESEE, Valencia, PubDAS
    en general). Devuelve (data[canales, muestras] float32, fs, dx, attrs).

    A propósito NO reusa `load_quakeflow_h5`: esa función tiene defaults
    silenciosos si faltan los attrs (`dt_s`->0.01, `dx_m`->8.0) -- correcto
    para QuakeFlow (que sí trae esos attrs por convención), pero peligroso
    acá, donde no hay ninguna convención de attrs garantizada. Confirmado
    en el archivo real de FORESEE (`FORESEE_UTC_20190404_194804.hdf5`):
    ni el archivo ni el dataset `raw` traen NINGÚN attr -- si este loader
    intentara leer `dt_s`/`dx_m` con default, asumiría fs=100Hz/dx=8m en
    silencio (el default de QuakeFlow) contra el fs=125Hz/dx=2m real de
    FORESEE, un error silencioso de sitio completo. `fs`/`dx` son
    OBLIGATORIOS acá, mismo contrato que `.npz` en `load_file` --
    `SystemExit` si faltan, nunca asumidos.

    `key`: nombre (o ruta anidada, ej. `"grupo/subgrupo/dataset"` --
    h5py soporta indexado con `/` nativamente) del dataset a leer. Si no
    se da, prueba `"raw"` primero (la convención observada en el archivo
    real de FORESEE), después el primer dataset 2D que encuentre en la
    raíz (mismo fallback defensivo que `load_quakeflow_h5`) -- sirve
    tanto para FORESEE como para Valencia sin necesitar dos loaders
    separados, aunque cada uno necesite un `key` explícito distinto
    (Valencia está anidado 3 niveles, `fa1-<id>/Source1/Zone1/SR_Valencia`
    -- el nombre del grupo raíz varía por archivo/interrogador, así que
    NO hay un default posible para ese caso, tiene que pasarse `key`).

    **Layout 3D (Valencia/Febus)**: a diferencia del `raw` 2D de FORESEE
    (canales × muestras directo), el dataset real de Valencia tiene shape
    `(n_bloques, muestras_por_bloque, n_canales)` -- confirmado en el
    archivo real (`(601, 250, 2977)`, con el atributo `SamplingRate=250`
    del grupo padre coincidiendo EXACTO con `muestras_por_bloque=250`,
    la evidencia de que esa dimensión es "muestras dentro de 1s a fs
    real", no una coincidencia asumida). Si el dataset resuelto es 3D,
    se verifica que la dimensión del medio coincida con `round(fs)`
    (si no coincide, falla fuerte -- no se asume el layout a ciegas para
    un archivo 3D distinto) y se reordena a `(canales, tiempo)` con
    `transpose(2, 0, 1).reshape(n_ch, -1)`.
    """
    if fs is None or dx is None:
        raise SystemExit(
            "Para HDF5 genérico hacen falta --fs y --dx explícitos "
            "(sin convención de attrs confiable, a diferencia de QuakeFlow)."
        )
    import h5py

    with h5py.File(path, "r") as fh:
        if key is not None:
            if key not in fh or not isinstance(fh[key], h5py.Dataset):
                raise SystemExit(
                    f"{path}: no se encontró el dataset '{key}' (claves: {list(fh.keys())})"
                )
            ds = fh[key]
        elif "raw" in fh and isinstance(fh["raw"], h5py.Dataset) and fh["raw"].ndim == 2:
            ds = fh["raw"]
        else:
            candidates = [k for k in fh if isinstance(fh[k], h5py.Dataset) and fh[k].ndim in (2, 3)]
            if not candidates:
                raise SystemExit(
                    f"{path}: no se encontró un dataset 2D/3D (claves: {list(fh.keys())})"
                )
            ds = fh[candidates[0]]

        if ds.ndim == 3:
            n_blocks, samples_per_block, n_ch = ds.shape
            if samples_per_block != round(fs):
                raise SystemExit(
                    f"{path}: dataset 3D con shape {ds.shape} -- la dimensión del medio "
                    f"({samples_per_block}) no coincide con fs={fs} (round={round(fs)}); "
                    "el layout (bloques, muestras/bloque, canales) asumido para Valencia/Febus "
                    "no aplica acá, no se reordena a ciegas."
                )
            raw = np.asarray(ds[()], dtype=np.float32)
            data = raw.transpose(2, 0, 1).reshape(n_ch, n_blocks * samples_per_block)
        elif ds.ndim == 2:
            data = np.asarray(ds[()], dtype=np.float32)
        else:
            raise SystemExit(f"{path}: dataset '{ds.name}' tiene ndim={ds.ndim}, se esperaba 2 o 3")
    return data, fs, dx, {}


def load_tdms(
    path: str, fs: float | None = None, dx: float | None = None
) -> tuple[np.ndarray, float, float, dict]:
    """Carga un TDMS de National Instruments -- FOSSA (PubDAS). Devuelve
    (data[canales, muestras] float32, fs, dx, attrs).

    **Benchmark de lectura parcial (F1.5), hecho contra un archivo real**
    (`westSac_170906155429.tdms`, 698,880,000 bytes crudos, 11,648
    canales x 30,000 muestras, int16): la lectura parcial por canal de
    `npTDMS` en modo streaming (`TdmsFile.open()` + 11,648 llamadas a
    `channel.read_data(offset, length)`, una por canal) tardó MÁS DE
    120s sin terminar. La lectura completa eager (`TdmsFile.read()` +
    apilar los 11,648 canales con `ch[:]`) tardó **14.6s** para el mismo
    archivo. **La lectura parcial NO es más rápida acá** -- cada llamada
    a `read_data()` en modo streaming aparenta re-parsear/buscar la
    estructura del segmento TDMS de forma independiente, sin el
    beneficio amortizado de un parseo único que sí tiene la lectura
    eager. Por eso este loader SIEMPRE hace lectura completa del
    archivo -- confirmado con evidencia (no elegido por default, y no
    es lo que se había propuesto originalmente en el pre-registro).

    Consecuencia para el esquema de muestreo de FOSSA (F1.3 §1c): en vez
    de lectura parcial bajo demanda, el esquema real es "archivo
    completo por trial" -- cada trial sortea 1 de los K archivos y
    carga ESE archivo entero (~14.6s + ~1.4GB en RAM tras el upcast a
    float32, liberado después) -- sigue acotado a 1 archivo en RAM a la
    vez (nunca los K simultáneos), solo que el costo por trial es más
    alto de lo que se había estimado con la lectura parcial que resultó
    inviable. Ver `snr_curve.run_step_lazy_single_file` para la
    implementación de este esquema.

    `fs`/`dx` OBLIGATORIOS (mismo contrato que los demás loaders no-QuakeFlow
    de este módulo, nunca leídos en silencio) -- corrección F1.5 sobre una
    afirmación previa incorrecta: grupo y canales SÍ vienen con
    `properties={}` vacío en el archivo real, pero el ARCHIVO (`tdms.properties`,
    no `group.properties` ni `channel.properties`) trae metadata rica del
    interrogador iDAS, incluyendo `SamplingFrequency[Hz]` y
    `SpatialResolution[m]` -- confirmado en el archivo real (500.0 y 2.0,
    coincidiendo exacto con lo ya usado). Como no todo TDMS de otro
    vendor/modelo va a traer esas claves exactas (es convención de iDAS, no
    del formato TDMS en general), `fs`/`dx` se mantienen obligatorios en vez
    de leerse solos del header -- pero si el header SÍ trae esas claves, "el
    header manda": se cruza contra lo pasado y falla fuerte en desacuerdo,
    mismo patrón que el guard de fs de `convert_stanford_sgy`/`read_segy`
    en `snr_curve.py`.
    """
    if fs is None or dx is None:
        raise SystemExit(
            "Para TDMS hacen falta --fs y --dx explícitos (nunca se leen "
            "en silencio, aunque el header a veces los tenga -- ver docstring)."
        )
    from nptdms import TdmsFile

    tdms = TdmsFile.read(path)
    header_fs = tdms.properties.get("SamplingFrequency[Hz]")
    if header_fs is not None and abs(float(header_fs) - fs) > 1e-6:
        raise SystemExit(
            f"{path}: --fs={fs} no coincide con SamplingFrequency[Hz] del header TDMS "
            f"({header_fs}) -- no se ignora el header, se corrige --fs o se omite."
        )
    header_dx = tdms.properties.get("SpatialResolution[m]")
    if header_dx is not None and abs(float(header_dx) - dx) > 1e-6:
        raise SystemExit(
            f"{path}: --dx={dx} no coincide con SpatialResolution[m] del header TDMS "
            f"({header_dx}) -- no se ignora el header, se corrige --dx o se omite."
        )
    groups = tdms.groups()
    if not groups:
        raise SystemExit(f"{path}: TDMS sin grupos")
    channels = groups[0].channels()
    if not channels:
        raise SystemExit(f"{path}: TDMS sin canales en el grupo '{groups[0].name}'")
    data = np.stack([ch[:] for ch in channels]).astype(np.float32)
    return data, fs, dx, {}


def iter_chunks(
    data: np.ndarray, fs: float, chunk_s: float = DEFAULT_CHUNK_S
) -> Iterator[np.ndarray]:
    """Parte `data` (n_ch, n_t) en chunks consecutivos de ~chunk_s
    segundos, sin traslape ni pacing -- generador puro, usado tanto por
    `replay()` (con pacing) como por tests (sin pacing, a máxima
    velocidad). El último chunk puede ser más corto."""
    n_t = data.shape[1]
    chunk_n = max(1, int(round(chunk_s * fs)))
    for start in range(0, n_t, chunk_n):
        yield data[:, start : start + chunk_n]


async def replay(
    data: np.ndarray,
    fs: float,
    chunk_s: float = DEFAULT_CHUNK_S,
    speed: float | None = 1.0,
) -> AsyncIterator[np.ndarray]:
    """Emite `data` como flujo async de chunks.

    `speed`: 1.0 = tiempo real, 10.0 = 10x más rápido, `None` o <=0 = sin
    pacing (emite tan rápido como el consumidor pueda procesar -- para
    tests). El pacing ancla contra el reloj de pared desde el primer
    chunk (tiempo objetivo acumulado, no `sleep(chunk_s/speed)` por
    chunk) para no acumular drift por el propio overhead del sleep y del
    procesamiento aguas abajo.
    """
    loop = asyncio.get_running_loop()
    t_start = loop.time()
    emitted_s = 0.0
    for chunk in iter_chunks(data, fs, chunk_s):
        this_chunk_s = chunk.shape[1] / fs
        if speed and speed > 0:
            target = t_start + (emitted_s + this_chunk_s) / speed
            delay = target - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
        emitted_s += this_chunk_s
        yield chunk


def main() -> None:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Simulador de interrogador: emite un H5/NPZ como flujo real-time (demo de pacing)."
    )
    ap.add_argument("--h5", help="Archivo .h5 de QuakeFlow DAS")
    ap.add_argument("--npz", help="Archivo .npz real (requiere --fs y --dx)")
    ap.add_argument("--key", default="data")
    ap.add_argument("--fs", type=float, default=None)
    ap.add_argument("--dx", type=float, default=None)
    ap.add_argument("--chunk-s", type=float, default=DEFAULT_CHUNK_S)
    ap.add_argument("--speed", type=float, default=1.0, help="1.0=tiempo real, 0=sin pacing")
    args = ap.parse_args()

    path = args.h5 or args.npz
    if not path:
        raise SystemExit("Indicá --h5 o --npz")
    data, fs, dx, _attrs = load_file(path, key=args.key, fs=args.fs, dx=args.dx)
    n_ch, n_t = data.shape
    total_s = n_t / fs
    print(
        f"Replay de {path}: {n_ch} canales, {n_t} muestras, {total_s:.1f}s @ {fs:.2f}Hz, "
        f"chunk={args.chunk_s}s, speed={args.speed}"
    )

    async def _run() -> None:
        t0 = time.perf_counter()
        n_chunks = 0
        n_samples = 0
        async for chunk in replay(data, fs, args.chunk_s, args.speed):
            n_chunks += 1
            n_samples += chunk.shape[1]
            elapsed = time.perf_counter() - t0
            print(
                f"  chunk {n_chunks:5d}  +{chunk.shape[1] / fs:5.2f}s de stream  "
                f"({n_samples / fs:7.1f}s / {total_s:.1f}s emitidos, {elapsed:6.2f}s de reloj real)",
                end="\r",
            )
        elapsed = time.perf_counter() - t0
        print()
        print(
            f"Listo: {n_chunks} chunks, {total_s:.1f}s de archivo emitidos en {elapsed:.2f}s de reloj real."
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
