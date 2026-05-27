from typing import List, Dict, Any
import math

def generate_rendering_metadata(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministically analyzes SQL query results to decide if a chart can be rendered
    and calculates high-level metrics for metric cards.
    """
    if not rows:
        return {"response_type": "table", "analytics": {}}

    row_count = len(rows)
    if row_count == 0:
        return {"response_type": "table", "analytics": {}}

    keys = list(rows[0].keys())
    
    # Exclude non-meaningful columns for charting
    exclude_substrings = ["id", "uuid", "phone", "email", "hash", "password", "url", "description", "details"]
    valid_keys = [k for k in keys if not any(sub in k.lower() for sub in exclude_substrings)]

    numeric_cols = []
    categorical_cols = []
    datetime_cols = []

    # Analyze data types based on the first few rows (up to 5)
    for k in valid_keys:
        types_found = set()
        for row in rows[:5]:
            val = row.get(k)
            if val is not None:
                if isinstance(val, (int, float)):
                    types_found.add("numeric")
                elif isinstance(val, str):
                    # basic heuristic for date
                    if len(val) >= 10 and "-" in val and val[:4].isdigit():
                        types_found.add("datetime")
                    else:
                        types_found.add("categorical")
                else:
                    types_found.add("categorical")
        
        if "numeric" in types_found and "categorical" not in types_found and "datetime" not in types_found:
            numeric_cols.append(k)
        elif "datetime" in types_found:
            datetime_cols.append(k)
        else:
            categorical_cols.append(k)

    # Calculate metrics if we have numeric columns
    analytics = {}
    if numeric_cols and row_count > 1:
        primary_num = numeric_cols[0]
        values = [r.get(primary_num) for r in rows if isinstance(r.get(primary_num), (int, float))]
        if values:
            total = sum(values)
            avg = total / len(values) if values else 0
            analytics = {
                "total": round(total, 2) if isinstance(total, float) else total,
                "average": round(avg, 2) if isinstance(avg, float) else avg,
                "min": min(values),
                "max": max(values),
                "count": len(values),
                "metric_key": primary_num
            }

    # Chart Rules
    if row_count <= 1 or row_count > 20 or len(keys) > 12:
        # Too many points/columns, or too few, stick to table
        return {"response_type": "table", "analytics": analytics}

    if not numeric_cols:
        return {"response_type": "table", "analytics": analytics}

    x_key = None
    if datetime_cols:
        x_key = datetime_cols[0]
        chart_type = "line"
    elif categorical_cols:
        x_key = categorical_cols[0]
        # Check label length for horizontal bar
        avg_len = sum(len(str(r.get(x_key, ""))) for r in rows) / row_count
        if avg_len > 15:
            chart_type = "horizontal_bar"
        elif row_count <= 6:
            chart_type = "pie" # good for small category distributions
        else:
            chart_type = "bar"
    else:
        return {"response_type": "table", "analytics": analytics}

    y_key = numeric_cols[0]

    return {
        "response_type": "chart_table",
        "chart": {
            "type": chart_type,
            "x_key": x_key,
            "y_key": y_key
        },
        "analytics": analytics
    }
