"""Optional FastAPI middleware to log API calls to user database.

This module provides integration between the FastAPI backend and the user
authentication database. It logs all API requests with user context.

Usage:
    from api_auth_middleware import log_api_request
    from auth import log_query

    # After handling a request:
    log_query(
        user_id=user_id,
        question=question,
        answer=answer,
        route=route,
        tokens=tokens_used,
        cost=estimated_cost
    )
"""

from datetime import datetime
from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).parent / "tessera_users.db"


def log_api_call(
    user_id: int,
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: float,
    token_count: int = 0,
    cost_usd: float = 0.0,
    error_msg: str = None
) -> bool:
    """Log an API call to the database.

    Args:
        user_id: User who made the request
        endpoint: API endpoint called (e.g., "/ask", "/upload")
        method: HTTP method (GET, POST, etc.)
        status_code: Response status code
        response_time_ms: Time to process request
        token_count: Tokens used (if applicable)
        cost_usd: Estimated cost
        error_msg: Error message if failed

    Returns:
        bool: Success or failure
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms REAL,
                tokens_used INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        cursor.execute(
            """INSERT INTO api_logs
               (user_id, endpoint, method, status_code, response_time_ms, tokens_used, cost_usd, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, endpoint, method, status_code, response_time_ms, token_count, cost_usd, error_msg)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging API call: {str(e)}")
        return False


def get_user_api_stats(user_id: int) -> dict:
    """Get API usage statistics for a user.

    Args:
        user_id: User ID

    Returns:
        dict with:
            - total_calls: Total API requests
            - successful_calls: 200-299 status codes
            - failed_calls: Non-2xx status codes
            - total_tokens: Sum of tokens used
            - total_cost: Sum of costs
            - avg_response_time_ms: Average latency
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Total calls
        cursor.execute("SELECT COUNT(*) FROM api_logs WHERE user_id = ?", (user_id,))
        total_calls = cursor.fetchone()[0]

        # Successful calls
        cursor.execute(
            "SELECT COUNT(*) FROM api_logs WHERE user_id = ? AND status_code >= 200 AND status_code < 300",
            (user_id,)
        )
        successful_calls = cursor.fetchone()[0]

        # Failed calls
        failed_calls = total_calls - successful_calls

        # Total tokens
        cursor.execute("SELECT SUM(tokens_used) FROM api_logs WHERE user_id = ?", (user_id,))
        total_tokens = cursor.fetchone()[0] or 0

        # Total cost
        cursor.execute("SELECT SUM(cost_usd) FROM api_logs WHERE user_id = ?", (user_id,))
        total_cost = cursor.fetchone()[0] or 0.0

        # Average response time
        cursor.execute("SELECT AVG(response_time_ms) FROM api_logs WHERE user_id = ?", (user_id,))
        avg_response_time = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "total_tokens": int(total_tokens),
            "total_cost_usd": round(total_cost, 6),
            "avg_response_time_ms": round(avg_response_time, 2)
        }
    except Exception:
        return {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "avg_response_time_ms": 0.0
        }


def get_endpoint_usage(user_id: int, endpoint: str = None, days: int = 30) -> list:
    """Get API usage by endpoint for a user.

    Args:
        user_id: User ID
        endpoint: Optional filter by endpoint
        days: How many days to look back

    Returns:
        list of dicts with endpoint, call_count, tokens, cost
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if endpoint:
            cursor.execute(
                """SELECT endpoint, COUNT(*) as calls, SUM(tokens_used) as tokens, SUM(cost_usd) as cost
                   FROM api_logs
                   WHERE user_id = ? AND endpoint = ? AND created_at > datetime('now', '-' || ? || ' days')
                   GROUP BY endpoint""",
                (user_id, endpoint, days)
            )
        else:
            cursor.execute(
                """SELECT endpoint, COUNT(*) as calls, SUM(tokens_used) as tokens, SUM(cost_usd) as cost
                   FROM api_logs
                   WHERE user_id = ? AND created_at > datetime('now', '-' || ? || ' days')
                   GROUP BY endpoint
                   ORDER BY calls DESC""",
                (user_id, days)
            )

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "endpoint": r[0],
                "calls": r[1],
                "tokens": r[2] or 0,
                "cost_usd": round(r[3] or 0.0, 6)
            }
            for r in results
        ]
    except Exception:
        return []


# Example FastAPI middleware integration
# Add to your FastAPI app:
#
# from fastapi import FastAPI, Request
# from contextlib import asynccontextmanager
# import time
#
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     """Middleware to log API calls."""
#     start_time = time.time()
#
#     # Try to extract user_id from request
#     user_id = getattr(request, "user_id", None)
#
#     response = await call_next(request)
#
#     process_time = (time.time() - start_time) * 1000  # ms
#
#     if user_id:
#         log_api_call(
#             user_id=user_id,
#             endpoint=request.url.path,
#             method=request.method,
#             status_code=response.status_code,
#             response_time_ms=process_time
#         )
#
#     return response
