import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go

@st.cache_data
def load_data():
    try:
        # ✅ 直接讀取 df（包含編號）
        df = pd.read_csv("date.csv", encoding="utf-8")
        df["交易日期"] = pd.to_datetime(df["交易日期"], errors='coerce').dt.date
        df["交易時段"] = df["交易時段"].astype(str).str.strip()
        df["到期月份(週別)"] = df["到期月份(週別)"].astype(str).str.strip()

        # ✅ datefollow 仍作為查詢基準（畫面跳號邏輯仍用它）
        datefollow_df = pd.read_csv("datefollow.csv", encoding="utf-8")
        datefollow_df["交易日期"] = pd.to_datetime(datefollow_df["交易日期"], errors='coerce').dt.date
        datefollow_df["交易時段"] = datefollow_df["交易時段"].astype(str).str.strip()

        # ✅ 載入 option_df
        option_df = pd.read_parquet("data.parquet")
        option_df["交易日期"] = pd.to_datetime(option_df["交易日期"], errors='coerce').dt.date
        option_df["履約價"] = pd.to_numeric(option_df["履約價"], errors='coerce')
        option_df["到期月份(週別)"] = option_df["到期月份(週別)"].astype(str).str.strip()
        option_df["交易時段"] = option_df["交易時段"].astype(str).str.strip()
        option_df["買賣權"] = option_df["買賣權"].astype(str).str.strip()

        return df, option_df, datefollow_df
    except Exception as e:
        st.error(f"🚨 載入資料失敗: {str(e)}")
        st.stop()
df, option_df, datefollow_df = load_data()
all_numbers = sorted(datefollow_df["編號"].unique())

if "curr_number" not in st.session_state:
    st.session_state.curr_number = all_numbers[0]
if "trades" not in st.session_state:
    st.session_state.trades = []

@st.cache_data
def get_option_data(date, expiry, at_price, session):
    if option_df.empty:
        return []
    expiry = str(expiry).strip()
    session = str(session).strip()
    at_price = int(at_price)
    strikes = [at_price + 50 * i for i in range(-11, 11)]
    result = []
    filtered_df = option_df[
        (option_df["交易日期"] == date) &
        (option_df["到期月份(週別)"] == expiry) &
        (option_df["交易時段"] == session)
    ]
    for strike in strikes:
        row = {"履約價": strike}
        for right in ["買權", "賣權"]:
            data = filtered_df[
                (filtered_df["履約價"] == strike) &
                (filtered_df["買賣權"] == right)
            ]
            if not data.empty and len(data["收盤價"].values) > 0:
                row[f"{right}_價"] = data["收盤價"].values[0]
                row[f"{right}_時段"] = data["交易時段"].values[0]
            else:
                row[f"{right}_價"] = "-"
                row[f"{right}_時段"] = "-"
        result.append(row)
    return result

def add_trade(action, right, strike, price, date, time):
    if price == "-":
        st.warning("無有效收盤價，無法添加交易")
        return
    trade = [date, time, action, right, strike, price, 1]
    st.session_state.trades.append(trade)

st.title("期權交易查詢")

col1, col2, col3 = st.columns([2, 1, 1])

# 根據編號取得當前資料
current_row = datefollow_df[datefollow_df["編號"] == st.session_state.curr_number]
if current_row.empty:
    st.error("找不到當前編號資料")
    st.stop()
current_row = current_row.iloc[0]
selected_date = current_row["交易日期"]
selected_session = current_row["交易時段"]

# 日期選擇器與交易時段切換
selected_date = col1.date_input("選擇日期", value=selected_date, min_value=datefollow_df["交易日期"].min(), max_value=datefollow_df["交易日期"].max())
session_filter = col1.radio("交易時段篩選", ["全部", "一般", "盤後"], horizontal=True)
if session_filter == "全部":
    sessions_today = datefollow_df[datefollow_df["交易日期"] == selected_date]
else:
    sessions_today = datefollow_df[
        (datefollow_df["交易日期"] == selected_date) &
        (datefollow_df["交易時段"] == session_filter)
    ]

sessions_available = sessions_today["交易時段"].unique().tolist()
def_idx = sessions_available.index(selected_session) if selected_session in sessions_available else 0
selected_session = col1.selectbox("選擇交易時段", sessions_available, index=def_idx)

# 自動切換至該交易時段最小編號
matched = sessions_today[sessions_today["交易時段"] == selected_session]
if not matched.empty:
    st.session_state.curr_number = matched["編號"].min()

# 上一筆 / 下一筆
if col2.button("← 上一筆"):
    idx = all_numbers.index(st.session_state.curr_number)
    if idx > 0:
        st.session_state.curr_number = all_numbers[idx - 1]
        st.rerun()
if col3.button("下一筆 →"):
    idx = all_numbers.index(st.session_state.curr_number)
    if idx < len(all_numbers) - 1:
        st.session_state.curr_number = all_numbers[idx + 1]
        st.rerun()

# 再次更新
current_row = datefollow_df[datefollow_df["編號"] == st.session_state.curr_number].iloc[0]
selected_date = current_row["交易日期"]
selected_session = current_row["交易時段"]

st.write(f"**編號**：{current_row['編號']}")
st.write(f"**交易日期**：{selected_date.strftime('%Y/%m/%d')}")
st.write(f"**交易時段**：{selected_session}")

