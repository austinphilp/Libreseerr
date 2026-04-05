from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from .readarr import ReadarrClient


@dataclass
class RequestTask:
    id: str
    status: str
    message: str
    title: str
    author: str
    target: str


_tasks: dict[str, RequestTask] = {}
_order: list[str] = []


def create_request_task(client: ReadarrClient, title: str, author: str, target: str, goodreads_id: str | None) -> RequestTask:
    task_id = str(uuid.uuid4())
    task = RequestTask(id=task_id, status='submitted', message='Request submitted', title=title, author=author, target=target)
    _tasks[task_id] = task
    _order.insert(0, task_id)
    del _order[20:]

    async def runner() -> None:
        try:
            _tasks[task_id] = RequestTask(id=task_id, status='processing', message='Submitting to Readarr', title=title, author=author, target=target)
            result = await client.request_book(title=title, author=author, goodreads_id=goodreads_id)
            _tasks[task_id] = RequestTask(id=task_id, status='success', message=result, title=title, author=author, target=target)
        except Exception as exc:
            _tasks[task_id] = RequestTask(id=task_id, status='error', message=str(exc), title=title, author=author, target=target)

    asyncio.create_task(runner())
    return task


def get_request_task(task_id: str) -> RequestTask | None:
    return _tasks.get(task_id)


def list_request_tasks() -> list[RequestTask]:
    return [_tasks[task_id] for task_id in _order if task_id in _tasks]
