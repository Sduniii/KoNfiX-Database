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
    source_url: Optional[str] = None
    manufacturer_id: str
    manufacturer_name: str
    manufacturer_code: Optional[str] = None
    devices_imported: List[ImportedDevice]

class BatchItemResult(BaseModel):
    filename: str
    status: str = "success"
    message: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    source_url: Optional[str] = None
    manufacturer_id: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_code: Optional[str] = None
    devices_imported: List[ImportedDevice] = []

class BatchUploadResponse(BaseModel):
    status: str = "success"
    message: str
    total_files: int
    successful_count: int
    failed_count: int
    results: List[BatchItemResult]


class UrlImportRequest(BaseModel):
    url: str
    store_binary: bool = False
    filename: Optional[str] = None


