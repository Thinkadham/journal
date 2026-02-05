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
st.set_page_config(page_title="Thinkzella", layout="wide")

# Persistent Session State
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Entry", "Exit", "Quantity", "Setup", "Mistake", "P&L", "Status"
    ])

# --- 2. GLOBAL DATA ENGINE ---
def load_master_data(uploaded_file):
    """Integrates manual entries and uploaded CSVs into one source of truth."""
    manual = st.session_state.manual_df.copy()
    if uploaded_file:
        up_df = pd.read_csv(uploaded_file)
        up_df.columns = up_df.columns.str.strip()
        up_df['Date'] = pd.to_datetime(up_df['Date'])
        if "P&L" not in up_df.columns:
            m = np.where(up_df["Type"].str.strip().str.capitalize() == "Long", 1, -1)
            up_df["P&L"] = (up_df["Exit"] - up_df["Entry"]) * up_df["Quantity"] * m
        up_df["Status"] = np.where(up_df["P&L"] > 0, "Win", "Loss")
        return pd.concat([manual, up_df], ignore_index=True)
    return manual

# --- 3. SIDEBAR ---
st.sidebar.title("💎 Thinkzella")
st.sidebar.caption("© 2026 Th!nkSolution. All rights reserved.")

# Risk Calculator
with st.sidebar.expander("🧮 Position Size Calculator"):
    acc = st.number_input("Balance ($)", value=10000.0)
    risk = st.number_input("Risk (%)", value=1.0)
    ent = st.number_input("Entry", value=0.0, format="%.4f")
    sl = st.number_input("Stop Loss", value=0.0, format="%.4f")
    if ent > 0 and sl > 0 and ent != sl:
        st.info(f"Size: {(acc * (risk/100)) / abs(ent-sl):.4f} units")

file = st.sidebar.file_uploader("Sync CSV Data", type="csv")
df = load_master_data(file)

# Ensure date consistency
if not df.empty:
    df['Date'] = pd.to_datetime(df['Date'])

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 4. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 Manual Entry")
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
        
        s, m = st.text_input("Setup"), st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge"])
        
        if st.form_submit_button("Save to Thinkzella"):
            pl = (ex - en) * q * (1 if tp == "Long" else -1)
            new_row = pd.DataFrame([{"Date": pd.to_datetime(d), "Ticker": t, "Type": tp, "Entry": en, "Exit": ex, "Quantity": q, "Setup": s, "Mistake": m, "P&L": pl, "Status": "Win" if pl > 0 else "Loss"}])
            st.session_state.manual_df = pd.concat([st.session_state.manual_df, new_row], ignore_index=True)
            st.rerun()

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if df.empty: st.info("Welcome to Thinkzella. Start by logging a trade.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
        c2.metric("Win Rate", f"{(len(df[df['P&L']>0])/len(df)*100):.1f}%")
        c3.metric("Total Trades", len(df))
        c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
        df_s = df.sort_values("Date")
        df_s["Equity"] = df_s["P&L"].cumsum()
        st.plotly_chart(px.area(df_s, x="Date", y="Equity", template="plotly_dark", color_discrete_sequence=['#00ffcc']), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L")
    if not df.empty:
        daily = df.groupby(df['Date'].dt.date)['P&L'].sum().reset_index()
        events = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c"} for _, r in daily.iterrows()]
        calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("📜 Trade Log")
    if not st.session_state.manual_df.empty:
        st.subheader("Manual Session")
        for i, row in st.session_state.manual_df.iterrows():
            cols = st.columns([2, 2, 2, 1])
            cols[0].write(f"{row['Date'].date()} - {row['Ticker']}")
            cols[1].write(f"P&L: ${row['P&L']:.2f}")
            if cols[3].button("Delete", key=f"d_{i}"):
                st.session_state.manual_df = st.session_state.manual_df.drop(i).reset_index(drop=True)
                st.rerun()
    st.subheader("Master History")
    st.dataframe(df, use_container_width=True)

elif menu == "Trade Analysis":
    st.title("📊 Technical Review")
    if df.empty: 
        st.warning("Add trades to see charts.")
    else:
        # 1. Selection UI
        tick = st.selectbox("Select Ticker", df["Ticker"].unique())
        tf = st.selectbox("Timeframe", ["1d", "1h", "15m"])
        
        # Get the specific trade details
        tr = df[df["Ticker"] == tick].iloc[-1]
        
        # 2. TICKER CLEANING (The "Secret Sauce")
        # Handles Crypto, Stocks, and removes any accidental spaces
        yf_t = str(tick).strip().upper()
        if yf_t in ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"]:
            yf_t = f"{yf_t}-USD"
        
        try:
            # 3. EXPANDED SEARCH WINDOW
            # We look back further to ensure we catch enough candles to fill the screen
            start_date = tr['Date'] - timedelta(days=40)
            end_date = tr['Date'] + timedelta(days=10)
            
            with st.spinner(f"Fetching {yf_t} market data..."):
                h = yf.download(yf_t, start=start_date, end=end_date, interval=tf, progress=False)
            
            if not h.empty:
                # Handle Multi-index columns if they exist in newer yfinance versions
                if isinstance(h.columns, pd.MultiIndex):
                    h.columns = h.columns.get_level_values(0)
                
                h = h.reset_index()
                # Find the date/time column dynamically
                d_c = next((col for col in h.columns if col in ['Date', 'Datetime']), h.columns[0])
                
                # 4. BUILD THE CHART
                fig = go.Figure(data=[go.Candlestick(
                    x=h[d_c], 
                    open=h['Open'], 
                    high=h['High'], 
                    low=h['Low'], 
                    close=h['Close'],
                    name=yf_t
                )])
                
                # Risk/Reward Line (White dotted)
                fig.add_shape(type="line", x0=tr['Date'], y0=tr['Entry'], x1=tr['Date'], y1=tr['Exit'],
                              line=dict(color="white", width=2, dash="dot"))
                
                # BUY/SELL Annotations
                fig.add_annotation(x=tr['Date'], y=tr['Entry'], text="BUY", arrowhead=1, bgcolor="#00ffcc", font=dict(color="black"))
                fig.add_annotation(x=tr['Date'], y=tr['Exit'], text="SELL", arrowhead=1, bgcolor="#ff4b4b")
                
                fig.update_layout(
                    template="plotly_dark", 
                    xaxis_rangeslider_visible=False, 
                    height=650,
                    margin=dict(l=10, r=10, t=10, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.info(f"Analysis for {yf_t} | Trade Date: {tr['Date'].date()}")
            else: 
                st.error(f"No market data found for {yf_t}. Please check if the ticker symbol is correct.")
        except Exception as e: 
            st.error(f"Chart Render Error: {e}")

elif menu == "Deep Statistics":
    st.title("📈 Analytics")
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", title="Profit by Strategy", template="plotly_dark"), use_container_width=True)
        with c2: st.plotly_chart(px.pie(df, values=df['P&L'].clip(lower=0), names='Ticker', title="Winning Symbols", template="plotly_dark"), use_container_width=True)

# Footer Copyright
st.sidebar.markdown("---")
st.sidebar.write("© Th!nkSolution")
