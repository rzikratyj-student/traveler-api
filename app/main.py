import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.locations import create_location_router
from app.plans import create_plan_router

logger = logging.getLogger("traveler_api")

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    database=os.environ["DB_NAME"],
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

app = FastAPI(title="TravelerAPI")

# PostgreSQL error codes (SQLSTATE) that are caused by client data.
CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Database unavailable"},
        )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exception: StarletteHTTPException):
    content = (
        exception.detail
        if isinstance(exception.detail, dict)
        else {"error": str(exception.detail)}
    )
    return JSONResponse(
        status_code=exception.status_code,
        content=content,
        headers=exception.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exception: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error: invalid request data"},
    )


@app.exception_handler(IntegrityError)
async def database_validation_error(
    request: Request, exception: IntegrityError
):
    sqlstate = getattr(exception.orig, "sqlstate", None)
    diag = getattr(exception.orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None)

    if sqlstate == UNIQUE_VIOLATION and constraint == "unique_plan_order":
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "Validation error: visit_order is already used "
                    "in this travel plan"
                )
            },
        )
    if sqlstate == CHECK_VIOLATION:
        return JSONResponse(
            status_code=400,
            content={"error": "Validation error: database constraint violated"},
        )

    # Any other integrity error is a server bug, not a client mistake.
    return await internal_error(request, exception)


@app.exception_handler(Exception)
async def internal_error(request: Request, exception: Exception):
    # Full details go to the server log only, never to the client.
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=exception,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


app.include_router(create_plan_router(engine))
app.include_router(create_location_router(engine))
