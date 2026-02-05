import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from streamlit_lightweight_charts import renderLightweightCharts
import io

# --- 1. SETTINGS ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide")

# --- 2. DATA PROCESSING ---
@st.cache_data
def process_data(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
    else:
        # Default Mock Data
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

    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'])
    
    if "P&L" not in df.columns:
        mult = np.where(df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
        df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * mult
    
    df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
    return df

# --- 3. SIDEBAR & EXPORT LOGIC ---
st.sidebar.title("💎 AlphaZella Pro")
file = st.sidebar.file_uploader("Upload CSV", type="csv")
df = process_data(file)

# Export Function
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_sheet = df.to_excel(writer, index=False, sheet_name='Trade_Log')
        # Summary Sheet
        summary = df.groupby("Ticker")["P&L"].sum().reset_index()
        summary.to_excel(writer, index=False, sheet_name='Summary_By_Ticker')
    return output.getvalue()

st.sidebar.download_button(
    label="📥 Download Excel Report",
    data=to_excel(df),
    file_name=f"Trading_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

menu = st.sidebar.radio("Navigate", ["Dashboard", "Calendar", "Trade Log", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION PAGES ---

if menu == "Dashboard":
    st.title("Performance Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
    win_rate = (len(df[df['P&L']>0])/len(df)*100)
    c2.metric("Win Rate", f"{win_rate:.1f}%")
    c3.metric("Total Trades", len(df))
    c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
    
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", title="Equity Curve", template="plotly_dark"), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Calendar")
    daily_pl = df.groupby(df['Date'].dt.date)['P&L'].sum().reset_index()
    events = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), 
               "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c", "allDay": True} 
              for _, r in daily_pl.iterrows()]
    calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("Full Trade History")
    st.write("You can click column headers to sort your trades.")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)

elif menu == "Trade Analysis":
    st.title("Interactive Trade Review")
    ticker = st.selectbox("Select Ticker", df["Ticker"].unique())
    trade = df[df["Ticker"] == ticker].iloc[-1]
    
    try:
        h = yf.download(ticker, start=trade['Date']-timedelta(days=20), end=trade['Date']+timedelta(days=10))
        if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
        h = h.reset_index()
        h.columns = [str(c).lower() for c in h.columns]
        chart_data = h.rename(columns={'date': 'time'}).to_dict('records')
        
        # Fixed markers to show exact entry point
        markers = [{"time": trade['Date'].strftime('%Y-%m-%d'), "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "ENTRY"}]
        
        renderLightweightCharts([{"type": 'Candlestick', "data": chart_data, "markers": markers}], 'chart', height=500)
        st.info(f"Analyzing {ticker}: Trade on {trade['Date'].date()} resulted in ${trade['P&L']:.2f}")
    except:
        st.warning("Chart data unavailable for this ticker or date range.")

elif menu == "Deep Statistics":
    st.title("Strategy & Error Analytics")
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("P&L by Strategy")
        st.plotly_chart(px.bar(df.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", color="P&L", template="plotly_dark"), use_container_width=True)
        
    with col_r:
        st.subheader("Financial Impact of Mistakes")
        mistakes = df[df["Mistake"] != "None"]
        if not mistakes.empty:
            st.plotly_chart(px.pie(mistakes, values=abs(mistakes['P&L']), names='Mistake', hole=0.4, template="plotly_dark"), use_container_width=True)
        else:
            st.success("No discipline errors logged!")
