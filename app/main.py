import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from app.locations import create_location_router
from app.plans import create_plan_router

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

@app.exception_handler(ValidationError)
async def model_validation_error(request: Request, exception: ValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error: invalid field combination"},
    )
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
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error: database constraint violated"},
    )


app.include_router(create_plan_router(engine))
app.include_router(create_location_router(engine))