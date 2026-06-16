from unittest.mock import patch, MagicMock
import pytest
from gogodoc.application.hospital_service import recommend_hospitals

MOCK_RESULT = {
    "items": [
        {"name": "공복혈당", "flag": "abnormal"},
        {"name": "총콜레스테롤", "flag": "caution"},
        {"name": "적혈구", "flag": "normal"},
    ]
}

MOCK_HOSPITALS = [
    {"name": "강남병원", "address": "서울 강남구 역삼로 1", "tel": "02-111-1111",
     "url": "http://test.com", "ykiho": "abc1", "departments": []},
    {"name": "서초병원", "address": "서울 서초구 반포로 1", "tel": "02-222-2222",
     "url": "", "ykiho": "abc2", "departments": []},
]


@patch("gogodoc.application.hospital_service.get_hospital_departments")
@patch("gogodoc.application.hospital_service.get_hospitals_by_region")
@patch("gogodoc.application.hospital_service.location_to_codes")
def test_recommend_returns_hospitals(mock_codes, mock_hosp, mock_dept):
    mock_codes.return_value = ("110000", "110023")
    mock_hosp.return_value = MOCK_HOSPITALS
    mock_dept.return_value = ["내분비내과", "심장내과"]

    mock_settings = MagicMock()
    mock_settings.hira_api_key = "test_key"

    mock_llm = MagicMock()
    mock_llm.complete.return_value = '["내분비내과", "심장내과"]'

    result = recommend_hospitals(MOCK_RESULT, "서울 강남구", mock_llm, mock_settings)

    assert len(result) <= 5
    assert result[0]["name"] == "강남병원"
    assert "departments" in result[0]
    mock_llm.complete.assert_called_once()


@patch("gogodoc.application.hospital_service.get_hospitals_by_region")
@patch("gogodoc.application.hospital_service.location_to_codes")
def test_no_flagged_items_returns_empty(mock_codes, mock_hosp):
    mock_codes.return_value = ("110000", "")
    result_no_flags = {
        "items": [{"name": "혈색소", "flag": "normal"}]
    }

    mock_settings = MagicMock()
    mock_llm = MagicMock()

    result = recommend_hospitals(result_no_flags, "서울", mock_llm, mock_settings)

    assert result == []
    mock_hosp.assert_not_called()


@patch("gogodoc.application.hospital_service.get_hospitals_by_region")
@patch("gogodoc.application.hospital_service.location_to_codes")
def test_unknown_location_returns_empty(mock_codes, mock_hosp):
    mock_codes.return_value = ("", "")  # 시도 변환 실패

    mock_settings = MagicMock()
    mock_settings.hira_api_key = "test_key"
    mock_llm = MagicMock()
    mock_llm.complete.return_value = '["내과"]'

    result = recommend_hospitals(MOCK_RESULT, "알수없는지역", mock_llm, mock_settings)

    assert result == []
    mock_hosp.assert_not_called()
