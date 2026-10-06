from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id = Column(Integer, primary_key=True, index=True)
    knx_id = Column(String(32), unique=True, index=True, nullable=False) # e.g. "M-00C5" or "00C5"
    name = Column(String(255), nullable=False, index=True)
    country = Column(String(64), nullable=True)
    website = Column(String(255), nullable=True)
    logo_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    devices = relationship("Device", back_populates="manufacturer", cascade="all, delete-orphan")
