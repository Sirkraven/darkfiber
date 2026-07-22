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
