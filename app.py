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

# Master Dataframe
all_trades = pd.concat([st.session_state.manual_df, uploaded_df], ignore_index=True)
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
            m_ticker = st.text_input("Ticker (e.g. BTC, AAPL)").upper()
        with col2:
            m_type = st.selectbox("Type", ["Long", "Short"])
            m_entry = st.number_input("Entry Price", min_value=0.0, step=0.01, format="%.2f")
        with col3:
            m_exit = st.number_input("Exit Price", min_value=0.0, step=0.01, format="%.2f")
            m_qty = st.number_input("Quantity", min_value=0.0001, step=0.0001, format="%.4f")
        
        m_setup = st.text_input("Setup Name")
        m_mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge", "Late Entry"])
        
        if st.form_submit_button("Add Trade"):
            mult = 1 if m_type == "Long" else -1
            pl = (m_exit - m_entry) * m_qty * mult
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(m_date), "Ticker": m_ticker, "Type": m_type,
                "Entry": m_entry, "Exit": m_exit, "Quantity": m_qty, 
                "Setup": m_setup, "Mistake": m_mistake, "P&L": pl, 
                "Status": "Win" if pl > 0 else "Loss"
            }])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new_row], ignore_index=True)
            st.rerun()

elif menu == "Trade Log":
    st.title("📜 Trade Log")
    if st.session_state.manual_df.empty and (uploaded_df is None or uploaded_df.empty):
        st.info("No trades to show.")
    else:
        # Displaying manual trades with a delete button
        st.subheader("Manual Entries")
        for i, row in st.session_state.manual_df.iterrows():
            cols = st.columns([1, 1, 1, 1, 1, 1])
            cols[0].write(row['Date'].date())
            cols[1].write(row['Ticker'])
            cols[2].write(f"${row['P&L']:.2f}")
            if cols[5].button("🗑️ Delete", key=f"del_{i}"):
                st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                st.rerun()
        
        st.subheader("All Data Preview")
        st.dataframe(all_trades, use_container_width=True)

elif menu == "Trade Analysis":
    st.title("📊 Technical Review")
    if all_trades.empty:
        st.warning("Add trades first.")
    else:
        ticker = st.selectbox("Ticker", all_trades["Ticker"].unique())
        interval = st.selectbox("Timeframe", ["1d", "1h", "15m"])
        trade = all_trades[all_trades["Ticker"] == ticker].iloc[-1]
        
        yf_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL"] else ticker
        h = yf.download(yf_ticker, start=trade['Date']-timedelta(days=20), end=trade['Date']+timedelta(days=5), interval=interval)
        
        if not h.empty:
            h = h.reset_index()
            d_col = 'Datetime' if 'Datetime' in h.columns else 'Date'
            fig = go.Figure(data=[go.Candlestick(x=h[d_col], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
            
            # --- RISK/REWARD LINE ---
            fig.add_shape(type="line", x0=trade['Date'], y0=trade['Entry'], x1=trade['Date'], y1=trade['Exit'],
                          line=dict(color="white", width=2, dash="dot"))
            
            fig.add_annotation(x=trade['Date'], y=trade['Entry'], text="BUY", showarrow=True, arrowhead=1, bgcolor="#00ffcc")
            fig.add_annotation(x=trade['Date'], y=trade['Exit'], text="SELL", showarrow=True, arrowhead=1, bgcolor="#ff4b4b")
            
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

elif menu == "Deep Statistics":
    st.title("📈 Strategy Analytics")
    if all_trades.empty:
        st.info("No data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("P&L by Setup")
            fig_setup = px.bar(all_trades.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", color="P&L", template="plotly_dark")
            st.plotly_chart(fig_setup, use_container_width=True)
        with c2:
            st.subheader("P&L by Ticker")
            fig_ticker = px.pie(all_trades, values=all_trades['P&L'].clip(lower=0), names='Ticker', template="plotly_dark")
            st.plotly_chart(fig_ticker, use_container_width=True)
