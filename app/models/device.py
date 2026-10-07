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
    source_url = Column(String(1024), nullable=True)
    yaml_content = Column(Text, nullable=True) # Optional legacy/cached YAML representation
    
    manufacturer_id = Column(Integer, ForeignKey("manufacturers.id"), nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    manufacturer = relationship("Manufacturer", back_populates="devices")
    applications = relationship("ApplicationProgram", back_populates="device", cascade="all, delete-orphan")
    communication_objects = relationship(
        "CommunicationObject",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="CommunicationObject.number"
    )
    parameters = relationship("Parameter", back_populates="device", cascade="all, delete-orphan")
    assign_rules = relationship("AssignRule", back_populates="device", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="device", cascade="all, delete-orphan")


class ApplicationProgram(Base):
    __tablename__ = "application_programs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    app_id = Column(String(128), nullable=True) # e.g. "mdt_a-00c5-41-204e"
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=True)
    mask_version = Column(String(64), nullable=True) # e.g. "MV-07B0"
    com_objects_count = Column(Integer, default=0)
    parameters_count = Column(Integer, default=0)

    device = relationship("Device", back_populates="applications")
