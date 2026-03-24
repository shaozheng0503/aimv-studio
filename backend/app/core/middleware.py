"""Global error handling middleware."""

import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            raise  # let FastAPI's own handler format 4xx/5xx correctly
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": str(e) if request.app.debug else "Something went wrong",
                },
            )
