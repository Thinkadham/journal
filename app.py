import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from supabase import create_client, Client

# --- 1. APP CONFIG & STYLING ---
st.set_page_config(page_title="Thinkzella", layout="wide")

# --- 2. SUPABASE CONNECTION ---
# Ensure these are set in Streamlit Cloud > Settings > Secrets
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Supabase Credentials Missing! Set them in Streamlit Secrets.")
    st.stop()

# --- 3. DATABASE ENGINE ---
def load_data():
    """Fetches all trades from Supabase."""
    try:
        response = supabase.table("trades").select("*").order("date", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

def delete_trade(trade_id):
    """Removes a trade from Supabase by ID."""
    supabase.table("trades").delete().eq("id", trade_id).execute()

# Fetch data for the session
all_trades = load_data()

# --- 4. SIDEBAR ---
st.sidebar.title("💎 Thinkzella")
st.sidebar.caption("© 2026 Th!nkSolution")

with st.sidebar.expander("🧮 Risk Calculator"):
    acc = st.number_input("Balance ($)", value=10000.0)
    risk_pct = st.number_input("Risk (%)", value=1.0)
    ent_p = st.number_input("Entry Price", value=0.0)
    sl_p = st.number_input("Stop Loss", value=0.0)
    if ent_p > 0 and sl_p > 0 and ent_p != sl_p:
        st.success(f"Size: {(acc * (risk_pct/100)) / abs(ent_p - sl_p):.4f}")

menu = st.sidebar.radio("Navigation", ["Dashboard", "Calendar", "Trade Log", "Manual Entry", "Trade Analysis", "Deep Statistics"])

# --- 5. NAVIGATION LOGIC ---

if menu == "Manual Entry":
    st.title("📝 New Journal Entry")
    with st.form("manual_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Trade Date", datetime.now())
            t = st.text_input("Ticker (e.g. BTC, TSLA)").upper()
        with c2:
            tp = st.selectbox("Type", ["Long", "Short"])
            en = st.number_input("Entry Price", format="%.4f")
        with c3:
            ex = st.number_input("Exit Price", format="%.4f")
            q = st.number_input("Quantity", min_value=0.0001, format="%.4f")
        
        setup = st.text_input("Setup/Strategy")
        mistake = st.selectbox("Mistake", ["None", "FOMO", "Early Exit", "Revenge"])
        notes = st.text_area("Journal Notes")
        
        if st.form_submit_button("Sync to Supabase"):
            pl = (ex - en) * q * (1 if tp == "Long" else -1)
            new_data = {
                "date": str(d), "ticker": t, "type": tp, "entry": en, 
                "exit": ex, "quantity": q, "setup": setup, "mistake": mistake, 
                "notes": notes, "p_l": float(pl), "status": "Win" if pl > 0 else "Loss"
            }
            supabase.table("trades").insert(new_data).execute()
            st.success("Trade Permanently Saved!")
            st.rerun()

elif menu == "Dashboard":
    st.title("Performance Dashboard")
    if all_trades.empty:
        st.info("No trades found in Supabase.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Net P&L", f"${all_trades['p_l'].sum():,.2f}")
        win_rate = (len(all_trades[all_trades['p_l'] > 0]) / len(all_trades) * 100)
        c2.metric("Win Rate", f"{win_rate:.1f}%")
        c3.metric("Total Trades", len(all_trades))
        
        df_plot = all_trades.sort_values("date")
        df_plot["Equity"] = df_plot["p_l"].cumsum()
        st.plotly_chart(px.area(df_plot, x="date", y="Equity", template="plotly_dark", color_discrete_sequence=['#00ffcc']), use_container_width=True)

elif menu == "Trade Log":
    st.title("📜 Permanent Trade Log")
    if all_trades.empty:
        st.info("Database is empty.")
    else:
        for _, row in all_trades.iterrows():
            with st.expander(f"{row['date'].date()} | {row['ticker']} | {row['status']} (${row['p_l']:.2f})"):
                st.write(f"**Strategy:** {row['setup']} | **Mistake:** {row['mistake']}")
                st.write(f"**Notes:** {row['notes']}")
                if st.button("Delete Permanently", key=f"del_{row['id']}"):
                    delete_trade(row['id'])
                    st.rerun()

elif menu == "Trade Analysis":
    st.title("📊 Technical Analysis")
    if all_trades.empty:
        st.warning("No data.")
    else:
        tick = st.selectbox("Select Ticker", all_trades["ticker"].unique())
        tr = all_trades[all_trades["ticker"] == tick].iloc[0]
        
        yf_t = f"{tick}-USD" if tick in ["BTC", "ETH", "SOL"] else tick
        try:
            h = yf.download(yf_t, start=tr['date']-timedelta(days=20), end=tr['date']+timedelta(days=5))
            if not h.empty:
                if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
                h = h.reset_index()
                fig = go.Figure(data=[go.Candlestick(x=h['Date'], open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'])])
                
                # Risk/Reward Dotted Line
                fig.add_shape(type="line", x0=tr['date'], y0=tr['entry'], x1=tr['date'], y1=tr['exit'], line=dict(color="white", dash="dot"))
                fig.add_annotation(x=tr['date'], y=tr['entry'], text="BUY", bgcolor="#00ffcc", font=dict(color="black"))
                fig.add_annotation(x=tr['date'], y=tr['exit'], text="SELL", bgcolor="#ff4b4b")
                
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else: st.error("No market data found.")
        except Exception as e: st.error(f"Candle Error: {e}")

elif menu == "Calendar":
    st.title("Daily P&L Calendar")
    if not all_trades.empty:
        daily = all_trades.groupby(all_trades['date'].dt.date)['p_l'].sum().reset_index()
        evts = [{"title": f"${r['p_l']:.0f}", "start": str(r['date']), "backgroundColor": "#2ecc71" if r['p_l'] >= 0 else "#e74c3c"} for _, r in daily.iterrows()]
        calendar(events=evts, options={"initialView": "dayGridMonth"})

elif menu == "Deep Statistics":
    st.title("📈 Advanced Analytics")
    
    if all_trades.empty:
        st.info("No data available in Supabase. Log some trades to see your deep stats.")
    else:
        # 1. Strategy Efficiency Table
        st.subheader("Strategy Performance Report")
        # Aggregating data based on Supabase column names
        stats = all_trades.groupby("setup").agg({
            'p_l': ['sum', 'count', 'mean'],
            'status': lambda x: (x == 'Win').sum()
        })
        
        # Cleaning up the multi-index columns
        stats.columns = ['Total P&L', 'Trade Count', 'Average P&L', 'Wins']
        stats['Win Rate'] = (stats['Wins'] / stats['Trade Count'] * 100).map('{:.1f}%'.format)
        
        # Display the table with color formatting
        st.table(stats[['Total P&L', 'Trade Count', 'Win Rate', 'Average P&L']].style.highlight_max(axis=0, color='#1e3d33'))

        # 2. Visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Profitability by Setup")
            setup_fig = px.bar(
                all_trades.groupby("setup")["p_l"].sum().reset_index(),
                x="setup", 
                y="p_l", 
                color="p_l",
                color_continuous_scale='RdYlGn',
                template="plotly_dark"
            )
            st.plotly_chart(setup_fig, use_container_width=True)
            
        with col2:
            st.subheader("Mistake Distribution")
            # Analyze which mistakes are costing the most money
            mistake_fig = px.pie(
                all_trades, 
                values=all_trades['p_l'].abs(), 
                names='mistake',
                hole=0.4,
                template="plotly_dark",
                color_discrete_sequence=px.colors.sequential.Reds_r
            )
            st.plotly_chart(mistake_fig, use_container_width=True)

        # 3. Ticker Heatmap
        st.subheader("Ticker Volume vs. Profit")
        ticker_fig = px.scatter(
            all_trades.groupby("ticker").agg({'p_l': 'sum', 'quantity': 'count'}).reset_index(),
            x="quantity",
            y="p_l",
            size="quantity",
            color="p_l",
            text="ticker",
            labels={'quantity': 'Number of Trades', 'p_l': 'Total Profit/Loss'},
            template="plotly_dark"
        )
        st.plotly_chart(ticker_fig, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.write("© Th!nkSolution")
