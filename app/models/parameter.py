from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Parameter(Base):
    __tablename__ = "parameters"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    param_id = Column(String(128), nullable=False, index=True) # e.g. "mdt_p-1"
    name = Column(String(255), nullable=False, index=True)
    text = Column(String(255), nullable=True)
    type = Column(String(64), nullable=True) # "enum", "number", "text", "float"
    default_value = Column(Text, nullable=True)
    page = Column(String(255), nullable=True, index=True) # e.g. "Kanal A > Zeiteinstellungen"
    section = Column(String(255), nullable=True)
    options = Column(JSON, nullable=True) # [{"value": "1", "text": "..."}, ...]
    conditions = Column(JSON, nullable=True) # [{"param_id": "...", "when_values": [...]}]

    device = relationship("Device", back_populates="parameters")
