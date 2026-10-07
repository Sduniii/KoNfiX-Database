from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class CommunicationObject(Base):
    __tablename__ = "communication_objects"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    obj_id = Column(String(128), nullable=False, index=True) # e.g. "mdt_o-1" or "mdt_a-00c5-41-204e_o-10"
    number = Column(Integer, nullable=False, index=True) # 0-65535
    name = Column(String(255), nullable=True)
    function = Column(String(255), nullable=True)
    dpt = Column(String(64), nullable=True, index=True) # e.g. "1.001", "DPST-11-1"
    size = Column(String(64), nullable=True) # e.g. "1 Bit", "3 Bytes"
    flags = Column(JSON, nullable=True) # {"communication": true, "read": false, "write": true, ...}
    conditions = Column(JSON, nullable=True) # [{"param_id": "...", "when_values": [...]}]

    device = relationship("Device", back_populates="communication_objects")
