from unittest.mock import patch, MagicMock
import pytest
from gogodoc.infrastructure.hira.hira_client import (
    get_hospitals_by_region, get_hospital_departments, HiraApiError
)

HOSP_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode></header>
  <body>
    <items>
      <item>
        <yadmNm>강남세브란스병원</yadmNm>
        <addr>서울특별시 강남구 언주로 211</addr>
        <telno>02-2019-3114</telno>
        <hospUrl>http://gs.iseverance.com</hospUrl>
        <ykiho>abc123</ykiho>
      </item>
    </items>
  </body>
</response>"""

DEPT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode></header>
  <body>
    <items>
      <item><dgsbjtNm>내과</dgsbjtNm></item>
      <item><dgsbjtNm>내분비내과</dgsbjtNm></item>
    </items>
  </body>
</response>"""


@patch("gogodoc.infrastructure.hira.hira_client.requests.get")
def test_get_hospitals_by_region(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = HOSP_LIST_XML
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = get_hospitals_by_region("test_key", "110000")

    assert len(result) == 1
    assert result[0]["name"] == "강남세브란스병원"
    assert result[0]["address"] == "서울특별시 강남구 언주로 211"
    assert result[0]["ykiho"] == "abc123"


@patch("gogodoc.infrastructure.hira.hira_client.requests.get")
def test_get_hospital_departments(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = DEPT_XML
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = get_hospital_departments("test_key", "abc123")

    assert "내과" in result
    assert "내분비내과" in result


@patch("gogodoc.infrastructure.hira.hira_client.requests.get")
def test_api_error_raises(mock_get):
    import requests as req
    mock_get.side_effect = req.RequestException("timeout")

    with pytest.raises(HiraApiError):
        get_hospitals_by_region("test_key", "110000")
