import io
import logging
import zipfile
from pathlib import Path
from typing import Dict, Optional, List
import xml.etree.ElementTree as ET
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class KnxprodGenerator:
    """
    Generates standard .knxprod archives from OpenKNX ETS XML definitions
    and baggage assets.
    """

    @staticmethod
    async def get_knx_master_xml(namespace_ver: int = 20) -> bytes:
        """Retrieves or loads cached knx_master.xml for the given project namespace."""
        cache_path = settings.OPENKNX_CACHE_DIR / f"knx_master_{namespace_ver}.xml"
        if cache_path.exists():
            return cache_path.read_bytes()

        url = f"https://update.knx.org/data/XML/project-{namespace_ver}/knx_master.xml"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    cache_path.write_bytes(resp.content)
                    return resp.content
        except Exception as ex:
            logger.warning("Konnte knx_master.xml nicht von update.knx.org laden: %s", ex)

        # Fallback minimal knx_master.xml
        minimal_master = f"""<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/{namespace_ver}">
  <MasterData />
</KNX>""".encode("utf-8")
        cache_path.write_bytes(minimal_master)
        return minimal_master

    @classmethod
    async def generate_knxprod_bytes(
        cls,
        xml_bytes: bytes,
        baggages: Optional[Dict[str, bytes]] = None,
        manufacturer_id: str = "M-00FA"
    ) -> bytes:
        """
        Creates a valid .knxprod ZIP file containing M-xxxx.xml, Baggages,
        and knx_master.xml.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Main XML
            zf.writestr(f"{manufacturer_id}.xml", xml_bytes)

            # Baggages
            if baggages:
                for b_path, b_data in baggages.items():
                    rel = b_path.lstrip("/")
                    zf.writestr(f"{manufacturer_id}/Baggages/{rel}", b_data)

            # Master XML
            master_xml = await cls.get_knx_master_xml(20)
            zf.writestr("knx_master.xml", master_xml)

        return buf.getvalue()


knxprod_generator = KnxprodGenerator()
