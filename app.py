import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="퍼시스 베트남 물류비 대시보드", layout="wide")

DEFAULT_DATA_FILE = "logistics_data_final.csv"

st.markdown("""
<style>
.block-container {padding-top: 1.1rem; padding-bottom: 1.1rem;}
.metric-card {
    background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 16px 18px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}
.small-note {
    font-size: 0.9rem;
    color: #475569;
}
</style>
""", unsafe_allow_html=True)

st.title("퍼시스 베트남 물류비 대시보드")
st.caption("1월 + 2월 검증 완료 데이터 / 하나은행 VND 100동 기준 평균환율 적용 / 호치민 경유 최신가 자동 조회")

def load_default_data():
    path = Path(DEFAULT_DATA_FILE)
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame(columns=[
        "Month", "Type", "Shipping Class", "Vendor",
        "Cost Center", "Amount_VND", "Rate_Avg"
    ])

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "월": "Month",
        "구분": "Type",
        "운송구분": "Shipping Class",
        "업체": "Vendor",
        "금액(VND)": "Amount_VND",
        "평균 환율": "Rate_Avg",
        "금액(KRW)": "Amount_KRW",
    }
    df = df.rename(columns=rename_map)
    required = ["Month", "Type", "Shipping Class", "Vendor", "Cost Center", "Amount_VND", "Rate_Avg"]
    for col in required:
        if col not in df.columns:
            df[col] = "일반" if col == "Shipping Class" else ""
    return df

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = normalize_columns(df).copy()
    for col in ["Month", "Type", "Shipping Class", "Vendor", "Cost Center"]:
        df[col] = df[col].astype(str)
    for col in ["Amount_VND", "Rate_Avg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["Amount_KRW"] = (df["Amount_VND"] / 100.0) * df["Rate_Avg"]
    return df

@st.cache_data(ttl=3600)
def fetch_hcm_diesel_live():
    sources = [
        "https://giaxanghomnay.com/tinh-tp/ho-chi-minh",
        "https://www.pvoil.com.vn/tin-gia-xang-dau",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []

    try:
        r = requests.get(sources[0], headers=headers, timeout=15)
        r.raise_for_status()
        text = r.text
        m = re.search(r"DO\s*0[,\.]?05S-II[^\d]{0,40}([\d\.,]+)đ/lít", text, flags=re.IGNORECASE)
        d = re.search(r"Hồ Chí Minh hôm nay ngày\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text, flags=re.IGNORECASE)
        if m:
            price = int(re.sub(r"[^\d]", "", m.group(1)))
            results.append({
                "source": "giaxanghomnay.com",
                "price": price,
                "date": d.group(1) if d else "",
                "url": sources[0],
            })
    except Exception:
        pass

    try:
        r = requests.get(sources[1], headers=headers, timeout=15)
        r.raise_for_status()
        text = r.text
        m = re.search(r"DO\s*0[,\.]?05S-II\s*([\d\.,]+)\s*đ", text, flags=re.IGNORECASE)
        d = re.search(r"22:00 ngày\s*(\d{2}/\d{2}/\d{4})", text, flags=re.IGNORECASE)
        if m:
            price = int(re.sub(r"[^\d]", "", m.group(1)))
            results.append({
                "source": "PVOIL",
                "price": price,
                "date": d.group(1) if d else "",
                "url": sources[1],
            })
    except Exception:
        pass

    if not results:
        return None
    for item in results:
        if item["source"] == "giaxanghomnay.com":
            return item
    return results[0]

df = prepare_data(load_default_data())

st.sidebar.header("데이터 입력")
uploaded_file = st.sidebar.file_uploader("물류 엑셀 또는 CSV 업로드", type=["xlsx", "csv"])
if uploaded_file is not None:
    raw_df = pd.read_excel(uploaded_file) if uploaded_file.name.lower().endswith(".xlsx") else pd.read_csv(uploaded_file, encoding="utf-8-sig")
    df = prepare_data(raw_df)
    st.sidebar.success("업로드 물류 데이터를 사용 중입니다.")
else:
    st.sidebar.info("기본 물류 데이터(logistics_data_final.csv)를 사용 중입니다.")

st.sidebar.header("전체 필터")
month_options = ["전체"] + sorted(df["Month"].dropna().unique().tolist()) if not df.empty else ["전체"]
selected_month = st.sidebar.selectbox("월", month_options)
type_options = ["전체"] + sorted(df["Type"].dropna().unique().tolist()) if not df.empty else ["전체"]
selected_type = st.sidebar.selectbox("구분", type_options)
shipping_options = ["전체"] + sorted(df["Shipping Class"].dropna().unique().tolist()) if not df.empty else ["전체"]
selected_shipping = st.sidebar.selectbox("운송구분", shipping_options)
vendor_options = ["전체"] + sorted(df["Vendor"].dropna().unique().tolist()) if not df.empty else ["전체"]
selected_vendor = st.sidebar.selectbox("업체", vendor_options)
cc_options = ["전체"] + sorted(df["Cost Center"].dropna().unique().tolist()) if not df.empty else ["전체"]
selected_cc = st.sidebar.selectbox("Cost Center", cc_options)

view_df = df.copy()
if not view_df.empty:
    if selected_month != "전체":
        view_df = view_df[view_df["Month"] == selected_month]
    if selected_type != "전체":
        view_df = view_df[view_df["Type"] == selected_type]
    if selected_shipping != "전체":
        view_df = view_df[view_df["Shipping Class"] == selected_shipping]
    if selected_vendor != "전체":
        view_df = view_df[view_df["Vendor"] == selected_vendor]
    if selected_cc != "전체":
        view_df = view_df[view_df["Cost Center"] == selected_cc]

if view_df.empty:
    st.warning("표시할 데이터가 없습니다.")
else:
    months_sorted = sorted(df["Month"].dropna().unique().tolist())
    latest_month = months_sorted[-1] if months_sorted else ""
    current_month = selected_month if selected_month != "전체" else latest_month

    current_month_df = df[df["Month"] == current_month] if current_month else pd.DataFrame()
    cumulative_df = df[df["Month"] <= current_month] if current_month else df.copy()

    month_vnd = current_month_df["Amount_VND"].sum()
    month_krw = current_month_df["Amount_KRW"].sum()
    cumulative_vnd = cumulative_df["Amount_VND"].sum()
    cumulative_krw = cumulative_df["Amount_KRW"].sum()

    previous_month = ""
    mom_pct = None
    if current_month and current_month in months_sorted:
        idx = months_sorted.index(current_month)
        if idx > 0:
            previous_month = months_sorted[idx - 1]
            prev_df = df[df["Month"] == previous_month]
            prev_krw = prev_df["Amount_KRW"].sum()
            if prev_krw != 0:
                mom_pct = ((month_krw - prev_krw) / prev_krw) * 100.0

    diesel_live = fetch_hcm_diesel_live()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(f"{current_month} 월별 물류비", f"{month_krw:,.0f} KRW")
        st.caption(f"{month_vnd:,.0f} VND")
        st.markdown('</div>', unsafe_allow_html=True)
    with k2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(f"{current_month} 누계", f"{cumulative_krw:,.0f} KRW")
        st.caption(f"{cumulative_vnd:,.0f} VND")
        st.markdown('</div>', unsafe_allow_html=True)
    with k3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        if mom_pct is None:
            st.metric("전월 대비 증감률", "-")
            st.caption("비교 월 없음")
        else:
            st.metric("전월 대비 증감률", f"{mom_pct:,.1f}%")
            st.caption(f"{previous_month} 대비")
        st.markdown('</div>', unsafe_allow_html=True)
    with k4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        if diesel_live:
            st.metric("호치민 경유 최신가", f'{diesel_live["price"]:,.0f} VND/L')
            st.caption(f'{diesel_live["date"]} / {diesel_live["source"]}')
        else:
            st.metric("호치민 경유 최신가", "-")
            st.caption("조회 실패")
        st.markdown('</div>', unsafe_allow_html=True)

    left, right = st.columns([2, 1])
    with left:
        month_sum = df.groupby("Month", as_index=False)["Amount_KRW"].sum().sort_values("Month")
        fig_month = px.bar(month_sum, x="Month", y="Amount_KRW", text="Amount_KRW", title="월별 물류비")
        fig_month.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_month.update_yaxes(tickformat=",")
        fig_month.update_xaxes(type="category")
        st.plotly_chart(fig_month, use_container_width=True)
    with right:
        st.subheader("경유 가격 참고")
        if diesel_live:
            diesel_ref = pd.DataFrame([{
                "기준일": diesel_live["date"],
                "경유가(VND/L)": f'{diesel_live["price"]:,.0f}',
                "출처": diesel_live["source"],
                "참고": diesel_live["url"],
            }])
            st.dataframe(diesel_ref, use_container_width=True, hide_index=True)
        else:
            st.info("실시간 경유가 조회 실패")

    row1_left, row1_right = st.columns(2)
    with row1_left:
        cc_sum = view_df.groupby("Cost Center", as_index=False)["Amount_KRW"].sum().sort_values("Amount_KRW", ascending=False)
        fig_cc = px.bar(cc_sum, x="Cost Center", y="Amount_KRW", text="Amount_KRW", title="Cost Center별 물류비")
        fig_cc.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_cc.update_yaxes(tickformat=",")
        st.plotly_chart(fig_cc, use_container_width=True)
    with row1_right:
        vendor_sum = view_df.groupby("Vendor", as_index=False)["Amount_KRW"].sum().sort_values("Amount_KRW", ascending=False)
        fig_vendor = px.bar(vendor_sum, x="Vendor", y="Amount_KRW", text="Amount_KRW", title="업체별 물류비")
        fig_vendor.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_vendor.update_yaxes(tickformat=",")
        st.plotly_chart(fig_vendor, use_container_width=True)

    row2_left, row2_right = st.columns(2)
    with row2_left:
        type_sum = view_df.groupby("Type", as_index=False)["Amount_KRW"].sum()
        fig_type = px.pie(type_sum, names="Type", values="Amount_KRW", title="구분별 비중")
        fig_type.update_traces(texttemplate="%{label}<br>%{value:,.0f}")
        st.plotly_chart(fig_type, use_container_width=True)
    with row2_right:
        shipping_sum = view_df.groupby("Shipping Class", as_index=False)["Amount_KRW"].sum().sort_values("Amount_KRW", ascending=False)
        fig_shipping = px.bar(shipping_sum, x="Shipping Class", y="Amount_KRW", text="Amount_KRW", title="운송구분별 물류비")
        fig_shipping.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_shipping.update_yaxes(tickformat=",")
        st.plotly_chart(fig_shipping, use_container_width=True)

    st.subheader("상세 데이터 표 필터")
    t1, t2, t3 = st.columns(3)
    with t1:
        table_vendor = st.selectbox("표 전용 업체 필터", ["전체"] + sorted(view_df["Vendor"].dropna().unique().tolist()))
    with t2:
        table_cc = st.selectbox("표 전용 Cost Center 필터", ["전체"] + sorted(view_df["Cost Center"].dropna().unique().tolist()))
    with t3:
        sort_by = st.selectbox("표 정렬", ["월 오름차순", "금액(VND) 큰 순", "금액(KRW) 큰 순"])

    table_df = view_df.copy()
    if table_vendor != "전체":
        table_df = table_df[table_df["Vendor"] == table_vendor]
    if table_cc != "전체":
        table_df = table_df[table_df["Cost Center"] == table_cc]
    if sort_by == "금액(VND) 큰 순":
        table_df = table_df.sort_values(["Month", "Type", "Shipping Class", "Vendor", "Cost Center", "Amount_VND"], ascending=[True, True, True, True, True, False])
    elif sort_by == "금액(KRW) 큰 순":
        table_df = table_df.sort_values(["Month", "Type", "Shipping Class", "Vendor", "Cost Center", "Amount_KRW"], ascending=[True, True, True, True, True, False])
    else:
        table_df = table_df.sort_values(["Month", "Type", "Shipping Class", "Vendor", "Cost Center"], ascending=True)

    st.subheader("상세 데이터")
    show_df = table_df[["Month", "Type", "Shipping Class", "Vendor", "Cost Center", "Amount_VND", "Rate_Avg", "Amount_KRW"]].copy()
    show_df = show_df.rename(columns={
        "Month": "월",
        "Type": "구분",
        "Shipping Class": "운송구분",
        "Vendor": "업체",
        "Amount_VND": "금액(VND)",
        "Rate_Avg": "평균 환율",
        "Amount_KRW": "금액(KRW)"
    })
    st.dataframe(
        show_df.style.format({
            "금액(VND)": "{:,.0f}",
            "평균 환율": "{:,.2f}",
            "금액(KRW)": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Cost Center 합계")
    summary_df = view_df.groupby(["Month", "Cost Center"], as_index=False)[["Amount_VND", "Amount_KRW"]].sum()
    summary_df = summary_df.sort_values(["Month", "Cost Center"], ascending=True)
    summary_df = summary_df.rename(columns={
        "Month": "월",
        "Amount_VND": "금액(VND)",
        "Amount_KRW": "금액(KRW)"
    })
    st.dataframe(
        summary_df.style.format({
            "금액(VND)": "{:,.0f}",
            "금액(KRW)": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True
    )

    csv_bytes = table_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="현재 표 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="logistics_dashboard_filtered.csv",
        mime="text/csv",
    )
