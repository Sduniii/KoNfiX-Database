from pydantic import BaseModel
from typing import List, Optional

class ImportedApplication(BaseModel):
    name: str
    version: Optional[str] = None
    mask_version: Optional[str] = None
    com_objects_count: int = 0
    parameters_count: int = 0

class ImportedDevice(BaseModel):
    order_number: str
    name: str
    hardware_version: Optional[str] = None
    bus_current_ma: Optional[float] = None
    applications: List[ImportedApplication] = []

class UploadResponse(BaseModel):
    status: str = "success"
    message: str
    filename: str
    file_size_bytes: int
    sha256: str
    manufacturer_id: str
    manufacturer_name: str
    devices_imported: List[ImportedDevice]
