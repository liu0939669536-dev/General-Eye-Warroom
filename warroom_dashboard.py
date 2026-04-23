import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# 🗝️ 將軍的富果即時金鑰 (已綁定)
FUGLE_API_KEY = "OGVlYmE0M2MtZTVjYy00N2QzLWJhZTktMWU2NzI2Yzk4ZmMwIGQ3MTI4ZjYxLTM0ZGYtNGE0Ny04ZWNhLWJmOGJlM2FhOWZlMg=="

# 1. 網頁配置
st.set_page_config(page_title="將軍天眼 AI 戰情室 5.2", layout="wide", page_icon="🦅")

# --- 新增武裝一：法人籌碼追蹤炮 (每日盤後更新) ---
@st.cache_data(ttl=3600)
def fetch_institutional_data():
    url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
    try:
        res = requests.get(url, timeout=10)
        df = pd.DataFrame(res.json())
        # 提取外資與投信買賣超股數，除以1000換算為「張」
        df['ForeignBuy'] = pd.to_numeric(df['ForeignInvestorNetBuySell'], errors='coerce') / 1000
        df['TrustBuy'] = pd.to_numeric(df['InvestmentTrustNetBuySell'], errors='coerce') / 1000
        return df[['Code', 'ForeignBuy', 'TrustBuy']].set_index('Code')
    except:
        return pd.DataFrame()

# --- 武裝二：總經與全球大盤探照燈 ---
@st.cache_data(ttl=300)
def fetch_macro_data():
    indices = {
        "🇺🇸 納斯達克 (昨收)": "^IXIC", 
        "🇺🇸 費城半導體 (昨收)": "^SOX", 
        "🇹🇼 台股加權指數 (即時)": "^TWII"
    }
    macro_info = {}
    for name, ticker in indices.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")
            if len(data) >= 2:
                current = data['Close'].iloc[-1]
                prev = data['Close'].iloc[-2]
                change = current - prev
                pct = (change / prev) * 100
                macro_info[name] = {"price": current, "change": change, "pct": pct}
        except:
            macro_info[name] = {"price": 0, "change": 0, "pct": 0}
    return macro_info

