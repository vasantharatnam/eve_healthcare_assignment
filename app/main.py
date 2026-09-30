from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import engine

from app.routers.auth import router as auth_router
from app.routers.catalogue import router as catalogue_router
from app.routers.bookings import router as bookings_router
from app.routers.payments import router as payments_router

app = FastAPI(title=get_settings().app_name)


app.include_router(auth_router)
app.include_router(catalogue_router)
app.include_router(bookings_router)
app.include_router(payments_router)

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