# 精準抓取資料
available_expiries = df[
    (df["交易日期"] == selected_date) &
    (df["交易時段"] == selected_session)
]["到期月份(週別)"].dropna().astype(str).unique().tolist()
selected_expiry = st.selectbox("選擇到期月份(週別)", available_expiries)

filtered_row = df[
    (df["編號"] == st.session_state.curr_number) &
    (df["到期月份(週別)"] == selected_expiry)
]

if filtered_row.empty:
    st.write("⚠️ 查無對應的期權資料，請確認日期、時段與到期月份是否正確")
else:
    row = filtered_row.iloc[0]
    st.write(f"**收盤價**：{row['收盤價']}")
    day_str = str(int(row['剩餘天數'])) if not pd.isna(row['剩餘天數']) else ""
    st.write(f"**剩餘天數**：{day_str}")
    at_price = int(row['價平']) if not pd.isna(row['價平']) else 0
    st.write(f"**價平**：{at_price}")

    option_rows = get_option_data(selected_date, selected_expiry, at_price, selected_session)
    if option_rows:
        st.subheader("下單操作")

        # 外層橫向卷軸容器
        st.markdown("""
        <style>
        .scroll-wrapper {
            overflow-x: auto;
            white-space: nowrap;
            padding-bottom: 10px;
        }
        .option-row {
            display: inline-block;
            width: 1100px;
            padding: 8px 10px;
            border-bottom: 1px solid #ddd;
            transition: background-color 0.2s;
        }
        .option-row:nth-child(even) {
            background-color: #f9f9f9;
        }
        .option-row:hover {
            background-color: #eef6ff;
        }
        </style>
        <div class="scroll-wrapper">
        """, unsafe_allow_html=True)


        for i, row in enumerate(option_rows):
            st.markdown("<div class='option-row'>", unsafe_allow_html=True)
            cols = st.columns(7)
            with cols[0]:
                st.text(row["買權_價"])
            with cols[1]:
                if st.button("買", key=f"buy_call_{st.session_state.curr_number}_{i}"):
                    add_trade("買進", "買權", row["履約價"], row["買權_價"], selected_date.strftime("%Y/%m/%d"), row["買權_時段"])
            with cols[2]:
                if st.button("賣", key=f"sell_call_{st.session_state.curr_number}_{i}"):
                    add_trade("賣出", "買權", row["履約價"], row["買權_價"], selected_date.strftime("%Y/%m/%d"), row["買權_時段"])
            with cols[3]:
                if row["履約價"] == at_price:
                    st.markdown(f"<span style='font-weight: bold; font-size: 20px; color: #d62728;'>{row['履約價']}</span>", unsafe_allow_html=True)
                else:
                    st.text(row["履約價"])
            with cols[4]:
                if st.button("買", key=f"buy_put_{st.session_state.curr_number}_{i}"):
                    add_trade("買進", "賣權", row["履約價"], row["賣權_價"], selected_date.strftime("%Y/%m/%d"), row["賣權_時段"])
            with cols[5]:
                if st.button("賣", key=f"sell_put_{st.session_state.curr_number}_{i}"):
                    add_trade("賣出", "賣權", row["履約價"], row["賣權_價"], selected_date.strftime("%Y/%m/%d"), row["賣權_時段"])
            with cols[6]:
                st.text(row["賣權_價"])
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.write("無期權資料")


st.subheader("下單明細")
col1, col2 = st.columns(2)
if col1.button("清除全部"):
    st.session_state.trades = []
if col2.button("清除最後一筆") and st.session_state.trades:
    st.session_state.trades.pop()

if st.session_state.trades:
    trade_df = pd.DataFrame(
        st.session_state.trades,
        columns=["交易日期", "交易時段", "買/賣", "買權/賣權", "履約價", "最後成交價", "口數"]
    )
    st.table(trade_df)

    st.subheader("損益圖")
    settlement_prices = np.arange(at_price - 1000, at_price + 1001, 10)
    pnl = np.zeros_like(settlement_prices, dtype=float)

    for row in st.session_state.trades:
        _, _, action, right, strike, premium, qty = row
        strike = float(strike)
        premium = float(premium)
        qty = int(qty)
        if right == "買權":
            if action == "買進":
                pnl += qty * np.maximum(((settlement_prices - strike) - premium) * 50 - 100, -(premium * 50) - 100)
            else:
                pnl += qty * np.minimum((premium - (settlement_prices - strike)) * 50 - 100, (premium * 50) - 100)
        elif right == "賣權":
            if action == "買進":
                pnl += qty * np.maximum(((strike - settlement_prices) - premium) * 50 - 100, -(premium * 50) - 100)
            else:
                pnl += qty * np.minimum((premium - (strike - settlement_prices)) * 50 - 100, (premium * 50) - 100)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=settlement_prices,
        y=pnl,
        mode='lines',
        name='損益',
        hovertemplate='結算價：%{x}<br>損益：%{y} 元<extra></extra>',
        line=dict(color='royalblue')
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    fig.update_layout(
        title="損益圖（滑鼠懸停顯示點數）",
        xaxis_title="結算價",
        yaxis_title="損益",
        font=dict(family="Microsoft JhengHei", size=14),
        hoverlabel=dict(bgcolor="white", font_size=14),
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)
