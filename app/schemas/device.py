from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any, Dict
from datetime import datetime

class KnxprodFileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = 0
    sha256: Optional[str] = None
    source_url: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    download_url: Optional[str] = None

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
    code: Optional[str] = None
    knx_id: Optional[str] = None
    name: str

class CommunicationObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    obj_id: str
    number: int
    name: Optional[str] = None
    function: Optional[str] = None
    dpt: Optional[str] = None
    size: Optional[str] = None
    flags: Optional[Dict[str, Any]] = None
    conditions: Optional[List[Dict[str, Any]]] = None

class ParameterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    param_id: str
    name: str
    text: Optional[str] = None
    type: Optional[str] = None
    default_value: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    conditions: Optional[List[Dict[str, Any]]] = None

class DeviceBase(BaseModel):
    order_number: str
    name: str
    description: Optional[str] = None
    hardware_name: Optional[str] = None
    hardware_version: Optional[str] = None
    bus_current_ma: Optional[float] = None
    source_url: Optional[str] = None

class DeviceResponse(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    manufacturer: ManufacturerSummary
    knxprod_file: Optional[KnxprodFileInfo] = None
    applications: List[ApplicationProgramResponse] = []
    yaml_url: Optional[str] = None
    com_objects_count: int = 0
    parameters_count: int = 0
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
