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

# --- 2. DATA PERSISTENCE & INITIALIZATION ---
# Using session_state ensures your manual entries don't vanish as you navigate
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "P&L", "Status"
    ])

# --- 3. DATA PROCESSING ---
@st.cache_data
def process_uploaded_file(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()
        df['Date'] = pd.to_datetime(df['Date'])
        if "P&L" not in df.columns:
            mult = np.where(df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
            df["P&L"] = (df["Exit"] - df["Entry"]) * df["Quantity"] * mult
        df["Status"] = np.where(df["P&L"] > 0, "Win", "Loss")
        return df
    return pd.DataFrame()

# --- 4. SIDEBAR ---
st.sidebar.title("💎 AlphaZella Pro")

# 4a. RISK CALCULATOR
with st.sidebar.expander("🧮 Position Size Calculator"):
    acc_size = st.number_input("Account Balance ($)", value=10000.0)
    risk_pct = st.number_input("Risk per Trade (%)", value=1.0)
    entry_p = st.number_input("Calc: Entry Price", value=0.0, step=0.01)
    stop_p = st.number_input("Calc: Stop Loss", value=0.0, step=0.01)
    
    if entry_p > 0 and stop_p > 0 and entry_p != stop_p:
        risk_amt = acc_size * (risk_pct / 100)
        risk_per_unit = abs(entry_p - stop_p)
        pos_size = risk_amt / risk_per_unit
        st.success(f"Size: {pos_size:.4f} units")

# 4b. DATA LOADING
file = st.sidebar.file_uploader("Upload CSV", type="csv")
uploaded_df = process_uploaded_file(file)

# Combine Manual + Uploaded into one Master DF
all_trades = pd.concat([st.session_state.manual_df, uploaded_df], ignore_index=True)

# Ensure Date is datetime objects for all logic
if not all_trades.empty:
    all_trades['Date'] = pd.to_datetime(all_trades['Date'])

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 5. PAGE LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Manual Trade Entry")
    with st.form("trade_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            m_date = st.date_input("Date", datetime.now())
            # Auto-populating Tickers based on existing data + manual input
            existing_tickers = all_trades["Ticker"].unique().tolist() if not all_trades.empty else []
            m_ticker = st.text_input("Ticker (e.g. BTC, AAPL)", help="Type new or existing ticker").upper()
        with col2:
            m_type = st.selectbox("Type", ["Long", "Short"])
            m_entry = st.number_input("Entry Price", min_value=0.0, step=0.01, format="%.2f")
        with col3:
            m_exit = st.number_input("Exit Price", min_value=0.0, step=0.01, format="%.2f")
            # FIX: Changed to float step to allow 0.1 BTC
            m_qty = st.number_input("Quantity", min_value=0.0001, step=0.0001, format="%.4f")
        
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
            st.success(f"Added {m_ticker} trade!")
            st.rerun()

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if all_trades.empty:
        st.info("No trades found. Add one in 'Manual Entry' or upload a CSV.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net P&L", f"${all_trades['P&L'].sum():,.2f}")
        win_rate = (len(all_trades[all_trades['P&L']>0])/len(all_trades)*100)
        c2.metric("Win Rate", f"{win_rate:.1f}%")
        c3.metric("Total Trades", len(all_trades))
        c4.metric("Avg Trade", f"${all_trades['P&L'].mean():.2f}")
        
        df_sorted = all_trades.sort_values("Date")
        df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
        st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", title="Equity Curve", template="plotly_dark"), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Calendar")
    if all_trades.empty:
        st.warning("Journal is empty.")
    else:
        daily_pl = all_trades.groupby(all_trades['Date'].dt.date)['P&L'].sum().reset_index()
        events = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), 
                   "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c", "allDay": True} 
                  for _, r in daily_pl.iterrows()]
        calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("Full Trade History")
    st.dataframe(all_trades.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)

elif menu == "Trade Analysis":
    if all_trades.empty:
        st.info("Log some trades first!")
    else:
        ticker = st.selectbox("Select Ticker to Analyze", all_trades["Ticker"].unique())
        # Visualizing the latest trade for that ticker
        trade = all_trades[all_trades["Ticker"] == ticker].iloc[-1]
        
        # Plotly Candlestick Logic... (Keeping your stable Plotly logic)
        yf_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL"] else ticker
        try:
            h = yf.download(yf_ticker, start=trade['Date']-timedelta(days=15), end=trade['Date']+timedelta(days=7))
            if not h.empty:
                if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
                h = h.reset_index()
                fig = go.Figure(data=[go.Candlestick(x=h['Date'], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
                fig.add_annotation(x=trade['Date'], y=trade['Entry'], text="ENTRY", showarrow=True, arrowhead=1, bgcolor="#2196F3")
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Chart error: {e}")
