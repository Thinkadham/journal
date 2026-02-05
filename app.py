import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import io
import os

# --- 1. APP CONFIG & PERSISTENCE ---
st.set_page_config(page_title="Thinkzella", layout="wide")
DB_FILE = "thinkzella_trades.csv"

# Function to load data from the local file
def load_local_storage():
    if os.path.exists(DB_FILE):
        df_local = pd.read_csv(DB_FILE)
        df_local['Date'] = pd.to_datetime(df_local['Date'])
        return df_local
    return pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "Notes", "P&L", "Status"
    ])

# Initialize session state with local file data
if "manual_df" not in st.session_state:
    st.session_state.manual_df = load_local_storage()

def save_to_local_storage():
    st.session_state.manual_df.to_csv(DB_FILE, index=False)

# --- 2. DATA ENGINE ---
def get_master_data(uploaded_file):
    manual = st.session_state.manual_df.copy()
    if uploaded_file:
        up_df = pd.read_csv(uploaded_file)
        up_df.columns = up_df.columns.str.strip()
        up_df['Date'] = pd.to_datetime(up_df['Date'])
        if "P&L" not in up_df.columns:
            m = np.where(up_df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
            up_df["P&L"] = (up_df["Exit"] - up_df["Entry"]) * up_df["Quantity"] * m
        up_df["Status"] = np.where(up_df["P&L"] > 0, "Win", "Loss")
        if "Notes" not in up_df.columns: up_df["Notes"] = ""
        return pd.concat([manual, up_df], ignore_index=True)
    return manual

# --- 3. SIDEBAR & BRANDING ---
st.sidebar.title("💎 Thinkzella")
st.sidebar.caption("© 2026 Th!nkSolution. All rights reserved.")

file = st.sidebar.file_uploader("Sync External CSV", type="csv")
all_trades = get_master_data(file)
if not all_trades.empty:
    all_trades['Date'] = pd.to_datetime(all_trades['Date'])

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Manual Entry & Journaling")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", datetime.now())
            t = st.text_input("Ticker").upper()
        with c2:
            tp = st.selectbox("Side", ["Long", "Short"])
            en = st.number_input("Entry Price", format="%.4f")
        with c3:
            ex = st.number_input("Exit Price", format="%.4f")
            q = st.number_input("Quantity", min_value=0.0001, format="%.4f", step=0.1)
        
        setup = st.text_input("Setup/Strategy")
        mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge"])
        notes = st.text_area("Trade Notes (Psychology, Why did you enter?)")
        
        if st.form_submit_button("Save to Thinkzella"):
            pl = (ex - en) * q * (1 if tp == "Long" else -1)
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(d), "Ticker": t, "Type": tp, "Entry": en, "Exit": ex, 
                "Quantity": q, "Setup": setup, "Mistake": mistake, "Notes": notes,
                "P&L": pl, "Status": "Win" if pl > 0 else "Loss"
            }])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new_row], ignore_index=True)
            save_to_local_storage() # Save to local CSV
            st.success("Trade saved to local database!")
            st.rerun()

elif menu == "Trade Log":
    st.title("📜 Trade Log")
    if not st.session_state.manual_df.empty:
        st.subheader("Persistent Journal")
        for i, row in st.session_state.manual_df.iterrows():
            with st.expander(f"{row['Date'].date()} | {row['Ticker']} | P&L: ${row['P&L']:.2f}"):
                st.write(f"**Notes:** {row['Notes']}")
                if st.button("Delete Permanent Entry", key=f"del_{i}"):
                    st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                    save_to_local_storage()
                    st.rerun()
    st.subheader("All Trades Overview")
    st.dataframe(all_trades, use_container_width=True)

elif menu == "Trade Analysis":
    st.title("📊 Technical Review")
    if all_trades.empty: st.warning("Add trades to see charts.")
    else:
        tick = st.selectbox("Select Ticker", all_trades["Ticker"].unique())
        tf = st.selectbox("Timeframe", ["1d", "1h", "15m"])
        tr = all_trades[all_trades["Ticker"] == tick].iloc[-1]
        
        yf_t = f"{tick}-USD" if tick in ["BTC", "ETH", "SOL"] else tick
        
        try:
            h = yf.download(yf_t, start=tr['Date']-timedelta(days=25), end=tr['Date']+timedelta(days=7), interval=tf)
            if not h.empty:
                h = h.reset_index()
                d_c = 'Datetime' if 'Datetime' in h.columns else 'Date'
                fig = go.Figure(data=[go.Candlestick(x=h[d_c], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
                
                # Risk/Reward Dotted Line
                fig.add_shape(type="line", x0=tr['Date'], y0=tr['Entry'], x1=tr['Date'], y1=tr['Exit'], line=dict(color="white", width=2, dash="dot"))
                fig.add_annotation(x=tr['Date'], y=tr['Entry'], text="BUY", bgcolor="#00ffcc", font=dict(color="black"))
                fig.add_annotation(x=tr['Date'], y=tr['Exit'], text="SELL", bgcolor="#ff4b4b")
                
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
                st.plotly_chart(fig, use_container_width=True)
                if tr['Notes']: st.info(f"**Journal Entry:** {tr['Notes']}")
            else: st.error("No market data found.")
        except Exception as e: st.error(f"Chart Error: {e}")

# (Dashboard, Calendar, and Deep Stats remain unchanged, automatically pulling from the persistent df)
elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if all_trades.empty: st.info("No data.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net P&L", f"${all_trades['P&L'].sum():,.2f}")
        c2.metric("Win Rate", f"{(len(all_trades[all_trades['P&L']>0])/len(all_trades)*100):.1f}%")
        c3.metric("Total Trades", len(all_trades))
        c4.metric("Avg Trade", f"${all_trades['P&L'].mean():.2f}")
        df_s = all_trades.sort_values("Date")
        df_s["Equity"] = df_s["P&L"].cumsum()
        st.plotly_chart(px.area(df_s, x="Date", y="Equity", template="plotly_dark", color_discrete_sequence=['#00ffcc']), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.write("© Th!nkSolution")
