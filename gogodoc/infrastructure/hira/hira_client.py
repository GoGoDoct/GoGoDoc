"""HIRA 공공데이터 API 어댑터"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

_BASE = "https://apis.data.go.kr/B551182"


class HiraApiError(Exception):
    """HIRA API 호출 실패"""


def get_hospitals_by_region(
    api_key: str,
    sido_cd: str,
    sggu_cd: str = "",
    num_of_rows: int = 50,
) -> list[dict]:
    """시도/시군구 기준 병원 기본목록 조회"""
    params: dict = {
        "serviceKey": api_key,
        "pageNo": 1,
        "numOfRows": num_of_rows,
        "sidoCd": sido_cd,
        "_type": "xml",
    }
    if sggu_cd:
        params["sgguCd"] = sggu_cd

    try:
        resp = requests.get(
            f"{_BASE}/hospInfoServicev2/getHospBasisList",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HiraApiError(f"병원목록 조회 실패: {e}") from e

    return _parse_hosp_list(resp.text)


def get_hospital_departments(api_key: str, ykiho: str) -> list[str]:
    """병원 진료과목 목록 조회"""
    params = {
        "serviceKey": api_key,
        "ykiho": ykiho,
        "_type": "xml",
    }

    try:
        resp = requests.get(
            f"{_BASE}/MadmDtlInfoService2.8/getDgsbjtInfo2.8",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HiraApiError(f"진료과목 조회 실패: {e}") from e

    return _parse_dept_list(resp.text)


def _parse_hosp_list(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    hospitals = []
    for item in root.findall(".//item"):
        hospitals.append({
            "name": item.findtext("yadmNm") or "",
            "address": item.findtext("addr") or "",
            "tel": item.findtext("telno") or "",
            "url": item.findtext("hospUrl") or "",
            "ykiho": item.findtext("ykiho") or "",
            "departments": [],
        })
    return hospitals


def _parse_dept_list(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [
        item.findtext("dgsbjtNm") or ""
        for item in root.findall(".//item")
        if item.findtext("dgsbjtNm")
    ]
