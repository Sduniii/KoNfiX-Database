from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class KnxprodFileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_size_bytes: int
    sha256: str
    source_url: Optional[str] = None
    uploaded_at: datetime
    download_url: str

class ApplicationProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    app_id: Optional[str] = None
    name: str
    version: Optional[str] = None
    mask_version: Optional[str] = None
    com_objects_count: int = 0
    parameters_count: int = 0

class ManufacturerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knx_id: str
    name: str

class DeviceBase(BaseModel):
    order_number: str
    name: str
    description: Optional[str] = None
    hardware_name: Optional[str] = None
    hardware_version: Optional[str] = None
    bus_current_ma: Optional[float] = None

class DeviceResponse(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manufacturer: ManufacturerSummary
    knxprod_file: Optional[KnxprodFileInfo] = None
    applications: List[ApplicationProgramResponse] = []
    created_at: datetime
    updated_at: datetime

class DeviceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    devices: List[DeviceResponse]


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    hardware_name: Optional[str] = None
    hardware_version: Optional[str] = None
    bus_current_ma: Optional[float] = None
    source_url: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    order_numbers: List[str]
    delete_files: bool = False


class BatchDeleteResponse(BaseModel):
    deleted_count: int
    deleted_order_numbers: List[str]
    errors: List[str] = []
    message: str

