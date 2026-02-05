import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from streamlit_lightweight_charts import renderLightweightCharts

# --- APP CONFIG ---
st.set_page_config(page_title="AlphaZella | Trading Journal", layout="wide", initial_sidebar_state="expanded")

# --- STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="metric-container"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- MOCK DATA GENERATOR ---
@st.cache_data
def get_trade_data():
    data = {
        "Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-10"]),
        "Ticker": ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"],
        "Type": ["Long", "Short", "Long", "Long", "Short"],
        "Entry": [185.20, 245.50, 480.10, 145.00, 390.20],
        "Exit": [190.50, 240.10, 495.00, 142.50, 395.00],
        "Quantity": [100, 50, 20, 100, 30],
        "Setup": ["Breakout", "Mean Reversion", "Gap Up", "Support Bounce", "Overextended"],
    }
    df = pd.DataFrame(data)
    df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * np.where(df["Type"]=="Long", 1, -1)
    df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
    return df

df = get_trade_data()

# --- SIDEBAR ---
st.sidebar.title("💎 AlphaZella")
menu = st.sidebar.radio("Menu", ["Dashboard", "Calendar", "Analysis"])

# --- PAGE 1: DASHBOARD ---
if menu == "Dashboard":
    st.title("Performance Dashboard")
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    total_pl = df["P&L"].sum()
    win_rate = (len(df[df["Status"]=="Win"]) / len(df)) * 100
    
    c1.metric("Net P&L", f"${total_pl:,.2f}", delta=f"{total_pl:.2f}")
    c2.metric("Win Rate", f"{win_rate:.1f}%")
    c3.metric("Avg Win", f"${df[df['P&L']>0]['P&L'].mean():.2f}")
    c4.metric("Profit Factor", "2.1")

    # Equity Curve
    st.subheader("Equity Growth")
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    st.line_chart(df_sorted.set_index("Date")["Cum_PL"])

# --- PAGE 2: CALENDAR ---
elif menu == "Calendar":
    st.title("Trading Calendar")
    
    # Format data for the calendar component
    daily_pl = df.groupby("Date")["P&L"].sum().reset_index()
    calendar_events = []
    
    for _, row in daily_pl.iterrows():
        color = "#2ecc71" if row["P&L"] >= 0 else "#e74c3c"
        calendar_events.append({
            "title": f"${row['P&L']:.0f}",
            "start": row["Date"].strftime("%Y-%m-%d"),
            "end": row["Date"].strftime("%Y-%m-%d"),
            "backgroundColor": color,
            "borderColor": color
        })

    cal_options = {
        "initialView": "dayGridMonth",
        "headerToolbar": {"left": "prev,next", "center": "title", "right": ""},
    }
    calendar(events=calendar_events, options=cal_options)

# --- PAGE 3: ANALYSIS (Interactive Charts) ---
elif menu == "Analysis":
    st.title("Trade Replay")
    
    selected_ticker = st.selectbox("Select a Trade to Review", df["Ticker"].unique())
    trade_info = df[df["Ticker"] == selected_ticker].iloc[0]
    
    # Fetch Real Market Data from Yahoo Finance
    @st.cache_data
    def fetch_history(symbol, date):
        end_date = date + timedelta(days=5)
        start_date = date - timedelta(days=10)
        hist = yf.download(symbol, start=start_date, end=end_date, interval="1d")
        hist = hist.reset_index()
        hist.columns = [c.lower() for c in hist.columns]
        # Lightweight charts expects 'time' column
        hist = hist.rename(columns={'date': 'time'})
        hist['time'] = hist['time'].dt.strftime('%Y-%m-%d')
        return hist.to_dict('records')

    try:
        chart_data = fetch_history(selected_ticker, trade_info["Date"])
        
        # Markers for Buy/Sell
        markers = [
            {
                "time": trade_info["Date"].strftime("%Y-%m-%d"),
                "position": "belowBar" if trade_info["Type"] == "Long" else "aboveBar",
