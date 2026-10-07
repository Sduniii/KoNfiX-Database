from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AssignRule(Base):
    __tablename__ = "assign_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    target = Column(String(128), nullable=False) # e.g. "mdt_p-2"
    source = Column(String(128), nullable=True) # e.g. "mdt_p-1"
    value = Column(Text, nullable=True) # e.g. "100"
    conditions = Column(JSON, nullable=True) # [{"param_id": "...", "when_values": [...]}]

    device = relationship("Device", back_populates="assign_rules")
