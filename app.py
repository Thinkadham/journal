import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import io

# --- 1. APP CONFIG ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide")

# --- 2. DATA PERSISTENCE ---
# Initialize session state for manual entries if not already there
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "P&L", "Status"
    ])

# --- 3. DATA ENGINE ---
@st.cache_data
def process_data(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()
        df['Date'] = pd.to_datetime(df['Date'])
        if "P&L" not in df.columns:
            mult = np.where(df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
            df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * mult
        df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
        return df
    return None

# --- 4. SIDEBAR TOOLS ---
st.sidebar.title("💎 AlphaZella Pro")

# 4a. RISK CALCULATOR
with st.sidebar.expander("🧮 Position Size Calculator"):
    acc_size = st.number_input("Account Balance ($)", value=10000)
    risk_pct = st.number_input("Risk per Trade (%)", value=1.0)
    entry_p = st.number_input("Entry Price", value=0.0)
    stop_p = st.number_input("Stop Loss Price", value=0.0)
    
    if entry_p > 0 and stop_p > 0 and entry_p != stop_p:
        risk_amt = acc_size * (risk_pct / 100)
        risk_per_share = abs(entry_p - stop_p)
        pos_size = risk_amt / risk_per_share
        st.success(f"Suggested Size: {pos_size:.2f} units")
        st.caption(f"Total Risk: ${risk_amt:.2f}")

# 4b. DATA INPUT
file = st.sidebar.file_uploader("Upload CSV", type="csv")
uploaded_df = process_data(file)

# Combine Manual + Uploaded
if uploaded_df is not None:
    df = pd.concat([st.session_state.manual_df, uploaded_df], ignore_index=True)
else:
    df = st.session_state.manual_df

# Fallback to demo data if everything is empty
if df.empty:
    df = pd.DataFrame({
        "Date": [pd.Timestamp("2025-12-10")], "Ticker": ["META"], "Type": ["Long"],
        "Entry": [580.0], "Exit": [560.0], "Quantity": [15], "Setup": ["Breakout"],
        "Mistake": ["Revenge"], "P&L": [-300.0], "Status": ["Loss"]
    })

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 5. PAGE LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Manual Trade Entry")
    with st.form("trade_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            m_date = st.date_input("Date", datetime.now())
            m_ticker = st.text_input("Ticker (e.g. AAPL)").upper()
        with col2:
            m_type = st.selectbox("Type", ["Long", "Short"])
            m_entry = st.number_input("Entry Price", min_value=0.01)
        with col3:
            m_exit = st.number_input("Exit Price", min_value=0.01)
            m_qty = st.number_input("Quantity", min_value=1)
        
        m_setup = st.text_input("Setup Name")
        m_mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge", "Late Entry"])
        
        if st.form_submit_button("Add Trade to Journal"):
            mult = 1 if m_type == "Long" else -1
            pl = (m_exit - m_entry) * m_qty * mult
            new_trade = pd.DataFrame([{
                "Date": pd.to_datetime(m_date), "Ticker": m_ticker, "Type": m_type,
                "Entry": m_entry, "Exit": m_exit, "Quantity": m_qty, 
                "Setup": m_setup, "Mistake": m_mistake, "P&L": pl, 
                "Status": "Win" if pl > 0 else "Loss"
            }])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new_trade], ignore_index=True)
            st.rerun()

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    # ... (Same metric code as previous)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
    c2.metric("Win Rate", f"{(len(df[df['P&L']>0])/len(df)*100):.1f}%")
    c3.metric("Total Trades", len(df))
    c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
    
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", template="plotly_dark"), use_container_width=True)

elif menu == "Trade Analysis":
    st.title("Technical Trade Review")
    # Select from the actual data available
    ticker = st.selectbox("Select Ticker", df["Ticker"].unique())
    interval = st.selectbox("Timeframe", ["1d", "1h", "15m"])
    trade = df[df["Ticker"] == ticker].iloc[-1]
    
    yf_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL"] else ticker
    
    try:
        # Fetch logic (Daily/Intraday)
        h = yf.download(yf_ticker, start=trade['Date']-timedelta(days=30), end=trade['Date']+timedelta(days=7), interval=interval)
        if not h.empty:
            if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
            h = h.reset_index()
            date_col = 'Datetime' if 'Datetime' in h.columns else 'Date'
            
            fig = go.Figure(data=[go.Candlestick(x=h[date_col], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
            
            # Risk/Reward Line
            fig.add_shape(type="line", x0=trade['Date'], y0=trade['Entry'], x1=trade['Date'], y1=trade['Exit'], line=dict(color="white", dash="dot"))
            
            # BUY/SELL Markers
            fig.add_annotation(x=trade['Date'], y=trade['Entry'], text=f"BUY @ {trade['Entry']}", showarrow=True, arrowhead=2, arrowcolor="#00ffcc", bgcolor="#00ffcc", font=dict(color="black"), ax=40)
            fig.add_annotation(x=trade['Date'], y=trade['Exit'], text=f"SELL @ {trade['Exit']}", showarrow=True, arrowhead=2, arrowcolor="#ff4b4b", bgcolor="#ff4b4b", font=dict(color="white"), ax=40)
            
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

# ... (Keep Calendar, Trade Log, and Deep Statistics blocks same as before)
