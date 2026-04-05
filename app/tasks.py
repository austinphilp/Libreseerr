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


_tasks: dict[str, RequestTask] = {}


def create_request_task(client: ReadarrClient, title: str, author: str, goodreads_id: str | None) -> RequestTask:
    task_id = str(uuid.uuid4())
    task = RequestTask(id=task_id, status='submitted', message='Request submitted')
    _tasks[task_id] = task

    async def runner() -> None:
        try:
            _tasks[task_id] = RequestTask(id=task_id, status='processing', message='Submitting to Readarr')
            result = await client.request_book(title=title, author=author, goodreads_id=goodreads_id)
            _tasks[task_id] = RequestTask(id=task_id, status='success', message=result)
        except Exception as exc:
            _tasks[task_id] = RequestTask(id=task_id, status='error', message=str(exc))

    asyncio.create_task(runner())
    return task


def get_request_task(task_id: str) -> RequestTask | None:
    return _tasks.get(task_id)
