from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import engine


app = FastAPI(title=get_settings().app_name)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return {"status":"ok"}