import asyncio
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from typing import Any, Protocol, Self

from longscrape.core.domain.pipeline import (
    FetchRequest,
    PipelineInput,
    RawInput,
    RichEntry,
)
from longscrape.core.domain.queue import InMemoryTaskQueue
from longscrape.core.ports.queue import TaskQueue
from longscrape.core.services.worker import ScraperWorker


class LifecycleResource(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class Crawler:
    def __init__(
        self,
        workers: Mapping[str, ScraperWorker[Any]],
        *,
        queue: TaskQueue | None = None,
        concurrency: int = 1,
        resources: Sequence[LifecycleResource] = (),
        manage_resources: bool = True,
    ) -> None:
        if not workers:
            raise ValueError("workers must not be empty")
        if concurrency < 1:
            raise ValueError("concurrency must be at least one")
        self.workers = dict(workers)
        self.queue = queue or InMemoryTaskQueue()
        self.concurrency = concurrency
        self.resources = tuple(resources)
        self.manage_resources = manage_resources
        self._entered = False
        self._running = False
        self._started_resources: list[LifecycleResource] = []

    async def __aenter__(self) -> Self:
        if self._entered:
            raise RuntimeError("Crawler is already entered")
        self._entered = True
        if self.manage_resources:
            try:
                for resource in self.resources:
                    await resource.start()
                    self._started_resources.append(resource)
            except Exception:
                await self._stop_resources()
                self._entered = False
                raise
        return self

    async def __aexit__(self, *_: object) -> None:
        try:
            if self.manage_resources:
                await self._stop_resources()
        finally:
            self._entered = False

    async def _stop_resources(self) -> None:
        while self._started_resources:
            resource = self._started_resources.pop()
            await resource.stop()

    async def stream(
        self, seeds: PipelineInput | Iterable[PipelineInput]
    ) -> AsyncIterator[RichEntry[Any]]:
        if self._running:
            raise RuntimeError("Crawler already has an active crawl")
        self._running = True
        seed_tasks = (
            (seeds,) if isinstance(seeds, (FetchRequest, RawInput)) else tuple(seeds)
        )
        if not seed_tasks:
            self._running = False
            return

        items: asyncio.Queue[RichEntry[Any]] = asyncio.Queue()
        done = asyncio.Event()
        state_lock = asyncio.Lock()
        pending = 0
        failure: Exception | None = None

        async def submit(task: PipelineInput) -> None:
            nonlocal pending
            async with state_lock:
                pending += 1
                await self.queue.put(task)

        async def complete() -> None:
            nonlocal pending
            async with state_lock:
                pending -= 1
                if pending == 0:
                    done.set()

        async def worker_loop() -> None:
            nonlocal failure
            while not done.is_set():
                task = await self.queue.get()
                try:
                    try:
                        worker = self.workers[task.kind]
                    except KeyError as error:
                        raise ValueError(
                            f"No worker registered for task kind: {task.kind}"
                        ) from error
                    result = await worker.run(task)
                    for child in result.tasks:
                        await submit(child)
                    for item in result.items:
                        await items.put(item)
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001 - surfaced by stream()
                    async with state_lock:
                        if failure is None:
                            failure = error
                            done.set()
                    return
                else:
                    await complete()

        workers = [asyncio.create_task(worker_loop()) for _ in range(self.concurrency)]
        try:
            for task in seed_tasks:
                await submit(task)

            while True:
                if failure is not None:
                    raise failure
                if done.is_set() and items.empty():
                    return

                item_task = asyncio.create_task(items.get())
                done_task = asyncio.create_task(done.wait())
                completed, _ = await asyncio.wait(
                    (item_task, done_task), return_when=asyncio.FIRST_COMPLETED
                )
                if item_task in completed:
                    done_task.cancel()
                    await asyncio.gather(done_task, return_exceptions=True)
                    yield item_task.result()
                else:
                    item_task.cancel()
                    await asyncio.gather(item_task, return_exceptions=True)
        finally:
            done.set()
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            self._running = False

    async def run(
        self, seeds: PipelineInput | Iterable[PipelineInput]
    ) -> list[RichEntry[Any]]:
        return [item async for item in self.stream(seeds)]

    async def stream_inputs(
        self, inputs: PipelineInput | Iterable[PipelineInput]
    ) -> AsyncIterator[RichEntry[Any]]:
        async for item in self.stream(inputs):
            yield item

    async def run_inputs(
        self, inputs: PipelineInput | Iterable[PipelineInput]
    ) -> list[RichEntry[Any]]:
        return await self.run(inputs)
