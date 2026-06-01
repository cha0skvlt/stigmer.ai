# STIGMER AI — HTTP mapping for stigmergy task endpoints.

from fastapi import HTTPException
from task_errors import TaskConflictError


def conflict_response(error: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"error": error})


def map_task_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskConflictError):
        return conflict_response(exc.error)
    if isinstance(exc, ValueError) and "Unknown card" in str(exc):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc
