import io
import os
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="견적·수주 통합 경영 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 🛠️ 정제 및 집계 헬퍼 함수
# ---------------------------------------------------------
def extract_year_num(val):
    if pd.isna(val):
        return 9999
    digits = re.findall(r'\d+', str(val))
    return int(digits[0]) if digits else 9999

def extract_month_num(val):
    if pd.isna(val):
        return 99
    digits = re.findall(r'\d+', str(val))
    return int(digits[0]) if digits else 99

def clean_project_name(name):
    """프로젝트명 뒤의 회차(#1, #2 등), 용량((200Ah) 등), 분수((1/2) 등) 표기 정제"""
    if not isinstance(name, str) or pd.isna(name):
        return ""
    s = name.strip()
    s = re.sub(r'\s*\(\s*\d+(?:\.\d+)?\s*(?:Ah|AH|ah)?\s*\)', '', s)
    s = re.sub(r'\s*\(\s*\d+\s*/\s*\d+\s*\)', '', s)
    s = re.sub(r'\s*#\s*\d+', '', s)
    s = re.sub(r'[\s/_-]+$', '', s)
    return s.strip()

def get_representative_project_name(series):
    cleaned_list = [clean_project_name(p) for p in series if pd.notna(p) and str(p).strip() not in ["", "-", "nan", "None"]]
    unique_cleaned = list(dict.fromkeys(cleaned_list))
    if not unique_cleaned:
        return "-"
    if len(unique_cleaned) == 1:
        return unique_cleaned[0]
    parts_list = [c.split(" / ") for c in unique_cleaned]
    common = []
    for parts in zip(*parts_list):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    if common:
        return " / ".join(common)
    return unique_cleaned[0]

def combine_unique_po(series):
    """유효한 PO No. 또는 견적 No.를 중복 없이 연결 (없으면 '-')"""
    vals = [str(x).strip() for x in series if pd.notna(x) and str(x).strip() not in ["", "-", "nan", "None", "0"]]
    unique_vals = list(dict.fromkeys(vals))
    return ", ".join(unique_vals) if unique_vals else "-"

def combine_unique(series):
    vals = [str(x).strip() for x in series if pd.notna(x) and str(x).strip() not in ["", "-", "nan", "None"]]
    unique_vals = list(dict.fromkeys(vals))
    return ", ".join(unique_vals) if unique_vals else "-"

def get_first_valid(series):
    for v in series:
        if pd.notna(v) and str(v).strip() not in ["", "-", "nan", "None"]:
            return str(v).strip()
    return "-"

def generate_printable_html(integrated_df, display_cols, total_sales, order_sales, quote_sales, total_row_count, yearly_summary):
    rows_html = []
    for _, r in integrated_df.iterrows():
        row_type = r.get("_row_type", "data")
        if row_type == "grand_total":
            tr_class = 'class="grand-total-row"'
        elif row_type == "year_total":
            tr_class = 'class="year-total-row"'
        elif row_type == "month_subtotal":
            tr_class = 'class="month-subtotal-row"'
        else:
            tr_class = ''

        tds = []
        for col in display_cols:
            val = r.get(col, "")
            if col == "매출금액":
                val_str = f"₩{val:,.0f}" if isinstance(val, (int, float)) else str(val)
                align = 'style="text-align: right;"'
            elif col in ["프로젝트명", "내용"]:
                val_str = str(val)
                align = 'style="text-align: left;"'
            else:
                val_str = str(val)
                align = 'style="text-align: center;"'
            tds.append(f'<td {align}>{val_str}</td>')

        rows_html.append(f'<tr {tr_class}>{"".join(tds)}</tr>')

    tbody_html = "\n".join(rows_html)
    thead_html = "".join([f'<th>{col}</th>' for col in display_cols])

    yearly_cards_html = ""
    for _, yr in yearly_summary.iterrows():
        y_name = yr["매출년도"]
        y_amt = yr["매출금액"]
        y_ratio = (y_amt / total_sales * 100) if total_sales > 0 else 0
        yearly_cards_html += f"""
        <div class="kpi-card" style="border-left: 3px solid #2563eb;">
            <div class="kpi-title">📅 {y_name} 합산</div>
            <div class="kpi-value">₩{y_amt:,.0f}</div>
            <div style="font-size: 9.5px; color: #64748b; margin-top: 3px;">약 {y_amt/1e8:.2f}억 ({y_ratio:.1f}%)</div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>견적·수주 통합 대시보드 보고서</title>
    <style>
        @page {{ size: A4 landscape; margin: 8mm 6mm; }}
        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
        body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; color: #1e293b; margin: 0; padding: 15px; font-size: 11px; }}
        .header-container {{ margin-bottom: 12px; border-bottom: 2px solid #334155; padding-bottom: 8px; }}
        .header-title {{ font-size: 18px; font-weight: bold; margin: 0 0 6px 0; color: #0f172a; }}
        .kpi-container {{ display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }}
        .kpi-card {{ flex: 1; min-width: 140px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px 12px; }}
        .kpi-title {{ font-size: 10px; color: #64748b; margin-bottom: 2px; }}
        .kpi-value {{ font-size: 13.5px; font-weight: bold; color: #0f172a; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 10px; line-height: 1.35; }}
        th {{ background-color: #f1f5f9; border: 1px solid #cbd5e1; padding: 6px 4px; text-align: center; font-weight: 600; }}
        td {{ border: 1px solid #e2e8f0; padding: 4px 6px; }}
        tr.month-subtotal-row {{ background-color: #f8fafc !important; font-weight: bold; color: #334155; }}
        tr.year-total-row {{ background-color: #fed7aa !important; font-weight: bold; color: #7c2d12; border-top: 1.5px solid #fdba74; border-bottom: 1.5px solid #fdba74; }}
        tr.grand-total-row {{ background-color: #cbd5e1 !important; font-weight: bold; color: #000000; border-top: 2px solid #475569; }}
        .print-btn {{ position: fixed; top: 15px; right: 15px; background-color: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }}
        @media print {{ .print-btn {{ display: none !important; }} body {{ padding: 0; }} }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">🖨️ 인쇄하기 (Ctrl+P)</button>
    <div class="header-container">
        <div class="header-title">📊 견적·수주 통합 실적 보고서</div>
    </div>
    <div class="kpi-container">
        <div class="kpi-card"><div class="kpi-title">통합 총 매출규모</div><div class="kpi-value">₩{total_sales:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-title">💼 수주 확정액</div><div class="kpi-value">₩{order_sales:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-title">📋 견적 예상액</div><div class="kpi-value">₩{quote_sales:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-title">통합 집계 항목수</div><div class="kpi-value">{total_row_count:,} 건</div></div>
        {yearly_cards_html}
    </div>
    <table>
        <thead><tr>{thead_html}</tr></thead>
        <tbody>{tbody_html}</tbody>
    </table>
</body>
</html>"""
    return html_content

