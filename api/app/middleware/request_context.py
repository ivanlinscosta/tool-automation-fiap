import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        lab_group = request.headers.get("X-Lab-Group") or "anonymous"

        request.state.request_id = request_id
        request.state.lab_group = lab_group

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "request_id=%s lab_group=%s method=%s path=%s status_code=%s elapsed_ms=%s",
                request_id,
                lab_group,
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
            )