"""Asset Register API: the original Flask app's data, rebuilt with FastAPI.

Assets are kept in memory for now. Lab 03 moves them into PostgreSQL.
"""

from datetime import UTC, datetime
from itertools import count

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(
    title="Asset Register API",
    description="Track equipment: what it is, what type it is, and who has it.",
    version="0.2.0",
)


class AssetIn(BaseModel):
    """What a client sends. The same three fields as the original Flask form."""

    # Trims spaces, so "  laptop " is stored as "laptop" and "   " counts as empty
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, examples=["Dell Latitude 7450"])
    type: str = Field(min_length=1, max_length=50, examples=["laptop"])
    assigned_to: str | None = Field(default=None, max_length=100, examples=["Finance team"])


class Asset(AssetIn):
    """What the API returns: the client's fields plus the two the server sets."""

    id: int
    added: datetime


# In-memory store, keyed by ID. Emptied whenever the app restarts
assets: dict[int, Asset] = {}
next_id = count(1)


def get_or_404(asset_id: int) -> Asset:
    """Return the asset, or stop the request with a 404 Not Found."""
    asset = assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    return asset


@app.get("/health")
def health() -> dict[str, str]:
    """A simple check that the API is running, for Docker and Kubernetes later."""
    return {"status": "ok"}


@app.get("/assets")
def list_assets() -> list[Asset]:
    """Every asset, oldest first."""
    return sorted(assets.values(), key=lambda asset: asset.id)


@app.get("/assets/{asset_id}")
def get_asset(asset_id: int) -> Asset:
    """One asset by its ID."""
    return get_or_404(asset_id)


@app.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(new: AssetIn) -> Asset:
    """Add an asset. The server chooses the ID and records when it was added."""
    asset = Asset(id=next(next_id), added=datetime.now(UTC), **new.model_dump())
    assets[asset.id] = asset
    return asset


@app.put("/assets/{asset_id}")
def update_asset(asset_id: int, changes: AssetIn) -> Asset:
    """Replace an asset's details. The ID and the date it was added never change."""
    existing = get_or_404(asset_id)
    updated = existing.model_copy(update=changes.model_dump())
    assets[asset_id] = updated
    return updated


@app.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int) -> None:
    """Remove an asset."""
    get_or_404(asset_id)
    del assets[asset_id]