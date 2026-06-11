from __future__ import annotations

import json
import os
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import streamlit as st


APP_TITLE = "신청 현황판"
DEFAULT_WORKSHEET_NAME = "시트1"
SOURCE_COLUMN = "데이터출처"
DEFAULT_PUBLIC_SHEET_URLS = """마인드PT 3차 현황 | https://docs.google.com/spreadsheets/d/1MLynxDsfhvyjNKTxMCDQYbV0evGMq2hpwGq-Nmus_CY/edit?gid=502869052#gid=502869052
자기계발 명상캠프 38기 현황 | https://docs.google.com/spreadsheets/d/1adpSW8uTDKUsX9Z-fHvdMIkrZUU08edGgfMfeVkW9P4/edit?gid=0#gid=0"""
SERVICE_ACCOUNT_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

NAME_COLUMN_CANDIDATES = ["이름", "성명", "신청자명", "참가자명"]
COURSE_COLUMN_CANDIDATES = [
    "과정",
    "과정명",
    "코스",
    "프로그램",
    "프로그램명",
    "캠프",
    "캠프명",
    "차수",
    "클래스명",
]
PAYMENT_COLUMN_CANDIDATES = ["입금", "입금여부", "결제", "결제상태", "결제 여부", "상태"]
EXPERIENCE_COLUMN_CANDIDATES = [
    "명상경험",
    "명상 경험",
    "경험여부",
    "수련경험",
    "수련 경험",
    "구분",
    "회원구분",
]

PAID_VALUES = {"입금", "입금완료", "완료", "결제완료", "o", "예", "y", "paid"}
UNPAID_VALUES = {"미입금", "대기", "결제대기", "미완료", "x", "아니오", "n", "unpaid"}
EXPERIENCE_ORDER = ["신규", "휴면", "과정생", "미파악"]


def create_sample_dataframe() -> pd.DataFrame:
    """Return a realistic fallback dataset that matches the requested report."""
    rows = [
        ("김민지", "마인드PT 3차", "입금완료", "신규"),
        ("이서준", "마인드PT 3차", "입금완료", "과정생"),
        ("박지현", "마인드PT 3차", "결제대기", "신규"),
        ("최하늘", "마인드PT 3차", "입금완료", "휴면"),
        ("정우진", "마인드PT 3차", "입금완료", "과정생"),
        ("강소라", "마인드PT 3차", "입금완료", "미파악"),
        ("윤도현", "마인드PT 3차", "결제대기", "과정생"),
        ("한지우", "마인드PT 3차", "입금완료", "신규"),
        ("오세훈", "마인드PT 3차", "입금완료", "신규"),
        ("문가영", "마인드PT 3차", "입금완료", "과정생"),
        ("임수아", "마인드PT 3차", "입금완료", "신규"),
        ("조현우", "마인드PT 3차", "입금완료", "과정생"),
        ("배유나", "마인드PT 3차", "결제대기", "미파악"),
        ("서민재", "마인드PT 3차", "입금완료", "신규"),
        ("남지민", "마인드PT 3차", "입금완료", "과정생"),
        ("류하준", "마인드PT 3차", "입금완료", "신규"),
    ]
    return pd.DataFrame(rows, columns=["이름", "과정명", "입금여부", "명상경험"])


def find_logo_file() -> str | None:
    for file_name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp"):
        logo_path = Path(file_name)
        if logo_path.exists():
            return str(logo_path)
    return None


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _clean_text(value)).lower()


def normalize_payment_status(value: Any) -> str:
    compact_value = _compact(value)
    if compact_value in PAID_VALUES:
        return "입금완료"
    if compact_value in UNPAID_VALUES:
        return "미입금/대기"
    return "미입금/대기"


