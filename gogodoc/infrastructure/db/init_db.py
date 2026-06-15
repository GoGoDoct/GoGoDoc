"""DB 초기화 - 테이블 DDL 실행"""

import psycopg2.pool

from gogodoc.infrastructure.config import Settings
from gogodoc.infrastructure.db.connection import create_pool, get_conn, put_conn

_CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    sex           VARCHAR(6) NOT NULL CHECK (sex IN ('male', 'female')),
    age           INTEGER NOT NULL CHECK (age >= 0 AND age <= 120),
    location      VARCHAR(100) NOT NULL DEFAULT '',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

_ADD_LOCATION_COLUMN = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'location'
    ) THEN
        ALTER TABLE users ADD COLUMN location VARCHAR(100) NOT NULL DEFAULT '';
    END IF;
END$$;
"""


def init_db(settings: Settings) -> psycopg2.pool.SimpleConnectionPool:
    """커넥션 풀 생성 후 DDL 실행, 풀 반환"""
    pool = create_pool(settings)
    conn = get_conn(pool)
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_USERS_TABLE)
            cur.execute(_ADD_LOCATION_COLUMN)
        conn.commit()
    finally:
        put_conn(pool, conn)
    return pool
