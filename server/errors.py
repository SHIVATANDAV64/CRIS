from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import logging

logger = logging.getLogger("cris")


def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "path": request.url.path
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "message": "Validation Error",
                "details": exc.errors(),
                "path": request.url.path
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception at {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Internal Server Error",
                "path": request.url.path
            },
        )
