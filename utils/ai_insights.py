```python
import json
import re
from snowflake.snowpark import Session

def detect_cortex(session: Session) -> bool:
    """Check if SNOWFLAKE.CORTEX.COMPLETE is available."""
    try:
        # Minimal query to test Cortex availability
        result = session.sql("SELECT SNOWFLAKE.CORTEX.COMPLETE('snowflake-arctic', 'test') AS test").collect()
        return result[0][0] is not None
    except Exception:
        return False

def build_prompt(page: str, context: dict) -> str:
    """Construct a prompt for Cortex based on page and context."""
    prompt = f"Provide an insight for the page '{page}'.\n"
    if context:
        prompt += f"Context: {json.dumps(context, indent=2)}\n"
    prompt += "Please give a short, actionable insight."
    return prompt

def rule_based_insight(page: str, context: dict) -> str:
    """Fallback deterministic insight when Cortex is unavailable."""
    page_lower = page.lower()
    if "query" in page_lower:
        return "Review your query performance and consider indexing or pruning partitions."
    elif "dashboard" in page_lower:
        return "Check for fresh data and ensure dashboard filters are applied correctly."
    elif "table" in page_lower or "view" in page_lower:
        return "Verify table structure and recent row counts; look for skewed distributions."
    else:
        return "No specific insight. Review general usage patterns and recent errors."

def get_cortex_insight(session: Session, page: str, context: dict) -> str:
    """Obtain an AI-generated insight using Snowflake Cortex."""
    prompt = build_prompt(page, context)
    # Escape single quotes in prompt to avoid SQL injection
    escaped_prompt = prompt.replace("'", "''")
    try:
        result = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('snowflake-arctic', '{escaped_prompt}') AS insight"
        ).collect()
        insight = result[0][0]
        return insight if insight else rule_based_insight(page, context)
    except Exception:
        return rule_based_insight(page, context)

def get_query_tip(session: Session, stats: dict) -> str:
    """Get an optimization tip for a SQL query based on its statistics."""
    prompt = f"Given the following query statistics, provide a brief optimization tip:\n{json.dumps(stats, indent=2)}\nTip:"
    escaped_prompt = prompt.replace("'", "''")
    try:
        result = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('snowflake-arctic', '{escaped_prompt}') AS tip"
        ).collect()
        return result[0][0] or "Consider reviewing execution plan and indexes."
    except Exception:
        return "Consider reviewing execution plan and indexes."
```
