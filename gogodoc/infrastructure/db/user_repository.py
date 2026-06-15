"""사용자 저장소 - users 테이블 CRUD"""

from __future__ import annotations

from typing import Any

import psycopg2.extras


def find_by_name(conn: Any, name: str) -> dict[str, Any] | None:
    """이름으로 사용자 조회 - 없으면 None"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, password_hash, sex, age, location FROM users WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def create(conn: Any, name: str, password_hash: str, sex: str, age: int, location: str = "") -> None:
    """사용자 생성 - 중복 이름이면 psycopg2.errors.UniqueViolation 전파"""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (name, password_hash, sex, age, location) VALUES (%s, %s, %s, %s, %s)",
            (name, password_hash, sex, age, location),
        )
