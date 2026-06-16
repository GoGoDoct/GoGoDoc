"""분석 결과 저장소 - analysis_results 테이블 CRUD"""

from __future__ import annotations

from typing import Any

import psycopg2.extras


def save(conn: Any, user_id: int, filename: str, result: dict) -> None:
    """분석 결과 저장 (커밋은 호출자 책임)"""
    counts = result.get("counts", {})
    items = result.get("items", [])
    conditions = [
        it["name"] for it in items if it.get("status") in ("이상", "응급", "주의")
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO analysis_results
                (user_id, filename, normal_count, caution_count, abnormal_count,
                 emergency_alerts, tracking_items, conditions, items_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                filename,
                counts.get("정상", 0),
                counts.get("주의", 0),
                counts.get("이상", 0),
                result.get("emergency_alerts") or [],
                result.get("tracked") or [],
                conditions,
                psycopg2.extras.Json(items),
            ),
        )


def find_latest(conn: Any, user_id: int) -> dict[str, Any] | None:
    """최신 분석 결과 1건 전체 조회"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, analyzed_at, filename,
                   normal_count, caution_count, abnormal_count,
                   emergency_alerts, tracking_items, conditions, items_json
            FROM analysis_results
            WHERE user_id = %s
            ORDER BY analyzed_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def find_by_user(conn: Any, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """사용자의 분석 이력 조회 (최신순, items_json 포함)"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, analyzed_at, filename,
                   normal_count, caution_count, abnormal_count,
                   tracking_items, conditions, items_json
            FROM analysis_results
            WHERE user_id = %s
            ORDER BY analyzed_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_by_id(conn: Any, user_id: int, analysis_id: int) -> bool:
    """사용자의 분석 결과 1건 삭제 (커밋은 호출자 책임)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM analysis_results
            WHERE id = %s AND user_id = %s
            """,
            (analysis_id, user_id),
        )
        return cur.rowcount > 0