# --- 武裝三：混合雙雷達 (Fugle 即時) ---
@st.cache_data(ttl=30)
def get_realtime_top_etfs(api_key):
    url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        twse_res = requests.get(url_twse, timeout=10)
        df_twse = pd.DataFrame(twse_res.json())
        etf_df = df_twse[df_twse['Code'].str.startswith('00')].copy()
        etf_df['Volume'] = pd.to_numeric(etf_df['TradeVolume'], errors='coerce')
        top_candidates = etf_df.sort_values(by='Volume', ascending=False).head(15)['Code'].tolist()
    except:
        top_candidates = ['00940', '00929', '00919', '00878', '0056', '0050', '00631L', '00632R', '00981A', '00992A', '00400A', '009816']

    headers = {"X-API-KEY": api_key}
    realtime_data = []
    
    for code in top_candidates:
        fugle_url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{code}"
        try:
            res = requests.get(fugle_url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                price = data.get('closePrice')
                change = data.get('change', 0)
                vol_shares = data.get('total', {}).get('tradeVolume', 0)
                
                if price is not None:
                    realtime_data.append({
                        "Code": code, "Name": data.get('name', f"{code}"),
                        "Price": float(price), "Change": float(change),
                        "Volume": vol_shares / 1000 
                    })
        except: continue
            
    if realtime_data:
        real_df = pd.DataFrame(realtime_data)
        return real_df.sort_values(by='Volume', ascending=False).head(12)
    return pd.DataFrame()

# --- 武裝四：Alpha 算力引擎 ---
class Alpha_Engine:
    @staticmethod
    @st.cache_data(ttl=3600)
    def calculate_historical_vwap(ticker, window=20):
        try:
            data = yf.Ticker(f"{ticker}.TW").history(period="2mo")
            if data.empty or len(data) < window: return None, None
            data['TP'] = (data['High'] + data['Low'] + data['Close']) / 3
            data['PV'] = data['TP'] * data['Volume']
            vwap = data['PV'].rolling(window=window).sum() / data['Volume'].rolling(window=window).sum()
            return data['Close'].rolling(window=window).mean().iloc[-1], vwap.iloc[-1]
        except: return None, None

# ================= 戰情室 UI 介面 =================
st.title("🦅 將軍天眼 5.2：法人籌碼武裝版")
st.caption(f"📡 數據源：Fugle 毫秒即時 + TWSE 法人籌碼 | 系統自動刷新 | 同步時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 🌍 橫欄一：全球宏觀氣象台
macro_data = fetch_macro_data()
if macro_data:
    cols = st.columns(3)
    for i, (name, data) in enumerate(macro_data.items()):
        with cols[i]:
            st.metric(label=name, value=f"{data['price']:,.2f}", delta=f"{data['change']:,.2f} ({data['pct']:.2f}%)")
st.divider()

# 📊 橫欄二：資金風格
col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
tech_data = yf.Ticker("00830.TW").history(period="5d")
div_data = yf.Ticker("0056.TW").history(period="5d")
if not tech_data.empty and not div_data.empty:
    ratio = (tech_data['Close'] * tech_data['Volume']).mean() / (div_data['Close'] * div_data['Volume']).mean()
    with col_kpi1: st.metric("資金風格比值 (AI/高息)", f"{ratio:.2f}")
    with col_kpi2:
        if ratio > 1.1: st.error("🔴 風險偏好：追逐動能 (科技強)")
        elif ratio < 0.9: st.success("🟢 風險避險：防禦啟動 (高息強)")
        else: st.warning("🟠 風格輪動：震盪盤整")
    with col_kpi3: st.metric("生存現金防線", "$138,691", "-$326,447", delta_color="inverse")
st.divider()

# 🔥 橫欄三：即時熱度雷達
st.header("📡 盤中即時雷達 (今日成交量 TOP 12)")
full_list = get_realtime_top_etfs(FUGLE_API_KEY)
if not full_list.empty:
    top_12 = full_list.head(12)
    cols = st.columns(4)
    for i, (idx, row) in enumerate(top_12.iterrows()):
        with cols[i % 4]:
            with st.container(border=True):
                st.subheader(f"{row['Code']}")
                st.write(f"**{row['Name']}**")
                if row['Change'] > 0: st.markdown(f":red[現價: {row['Price']:.2f} ▲]")
                elif row['Change'] < 0: st.markdown(f":green[現價: {row['Price']:.2f} ▼]")
                else: st.markdown(f"現價: {row['Price']:.2f} ▬")
                st.caption(f"盤中成交量: {int(row['Volume']):,} 張")
st.divider()

# 🎯 橫欄四：主力成本與法人籌碼透視
st.header("🎯 戰術決策：籌碼透視與即時狙擊號誌")
engine = Alpha_Engine()
inst_df = fetch_institutional_data() # 啟動法人籌碼雷達

if not full_list.empty:
    top_8_df = top_12.head(8)
    decision_data = []
    for idx, row in top_8_df.iterrows():
        code, name, price = row['Code'], row['Name'], row['Price']
        
        # 1. 計算技術面成本
        ma20, vwap20 = engine.calculate_historical_vwap(code)
        
        # 2. 獲取法人籌碼動向 (若無資料則為0)
        foreign_buy = inst_df.loc[code, 'ForeignBuy'] if (not inst_df.empty and code in inst_df.index) else 0
        trust_buy = inst_df.loc[code, 'TrustBuy'] if (not inst_df.empty and code in inst_df.index) else 0
        
        # 3. 戰略判定
        if vwap20 is not None and ma20 is not None:
            bias = ((price - vwap20) / vwap20) * 100
            if price < ma20 and price >= vwap20: signal, intensity = "🟢 假跌破", "🔥 強烈買進"
            elif price < vwap20: signal, intensity = "🔴 趨勢破壞", "❄️ 嚴禁接刀"
            elif bias > 5.0: signal, intensity = "🔴 正乖離過大", "⚠️ 逢高減碼"
            elif price >= ma20 and price >= vwap20: signal, intensity = "🟢 穩定多頭", "🛡️ 抱緊持股"
            else: signal, intensity = "🟠 震盪整理", "⏳ 觀望等待"
        else:
            vwap20, bias, signal, intensity = np.nan, np.nan, "⚪ 數據建置中", "📡 新兵入陣"
            
        decision_data.append({
            "代號": code, "名稱": name, "即時現價": price, 
            "歷史主力成本(VWAP)": vwap20, 
            "外資動向(張)": foreign_buy, "投信動向(張)": trust_buy, # 🕵️ 新增籌碼欄位
            "成本乖離%": bias, "盤中號誌": signal, "戰略建議": intensity
        })

    if decision_data:
        df_final = pd.DataFrame(decision_data)
        df_final.index = df_final.index + 1
        
        # 🎨 上色邏輯：買超(大於0)顯示紅色，賣超(小於0)顯示綠色
        def color_net_buy(val):
            if pd.isna(val) or val == 0: return ''
            return 'color: #ff4b4b; font-weight: bold' if val > 0 else 'color: #00ff00; font-weight: bold'

        styled_df = df_final.style.format(
            formatter={"即時現價": "{:.2f}", "歷史主力成本(VWAP)": "{:.2f}", "成本乖離%": "{:.2f}", "外資動向(張)": "{:,.0f}", "投信動向(張)": "{:,.0f}"}, na_rep="-"
        ).map(
            color_net_buy, subset=['外資動向(張)', '投信動向(張)']
        ).map(
            lambda x: f'color: #00ff00; font-weight: bold' if '🟢' in str(x) else 
                      (f'color: #ff4b4b; font-weight: bold' if '🔴' in str(x) else 
                      (f'color: #ffa500; font-weight: bold' if '🟠' in str(x) else '')),
            subset=['盤中號誌']
        )
        st.dataframe(styled_df, use_container_width=True)
        st.info("💡 **籌碼判讀指南**：外資與投信動向為前一交易日之盤後結算數據。紅色代表法人買超護盤，綠色代表法人倒貨抽資！")