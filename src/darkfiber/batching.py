"""
DarkFiber MAS v5 — Nivel 1: micro-batching asíncrono para el MLClient.

Problema: inferir canal por canal serializa la latencia (N llamadas de ~6 ms).
Solución: un colector asíncrono que agrupa espectrogramas en un solo tensor
(N, 1, H, W) y ejecuta UNA pasada de ONNX Runtime. Compatible con el patrón
de inyección de dependencias del proyecto (DF_ML_BACKEND): envuelve cualquier
`infer_fn(batch)->labels` sin acoplarse a ONNX.

Nota de honestidad: el speedup real depende del modelo y el hardware; este
módulo entrega el mecanismo, y `run_on_stanford.py` permite medirlo con
DASNetv2 real en tu máquina.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

import numpy as np


class AsyncMicroBatcher:
    """Agrupa peticiones de inferencia y las despacha en lotes.

    infer_fn: callable síncrono (np.ndarray (N,...)) -> list/np.ndarray de N
              resultados. Se ejecuta con asyncio.to_thread (regla del proyecto:
              nada CPU-bound bloquea el event loop).
    """

    def __init__(
        self,
        infer_fn: Callable[[np.ndarray], list],
        max_batch: int = 64,
        max_wait_ms: float = 20.0,
    ):
        self._infer = infer_fn
        self.max_batch = max_batch
        self.max_wait = max_wait_ms / 1000.0
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Arranca el loop de despacho si no está corriendo (idempotente)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Detiene el loop y FALLA los pendientes (nunca futures colgados)."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._fail_pending(RuntimeError("AsyncMicroBatcher detenido"))

    def _fail_pending(self, exc: BaseException) -> None:
        while not self._queue.empty():
            try:
                _, fut = self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - carrera benigna
                break
            if not fut.done():
                fut.set_exception(exc)

    async def submit(self, spec: np.ndarray):
        """Encola un espectrograma; resuelve cuando el lote fue inferido.

        Auto-arranca el loop en el primer uso: un submit() sin start()
        previo jamás debe colgar en silencio.
        """
        await self.start()
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((spec, fut))
        return await fut

    async def _loop(self) -> None:
        try:
            while True:
                spec, fut = await self._queue.get()
                batch = [(spec, fut)]
                deadline = asyncio.get_running_loop().time() + self.max_wait
                while len(batch) < self.max_batch:
                    timeout = deadline - asyncio.get_running_loop().time()
                    if timeout <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(self._queue.get(), timeout)
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                try:
                    # El stack va DENTRO del try: shapes heterogéneos deben
                    # fallar los futures del lote, no matar el loop entero.
                    tensor = np.stack([b[0] for b in batch]).astype(np.float32)
                    results = await asyncio.to_thread(self._infer, tensor)
                    if len(results) != len(batch):
                        raise RuntimeError(
                            f"infer_fn devolvió {len(results)} resultados para "
                            f"un lote de {len(batch)}: contrato roto."
                        )
                    for (_, f), r in zip(batch, results, strict=True):
                        if not f.done():
                            f.set_result(r)
                except Exception as exc:  # noqa: BLE001 - propagar al llamador
                    for _, f in batch:
                        if not f.done():
                            f.set_exception(exc)
        except asyncio.CancelledError:
            # Cancelación limpia: nada de futures huérfanos.
            self._fail_pending(asyncio.CancelledError("batcher cancelado"))
            raise


def make_onnx_batch_infer(onnx_path: str, input_name: str = "input"):
    """Fábrica de infer_fn para ONNX Runtime (import diferido)."""
    import onnxruntime as ort  # import local: dependencia opcional

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    def infer(batch: np.ndarray):
        (logits,) = sess.run(None, {input_name: batch})
        return list(np.argmax(logits, axis=1))

    return infer
