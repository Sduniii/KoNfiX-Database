from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class OpenKnxAssetSchema(BaseModel):
    name: str
    size: int = 0
    download_url: str


class OpenKnxReleaseSchema(BaseModel):
    tag: str
    name: str
    prerelease: bool = False
    published_at: Optional[str] = None
    html_url: Optional[str] = None
    body: Optional[str] = None
    assets: List[OpenKnxAssetSchema] = []


class OpenKnxRepositorySchema(BaseModel):
    repository: str
    description: Optional[str] = None
    repo_url: Optional[str] = None
    releases: List[OpenKnxReleaseSchema] = []


class OpenKnxDeviceSchema(BaseModel):
    hostname: str
    ip: str
    port: int
    architecture: str
    individual_address: str = "0.0.0"
    app_id: str = ""
    firmware_name: str = ""
    firmware_version: str = ""
    serial_number: str = ""
    configured: bool = False
    update_available: bool = False
    latest_version: Optional[str] = None
    help_thread: Optional[str] = None
    discovered_via: str = "mdns"
    last_seen: float


class KnxGatewayCreate(BaseModel):
    name: str
    host: str
    port: int = 3671
    protocol: str = "tunneling_udp"
    individual_address: Optional[str] = "0.0.0"
    is_default: bool = False


class KnxGatewayResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    protocol: str
    individual_address: Optional[str] = None
    is_default: bool = False
    created_at: str


class ImportReleaseRequest(BaseModel):
    repository: str
    tag: str


class DeviceRestartRequest(BaseModel):
    target_address: Optional[str] = None
    ip: Optional[str] = None
    gateway_id: Optional[int] = None


class FileItemSchema(BaseModel):
    name: str
    is_file: bool
    path: str
    size: Optional[int] = None


class FileListRequest(BaseModel):
    target_address: str
    remote_path: str = "/"
    gateway_id: Optional[int] = None


class FileDeleteRequest(BaseModel):
    target_address: str
    remote_path: str
    gateway_id: Optional[int] = None


class DirCreateRequest(BaseModel):
    target_address: str
    remote_path: str
    gateway_id: Optional[int] = None


class FlashFirmwareRequest(BaseModel):
    method: str  # "bus" or "ota"
    target_address: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    repository: Optional[str] = None
    tag: Optional[str] = None
    asset_name: Optional[str] = None
    gateway_id: Optional[int] = None
