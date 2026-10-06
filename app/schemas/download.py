from pydantic import BaseModel, Field
from typing import Optional

class DownloadRequest(BaseModel):
    order_number: Optional[str] = Field(None, description="KNX device order number / Bestellnummer (e.g. 'AKS-0816.04')")
    manufacturer_id: Optional[str] = Field(None, description="KNX manufacturer ID (e.g. 'M-00C5' or '00C5')")
    device_id: Optional[int] = Field(None, description="Numeric database ID of the device")
    sha256: Optional[str] = Field(None, description="SHA256 checksum of the .knxprod file")
    exact_match: bool = Field(True, description="Whether to require exact match on order number")