def normalize_experience_status(value: Any) -> str:
    compact_value = _compact(value)
    if not compact_value:
        return "미파악"
    if "신규" in compact_value:
        return "신규"
    if "휴면" in compact_value:
        return "휴면"
    if (
        "과정생" in compact_value
        or "수강생" in compact_value
        or "재수강" in compact_value
        or re.search(r"\d+과정", compact_value)
        or compact_value.endswith("과정")
        or "희망반" in compact_value
        or "행복반" in compact_value
        or compact_value in {"희망", "행복"}
    ):
        return "과정생"
    if "미파악" in compact_value or "알수없" in compact_value or "확인필요" in compact_value:
        return "미파악"
    return "미파악"


def _student_detail_sort_key(value: Any) -> tuple[int, int | str]:
    text = _clean_text(value)
    compact_value = _compact(text)
    match = re.search(r"(\d+)과정", compact_value)
    if match:
        return (0, int(match.group(1)))
    if "희망" in compact_value:
        return (1, 0)
    if "행복" in compact_value:
        return (1, 1)
    return (2, text)


def guess_column(columns: list[str], candidates: list[str]) -> str | None:
    compact_columns = {_compact(column): column for column in columns}
    compact_candidates = [_compact(candidate) for candidate in candidates]

    for candidate in compact_candidates:
        if candidate in compact_columns:
            return compact_columns[candidate]

    for candidate in compact_candidates:
        for compact_column, original_column in compact_columns.items():
            if candidate and (candidate in compact_column or compact_column in candidate):
                return original_column

    return None


def split_setting_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        values: list[str] = []
        for item in value:
            values.extend(split_setting_values(item))
        return values
    return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]


def split_url_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        values: list[str] = []
        for item in value:
            values.extend(split_url_lines(item))
        return values
    return [part.strip() for part in str(value).splitlines() if part.strip()]


def parse_public_sheet_inputs(value: Any) -> list[tuple[str | None, str]]:
    parsed_inputs = []
    for line in split_url_lines(value):
        if "|" in line:
            label, url = line.split("|", 1)
            parsed_inputs.append((label.strip() or None, url.strip()))
        else:
            parsed_inputs.append((None, line))
    return [(label, url) for label, url in parsed_inputs if url]


def extract_spreadsheet_id(value: str) -> str:
    text = value.strip()
    match = re.search(r"/spreadsheets/d/([^/]+)", text)
    return match.group(1) if match else text


def convert_google_sheet_url_to_csv_url(sheet_url: str) -> str:
    url = sheet_url.strip()
    if not url:
        return ""
    if "docs.google.com/spreadsheets" not in url:
        return url
    if "/export" in url and "format=csv" in url:
        return url

    match = re.search(r"/spreadsheets/d/([^/]+)", url)
    if not match:
        return url

    parsed = urlparse(url)
    gid = "0"
    query_gid = parse_qs(parsed.query).get("gid", [""])[0]
    fragment_gid_match = re.search(r"gid=([^&]+)", parsed.fragment)
    if query_gid:
        gid = query_gid
    elif fragment_gid_match:
        gid = fragment_gid_match.group(1)

    spreadsheet_id = match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def load_dataframe_from_public_csv(sheet_url: str) -> pd.DataFrame:
    csv_url = convert_google_sheet_url_to_csv_url(sheet_url)
    if not csv_url:
        raise ValueError("구글 시트 URL 또는 CSV 링크를 입력해 주세요.")

    try:
        return pd.read_csv(csv_url)
    except UnicodeDecodeError:
        return pd.read_csv(csv_url, encoding="cp949")


