from sqlalchemy import Column, Integer, String, BigInteger, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class KnxprodFile(Base):
    __tablename__ = "knxprod_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), unique=True, index=True, nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(64), default="application/octet-stream")
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    devices = relationship("Device", back_populates="knxprod_file")
