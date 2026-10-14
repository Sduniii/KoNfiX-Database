import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Coroutine
from dataclasses import dataclass, field


@dataclass
class OpenKnxTask:
    task_id: str
    name: str
    task_type: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    logs: List[str] = field(default_factory=list)
    cancel_requested: bool = False
    _asyncio_task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "logs": self.logs[-50:],  # return last 50 log lines
        }


class TaskRunner:
    def __init__(self):
        self._tasks: Dict[str, OpenKnxTask] = {}
        self._lock = asyncio.Lock()

    def create_task(
        self,
        name: str,
        task_type: str,
        target_coro: Callable[["OpenKnxTask"], Coroutine[Any, Any, Any]],
    ) -> OpenKnxTask:
        task_id = str(uuid.uuid4())
        task_obj = OpenKnxTask(task_id=task_id, name=name, task_type=task_type)
        self._tasks[task_id] = task_obj

        async def _wrapper():
            task_obj.status = "running"
            task_obj.updated_at = datetime.utcnow()
            task_obj.logs.append(f"Task '{name}' gestartet.")
            try:
                await target_coro(task_obj)
                if not task_obj.cancel_requested and task_obj.status != "failed":
                    task_obj.status = "completed"
                    task_obj.progress = 100
                    task_obj.logs.append("Task erfolgreich abgeschlossen.")
            except asyncio.CancelledError:
                task_obj.status = "cancelled"
                task_obj.logs.append("Task wurde abgebrochen.")
            except Exception as ex:
                task_obj.status = "failed"
                task_obj.error = str(ex)
                task_obj.logs.append(f"Fehler: {ex}")
            finally:
                task_obj.updated_at = datetime.utcnow()

        t = asyncio.create_task(_wrapper())
        task_obj._asyncio_task = t
        return task_obj

    def get_task(self, task_id: str) -> Optional[OpenKnxTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        sorted_tasks = sorted(
            self._tasks.values(), key=lambda t: t.created_at, reverse=True
        )
        return [t.to_dict() for t in sorted_tasks[:limit]]

    def cancel_task(self, task_id: str) -> bool:
        task_obj = self._tasks.get(task_id)
        if not task_obj or task_obj.status in ("completed", "failed", "cancelled"):
            return False
        task_obj.cancel_requested = True
        task_obj.status = "cancelled"
        if task_obj._asyncio_task and not task_obj._asyncio_task.done():
            task_obj._asyncio_task.cancel()
        task_obj.updated_at = datetime.utcnow()
        task_obj.logs.append("Abbruch angefordert.")
        return True


task_runner = TaskRunner()
