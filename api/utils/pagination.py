import pandas as pd
from typing import Dict, Any, List
import math

def paginate_dataframe(df: pd.DataFrame, page: int, limit: int, sort_by: str = None, sort_desc: bool = True) -> Dict[str, Any]:
    """
    Paginates and sorts a Pandas DataFrame and returns a standardized paginated envelope.
    """
    total = len(df)
    
    if sort_by and sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=not sort_desc)
        
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    paginated_df = df.iloc[start_idx:end_idx]
    
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    
    return {
        "data": paginated_df,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }
