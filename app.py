import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from streamlit_lightweight_charts import renderLightweightCharts

# --- 1. SETTINGS ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide")

# --- 2. ROBUST DATA PROCESSING ---
@st.cache_data
def process_data(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
    else:
        # Mock Data as fallback
        data = {
            "Date": ["2025-11-03", "2025-11-07", "2025-11-12", "2025-12-10", "2026-01-05"],
            "Ticker": ["AAPL", "TSLA", "NVDA", "META", "BTC"],
            "Type": ["Long", "Short", "Long", "Long", "Long"],
            "Entry": [220.5, 250.0, 140.0, 580.0, 95000.0],
            "Exit": [235.0, 255.0, 155.0, 560.0, 99000.0],
            "Quantity": [50, 20, 100, 15, 1],
            "Setup": ["Breakout", "Overextended", "Gap Up", "Breakout", "Momentum"],
            "Mistake": ["None", "FOMO", "None", "Revenge", "None"]
        }
        df = pd.DataFrame(data)

    # Standardize columns and formats
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Calculate P&L if missing
    if "P&L" not in df.columns:
        mult = np.where(df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
        df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * mult
    
    df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
    return df

# --- 3. SIDEBAR ---
st.sidebar.title("💎 AlphaZella Pro")
file = st.sidebar.file_uploader("Upload CSV", type="csv")
df = process_data(file)
menu = st.sidebar.radio("Navigate", ["Dashboard", "Calendar", "Trade Log", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Dashboard":
    st.title("Performance Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
    c2.metric("Win Rate", f"{(len(df[df['P&L']>0])/len(df)*100):.1f}%")
    c3.metric("Total Trades", len(df))
    c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
    
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", template="plotly_dark"), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Calendar")
    # Calendar expects specific keys: 'title', 'start', 'allDay'
    daily_pl = df.groupby(df['Date'].dt.date)['P&L'].sum().reset_index()
    events = []
    for _, row in daily_pl.iterrows():
        events.append({
            "title": f"{'$' if row['P&L'] >= 0 else '-$'}{abs(row['P&L']):.0f}",
            "start": str(row['Date']),
            "backgroundColor": "#2ecc71" if row['P&L'] >= 0 else "#e74c3c",
            "borderColor": "#2ecc71" if row['P&L'] >= 0 else "#e74c3c",
            "allDay": True
        })
    calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("All Trades")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)

elif menu == "Trade Analysis":
    st.title("Interactive Trade Review")
    ticker = st.selectbox("Select Ticker", df["Ticker"].unique())
    trade = df[df["Ticker"] == ticker].iloc[-1]
    
    try:
        # Get chart data
        h = yf.download(ticker, start=trade['Date']-timedelta(days=20), end=trade['Date']+timedelta(days=10))
        if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
        h = h.reset_index()
        h.columns = [str(c).lower() for c in h.columns]
        chart_data = h.rename(columns={'date': 'time'}).to_dict('records')
        
        # Fixed component call
        renderLightweightCharts([{"type": 'Candlestick', "data": chart_data}], 'chart', height=400)
        st.success(f"Trade Detail: {trade['Type']} {ticker} for ${trade['P&L']:.2f}")
    except:
        st.warning("Could not load market data for this ticker.")

elif menu == "Deep Statistics":
    st.title("Strategy Analytics")
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("Performance by Setup")
        fig = px.bar(df.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", color="P&L", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
    with col_r:
        st.subheader("Mistake Costs")
        mistakes = df[df["Mistake"] != "None"]
        if not mistakes.empty:
            st.plotly_chart(px.pie(mistakes, values=abs(mistakes['P&L']), names='Mistake', template="plotly_dark"), use_container_width=True)
        else:
            st.info("No mistakes logged yet!")
