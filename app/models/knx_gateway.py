from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class KnxGateway(Base):
    __tablename__ = "knx_gateways"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    host = Column(String(256), nullable=False)
    port = Column(Integer, default=3671, nullable=False)
    protocol = Column(String(32), default="tunneling_udp", nullable=False)  # tunneling_udp, tunneling_tcp, routing
    individual_address = Column(String(32), nullable=True, default="0.0.0")
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
