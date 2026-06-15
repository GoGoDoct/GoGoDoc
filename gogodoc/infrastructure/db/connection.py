"""DB 커넥션 풀 관리"""

import streamlit as st
import psycopg2.pool

from gogodoc.infrastructure.config import Settings


@st.cache_resource
def create_pool(settings: Settings) -> psycopg2.pool.SimpleConnectionPool:
    """앱 프로세스 생명주기 동안 한 번만 커넥션 풀 생성 (Streamlit cache_resource)"""
    return psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def get_conn(pool: psycopg2.pool.SimpleConnectionPool):
    """풀에서 커넥션 획득"""
    return pool.getconn()


def put_conn(pool: psycopg2.pool.SimpleConnectionPool, conn) -> None:
    """풀에 커넥션 반환"""
    pool.putconn(conn)
