"""인증 서비스 - 회원가입 및 로그인"""

from __future__ import annotations

from typing import Any

from passlib.context import CryptContext

from gogodoc.infrastructure.db.connection import get_conn, put_conn
from gogodoc.infrastructure.db.user_repository import find_by_name, create


class AuthError(Exception):
    """비밀번호 불일치 또는 존재하지 않는 이름"""


class DuplicateNameError(Exception):
    """회원가입 시 이름 중복"""


# passlib CryptContext 인스턴스 모듈 레벨에서 생성
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def register(pool: Any, name: str, password: str, sex: str, age: int, location: str = "") -> None:
    """중복 이름 체크 후 bcrypt 해싱·저장

    Args:
        pool: 커넥션 풀
        name: 사용자명
        password: 평문 비밀번호
        sex: 성별
        age: 나이
        location: 거주지

    Raises:
        DuplicateNameError: 이미 존재하는 이름
    """
    conn = get_conn(pool)
    try:
        existing_user = find_by_name(conn, name)
        if existing_user is not None:
            raise DuplicateNameError(f"이미 존재하는 이름: {name}")

        hashed_password = _pwd_context.hash(password)
        create(conn, name, hashed_password, sex, age, location)
        conn.commit()
    finally:
        put_conn(pool, conn)


def login(pool: Any, name: str, password: str) -> dict[str, Any]:
    """비밀번호 검증 후 사용자 정보 반환

    Args:
        pool: 커넥션 풀
        name: 사용자명
        password: 평문 비밀번호

    Returns:
        dict: {name, sex, age}

    Raises:
        AuthError: 존재하지 않는 이름 또는 비밀번호 불일치
    """
    conn = get_conn(pool)
    try:
        # 사용자 조회
        user = find_by_name(conn, name)
        if user is None:
            raise AuthError(f"존재하지 않는 이름: {name}")

        # 비밀번호 검증
        password_hash = user["password_hash"]
        if not _pwd_context.verify(password, password_hash):
            raise AuthError("비밀번호 불일치")

        # 사용자 정보 반환
        return {
            "id": user["id"],
            "name": user["name"],
            "sex": user["sex"],
            "age": user["age"],
            "location": user.get("location", ""),
        }
    finally:
        put_conn(pool, conn)
