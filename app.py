import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import io

# --- 1. APP CONFIG & SESSION INITIALIZATION ---
st.set_page_config(page_title="AlphaZella Pro", layout="wide")

# Ensure the database exists even if no file is uploaded
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "P&L", "Status"
    ])

# --- 2. DATA ENGINE ---
def get_master_data(uploaded_file):
    """Combines uploaded CSV data with manual session entries."""
    manual_data = st.session_state.manual_df.copy()
    
    if uploaded_file:
        uploaded_df = pd.read_csv(uploaded_file)
        uploaded_df.columns = uploaded_df.columns.str.strip()
        uploaded_df['Date'] = pd.to_datetime(uploaded_df['Date'])
        # Auto-calculate P&L for uploads if missing
        if "P&L" not in uploaded_df.columns:
            mult = np.where(uploaded_df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
            uploaded_df["P&L"] = (uploaded_df["Exit"] - uploaded_df["Entry"]) * uploaded_df["Quantity"] * mult
        uploaded_df["Status"] = np.where(uploaded_df["P&L"] > 0, "Win", "Loss")
        
        return pd.concat([manual_data, uploaded_df], ignore_index=True)
    
    return manual_data

# --- 3. SIDEBAR ---
st.sidebar.title("💎 AlphaZella Pro")

with st.sidebar.expander("🧮 Position Size Calculator"):
    acc_size = st.number_input("Account Balance ($)", value=10000.0)
    risk_pct = st.number_input("Risk per Trade (%)", value=1.0)
    entry_p = st.number_input("Calc: Entry Price", value=0.0, step=0.01)
    stop_p = st.number_input("Calc: Stop Loss", value=0.0, step=0.01)
    if entry_p > 0 and stop_p > 0 and entry_p != stop_p:
        pos_size = (acc_size * (risk_pct / 100)) / abs(entry_p - stop_p)
        st.success(f"Size: {pos_size:.4f} units")

file = st.sidebar.file_uploader("Upload CSV", type="csv")
all_trades = get_master_data(file)

# Ensure Date is datetime for everyone
if not all_trades.empty:
    all_trades['Date'] = pd.to_datetime(all_trades['Date'])

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Manual Trade Entry")
    with st.form("trade_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            m_date = st.date_input("Trade Date", datetime.now())
            m_ticker = st.text_input("Ticker (BTC, AAPL, etc.)").upper()
        with c2:
            m_type = st.selectbox("Type", ["Long", "Short"])
            m_entry = st.number_input("Entry Price", min_value=0.0, format="%.4f")
        with c3:
            m_exit = st.number_input("Exit Price", min_value=0.0, format="%.4f")
            m_qty = st.number_input("Quantity", min_value=0.0001, format="%.4f", step=0.1)
        
        m_setup = st.text_input("Setup")
        m_mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge"])
        
        if st.form_submit_button("Save Trade"):
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

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if all_trades.empty:
        st.info("No trades logged yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net P&L", f"${all_trades['P&L'].sum():,.2f}")
        c2.metric("Win Rate", f"{(len(all_trades[all_trades['P&L']>0])/len(all_trades)*100):.1f}%")
        c3.metric("Total Trades", len(all_trades))
        c4.metric("Avg Trade", f"${all_trades['P&L'].mean():.2f}")
        
        df_sorted = all_trades.sort_values("Date")
        df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
        st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", template="plotly_dark", color_discrete_sequence=['#00ffcc']), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Tracker")
    if not all_trades.empty:
        daily_pl = all_trades.groupby(all_trades['Date'].dt.date)['P&L'].sum().reset_index()
        events = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), 
                   "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c", "allDay": True} 
                  for _, r in daily_pl.iterrows()]
        calendar(events=events, options={"initialView": "dayGridMonth"})
    else:
        st.info("No data for calendar.")

elif menu == "Trade Log":
    st.title("📜 Trade Log")
    if not st.session_state.manual_df.empty:
        st.subheader("Current Session Trades (Manual)")
        for i, row in st.session_state.manual_df.iterrows():
            cols = st.columns([1, 1, 1, 1, 1])
            cols[0].write(f"{row['Date'].date()}")
            cols[1].write(f"{row['Ticker']}")
            cols[2].write(f"${row['P&L']:.2f}")
            if cols[4].button("Delete", key=f"del_{i}"):
                st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                st.rerun()
    st.subheader("All Trades Overview")
    st.dataframe(all_trades, use_container_width=True)

elif menu == "Trade Analysis":
    st.title("📊 Candlestick Review")
    if all_trades.empty:
        st.warning("No trades available to analyze.")
    else:
        ticker = st.selectbox("Ticker", all_trades["Ticker"].unique())
        interval = st.selectbox("Timeframe", ["1d", "1h", "15m"])
        trade = all_trades[all_trades["Ticker"] == ticker].iloc[-1]
        
        # Format ticker for Yahoo Finance
        clean_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL", "BNB"] else ticker
        
        try:
            h = yf.download(clean_ticker, start=trade['Date']-timedelta(days=20), end=trade['Date']+timedelta(days=5), interval=interval)
            if not h.empty:
                h = h.reset_index()
                d_col = 'Datetime' if 'Datetime' in h.columns else 'Date'
                
                fig = go.Figure(data=[go.Candlestick(x=h[d_col], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'], name="Price")])
                
                # Risk/Reward dotted line
                fig.add_shape(type="line", x0=trade['Date'], y0=trade['Entry'], x1=trade['Date'], y1=trade['Exit'],
                              line=dict(color="white", width=2, dash="dot"))
                
                fig.add_annotation(x=trade['Date'], y=trade['Entry'], text="BUY", arrowhead=1, bgcolor="#00ffcc")
                fig.add_annotation(x=trade['Date'], y=trade['Exit'], text="SELL", arrowhead=1, bgcolor="#ff4b4b")
                
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Yahoo Finance could not find data for this ticker/date.")
        except Exception as e:
            st.error(f"Chart Error: {e}")

elif menu == "Deep Statistics":
    st.title("📈 Analytics")
    if not all_trades.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(all_trades.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", title="Profit by Setup", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(all_trades, values=all_trades['P&L'].clip(lower=0), names='Ticker', title="Winning Tickers", template="plotly_dark"), use_container_width=True)
