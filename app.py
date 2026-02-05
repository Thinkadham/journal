import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from streamlit_lightweight_charts import renderLightweightCharts
import io

# --- 1. APP CONFIG & STYLE ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stPlotlyChart { border: 1px solid #30363d; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ROBUST DATA ENGINE ---
@st.cache_data
def process_data(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
    else:
        # Initial Demo Data
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

    # Standardize column headers
    df.columns = df.columns.str.strip()
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Auto-calculate P&L if missing
    if "P&L" not in df.columns:
        mult = np.where(df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
        df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * mult
    
    df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
    return df

# --- 3. SIDEBAR & EXPORT ---
st.sidebar.title("💎 AlphaZella Pro")
file = st.sidebar.file_uploader("Upload Trade CSV", type="csv")
df = process_data(file)

def to_excel(df_to_export):
    output = io.BytesIO()
    df_clean = df_to_export.copy()
    df_clean['Date'] = df_clean['Date'].dt.strftime('%Y-%m-%d')
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_clean.to_excel(writer, index=False, sheet_name='TradeLog')
        summary = df_to_export.groupby("Ticker")["P&L"].sum().reset_index()
        summary.to_excel(writer, index=False, sheet_name='TickerSummary')
    return output.getvalue()

st.sidebar.download_button(
    label="📥 Export to Excel",
    data=to_excel(df),
    file_name=f"Trading_Journal_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Dashboard":
    st.title("Performance Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
    win_rate = (len(df[df['P&L']>0])/len(df)*100) if len(df)>0 else 0
    c2.metric("Win Rate", f"{win_rate:.1f}%")
    c3.metric("Total Trades", len(df))
    c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
    
    st.subheader("Account Equity Curve")
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    fig = px.area(df_sorted, x="Date", y="Cum_PL", template="plotly_dark", color_discrete_sequence=['#00ffcc'])
    st.plotly_chart(fig, use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Tracker")
    daily_pl = df.groupby(df['Date'].dt.date)['P&L'].sum().reset_index()
    events = []
    for _, row in daily_pl.iterrows():
        color = "#2ecc71" if row['P&L'] >= 0 else "#e74c3c"
        events.append({
            "title": f"${row['P&L']:.0f}",
            "start": str(row['Date']),
            "backgroundColor": color,
            "borderColor": color,
            "allDay": True
        })
    calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("Full Trade History")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)

elif menu == "Trade Analysis":
    st.title("Technical Trade Review")
    ticker = st.selectbox("Select Ticker", df["Ticker"].unique())
    trade = df[df["Ticker"] == ticker].iloc[-1]
    
    # Ticker format fix for Crypto
    yf_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL"] else ticker
    
    try:
        start_date = trade['Date'] - timedelta(days=25)
        end_date = trade['Date'] + timedelta(days=10)
        h = yf.download(yf_ticker, start=start_date, end=end_date)
        
        if not h.empty:
            if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
            h = h.reset_index()
            h.columns = [str(c).lower() for c in h.columns]
            
            # Find closest date to trade for the marker (fixes weekend gaps)
            h['diff'] = (pd.to_datetime(h['time']) - trade['Date']).abs()
            marker_time = h.sort_values('diff').iloc[0]['time']
            
            chart_data = h.rename(columns={'date': 'time'}).to_dict('records')
            markers = [{"time": str(marker_time)[:10], "position": "belowBar", "color": "#2196F3", "shape": "arrowUp", "text": "ENTRY"}]
            
            renderLightweightCharts([{"type": 'Candlestick', "data": chart_data, "markers": markers}], 'chart', height=500)
            st.info(f"Entry on {trade['Date'].date()} | P&L: ${trade['P&L']:.2f} | Setup: {trade['Setup']}")
        else:
            st.warning("No price data found for this ticker/date range.")
    except Exception as e:
        st.error(f"Chart Load Error: {e}")

elif menu == "Deep Statistics":
    st.title("Advanced Strategy Analytics")
    cl, cr = st.columns(2)
    with cl:
        st.subheader("P&L by Strategy Setup")
        fig_setup = px.bar(df.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", color="P&L", template="plotly_dark")
        st.plotly_chart(fig_setup, use_container_width=True)
    with cr:
        st.subheader("Cost of Mistakes")
        mistakes = df[df["Mistake"] != "None"]
        if not mistakes.empty:
            fig_mistake = px.pie(mistakes, values=abs(mistakes['P&L']), names='Mistake', hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_mistake, use_container_width=True)
        else:
            st.success("No discipline errors logged yet!")
