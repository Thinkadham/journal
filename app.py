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

def load_local_storage():
    """Reads the local CSV database if it exists."""
    if os.path.exists(DB_FILE):
        try:
            df_local = pd.read_csv(DB_FILE)
            df_local['Date'] = pd.to_datetime(df_local['Date'])
            return df_local
        except:
            pass
    return pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "Notes", "P&L", "Status"
    ])

if "manual_df" not in st.session_state:
    st.session_state.manual_df = load_local_storage()

def save_to_local_storage():
    """Writes current session data to the local CSV database."""
    st.session_state.manual_df.to_csv(DB_FILE, index=False)

# --- 2. GLOBAL DATA ENGINE ---
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
        for col in ["Notes", "Setup", "Mistake"]:
            if col not in up_df.columns: up_df[col] = ""
        return pd.concat([manual, up_df], ignore_index=True)
    return manual

# --- 3. SIDEBAR ---
st.sidebar.title("💎 Thinkzella")
st.sidebar.caption("© 2026 Th!nkSolution")

file = st.sidebar.file_uploader("Sync External CSV", type="csv")
all_trades = get_master_data(file)
if not all_trades.empty:
    all_trades['Date'] = pd.to_datetime(all_trades['Date'])

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Trade Journaling")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", datetime.now())
            t = st.text_input("Ticker (e.g., NVDA, BTC)").upper()
        with c2:
            tp = st.selectbox("Side", ["Long", "Short"])
            en = st.number_input("Entry Price", format="%.4f", step=0.01)
        with c3:
            ex = st.number_input("Exit Price", format="%.4f", step=0.01)
            q = st.number_input("Quantity", min_value=0.0001, format="%.4f", step=0.1)
        
        setup = st.text_input("Setup (e.g., Breakout, RSI Divergence)")
        mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge", "Over-leveraged"])
        notes = st.text_area("Psychology & Entry Reason")
        
        if st.form_submit_button("Lock Trade into Thinkzella"):
            pl = (ex - en) * q * (1 if tp == "Long" else -1)
            new_row = pd.DataFrame([{
                "Date": pd.to_datetime(d), "Ticker": t, "Type": tp, "Entry": en, "Exit": ex, 
                "Quantity": q, "Setup": setup, "Mistake": mistake, "Notes": notes,
                "P&L": pl, "Status": "Win" if pl > 0 else "Loss"
            }])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new_row], ignore_index=True)
            save_to_local_storage()
            st.rerun()

elif menu == "Trade Log":
    st.title("📜 Trade History")
    if not st.session_state.manual_df.empty:
        for i, row in st.session_state.manual_df.iterrows():
            with st.expander(f"{row['Date'].date()} | {row['Ticker']} | {'🟢' if row['P&L'] > 0 else '🔴'} ${row['P&L']:.2f}"):
                st.write(f"**Strategy:** {row['Setup']} | **Mistake:** {row['Mistake']}")
                st.write(f"**Journal Notes:** {row['Notes']}")
                if st.button("Delete Entry", key=f"del_{i}"):
                    st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                    save_to_local_storage()
                    st.rerun()
    else:
        st.info("No persistent trades found.")

elif menu == "Trade Analysis":
    st.title("📊 Price Action Review")
    if all_trades.empty: st.warning("Please log a trade first.")
    else:
        tick = st.selectbox("Ticker", all_trades["Ticker"].unique())
        tr = all_trades[all_trades["Ticker"] == tick].iloc[-1]
        
        yf_t = f"{tick}-USD" if tick in ["BTC", "ETH", "SOL", "BNB"] else tick
        h = yf.download(yf_t, start=tr['Date']-timedelta(days=30), end=tr['Date']+timedelta(days=7), interval="1d")
        
        if not h.empty:
            h = h.reset_index()
            fig = go.Figure(data=[go.Candlestick(x=h['Date'], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
            
            # Risk/Reward Line
            fig.add_shape(type="line", x0=tr['Date'], y0=tr['Entry'], x1=tr['Date'], y1=tr['Exit'], line=dict(color="white", width=2, dash="dot"))
            fig.add_annotation(x=tr['Date'], y=tr['Entry'], text="ENTRY", bgcolor="#00ffcc", font=dict(color="black"))
            fig.add_annotation(x=tr['Date'], y=tr['Exit'], text="EXIT", bgcolor="#ff4b4b")
            
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
            st.plotly_chart(fig, use_container_width=True)
            if tr['Notes']: st.chat_message("assistant").write(f"**Journal Note:** {tr['Notes']}")

elif menu == "Deep Statistics":
    st.title("📈 Strategy Analytics")
    if all_trades.empty: st.info("Need data for analytics.")
    else:
        # Strategy Efficiency Table
        st.subheader("Strategy Performance Report")
        stats = all_trades.groupby("Setup").agg({'P&L': ['sum', 'count', 'mean']})
        stats.columns = ['Total Profit', 'Trade Count', 'Average Profit']
        st.table(stats.style.highlight_max(axis=0, color='#1e3d33'))

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(all_trades.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", title="Profitability by Setup", template="plotly_dark"), use_container_width=True)
        with col2:
            st.plotly_chart(px.sunburst(all_trades, path=['Status', 'Setup'], values='Quantity', title="Trade Composition", template="plotly_dark"), use_container_width=True)

# ... (Dashboard & Calendar pulling from 'all_trades' as before)

st.sidebar.markdown("---")
st.sidebar.write("© Th!nkSolution")
