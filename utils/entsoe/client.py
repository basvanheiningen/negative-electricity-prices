from __future__ import annotations

import os
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

load_dotenv()


def get_entsoe_client() -> EntsoePandasClient:
    """Get an authenticated ENTSOE API client."""
    api_key = os.getenv("ENTSOE_API_KEY")
    if not api_key:
        raise ValueError("ENTSOE_API_KEY not found in environment variables")
    return EntsoePandasClient(api_key=api_key)
