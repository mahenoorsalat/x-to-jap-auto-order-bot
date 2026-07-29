import os
import json
from dataclasses import dataclass, field
from typing import Dict, List
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

@dataclass
class Config:
    jap_api_key: str = os.getenv("JAP_API_KEY", "YOUR_JAP_API_KEY_HERE")
    jap_api_url: str = os.getenv("JAP_API_URL", "https://justanotherpanel.com/api/v2")
    target_x_username: str = os.getenv("TARGET_X_USERNAME", "elonmusk").strip("@").strip()
    poll_interval: float = float(os.getenv("POLL_INTERVAL_SECONDS", "3.0"))
    default_service_id: str = str(os.getenv("DEFAULT_SERVICE_ID", "1234"))
    default_quantity: int = int(os.getenv("DEFAULT_QUANTITY", "1000"))
    
    nitter_instances: List[str] = field(default_factory=lambda: [
        inst.strip() for inst in os.getenv(
            "NITTER_INSTANCES", 
            "https://nitter.net,https://nitter.poast.org,https://privacydev.net,https://nitter.privacydev.net,https://nitter.hu,https://nitter.cz"
        ).split(",") if inst.strip()
    ])
    
    service_mappings: Dict[str, str] = field(default_factory=lambda: {})

    def __post_init__(self):
        raw_json = os.getenv("SERVICE_MAPPING_JSON", "")
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                self.service_mappings = {k.lower(): str(v) for k, v in parsed.items()}
            except Exception as e:
                print(f"[Warning] Failed to parse SERVICE_MAPPING_JSON: {e}")
                
    def get_service_id_for_url(self, url: str) -> str:
        """Find matching service ID from domain mapping or fall back to default."""
        url_lower = url.lower()
        for domain, service_id in self.service_mappings.items():
            if domain in url_lower:
                return service_id
        return self.default_service_id

# Singleton config instance
config = Config()