def _append_source_column(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    result = df.copy()
    source_column = SOURCE_COLUMN if SOURCE_COLUMN not in result.columns else f"{SOURCE_COLUMN}_앱"
    result[source_column] = source_name
    return result


def load_dataframe_from_public_csv_list(sheet_urls: str) -> pd.DataFrame:
    sheet_inputs = parse_public_sheet_inputs(sheet_urls)
    if not sheet_inputs:
        raise ValueError("구글 시트 URL 또는 CSV 링크를 한 줄에 하나씩 입력해 주세요.")

    frames = []
    for index, (label, url) in enumerate(sheet_inputs, start=1):
        frame = load_dataframe_from_public_csv(url)
        frames.append(_append_source_column(frame, label or f"공개 CSV {index}"))
    return pd.concat(frames, ignore_index=True, sort=False)


def _get_secret_section(section_name: str) -> dict[str, Any]:
    try:
        if section_name in st.secrets:
            return dict(st.secrets[section_name])
    except Exception:
        return {}
    return {}


def _get_service_account_info() -> dict[str, Any] | None:
    secrets_info = _get_secret_section("gcp_service_account")
    if secrets_info:
        return secrets_info

    env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_json:
        return json.loads(env_json)

    return None


def _get_default_sheet_setting(key: str, default: str = "") -> str:
    sheet_section = _get_secret_section("google_sheet")
    if sheet_section.get(key):
        value = sheet_section[key]
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value)
        return str(value)

    env_key = f"GOOGLE_SHEET_{key.upper()}"
    return os.getenv(env_key, default)


