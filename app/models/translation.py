from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(128), nullable=False, index=True) # e.g. "mdt_p-1", "mdt_o-1"
    language = Column(String(16), nullable=False, index=True) # e.g. "de", "en"
    text = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("device_id", "entity_id", "language", name="uq_translation_device_entity_lang"),
    )

    device = relationship("Device", back_populates="translations")
