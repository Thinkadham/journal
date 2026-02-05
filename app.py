import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import os

# --- 1. APP CONFIG & REPAIR ENGINE ---
st.set_page_config(page_title="Thinkzella", layout="wide")
DB_FILE = "thinkzella_trades.csv"

def load_and_repair_db():
    """Loads the CSV and ensures all required columns exist to prevent KeyErrors."""
    required_cols = ["Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "Notes", "P&L", "Status"]
    
    if os.path.exists(DB_FILE):
        try:
            df_local = pd.read_csv(DB_FILE)
            # Add missing columns dynamically
            for col in required_cols:
                if col not in df_local.columns:
                    df_local[col] = ""
            df_local['Date'] = pd.to_datetime(df_local['Date'])
            return df_local
        except Exception:
            return pd.DataFrame(columns=required_cols)
    return pd.DataFrame(columns=required_cols)

# Initialize Session State
if "manual_df" not in st.session_state:
    st.session_state.manual_df = load_and_repair_db()

def save_db():
    st.session_state.manual_df.to_csv(DB_FILE, index=False)

# --- 2. DATA MERGING ---
def get_all_data(uploaded_file):
    manual = st.session_state.manual_df.copy()
    if uploaded_file:
        try:
            up_df = pd.read_csv(uploaded_file)
            up_df.columns = up_df.columns.str.strip()
            up_df['Date'] = pd.to_datetime(up_df['Date'])
            if "P&L" not in up_df.columns:
                m = np.where(up_df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
                up_df["P&L"] = (up_df["Exit"] - up_df["Entry"]) * up_df["Quantity"] * m
            # Ensure consistency
            for col in ["Notes", "Setup", "Mistake", "Status"]:
                if col not in up_df.columns: up_df[col] = "N/A"
            return pd.concat([manual, up_df], ignore_index=True)
        except:
            return manual
    return manual

# --- 3. SIDEBAR (Always Rendered First) ---
st.sidebar.title("💎 Thinkzella")
st.sidebar.caption("© 2026 Th!nkSolution")

# RISK CALCULATOR (Fixed placement to ensure it's always visible)
with st.sidebar.expander("🧮 Risk Calculator", expanded=False):
    acc = st.number_input("Balance ($)", value=10000.0)
    risk_pct = st.number_input("Risk (%)", value=1.0)
    ent_p = st.number_input("Entry Price", value=0.0)
    sl_p = st.number_input("Stop Loss", value=0.0)
    if ent_p > 0 and sl_p > 0 and ent_p != sl_p:
        size = (acc * (risk_pct/100)) / abs(ent_p - sl_p)
        st.success(f"Position Size: {size:.4f}")

file_up = st.sidebar.file_uploader("Upload CSV", type="csv")
all_trades = get_all_data(file_up)

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Trade Journaling")
    with st.form("main_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", datetime.now())
            t = st.text_input("Ticker").upper()
        with c2:
            tp = st.selectbox("Side", ["Long", "Short"])
            en = st.number_input("Entry", format="%.4f")
        with c3:
            ex = st.number_input("Exit", format="%.4f")
            q = st.number_input("Quantity", min_value=0.0001, format="%.4f")
        
        setp = st.text_input("Setup")
        mist = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge"])
        note = st.text_area("Notes")
        
        if st.form_submit_button("Save Trade"):
            pl = (ex - en) * q * (1 if tp == "Long" else -1)
            new = pd.DataFrame([{"Date":pd.to_datetime(d),"Ticker":t,"Type":tp,"Entry":en,"Exit":ex,"Quantity":q,"Setup":setp,"Mistake":mist,"Notes":note,"P&L":pl,"Status":"Win" if pl>0 else "Loss"}])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new], ignore_index=True)
            save_db()
            st.rerun()

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if all_trades.empty:
        st.info("Log a trade to see your stats!")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Net P&L", f"${all_trades['P&L'].sum():,.2f}")
        m2.metric("Trades", len(all_trades))
        win_r = (len(all_trades[all_trades['P&L']>0])/len(all_trades)*100)
        m3.metric("Win Rate", f"{win_r:.1f}%")
        
        all_trades = all_trades.sort_values("Date")
        all_trades["Equity"] = all_trades["P&L"].cumsum()
        st.plotly_chart(px.area(all_trades, x="Date", y="Equity", template="plotly_dark", title="Equity Curve"), use_container_width=True)

elif menu == "Trade Log":
    st.title("📜 Trade Log")
    for i, row in st.session_state.manual_df.iterrows():
        with st.expander(f"{row['Date'].date()} | {row['Ticker']} | ${row['P&L']:.2f}"):
            st.write(f"**Notes:** {row.get('Notes', 'No notes available')}")
            if st.button("Delete", key=f"del_{i}"):
                st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                save_db()
                st.rerun()

elif menu == "Trade Analysis":
    st.title("📊 Technical Analysis")
    if all_trades.empty:
        st.warning("No data.")
    else:
        sel_tick = st.selectbox("Ticker", all_trades["Ticker"].unique())
        tr_data = all_trades[all_trades["Ticker"] == sel_tick].iloc[-1]
        
        # Yahoo Finance Ticker Fix
        ytick = f"{sel_tick}-USD" if sel_tick in ["BTC", "ETH", "SOL"] else sel_tick
        
        try:
            # CANDLE FETCH FIX: Flatten Multi-Index
            h = yf.download(ytick, start=tr_data['Date']-timedelta(days=20), end=tr_data['Date']+timedelta(days=5))
            if not h.empty:
                if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
                h = h.reset_index()
                
                fig = go.Figure(data=[go.Candlestick(x=h['Date'], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
                
                # Risk/Reward Dotted Line
                fig.add_shape(type="line", x0=tr_data['Date'], y0=tr_data['Entry'], x1=tr_data['Date'], y1=tr_data['Exit'], line=dict(color="white", width=2, dash="dot"))
                fig.add_annotation(x=tr_data['Date'], y=tr_data['Entry'], text="BUY", bgcolor="#00ffcc", font=dict(color="black"))
                fig.add_annotation(x=tr_data['Date'], y=tr_data['Exit'], text="SELL", bgcolor="#ff4b4b")
                
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Market data not found for this date.")
        except Exception as e:
            st.error(f"Candle Error: {e}")

elif menu == "Calendar":
    st.title("P&L Calendar")
    if not all_trades.empty:
        day_pl = all_trades.groupby(all_trades['Date'].dt.date)['P&L'].sum().reset_index()
        evts = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c"} for _, r in day_pl.iterrows()]
        calendar(events=evts, options={"initialView": "dayGridMonth"})

st.sidebar.markdown("---")
st.sidebar.write("© Th!nkSolution")
