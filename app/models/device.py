from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(128), unique=True, index=True, nullable=False) # e.g. "AKS-0816.04"
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    hardware_name = Column(String(255), nullable=True)
    hardware_version = Column(String(64), nullable=True)
    bus_current_ma = Column(Float, nullable=True)
    
    manufacturer_id = Column(Integer, ForeignKey("manufacturers.id"), nullable=False)
    knxprod_file_id = Column(Integer, ForeignKey("knxprod_files.id"), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    manufacturer = relationship("Manufacturer", back_populates="devices")
    knxprod_file = relationship("KnxprodFile", back_populates="devices")
    applications = relationship("ApplicationProgram", back_populates="device", cascade="all, delete-orphan")


class ApplicationProgram(Base):
    __tablename__ = "application_programs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    app_id = Column(String(128), nullable=True) # e.g. "M-00C5_A-0816-42"
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=True)
    mask_version = Column(String(64), nullable=True) # e.g. "MV-07B0"
    com_objects_count = Column(Integer, default=0)
    parameters_count = Column(Integer, default=0)

    device = relationship("Device", back_populates="applications")
