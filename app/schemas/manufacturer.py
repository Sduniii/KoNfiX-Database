from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ManufacturerBase(BaseModel):
    knx_id: str
    name: str
    country: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

class ManufacturerCreate(ManufacturerBase):
    pass

class ManufacturerResponse(ManufacturerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    device_count: Optional[int] = 0
