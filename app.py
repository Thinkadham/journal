import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from streamlit_lightweight_charts import renderLightweightCharts

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stPlotlyChart { border: 1px solid #30363d; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data
def get_enhanced_data():
    data = {
        "Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-10", "2024-01-12"]),
        "Ticker": ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "META"],
        "Type": ["Long", "Short", "Long", "Long", "Short", "Long"],
        "Entry": [185.20, 245.50, 480.10, 145.00, 390.20, 340.00],
        "Exit": [190.50, 240.10, 495.00, 142.50, 395.00, 355.00],
        "Quantity": [100, 50, 20, 100, 30, 40],
        "Setup": ["Breakout", "Mean Reversion", "Gap Up", "Support Bounce", "Overextended", "Breakout"],
        "Mistake": ["None", "None", "None", "Early Exit", "FOMO", "None"]
    }
    df = pd.DataFrame(data)
    df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * np.where(df["Type"]=="Long", 1, -1)
    df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
    return df

df = get_enhanced_data()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("💎 AlphaZella Pro")
menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Analysis", "Deep Statistics"])

# --- 4. PAGE: DASHBOARD ---
if menu == "Dashboard":
    st.title("Performance Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    total_pl = df["P&L"].sum()
    win_rate = (len(df[df["Status"]=="Win"]) / len(df)) * 100
    
    col1.metric("Net P&L", f"${total_pl:,.2f}", delta=f"{total_pl:.2f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Profit Factor", "2.14")
    col4.metric("Total Trades", len(df))

    st.subheader("Equity Curve")
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    fig_curve = px.area(df_sorted, x="Date", y="Cum_PL", title="Account Growth",
                        color_discrete_sequence=['#00ffcc'], template="plotly_dark")
    st.plotly_chart(fig_curve, use_container_width=True)

# --- 5. PAGE: CALENDAR ---
elif menu == "Calendar":
    st.title("Trading Calendar")
    daily_pl = df.groupby("Date")["P&L"].sum().reset_index()
    calendar_events = []
    
    for _, row in daily_pl.iterrows():
        color = "#2ecc71" if row["P&L"] >= 0 else "#e74c3c"
        calendar_events.append({
            "title": f"${row['P&L']:.0f}",
            "start": row["Date"].strftime("%Y-%m-%d"),
            "backgroundColor": color,
        })

    cal_options = {"initialView": "dayGridMonth", "selectable": True}
    calendar(events=calendar_events, options=cal_options)

# --- 6. PAGE: TRADE ANALYSIS ---
elif menu == "Trade Analysis":
    st.title("Trade Replay")
    selected_ticker = st.selectbox("Select Trade", df["Ticker"].unique())
    trade = df[df["Ticker"] == selected_ticker].iloc[0]
    
    @st.cache_data
    def fetch_chart(symbol, date):
        h = yf.download(symbol, start=date-timedelta(days=10), end=date+timedelta(days=5), interval="1d")
        h = h.reset_index()
        h.columns = [c.lower() for c in h.columns]
        h = h.rename(columns={'date': 'time'})
        h['time'] = h['time'].dt.strftime('%Y-%m-%d')
        return h.to_dict('records')

    chart_data = fetch_chart(selected_ticker, trade["Date"])
    
    markers = [{
        "time": trade["Date"].strftime("%Y-%m-%d"),
        "position": "belowBar" if trade["Type"]=="Long" else "aboveBar