# ---------------------------------------------------------
# 📥 1. 수주대장 로더 (PO No.만 정확히 추출)
# ---------------------------------------------------------
def load_order_ledger(folder_path="."):
    target_file = None
    for f in os.listdir(folder_path):
        if f.endswith(".xlsx") and not f.startswith("~$") and "수주대장" in f:
            target_file = os.path.join(folder_path, f)
            break

    if not target_file:
        return pd.DataFrame()

    raw_df = pd.read_excel(target_file, sheet_name=0, header=None)
    header_idx = 0
    for i in range(min(50, len(raw_df))):
        row_vals = [str(x).replace('\n', '').strip() for x in raw_df.iloc[i].values if pd.notna(x)]
        if any(k in row_vals for k in ["진행현황", "PO No.", "수주처"]):
            header_idx = i
            break

    df_raw = pd.read_excel(target_file, sheet_name=0, header=header_idx)
    new_cols = []
    for c in df_raw.columns:
        c_str = str(c).replace('\n', '').strip()
        if "진행현황" in c_str or "수주현황" in c_str:
            new_cols.append("수주현황")
        elif "내용" in c_str or "품명" in c_str:
            new_cols.append("내용")
        elif "매출 단가" in c_str or "매출단가" in c_str or "매출금액" in c_str:
            new_cols.append("매출금액")
        elif "매출년도" in c_str or "매출예정년도" in c_str:
            new_cols.append("매출년도")
        elif "매출월" in c_str or "매출예정월" in c_str:
            new_cols.append("매출월")
        elif "수주처" in c_str or "견적처" in c_str:
            new_cols.append("거래처")
        # 관리코드는 제외하고 순수 PO No.만 매핑
        elif "PO NO" in c_str.upper() or "PONO" in c_str.upper():
            new_cols.append("PO_견적_번호")
        else:
            new_cols.append(c_str)

    df = pd.DataFrame()
    for orig_c, mapped_c in zip(df_raw.columns, new_cols):
        if mapped_c not in df.columns:
            df[mapped_c] = df_raw[orig_c]
        else:
            df[mapped_c] = df[mapped_c].fillna(df_raw[orig_c])

    defaults = {
        "수주현황": "수주완료",
        "PO_견적_번호": "-",
        "거래처": "미기재",
        "프로젝트명": "-",
        "내용": "-",
        "매출년도": "미정",
        "매출월": "미정",
        "매출금액": 0
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val
        else:
            df[col] = df[col].fillna(default_val)

    invalid_keywords = ["", "nan", "None", "-", "미정"]
    df["매출년도"] = df["매출년도"].astype(str).str.strip()
    df["매출월"] = df["매출월"].astype(str).str.strip()
    df["거래처"] = df["거래처"].astype(str).str.strip()
    df["매출금액"] = pd.to_numeric(df["매출금액"], errors="coerce").fillna(0)

    df = df[
        df["매출년도"].notna() &
        df["매출월"].notna() &
        ~df["매출년도"].isin(invalid_keywords) &
        ~df["매출월"].isin(invalid_keywords) &
        (df["프로젝트명"] != "-")
    ].copy()

    df["구분"] = "수주"
    df["건수"] = 1
    df["_년도_정렬키"] = df["매출년도"].apply(extract_year_num)
    df["_월_정렬키"] = df["매출월"].apply(extract_month_num)
    df["프로젝트명_정제"] = df["프로젝트명"].apply(clean_project_name)

    # 같은 년/월/거래처/프로젝트명 단위로 그룹핑
    group_keys = ["_년도_정렬키", "_월_정렬키", "매출년도", "매출월", "구분", "거래처", "프로젝트명_정제"]
    df_grouped = df.groupby(group_keys, as_index=False, dropna=False).agg({
        "수주현황": get_first_valid,
        "PO_견적_번호": combine_unique_po,
        "프로젝트명": get_representative_project_name,
        "내용": combine_unique,
        "매출금액": "sum",
        "건수": lambda s: f"{len(s)}건"
    })

    return df_grouped

# ---------------------------------------------------------
# 📥 2. 견적대장 로더 (견적 NO.만 정확히 추출)
# ---------------------------------------------------------
def load_quote_ledger(folder_path="."):
    target_file = None
    for f in os.listdir(folder_path):
        if f.endswith(".xlsx") and not f.startswith("~$") and "견적대장" in f:
            target_file = os.path.join(folder_path, f)
            break

    if not target_file:
        return pd.DataFrame()

    raw_df = pd.read_excel(target_file, sheet_name=0, header=None)
    header_idx = 0
    for i in range(min(50, len(raw_df))):
        row_vals = [str(x).replace('\n', '').strip() for x in raw_df.iloc[i].values if pd.notna(x)]
        if any(k in row_vals for k in ["견적 NO.", "수주현황", "견적처"]):
            header_idx = i
            break

    df_raw = pd.read_excel(target_file, sheet_name=0, header=header_idx)
    new_cols = []
    for c in df_raw.columns:
        c_str = str(c).replace('\n', '').strip()
        if "수주현황" in c_str:
            new_cols.append("수주현황")
        elif "견적 NO" in c_str or "견적NO" in c_str or "견적번호" in c_str:
            new_cols.append("PO_견적_번호")
        elif "견적처" in c_str or "수주처" in c_str:
            new_cols.append("거래처")
        elif "내용" in c_str or "품명" in c_str or "품목" in c_str:
            new_cols.append("내용")
        elif "매출금액" in c_str or "매출 단가" in c_str or "매출단가" in c_str:
            new_cols.append("매출금액")
        elif "매출예정년도" in c_str or "매출년도" in c_str:
            new_cols.append("매출년도")
        elif "매출예정월" in c_str or "매출월" in c_str:
            new_cols.append("매출월")
        else:
            new_cols.append(c_str)

    df = pd.DataFrame()
    for orig_c, mapped_c in zip(df_raw.columns, new_cols):
        if mapped_c not in df.columns:
            df[mapped_c] = df_raw[orig_c]
        else:
            df[mapped_c] = df[mapped_c].fillna(df_raw[orig_c])

    defaults = {
        "수주현황": "견적발송",
        "PO_견적_번호": "-",
        "거래처": "미기재",
        "프로젝트명": "-",
        "내용": "-",
        "매출년도": "미정",
        "매출월": "미정",
        "매출금액": 0
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val
        else:
            df[col] = df[col].fillna(default_val)

    invalid_keywords = ["", "nan", "None", "-", "미정"]
    df["매출년도"] = df["매출년도"].astype(str).str.strip()
    df["매출월"] = df["매출월"].astype(str).str.strip()
    df["거래처"] = df["거래처"].astype(str).str.strip()
    df["매출금액"] = pd.to_numeric(df["매출금액"], errors="coerce").fillna(0)

    df = df[
        df["매출년도"].notna() &
        df["매출월"].notna() &
        ~df["매출년도"].isin(invalid_keywords) &
        ~df["매출월"].isin(invalid_keywords) &
        (df["프로젝트명"] != "-")
    ].copy()

    df["구분"] = "견적"
    df["건수"] = 1
    df["_년도_정렬키"] = df["매출년도"].apply(extract_year_num)
    df["_월_정렬키"] = df["매출월"].apply(extract_month_num)
    df["프로젝트명_정제"] = df["프로젝트명"].apply(clean_project_name)

    # 같은 년/월/거래처/프로젝트명 단위로 그룹핑
    group_keys = ["_년도_정렬키", "_월_정렬키", "매출년도", "매출월", "구분", "거래처", "프로젝트명_정제"]
    df_grouped = df.groupby(group_keys, as_index=False, dropna=False).agg({
        "수주현황": get_first_valid,
        "PO_견적_번호": combine_unique_po,
        "프로젝트명": get_representative_project_name,
        "내용": combine_unique,
        "매출금액": "sum",
        "건수": lambda s: f"{len(s)}건"
    })

    return df_grouped

# ---------------------------------------------------------
# 📥 3. 두 대장 통합 로더
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_combined_data():
    df_orders = load_order_ledger(".")
    df_quotes = load_quote_ledger(".")

    combined_df = pd.concat([df_orders, df_quotes], ignore_index=True)
    if combined_df.empty:
        raise FileNotFoundError("수주대장 또는 견적대장 엑셀 파일을 작업 폴더에서 찾을 수 없습니다.")

    # 표시에 사용할 컬럼명 변경 (관리번호 -> PO No. / 견적 No.)
    combined_df.rename(columns={"PO_견적_번호": "PO No. / 견적 No."}, inplace=True)
    combined_df["정렬용_번호"] = combined_df["PO No. / 견적 No."].apply(lambda x: "ZZZ" if x == "-" else str(x))

    combined_df = combined_df.sort_values(
        by=["_년도_정렬키", "_월_정렬키", "구분", "정렬용_번호", "매출금액"],
        ascending=[True, True, False, True, False]
    ).reset_index(drop=True)

    return combined_df


def main():
    st.markdown("""
        <style>
        @media print {
            [data-testid="stSidebar"], section[data-testid="stSidebar"], .stSidebar, header[data-testid="stHeader"], header, [data-testid="stToolbar"], footer, .stDeployButton, .no-print { display: none !important; }
            html, body, [data-testid="stAppViewContainer"], .main, .block-container { background-color: #ffffff !important; color: #000000 !important; width: 100% !important; max-width: 100% !important; padding: 10px !important; margin: 0 !important; }
            @page { size: A4 landscape; margin: 8mm; }
            .stPlotlyChart, .stDataFrame, [data-testid="stMetric"] { page-break-inside: avoid !important; break-inside: avoid !important; }
            * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    col_title, col_print_info = st.columns([3, 1])
    with col_title:
        st.title("📊 견적·수주 통합 경영 대시보드")
        st.caption("매출년도와 월을 기준으로 확정 수주와 견적 파이프라인을 단일 시계열로 통합 분석합니다.")
    with col_print_info:
        st.markdown(
            """<div class="no-print" style="text-align: right; padding-top: 18px; font-size: 0.85rem; color: #64748b;">
                🖨️ <b>프린트 (PDF 저장)</b>: <kbd>Ctrl</kbd> + <kbd>P</kbd>
            </div>""", unsafe_allow_html=True
        )
    st.markdown("---")

    try:
        df = load_combined_data()
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        st.info("작업 폴더 안에 '수주대장' 및 '견적대장' 엑셀(.xlsx) 파일이 있는지 확인해 주세요.")
        st.stop()

    # 🔍 사이드바 검색 및 필터
    st.sidebar.header("🔍 통합 대시보드 필터")

    type_options = ["전체"] + sorted(df["구분"].unique().tolist())
    selected_type = st.sidebar.selectbox("대장 구분 선택", options=type_options, index=0)

    status_options = sorted([str(x) for x in df["수주현황"].unique() if str(x).strip() and str(x) != "-"])
    selected_status = st.sidebar.multiselect("수주현황 선택", options=status_options, default=status_options)

    year_options = sorted(df["매출년도"].unique(), key=extract_year_num)
    selected_years = st.sidebar.multiselect("매출년도 선택", options=year_options, default=year_options)

    month_options = sorted(df["매출월"].unique(), key=extract_month_num)
    selected_months = st.sidebar.multiselect("매출월 선택", options=month_options, default=month_options)

    client_options = sorted([str(x) for x in df["거래처"].unique() if str(x).strip() and str(x) != "-"])
    selected_clients = st.sidebar.multiselect("거래처 선택", options=client_options, default=client_options)

    search_text = st.sidebar.text_input("프로젝트명 / PO No.·견적 No. / 거래처 / 내용 검색", "").strip()

    filtered_df = df.copy()
    if selected_type != "전체":
        filtered_df = filtered_df[filtered_df["구분"] == selected_type]
    if selected_status:
        filtered_df = filtered_df[filtered_df["수주현황"].isin(selected_status)]
    if selected_years:
        filtered_df = filtered_df[filtered_df["매출년도"].isin(selected_years)]
    if selected_months:
        filtered_df = filtered_df[filtered_df["매출월"].isin(selected_months)]
    if selected_clients:
        filtered_df = filtered_df[filtered_df["거래처"].isin(selected_clients)]
    if search_text:
        filtered_df = filtered_df[
            filtered_df["프로젝트명"].astype(str).str.contains(search_text, case=False, na=False) |
            filtered_df["PO No. / 견적 No."].astype(str).str.contains(search_text, case=False, na=False) |
            filtered_df["내용"].astype(str).str.contains(search_text, case=False, na=False) |
            filtered_df["거래처"].astype(str).str.contains(search_text, case=False, na=False)
        ]

    # 📌 1. 전체 KPI 카드
    total_sales = filtered_df["매출금액"].sum()
    order_sales = filtered_df[filtered_df["구분"] == "수주"]["매출금액"].sum()
    quote_sales = filtered_df[filtered_df["구분"] == "견적"]["매출금액"].sum()
    total_row_count = len(filtered_df)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("통합 총 매출규모", f"₩{total_sales:,.0f}", help=f"약 {total_sales / 1e8:.2f} 억원")
    with kpi2:
        st.metric("💼 수주 확정액", f"₩{order_sales:,.0f}", help=f"비중: {(order_sales/total_sales*100 if total_sales>0 else 0):.1f}%")
    with kpi3:
        st.metric("📋 견적 예상액", f"₩{quote_sales:,.0f}", help=f"비중: {(quote_sales/total_sales*100 if total_sales>0 else 0):.1f}%")
    with kpi4:
        st.metric("통합 집계 항목 수", f"{total_row_count:,} 건")

    if filtered_df.empty:
        st.warning("선택된 필터 조건에 해당하는 데이터가 없습니다.")
        return

    # 📌 2. 연도별 매출 합산 카드
    st.markdown("##### 📅 연도별 매출합산 금액")
    yearly_summary = filtered_df.groupby(
        ["_년도_정렬키", "매출년도"],
        as_index=False
    )["매출금액"].sum().sort_values("_년도_정렬키")

    if not yearly_summary.empty:
        year_cols = st.columns(len(yearly_summary))
        for idx, (_, yr) in enumerate(yearly_summary.iterrows()):
            y_name = yr["매출년도"]
            y_amt = yr["매출금액"]
            ratio = (y_amt / total_sales * 100) if total_sales > 0 else 0
            with year_cols[idx]:
                st.metric(
                    label=f"{y_name} 통합 실적",
                    value=f"₩{y_amt:,.0f}",
                    help=f"약 {y_amt / 1e8:.2f} 억원 (전체 대비 {ratio:.1f}%)"
                )

    st.markdown("<br>", unsafe_allow_html=True)

    # 📊 3. 월별 통합 매출 추이
    st.subheader("📈 월별 매출 추이 (수주 확정 vs 견적 파이프라인 누적)")

    monthly_summary = filtered_df.groupby(
        ["_년도_정렬키", "_월_정렬키", "매출년도", "매출월", "구분"],
        as_index=False
    )["매출금액"].sum().sort_values(by=["_년도_정렬키", "_월_정렬키"])

    monthly_summary["매출년월"] = monthly_summary.apply(
        lambda r: f"{r['매출년도']} {r['매출월']}".strip(),
        axis=1
    )

    all_yms = monthly_summary[["_년도_정렬키", "_월_정렬키", "매출년월"]].drop_duplicates().sort_values(["_년도_정렬키", "_월_정렬키"])["매출년월"].tolist()

    fig_monthly = go.Figure()
    order_monthly = monthly_summary[monthly_summary["구분"] == "수주"]
    quote_monthly = monthly_summary[monthly_summary["구분"] == "견적"]

    fig_monthly.add_trace(
        go.Bar(
            x=order_monthly["매출년월"],
            y=order_monthly["매출금액"],
            name="수주 (확정)",
            marker_color="#2563eb",
            hovertemplate="<b>%{x} 수주</b>: ₩%{y:,.0f}<extra></extra>"
        )
    )
    fig_monthly.add_trace(
        go.Bar(
            x=quote_monthly["매출년월"],
            y=quote_monthly["매출금액"],
            name="견적 (예상)",
            marker_color="#93c5fd",
            hovertemplate="<b>%{x} 견적</b>: ₩%{y:,.0f}<extra></extra>"
        )
    )
    fig_monthly.update_layout(
        barmode="stack",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=40),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(categoryorder="array", categoryarray=all_yms),
        yaxis=dict(title="금액 (원)", tickformat=",")
    )
    st.plotly_chart(fig_monthly, use_container_width=True)
    st.markdown("---")

    # 📋 4. 통합 테이블
    st.subheader("📋 월별 세부 통합 실적 (수주 및 견적)")
    st.caption("동일 월 내 거래처와 프로젝트명이 일치하는 건은 1행으로 합산되며 건수(N건)가 표시됩니다.")

    sorted_df = filtered_df.sort_values(
        by=["_년도_정렬키", "_월_정렬키", "구분", "정렬용_번호", "매출금액"],
        ascending=[True, True, False, True, False]
    )

    display_cols = [
        "구분", "수주현황", "PO No. / 견적 No.", "거래처", "프로젝트명", "건수", "내용", "매출년도", "매출월", "매출금액"
    ]

    table_rows = []
    for (y_key, y_disp), y_group in sorted_df.groupby(["_년도_정렬키", "매출년도"], sort=False):
        for (m_key, m_disp), group in y_group.groupby(["_월_정렬키", "매출월"], sort=False):
            label_ym = f"{y_disp} {m_disp}".strip()

            for _, r in group.iterrows():
                table_rows.append({
                    "구분": r.get("구분", "-"),
                    "수주현황": r.get("수주현황", "-"),
                    "PO No. / 견적 No.": r.get("PO No. / 견적 No.", "-"),
                    "거래처": r.get("거래처", "-"),
                    "프로젝트명": r.get("프로젝트명", "-"),
                    "건수": r.get("건수", "-"),
                    "내용": r.get("내용", "-"),
                    "매출년도": y_disp,
                    "매출월": m_disp,
                    "매출금액": r.get("매출금액", 0),
                    "_row_type": "data"
                })

            sub_sales = group["매출금액"].sum()
            table_rows.append({
                "구분": "소계",
                "수주현황": f"🔹 [{label_ym} 소계]",
                "PO No. / 견적 No.": "-",
                "거래처": "-",
                "프로젝트명": f"[{label_ym} 전체 합계 ({len(group)}건)]",
                "건수": "-",
                "내용": "-",
                "매출년도": y_disp,
                "매출월": m_disp,
                "매출금액": sub_sales,
                "_row_type": "month_subtotal"
            })

        year_sales = y_group["매출금액"].sum()
        table_rows.append({
            "구분": "연간합계",
            "수주현황": f"🔶 [{y_disp} 연간 합계]",
            "PO No. / 견적 No.": "-",
            "거래처": "-",
            "프로젝트명": f"[{y_disp} 총 합계 ({len(y_group)}건)]",
            "건수": "-",
            "내용": "-",
            "매출년도": y_disp,
            "매출월": "-",
            "매출금액": year_sales,
            "_row_type": "year_total"
        })

    table_rows.append({
        "구분": "총계",
        "수주현황": "🏆 [전체 총계]",
        "PO No. / 견적 No.": "-",
        "거래처": "-",
        "프로젝트명": f"[전체 총계 ({len(filtered_df)}건)]",
        "건수": "-",
        "내용": "-",
        "매출년도": "-",
        "매출월": "-",
        "매출금액": total_sales,
        "_row_type": "grand_total"
    })

    integrated_df = pd.DataFrame(table_rows)

    def highlight_rows(row):
        r_type = row.get("_row_type", "data")
        if r_type == "grand_total":
            return ["background-color: #cbd5e1; font-weight: bold; color: #000000;"] * len(row)
        elif r_type == "year_total":
            return ["background-color: #fed7aa; font-weight: bold; color: #7c2d12;"] * len(row)
        elif r_type == "month_subtotal":
            return ["background-color: #f1f5f9; font-weight: bold; color: #334155;"] * len(row)
        if row.get("구분") == "수주":
            return ["background-color: #f0fdf4; color: #166534;"] * len(row)
        return [""] * len(row)

    styled_table = (
        integrated_df[display_cols + ["_row_type"]]
        .style.apply(highlight_rows, axis=1)
        .format({"매출금액": "₩{:,.0f}"})
        .hide(subset=["_row_type"], axis="columns")
    )
    st.dataframe(styled_table, use_container_width=True, hide_index=True)

    col_csv, col_html = st.columns(2)
    with col_csv:
        csv_buffer = io.StringIO()
        integrated_df[display_cols].to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 통합 실적 데이터 다운로드 (CSV)",
            csv_buffer.getvalue(),
            "견적수주_통합실적데이터.csv",
            "text/csv",
            use_container_width=True
        )

    with col_html:
        printable_html = generate_printable_html(
            integrated_df=integrated_df,
            display_cols=display_cols,
            total_sales=total_sales,
            order_sales=order_sales,
            quote_sales=quote_sales,
            total_row_count=total_row_count,
            yearly_summary=yearly_summary
        )
        st.download_button(
            "🖨️ 인쇄용 전체 화면 다운로드 (HTML)",
            printable_html,
            "통합실적_인쇄용.html",
            "text/html",
            use_container_width=True
        )


if __name__ == "__main__":
    main()