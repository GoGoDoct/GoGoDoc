"""인증 서비스 단위 테스트 - mock.patch 사용, DB 없이 실행"""

import pytest
from unittest.mock import patch, MagicMock

from gogodoc.application.auth_service import (
    register, login, AuthError, DuplicateNameError
)


@patch("gogodoc.application.auth_service._pwd_context")
@patch("gogodoc.application.auth_service.put_conn")
@patch("gogodoc.application.auth_service.get_conn")
@patch("gogodoc.application.auth_service.create")
@patch("gogodoc.application.auth_service.find_by_name")
def test_register_creates_user(mock_find, mock_create, mock_get_conn, mock_put_conn, mock_ctx):
    """중복 없는 경우 create가 정확히 1번 호출되는지 검증"""
    pool = MagicMock()
    mock_get_conn.return_value = MagicMock()
    mock_find.return_value = None  # 중복 없음
    mock_ctx.hash.return_value = "hashed_pass"

    register(pool, "홍길동", "pass123", "male", 40)

    args = mock_create.call_args[0]  # positional args
    assert args[1] == "홍길동"       # name
    assert args[3] == "male"         # sex
    assert args[4] == 40             # age
    # args[2]는 hashed password - 타입만 str 확인
    assert isinstance(args[2], str) and len(args[2]) > 0

    conn = mock_get_conn.return_value
    conn.commit.assert_called_once()


@patch("gogodoc.application.auth_service.put_conn")
@patch("gogodoc.application.auth_service.get_conn")
@patch("gogodoc.application.auth_service.create")
@patch("gogodoc.application.auth_service.find_by_name")
def test_register_duplicate_name_raises(mock_find, mock_create, mock_get_conn, mock_put_conn):
    """이미 존재하는 이름으로 회원가입 시 DuplicateNameError 발생"""
    pool = MagicMock()
    mock_get_conn.return_value = MagicMock()
    mock_find.return_value = {"name": "홍길동", "sex": "male", "age": 40}  # 이미 존재

    with pytest.raises(DuplicateNameError):
        register(pool, "홍길동", "pass123", "male", 40)


@patch("gogodoc.application.auth_service._pwd_context")
@patch("gogodoc.application.auth_service.put_conn")
@patch("gogodoc.application.auth_service.get_conn")
@patch("gogodoc.application.auth_service.find_by_name")
def test_login_success(mock_find, mock_get_conn, mock_put_conn, mock_ctx):
    """올바른 이름과 비밀번호로 로그인 시 사용자 정보 반환"""
    pool = MagicMock()
    mock_get_conn.return_value = MagicMock()
    mock_find.return_value = {
        "id": 1,
        "name": "홍길동",
        "password_hash": "hashed_pass",
        "sex": "male",
        "age": 40,
        "location": "서울",
    }
    mock_ctx.verify.return_value = True

    result = login(pool, "홍길동", "pass123")

    assert result == {"id": 1, "name": "홍길동", "sex": "male", "age": 40, "location": "서울"}
    mock_find.assert_called_once_with(mock_get_conn.return_value, "홍길동")


@patch("gogodoc.application.auth_service._pwd_context")
@patch("gogodoc.application.auth_service.put_conn")
@patch("gogodoc.application.auth_service.get_conn")
@patch("gogodoc.application.auth_service.find_by_name")
def test_login_wrong_password_raises(mock_find, mock_get_conn, mock_put_conn, mock_ctx):
    """잘못된 비밀번호로 로그인 시 AuthError 발생"""
    pool = MagicMock()
    mock_get_conn.return_value = MagicMock()
    mock_find.return_value = {
        "name": "홍길동",
        "password_hash": "hashed_pass",
        "sex": "male",
        "age": 40,
    }
    mock_ctx.verify.return_value = False  # 비밀번호 불일치

    with pytest.raises(AuthError):
        login(pool, "홍길동", "wrong_password")

    mock_find.assert_called_once_with(mock_get_conn.return_value, "홍길동")


@patch("gogodoc.application.auth_service.put_conn")
@patch("gogodoc.application.auth_service.get_conn")
@patch("gogodoc.application.auth_service.find_by_name")
def test_login_unknown_name_raises(mock_find, mock_get_conn, mock_put_conn):
    """존재하지 않는 이름으로 로그인 시 AuthError 발생"""
    pool = MagicMock()
    mock_get_conn.return_value = MagicMock()
    mock_find.return_value = None  # 존재하지 않는 사용자

    with pytest.raises(AuthError):
        login(pool, "없는이름", "pass123")

    mock_find.assert_called_once_with(mock_get_conn.return_value, "없는이름")
