from typing import Any, Dict

from django.conf import settings
from rest_framework.settings import APISettings

DRF_CACHED_VIEW_SETTINGS: Dict[str, Any] = {
    "CACHE_KEY_PREFIX": "DRFCV",
    "TIMEOUT": None,
}

cache_settings = APISettings(
    user_settings=getattr(settings, "DRF_CACHED_VIEW_SETTINGS", {}),
    defaults=DRF_CACHED_VIEW_SETTINGS,
)
