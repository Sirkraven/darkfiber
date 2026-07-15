"""Convierte SEG-Y reales del arreglo DAS de Stanford (Stanford-1-Campus, PubDAS
o el repo FiberOpticEarthquakes) a un único NPZ (canales x muestras) que
run_on_stanford.py puede leer.

SEG-Y rev1 estándar: texto 3200B + binario 400B + por traza (240B header +
N muestras). fs, muestras/traza y n_canales se leen del propio header — en
la práctica el archivo trae 626 canales, formato IEEE float32 big-endian
(code 5), pero fs varió con el tiempo (50 Hz en 2016, 100 Hz en otras
épocas según el ejemplo de 2017 usado en la validación real).

Usado para validar dos casos reales:
  - Pawnee M5.8 (telesismo, 2016-09-03) -> COHERENTE_DESCONOCIDO (correcto)
  - East Foothills M4.1 (sismo local, 2017-10-10) -> SISMO_CONFIRMADO
    (ver validacion_real/ para el detalle)

Uso: python convert_stanford_sgy.py <carpeta_con_sgy> --out salida.npz
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio

TXT_HEADER, BIN_HEADER, TRACE_HEADER = 3200, 400, 240


def read_binary_header(fh) -> tuple[int, int, int]:
    """Lee (sample_interval_us, samples_per_trace, data_format_code) del
    binary header SEG-Y (offset 3200, 400 bytes)."""
    fh.seek(TXT_HEADER)
    binh = fh.read(BIN_HEADER)
    sample_interval_us = struct.unpack(">h", binh[16:18])[0]
    samples_per_trace = struct.unpack(">h", binh[20:22])[0]
    data_format_code = struct.unpack(">h", binh[24:26])[0]
    if data_format_code != 5:
        raise ValueError(
            f"formato SEG-Y {data_format_code} no soportado (se esperaba 5=IEEE float32)"
        )
    return sample_interval_us, samples_per_trace, data_format_code


def read_segy(path: Path) -> tuple[np.ndarray, float]:
    """Devuelve (data[canales, muestras], fs_hz) para un archivo SEG-Y."""
    size = path.stat().st_size
    with open(path, "rb") as fh:
        sample_interval_us, samples_per_trace, _ = read_binary_header(fh)
        fs = 1e6 / sample_interval_us
        bytes_per_trace = TRACE_HEADER + 4 * samples_per_trace
        n_traces = (size - TXT_HEADER - BIN_HEADER) / bytes_per_trace
        if n_traces != int(n_traces):
            raise ValueError(
                f"{path.name}: tamaño de archivo no calza con {samples_per_trace} muestras/traza"
            )
        n_traces = int(n_traces)

        fh.seek(TXT_HEADER + BIN_HEADER)
        data = np.empty((n_traces, samples_per_trace), dtype=np.float32)
        for ch in range(n_traces):
            fh.read(TRACE_HEADER)
            raw = fh.read(4 * samples_per_trace)
            data[ch] = np.frombuffer(raw, dtype=">f4").astype(np.float32)
    return data, fs


def main() -> None:
    """CLI de convert_stanford_sgy.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="Carpeta con los .sgy (p.ej. .../data/Pawnee)")
    ap.add_argument("--out", default="pawnee_real.npz")
    ap.add_argument("--key", default="data")
    ap.add_argument(
        "--no-diff",
        action="store_true",
        help="No derivar en el tiempo (por defecto SÍ se deriva: el SEG-Y crudo "
        "trae fase óptica desenrollada, no strain-rate; FIG5_Pawnee_DAS_and_JRSC.py "
        "del repo original deriva antes de todo lo demás)",
    )
    args = ap.parse_args()

    files = sorted(Path(args.folder).glob("*.sgy"))
    if not files:
        raise SystemExit(f"no se encontraron .sgy en {args.folder}")

    chunks = []
    fs_ref = None
    for f in files:
        data, fs = read_segy(f)
        if fs_ref is None:
            fs_ref = fs
        elif fs != fs_ref:
            raise SystemExit(f"{f.name}: fs={fs} no coincide con fs_ref={fs_ref}")
        chunks.append(data)
        print(f"  {f.name}: {data.shape[0]} canales x {data.shape[1]} muestras (fs={fs} Hz)")

    full = np.concatenate(chunks, axis=1)

    if not args.no_diff:
        full = (full[:, 1:] - full[:, :-1]) * fs_ref
        full -= np.median(full, axis=0, keepdims=True)  # quita el drift común (láser) entre canales
        print(
            "Derivada temporal + remoción de drift común aplicadas "
            "(fase óptica -> strain-rate, igual que el paper original)."
        )

    print(
        f"\nMatriz final: {full.shape[0]} canales x {full.shape[1]} muestras "
        f"({full.shape[1] / fs_ref:.1f} s) fs={fs_ref} Hz"
    )
    np.savez(args.out, **{args.key: full.astype(np.float32)})
    print(f"Guardado en {args.out} (key='{args.key}')")


if __name__ == "__main__":
    main()
