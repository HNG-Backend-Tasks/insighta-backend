import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import admin_router, read_router
from .auth.router import auth_router
from .database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insighta")

request_counts: dict = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Invalid query parameters"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.middleware("http")
async def require_api_version(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if request.headers.get("X-API-Version") != "1":
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "API version header required"},
            )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info(
        f"{request.method} {request.url.path} {response.status_code} {duration:.3f}s"
    )
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    now = time.time()
    path = request.url.path
    client_host = request.client.host if request.client else "testclient"

    if path.startswith("/auth/"):
        key = f"{client_host}:{path}"
        limit = 10
    else:
        token = request.headers.get("Authorization", "") or request.cookies.get(
            "access_token", ""
        )
        key = f"{token}:{path}" if token else f"{client_host}:{path}"
        limit = 60

    request_counts[key] = [t for t in request_counts[key] if now - t < 60]

    if len(request_counts[key]) >= limit:
        return JSONResponse(
            status_code=429, content={"status": "error", "message": "Too many requests"}
        )

    request_counts[key].append(now)
    return await call_next(request)


app.include_router(auth_router)
app.include_router(read_router)
app.include_router(admin_router)
