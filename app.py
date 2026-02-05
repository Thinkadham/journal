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

# --- 2. DATA ENGINE ---
@st.cache_data
def process_data(uploaded_file):
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
    else:
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
    return output.getvalue()

st.sidebar.download_button("📥 Export to Excel", data=to_excel(df), file_name="Trades.xlsx")

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Trade Analysis", "Deep Statistics"])

# --- 4. PAGE LOGIC ---

if menu == "Dashboard":
    st.title("Performance Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net P&L", f"${df['P&L'].sum():,.2f}")
    c2.metric("Win Rate", f"{(len(df[df['P&L']>0])/len(df)*100):.1f}%")
    c3.metric("Total Trades", len(df))
    c4.metric("Avg Trade", f"${df['P&L'].mean():.2f}")
    
    df_sorted = df.sort_values("Date")
    df_sorted["Cum_PL"] = df_sorted["P&L"].cumsum()
    st.plotly_chart(px.area(df_sorted, x="Date", y="Cum_PL", template="plotly_dark"), use_container_width=True)

elif menu == "Calendar":
    st.title("Daily P&L Tracker")
    daily_pl = df.groupby(df['Date'].dt.date)['P&L'].sum().reset_index()
    events = [{"title": f"${r['P&L']:.0f}", "start": str(r['Date']), 
               "backgroundColor": "#2ecc71" if r['P&L'] >= 0 else "#e74c3c", "allDay": True} 
              for _, r in daily_pl.iterrows()]
    calendar(events=events, options={"initialView": "dayGridMonth"})

elif menu == "Trade Log":
    st.title("Full Trade History")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)

elif menu == "Trade Analysis":
    st.title("Technical Trade Review")
    ticker = st.selectbox("Select Ticker", df["Ticker"].unique())
    trade = df[df["Ticker"] == ticker].iloc[-1]
    
    yf_ticker = f"{ticker}-USD" if ticker in ["BTC", "ETH", "SOL"] else ticker
    
    try:
        h = yf.download(yf_ticker, start=trade['Date']-timedelta(days=30), end=trade['Date']+timedelta(days=7))
        if not h.empty:
            if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
            h = h.reset_index()
            
            # Create Plotly Candlestick
            fig = go.Figure(data=[go.Candlestick(
                x=h['Date'], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'],
                name="Price"
            )])
            
            # Add Marker for Trade Entry
            fig.add_annotation(
                x=trade['Date'], y=trade['Entry'],
                text="ENTRY", showarrow=True, arrowhead=1, bgcolor="#2196F3", font=dict(color="white")
            )
            
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
            st.plotly_chart(fig, use_container_width=True)
            st.info(f"Entry: {trade['Entry']} | Exit: {trade['Exit']} | P&L: ${trade['P&L']:.2f}")
        else:
            st.warning("No market data found.")
    except Exception as e:
        st.error(f"Error: {e}")

elif menu == "Deep Statistics":
    st.title("Advanced Analytics")
    cl, cr = st.columns(2)
    with cl:
        st.subheader("P&L by Strategy")
        st.plotly_chart(px.bar(df.groupby("Setup")["P&L"].sum().reset_index(), x="Setup", y="P&L", template="plotly_dark"), use_container_width=True)
    with cr:
        st.subheader("Mistake Costs")
        mistakes = df[df["Mistake"] != "None"]
        if not mistakes.empty:
            st.plotly_chart(px.pie(mistakes, values=abs(mistakes['P&L']), names='Mistake', template="plotly_dark"), use_container_width=True)
