"""Asset Register API, now stored in PostgreSQL."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Base, engine, get_session
from models import AssetRecord


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the table on start-up if it does not exist yet."""
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Asset Register API",
    description="Track equipment: what it is, what type it is, and who has it.",
    version="0.3.0",
    lifespan=lifespan,
)

# A database session, supplied to any route that asks for one
SessionDep = Annotated[Session, Depends(get_session)]


class AssetIn(BaseModel):
    """What a client sends. The same three fields as the original Flask form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, examples=["Dell Latitude 7450"])
    type: str = Field(min_length=1, max_length=50, examples=["laptop"])
    assigned_to: str | None = Field(default=None, max_length=100, examples=["Finance team"])


class Asset(AssetIn):
    """What the API returns. Built straight from a database row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    added: datetime


def get_or_404(session: Session, asset_id: int) -> AssetRecord:
    """Return the row, or stop the request with a 404 Not Found."""
    record = session.get(AssetRecord, asset_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    return record


@app.get("/health")
def health() -> dict[str, str]:
    """A simple check that the API is running."""
    return {"status": "ok"}


@app.get("/assets")
def list_assets(session: SessionDep) -> list[Asset]:
    """Every asset, oldest first."""
    records = session.scalars(select(AssetRecord).order_by(AssetRecord.id))
    return [Asset.model_validate(record) for record in records]


@app.get("/assets/{asset_id}")
def get_asset(asset_id: int, session: SessionDep) -> Asset:
    """One asset by its ID."""
    return Asset.model_validate(get_or_404(session, asset_id))


@app.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(new: AssetIn, session: SessionDep) -> Asset:
    """Add an asset. The database chooses the ID and records when it was added."""
    record = AssetRecord(**new.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return Asset.model_validate(record)


@app.put("/assets/{asset_id}")
def update_asset(asset_id: int, changes: AssetIn, session: SessionDep) -> Asset:
    """Replace an asset's details. The ID and the date it was added never change."""
    record = get_or_404(session, asset_id)
    for field, value in changes.model_dump().items():
        setattr(record, field, value)
    session.commit()
    session.refresh(record)
    return Asset.model_validate(record)


@app.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, session: SessionDep) -> None:
    """Remove an asset."""
    record = get_or_404(session, asset_id)
    session.delete(record)
    session.commit()