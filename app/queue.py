"""In-process очередь медленного пути. В проде здесь Redis или Kafka; интерфейс
(submit + воркер) специально такой же, чтобы замена осталась локальной."""
import asyncio
import uuid


class TaskQueue:
    def __init__(self, pipeline, store) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pipeline = pipeline
        self.store = store
        self._worker_task: asyncio.Task | None = None

    def submit(self, payload: dict, result: dict) -> str:
        task_id = uuid.uuid4().hex[:12]
        self.store.put_task(task_id, result["request_id"], "queued")
        # копия результата уже знает свой task_id: иначе GET /v1/tasks/{id} отдаёт task_id=null
        self.queue.put_nowait((task_id, payload, {**result, "task_id": task_id}))
        return task_id

    async def _worker(self) -> None:
        while True:
            task_id, payload, result = await self.queue.get()
            try:
                self.store.put_task(task_id, result["request_id"], "running")
                done = await asyncio.to_thread(self.pipeline.generate, payload, result)
                self.store.put_task(task_id, result["request_id"], "done", done)
            except Exception as exc:  # одна задача не должна убивать воркер
                self.store.put_task(task_id, result["request_id"], "failed", {"error": str(exc)})
            finally:
                self.queue.task_done()

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