def load_dataframe_from_service_account(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    service_account_info = _get_service_account_info()
    if not service_account_info:
        raise ValueError(".streamlit/secrets.toml 또는 환경변수에 서비스 계정 인증정보가 없습니다.")

    spreadsheet_key = extract_spreadsheet_id(spreadsheet_id) or _get_default_sheet_setting("spreadsheet_id")
    if not spreadsheet_key:
        raise ValueError("서비스 계정 방식에는 spreadsheet_id가 필요합니다.")

    worksheet = worksheet_name.strip() or _get_default_sheet_setting("worksheet_name", DEFAULT_WORKSHEET_NAME)

    import gspread
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SERVICE_ACCOUNT_SCOPES,
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(spreadsheet_key)
    worksheet_obj = sheet.worksheet(worksheet) if worksheet else sheet.sheet1
    records = worksheet_obj.get_all_records()
    if not records:
        raise ValueError("구글 시트에서 읽은 데이터가 비어 있습니다.")
    return pd.DataFrame(records)


def _build_service_account_targets(spreadsheet_id_text: str, worksheet_name_text: str) -> list[tuple[str, str]]:
    spreadsheet_values = split_setting_values(spreadsheet_id_text or _get_default_sheet_setting("spreadsheet_id"))
    worksheet_values = split_setting_values(worksheet_name_text or _get_default_sheet_setting("worksheet_name"))

    spreadsheet_ids = [extract_spreadsheet_id(value) for value in spreadsheet_values if extract_spreadsheet_id(value)]
    worksheets = worksheet_values or [DEFAULT_WORKSHEET_NAME]

    if not spreadsheet_ids:
        raise ValueError("서비스 계정 방식에는 spreadsheet_id 또는 구글 시트 URL이 필요합니다.")

    if len(spreadsheet_ids) == 1:
        return [(spreadsheet_ids[0], worksheet) for worksheet in worksheets]
    if len(worksheets) == 1:
        return [(spreadsheet_id, worksheets[0]) for spreadsheet_id in spreadsheet_ids]
    if len(spreadsheet_ids) == len(worksheets):
        return list(zip(spreadsheet_ids, worksheets, strict=True))

    raise ValueError(
        "여러 spreadsheet_id와 여러 워크시트 이름을 함께 쓰려면 개수가 같아야 합니다. "
        "또는 spreadsheet_id 1개에 워크시트 이름을 여러 개 입력해 주세요."
    )


def load_dataframe_from_service_account_list(spreadsheet_id_text: str, worksheet_name_text: str) -> pd.DataFrame:
    targets = _build_service_account_targets(spreadsheet_id_text, worksheet_name_text)
    frames = []
    for spreadsheet_id, worksheet_name in targets:
        frame = load_dataframe_from_service_account(spreadsheet_id, worksheet_name)
        frames.append(_append_source_column(frame, worksheet_name))
    return pd.concat(frames, ignore_index=True, sort=False)


def load_dataframe_with_fallback(
    connection_mode: str,
    sheet_url: str,
    spreadsheet_id: str,
    worksheet_name: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sample_df = create_sample_dataframe()

    if connection_mode == "샘플 데이터":
        return sample_df, {
            "status": "sample",
            "title": "샘플 데이터 모드",
            "message": "구글 시트 연결 없이 내장 샘플 데이터로 실행 중입니다.",
            "using_sample": True,
        }

    try:
        if connection_mode == "공개 CSV 링크":
            df = load_dataframe_from_public_csv_list(sheet_url)
            return df, {
                "status": "public_csv",
                "title": "공개 CSV 링크 연결됨",
                "message": "공개 CSV 링크에서 데이터를 읽어 합쳤습니다.",
                "using_sample": False,
            }

        df = load_dataframe_from_service_account_list(spreadsheet_id, worksheet_name)
        return df, {
            "status": "service_account",
            "title": "서비스 계정 연결됨",
            "message": "서비스 계정 인증으로 구글 시트를 읽어 합쳤습니다.",
            "using_sample": False,
        }
    except Exception as exc:
        return sample_df, {
            "status": "fallback",
            "title": "연결 실패, 샘플 데이터 사용 중",
            "message": f"{exc}",
            "using_sample": True,
        }


def summarize_applicants(
    df: pd.DataFrame,
    payment_column: str | None,
    experience_column: str | None,
    name_column: str | None = None,
) -> dict[str, Any]:
    if name_column and name_column in df.columns:
        applicant_df = df[df[name_column].map(lambda value: bool(_clean_text(value)))].copy()
    else:
        applicant_df = df.copy()

    total_count = int(len(applicant_df))

    if payment_column and payment_column in applicant_df.columns:
        payment_series = applicant_df[payment_column].map(normalize_payment_status)
    else:
        payment_series = pd.Series(["미입금/대기"] * total_count, index=applicant_df.index)

    paid_count = int((payment_series == "입금완료").sum())
    unpaid_count = total_count - paid_count

    if experience_column and experience_column in applicant_df.columns:
        experience_series = applicant_df[experience_column].map(normalize_experience_status)
    else:
        experience_series = pd.Series(["미파악"] * total_count, index=applicant_df.index)

    experience_counts = {
        label: int((experience_series == label).sum())
        for label in EXPERIENCE_ORDER
    }
    if experience_column and experience_column in applicant_df.columns:
        student_raw_values = applicant_df.loc[experience_series == "과정생", experience_column].map(_clean_text)
        student_detail_df = (
            student_raw_values.replace("", "미파악")
            .value_counts()
            .rename_axis("과정")
            .reset_index(name="인원")
        )
        if not student_detail_df.empty:
            student_detail_df["_정렬"] = student_detail_df["과정"].map(_student_detail_sort_key)
            student_detail_df = (
                student_detail_df.sort_values("_정렬")
                .drop(columns=["_정렬"])
                .reset_index(drop=True)
            )
    else:
        student_detail_df = pd.DataFrame(columns=["과정", "인원"])

    payment_counts = {
        "입금완료": paid_count,
        "미입금/대기": unpaid_count,
    }

    summary_rows = [
        ("신청 총합", total_count),
        ("입금 완료", paid_count),
        ("미입금/대기", unpaid_count),
        ("신규", experience_counts["신규"]),
        ("휴면", experience_counts["휴면"]),
        ("과정생", experience_counts["과정생"]),
        ("미파악", experience_counts["미파악"]),
    ]

    return {
        "total": total_count,
        "paid": paid_count,
        "unpaid": unpaid_count,
        "experience_counts": experience_counts,
        "payment_counts": payment_counts,
        "summary_df": pd.DataFrame(summary_rows, columns=["항목", "인원"]),
        "applicant_df": applicant_df,
        "student_detail_df": student_detail_df,
        "experience_df": pd.DataFrame(
            [{"명상경험": label, "인원": experience_counts[label]} for label in EXPERIENCE_ORDER]
        ),
        "payment_df": pd.DataFrame(
            [{"입금상태": label, "인원": count} for label, count in payment_counts.items()]
        ),
    }


def create_share_message(summary: dict[str, Any], selected_course: str) -> str:
    title = selected_course or "전체 신청 현황"
    experience_counts = summary["experience_counts"]

    return "\n".join(
        [
            f"<{title}>",
            f"신청 총합 {summary['total']}명 / 입금 {summary['paid']}명",
            f"신규 {experience_counts['신규']} / 휴면 {experience_counts['휴면']}",
            f"과정생 {experience_counts['과정생']} / 미파악 {experience_counts['미파악']}",
            "",
            "[상세 현황]",
            f"- 총 신청자: {summary['total']}명",
            f"- 입금 완료: {summary['paid']}명",
            f"- 미입금/대기: {summary['unpaid']}명",
            f"- 신규: {experience_counts['신규']}명",
            f"- 휴면: {experience_counts['휴면']}명",
            f"- 과정생: {experience_counts['과정생']}명",
            f"- 미파악: {experience_counts['미파악']}명",
        ]
    )


def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def render_connection_status(connection_info: dict[str, Any]) -> None:
    title = connection_info["title"]
    message = connection_info["message"]
    if connection_info["status"] == "sample":
        st.info(f"{title}: {message}")
    elif connection_info["status"] in {"public_csv", "service_account"}:
        st.success(f"{title}: {message}")
    else:
        st.warning(f"{title}: {message}")


def render_summary_panel(summary: dict[str, Any]) -> None:
    experience_counts = summary["experience_counts"]
    st.markdown(
        """
        <style>
        .summary-board {
            max-width: 960px;
            margin: 1.25rem auto 1.8rem;
            color: #111827;
            text-align: center;
        }
        .summary-total {
            border: 1px solid #93c5fd;
            background: #e8f2ff;
            border-radius: 8px;
            padding: 1.6rem 1.5rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
        }
        .summary-total-label {
            font-size: 1rem;
            font-weight: 700;
            color: #4b5563;
            margin-bottom: 0.25rem;
        }
        .summary-total-value {
            font-size: 4rem;
            line-height: 1;
            font-weight: 800;
            color: #111827;
        }
        .summary-total-unit {
            font-size: 1.35rem;
            font-weight: 700;
            margin-left: 0.25rem;
            color: #4b5563;
        }
        .summary-box {
            border: 1px solid #d1d5db;
            background: #ffffff;
            border-radius: 8px;
            display: grid;
            overflow: hidden;
            margin-bottom: 0.75rem;
        }
        .summary-box.four {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }
        .summary-box.two {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .summary-cell {
            min-height: 118px;
            padding: 1rem 0.75rem;
            border-right: 1px solid #e5e7eb;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }
        .summary-cell:last-child {
            border-right: 0;
        }
        .summary-cell.new {
            background: #eff6ff;
        }
        .summary-cell.rest {
            background: #f5f3ff;
        }
        .summary-cell.student {
            background: #ecfeff;
        }
        .summary-cell.unknown {
            background: #fffbeb;
        }
        .summary-cell.pay {
            background: #f0fdf4;
        }
        .summary-cell.wait {
            background: #fef2f2;
        }
        .summary-box-title {
            font-size: 0.95rem;
            font-weight: 800;
            color: #374151;
            margin: 0.35rem 0 0.5rem;
            text-align: center;
        }
        .summary-label {
            font-size: 0.98rem;
            font-weight: 700;
            color: #4b5563;
            margin-bottom: 0.35rem;
        }
        .summary-value {
            font-size: 2.45rem;
            line-height: 1;
            font-weight: 800;
            color: #111827;
        }
        .summary-unit {
            font-size: 1rem;
            font-weight: 700;
            color: #4b5563;
            margin-left: 0.15rem;
        }
        .summary-note {
            font-size: 0.88rem;
            color: #6b7280;
            margin-top: 0.5rem;
        }
        .summary-rules {
            margin-top: 0.85rem;
            font-size: 0.9rem;
            color: #4b5563;
        }
        @media (max-width: 600px) {
            .summary-board {
                margin: 0.8rem auto 1.2rem;
            }
            .summary-total {
                padding: 1rem 0.75rem;
                margin-bottom: 0.55rem;
            }
            .summary-total-label {
                font-size: 0.95rem;
            }
            .summary-total-value {
                font-size: 3.15rem;
            }
            .summary-total-unit {
                font-size: 1rem;
            }
            .summary-note {
                font-size: 0.78rem;
                margin-top: 0.4rem;
            }
            .summary-box.two,
            .summary-box.four {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                margin-bottom: 0.55rem;
            }
            .summary-cell {
                min-height: 86px;
                padding: 0.7rem 0.35rem;
                border-right: 1px solid #e5e7eb;
                border-bottom: 0;
            }
            .summary-box.four .summary-cell:nth-child(2n),
            .summary-box.two .summary-cell:nth-child(2n) {
                border-right: 0;
            }
            .summary-box.four .summary-cell:nth-child(-n+2) {
                border-bottom: 1px solid #e5e7eb;
            }
            .summary-label {
                font-size: 0.86rem;
                margin-bottom: 0.25rem;
            }
            .summary-value {
                font-size: 1.9rem;
            }
            .summary-unit {
                font-size: 0.82rem;
            }
            .summary-box-title {
                font-size: 0.88rem;
                margin: 0.25rem 0 0.35rem;
            }
            .summary-rules {
                font-size: 0.76rem;
                line-height: 1.45;
                margin-top: 0.55rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="summary-board" aria-label="신청 현황 요약">
            <div class="summary-total">
                <div class="summary-total-label">신청자 총합</div>
                <div><span class="summary-total-value">{summary["total"]}</span><span class="summary-total-unit">명</span></div>
                <div class="summary-note">이름이 입력된 신청자만 집계합니다.</div>
            </div>
            <div class="summary-box-title">명상경험 현황</div>
            <div class="summary-box four">
                <div class="summary-cell new">
                    <div class="summary-label">신규</div>
                    <div><span class="summary-value">{experience_counts["신규"]}</span><span class="summary-unit">명</span></div>
                </div>
                <div class="summary-cell rest">
                    <div class="summary-label">휴면</div>
                    <div><span class="summary-value">{experience_counts["휴면"]}</span><span class="summary-unit">명</span></div>
                </div>
                <div class="summary-cell student">
                    <div class="summary-label">과정생</div>
                    <div><span class="summary-value">{experience_counts["과정생"]}</span><span class="summary-unit">명</span></div>
                </div>
                <div class="summary-cell unknown">
                    <div class="summary-label">미파악</div>
                    <div><span class="summary-value">{experience_counts["미파악"]}</span><span class="summary-unit">명</span></div>
                </div>
            </div>
            <div class="summary-box-title">결제 현황</div>
            <div class="summary-box two">
                <div class="summary-cell pay">
                    <div class="summary-label">입금완료</div>
                    <div><span class="summary-value">{summary["paid"]}</span><span class="summary-unit">명</span></div>
                </div>
                <div class="summary-cell wait">
                    <div class="summary-label">미입금/대기</div>
                    <div><span class="summary-value">{summary["unpaid"]}</span><span class="summary-unit">명</span></div>
                </div>
            </div>
            <div class="summary-rules">집계 기준: 이름이 있는 행만 계산 · 결제여부가 입금이면 입금완료 · 시트 수정 후 새로고침하면 최신 데이터 반영</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _select_column(
    label: str,
    columns: list[str],
    guessed_column: str | None,
    help_text: str,
) -> str | None:
    options = ["자동/없음"] + columns
    default_index = options.index(guessed_column) if guessed_column in options else 0
    selected = st.sidebar.selectbox(label, options, index=default_index, help=help_text)
    return None if selected == "자동/없음" else selected


def _filter_by_course(df: pd.DataFrame, course_column: str | None) -> tuple[pd.DataFrame, str]:
    if not course_column or course_column not in df.columns:
        st.selectbox("과정명/차수 필터", ["선택 가능한 과정 없음"], disabled=True)
        return df.copy(), "전체 신청 현황"

    courses = [
        course
        for course in df[course_column].dropna().astype(str).str.strip().drop_duplicates().tolist()
        if course
    ]
    if not courses:
        st.selectbox("과정명/차수 필터", ["선택 가능한 과정 없음"], disabled=True)
        return df.copy(), "전체 신청 현황"

    selected_course = st.selectbox("과정명/차수 필터", courses)
    filtered_df = df[df[course_column].astype(str).str.strip() == selected_course].copy()
    return filtered_df, selected_course


def render_dashboard(
    df: pd.DataFrame,
    connection_info: dict[str, Any],
    column_map: dict[str, str | None],
) -> None:
    logo_file = find_logo_file()
    if logo_file:
        st.image(logo_file, width=120)

    st.markdown(
        f"""
        <div style="text-align:center; margin: 0.35rem 0 1rem;">
            <h1 style="margin-bottom:0.25rem;">{APP_TITLE}</h1>
            <p style="margin:0; color:#6b7280;">구글 스프레드시트와 연동해 신청 현황을 자동 집계합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_connection_status(connection_info)

    filtered_df, selected_course = _filter_by_course(df, column_map["course"])
    summary = summarize_applicants(
        filtered_df,
        column_map["payment"],
        column_map["experience"],
        name_column=column_map["name"],
    )
    share_message = create_share_message(summary, selected_course)

    render_summary_panel(summary)
    student_count = summary["experience_counts"]["과정생"]
    with st.expander(f"과정생 {student_count}명 - 클릭해서 과정별 인원 보기", expanded=False):
        if summary["student_detail_df"].empty:
            st.info("과정생으로 분류된 신청자가 없습니다.")
        else:
            st.table(summary["student_detail_df"])

    st.subheader("담당자 공유용 문구")
    st.text_area("복사용 문구", share_message, height=230)

    text_col, md_col, csv_col = st.columns(3)
    with text_col:
        st.download_button(
            "TXT 다운로드",
            data=share_message.encode("utf-8-sig"),
            file_name="mindpt_summary.txt",
            mime="text/plain",
            width="stretch",
        )
    with md_col:
        markdown_message = f"```text\n{share_message}\n```"
        st.download_button(
            "Markdown 다운로드",
            data=markdown_message.encode("utf-8-sig"),
            file_name="mindpt_summary.md",
            mime="text/markdown",
            width="stretch",
        )
    with csv_col:
        st.download_button(
            "집계 CSV 다운로드",
            data=convert_df_to_csv(summary["summary_df"]),
            file_name="mindpt_summary.csv",
            mime="text/csv",
            width="stretch",
        )

def _render_sidebar() -> dict[str, str]:
    st.sidebar.header("데이터 설정")
    default_connection_index = 1 if DEFAULT_PUBLIC_SHEET_URLS else 0
    connection_mode = st.sidebar.radio(
        "데이터 연결 방식",
        ["샘플 데이터", "공개 CSV 링크", "서비스 계정"],
        index=default_connection_index,
        help="인증정보가 없거나 연결에 실패하면 자동으로 샘플 데이터가 사용됩니다.",
    )

    sheet_url = st.sidebar.text_area(
        "구글 시트 URL 또는 CSV export URL",
        value=os.getenv("GOOGLE_SHEET_URL", DEFAULT_PUBLIC_SHEET_URLS),
        height=110,
        placeholder="https://docs.google.com/spreadsheets/d/...",
        help="여러 시트를 연결하려면 URL을 한 줄에 하나씩 입력하세요. '표시이름 | URL' 형식도 가능합니다.",
    )
    spreadsheet_id = st.sidebar.text_area(
        "서비스 계정용 spreadsheet_id 또는 시트 URL",
        value=_get_default_sheet_setting("spreadsheet_id"),
        height=90,
        placeholder="구글 시트 주소의 /d/ 뒤에 있는 값",
        help="같은 스프레드시트의 여러 워크시트를 읽을 때는 1개만 입력하면 됩니다.",
    )
    worksheet_name = st.sidebar.text_area(
        "워크시트 이름",
        value=_get_default_sheet_setting("worksheet_name", DEFAULT_WORKSHEET_NAME),
        height=90,
        help="여러 워크시트를 읽으려면 이름을 쉼표 또는 줄바꿈으로 구분하세요.",
    )

    if st.sidebar.button("새로고침", width="stretch"):
        st.cache_data.clear()
        st.session_state["last_refresh"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.rerun()

    auto_refresh = st.sidebar.toggle(
        "자동 갱신(10초)",
        value=False,
        help="켜두면 앱이 열려 있는 동안 10초마다 구글 시트를 다시 읽습니다.",
    )

    last_refresh = st.session_state.get("last_refresh")
    if last_refresh:
        st.sidebar.caption(f"마지막 새로고침: {last_refresh}")

    return {
        "connection_mode": connection_mode,
        "sheet_url": sheet_url,
        "spreadsheet_id": spreadsheet_id,
        "worksheet_name": worksheet_name,
        "auto_refresh": auto_refresh,
    }


def render_app_body(settings: dict[str, Any]) -> None:
    df, connection_info = load_dataframe_with_fallback(
        settings["connection_mode"],
        settings["sheet_url"],
        settings["spreadsheet_id"],
        settings["worksheet_name"],
    )
    df.columns = [str(column).strip() for column in df.columns]
    columns = df.columns.tolist()

    guessed_name = guess_column(columns, NAME_COLUMN_CANDIDATES)
    guessed_course = guess_column(columns, COURSE_COLUMN_CANDIDATES)
    source_count = df[SOURCE_COLUMN].dropna().astype(str).str.strip().nunique() if SOURCE_COLUMN in columns else 0
    if SOURCE_COLUMN in columns and source_count > 1:
        guessed_course = SOURCE_COLUMN
    elif not guessed_course and SOURCE_COLUMN in columns:
        guessed_course = SOURCE_COLUMN
    guessed_payment = guess_column(columns, PAYMENT_COLUMN_CANDIDATES)
    guessed_experience = guess_column(columns, EXPERIENCE_COLUMN_CANDIDATES)

    st.sidebar.header("열 선택")
    st.sidebar.caption("자동 추정이 맞지 않으면 여기서 직접 고를 수 있습니다.")
    column_map = {
        "name": _select_column("이름 열", columns, guessed_name, "이름 열은 원본 표 확인용입니다."),
        "course": _select_column("과정명/차수 열", columns, guessed_course, "과정별 필터에 사용됩니다."),
        "payment": _select_column("입금 여부 열", columns, guessed_payment, "입금 완료와 미입금/대기 집계에 사용됩니다."),
        "experience": _select_column("명상경험 열", columns, guessed_experience, "신규, 휴면, 과정생, 미파악 집계에 사용됩니다."),
    }

    render_dashboard(df, connection_info, column_map)


@st.fragment(run_every="10s")
def render_auto_refresh_app_body(settings: dict[str, Any]) -> None:
    render_app_body(settings)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="MP", layout="wide")

    settings = _render_sidebar()
    if settings["auto_refresh"]:
        render_auto_refresh_app_body(settings)
    else:
        render_app_body(settings)


if __name__ == "__main__":
    main()
