import sys
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path

# Add project root to path to allow imports from core
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from core.local_data_client import LocalDataClient

# Global cache for the client
_client: Optional[LocalDataClient] = None

def get_analytics_data() -> Dict[str, Any]:
    """
    Returns the analytics data dictionary, initializing the client if needed.
    Bypasses Streamlit's caching.
    """
    global _client
    if _client is None:
        _client = LocalDataClient()
        # Force a pre-warm
        _client.get_analytics()
    return _client.get_analytics()

def get_scored_events() -> Optional[pd.DataFrame]:
    """Returns the fully scored dataframe from analytics."""
    data = get_analytics_data()
    if "error" in data:
        return None
    return data.get("scored_df")
