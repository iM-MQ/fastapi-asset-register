"""The assets table, matching the original Flask app's CREATE TABLE."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AssetRecord(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    added: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())