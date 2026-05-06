"""Feature-related API router.

This module is intentionally minimal for now. It provides a stable import
target so dashboard startup does not fail when feature endpoints are not yet
implemented.
"""

from fastapi import APIRouter

router = APIRouter(tags=["features"])
