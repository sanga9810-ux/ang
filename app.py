import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="미국주식 수급 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 다크모드 CSS
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
    .metric-title { font-size: 14px; color: #8b949e; margin-bottom: 4px; }
    .metric-value { font-size: 24px; font-weight: 600; color: #f0f6fc; }
    .metric-change-up { color: #3fb950; font-size: 14px; }
    .metric-change-down { color: #f85149; font-size: 14px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; }
    .badge-buy { background: rgba(47,129,247,0.15); color: #58a6ff; }
    .badge-hold { background: rgba(210,153,34,0.15); color: #d29922; }
    .badge-sell { background: rgba(248,81,73,0.15); color: #f85149; }
    .insider-buy { color: #3fb950; font-weight: 500; }
    .insider-sell { color: #f85149; font-weight: 500; }
    .rank-1 { background: rgba(255,215,0,0.1); border-left: 3px solid #ffd700; }
    .rank-2 { background: rgba(192,192,192,0.1); border-left: 3px solid #c0c0c0; }
    .rank-3 { background: rgba(205,127,50,0.1); border-left: 3px solid #cd7f32; }
    div[data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 600 !important; }
    div[data-testid="stMetricDelta"] { font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

st.title("미국주식 수급 대시보드")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST | 30초마다 자동 갱신")

# 기본 종목 리스트
DEFAULT_TICKERS = "AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD, NFLX, CRM, AVGO, INTC, QCOM, JPM, BAC, XOM, JNJ, V, MA, DIS"

with st.sidebar:
    st.header("설정")
    tickers_input = st.text_area("관심 종목 (쉼표 구분)", value=DEFAULT_TICKERS, height=80)
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    st.markdown("---")
    st.markdown("**수급 점수 산정 기준**")
    st.markdown("- 기관 보유율 ↑ : +점수")
    st.markdown("- 내부자 매수 발생 : +점수")
    st.markdown("- 컨센서스 Strong Buy : +점수")
    st.markdown("- 공매도 급증 : -점수")

    st.markdown("---")
    st.markdown("**데이터 출처**: Yahoo Finance")
    st.markdown("**지연**: 15~20분 지연 데이터")

@st.cache_data(ttl=60)
def fetch_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")

        if hist.empty:
            return None

        current_price = hist["Close"].iloc[-1]
        prev_close = info.get("previousClose", hist["Close"].iloc[-2] if len(hist) > 1 else current_price)
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
        volume = hist["Volume"].iloc[-1]
        avg_volume = info.get("averageVolume", volume)

        # 기관/내부자 데이터
        inst_pct = info.get("heldPercentInstitutions", 0) * 100
        insider_pct = info.get("heldPercentInsiders", 0) * 100

        # 컨센서스
        rec_mean = info.get("recommendationMean", 3)
        rec_key = info.get("recommendationKey", "hold")
        target_mean = info.get("targetMeanPrice", current_price)
        num_analysts = info.get("numberOfAnalystOpinions", 0)

        # 내부자 거래 (최근 30일)
        insider_buy = 0
        insider_sell = 0
        try:
            insider_df = stock.insider_transactions
            if insider_df is not None and not insider_df.empty:
                recent = insider_df[insider_df.index >= (datetime.now() - timedelta(days=30))]
                if not recent.empty and "Transaction" in recent.columns:
                    buys = recent[recent["Transaction"].str.contains("Buy", case=False, na=False)]
                    sells = recent[recent["Transaction"].str.contains("Sale", case=False, na=False)]
                    insider_buy = len(buys)
                    insider_sell = len(sells)
        except:
            pass

        # 기관 보유 변화 (최근 보고)
        inst_change = 0
        try:
            inst_df = stock.institutional_holders
            if inst_df is not None and not inst_df.empty and "pctChange" in inst_df.columns:
                inst_change = inst_df["pctChange"].sum()
        except:
            pass

        # 수급 점수 계산
        score = 0
        score += min(inst_change * 50, 20)  # 기관 증가분
        score += insider_buy * 10  # 내부자 매수
        score -= insider_sell * 5  # 내부자 매도
        score += (3 - rec_mean) * 5 if rec_mean else 0  # 컨센서스
        score += (target_mean / current_price - 1) * 20 if current_price > 0 else 0  # 목표주가 괴리

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": current_price,
            "change_pct": change_pct,
            "volume": volume,
            "avg_volume": avg_volume,
            "market_cap": info.get("marketCap", 0),
            "inst_pct": inst_pct,
            "insider_pct": insider_pct,
            "inst_change": inst_change,
            "insider_buy": insider_buy,
            "insider_sell": insider_sell,
            "rec_mean": rec_mean,
            "rec_key": rec_key,
            "target_mean": target_mean,
            "num_analysts": num_analysts,
            "score": score,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
        }
    except Exception as e:
        return None

# 데이터 수집
progress = st.progress(0)
all_data = []
for i, t in enumerate(tickers):
    progress.progress((i + 1) / len(tickers), text=f"{t} 데이터 수집 중...")
    data = fetch_stock_data(t)
    if data:
        all_data.append(data)
progress.empty()

if not all_data:
    st.error("데이터를 가져올 수 없습니다. 종목 코드를 확인해주세요.")
    st.stop()

df = pd.DataFrame(all_data)

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["전체 현황", "수급 랭킹", "내부자 매수", "기관 매수"])

with tab1:
    st.subheader("전체 종목 현황")

    cols = st.columns(4)
    metrics = [
        ("평균 등락률", f"{df['change_pct'].mean():+.2f}%", "전 종목 평균"),
        ("상승 종목", f"{(df['change_pct'] > 0).sum()}개", f"/{len(df)}개"),
        ("내부자 매수 발생", f"{(df['insider_buy'] > 0).sum()}개", "최근 30일"),
        ("기관 증가 종목", f"{(df['inst_change'] > 0).sum()}개", "최근 보고"),
    ]
    for col, (label, value, help_text) in zip(cols, metrics):
        with col:
            st.metric(label, value, help=help_text)

    st.markdown("---")

    # 종목 카드 그리드
    for i in range(0, len(df), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(df):
                row = df.iloc[idx]
                with col:
                    change_color = "metric-change-up" if row['change_pct'] >= 0 else "metric-change-down"
                    change_sign = "+" if row['change_pct'] >= 0 else ""

                    rec_badge = "badge-buy" if row['rec_key'] in ['strong_buy', 'buy'] else ("badge-sell" if row['rec_key'] in ['strong_sell', 'sell'] else "badge-hold")
                    rec_text = {"strong_buy": "강력매수", "buy": "매수", "hold": "중립", "sell": "매도", "strong_sell": "강력매도"}.get(row['rec_key'], row['rec_key'])

                    cap_b = row['market_cap'] / 1e9
                    cap_str = f"{cap_b:.1f}B" if cap_b >= 1 else f"{row['market_cap']/1e6:.1f}M"

                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:16px; font-weight:600;">{row['ticker']}</span>
                            <span class="badge {rec_badge}">{rec_text} ({row['num_analysts']}명)</span>
                        </div>
                        <div style="font-size:12px; color:#8b949e; margin-bottom:4px;">{row['name']}</div>
                        <div class="metric-value">${row['price']:.2f}</div>
                        <div class="{change_color}">{change_sign}{row['change_pct']:.2f}%</div>
                        <div style="margin-top:8px; font-size:12px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:4px;">
                            <div>시총: {cap_str}</div>
                            <div>거래량: {row['volume']/1e6:.1f}M</div>
                            <div>기관: {row['inst_pct']:.1f}%</div>
                            <div>내부자: {row['insider_pct']:.1f}%</div>
                            <div>내부자매수: <span class="{'insider-buy' if row['insider_buy']>0 else ''}">{int(row['insider_buy'])}회</span></div>
                            <div>기관변화: <span class="{'insider-buy' if row['inst_change']>0 else 'insider-sell' if row['inst_change']<0 else ''}">{row['inst_change']:+.2f}%p</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

with tab2:
    st.subheader("수급 점수 랭킹 (기관 + 내부자 + 컨센서스 종합)")
    df_rank = df.sort_values("score", ascending=False).reset_index(drop=True)

    for i, row in df_rank.iterrows():
        rank_class = ""
        if i == 0: rank_class = "rank-1"
        elif i == 1: rank_class = "rank-2"
        elif i == 2: rank_class = "rank-3"

        change_color = "color:#3fb950;" if row['change_pct'] >= 0 else "color:#f85149;"
        change_sign = "+" if row['change_pct'] >= 0 else ""

        st.markdown(f"""
        <div class="metric-card {rank_class}" style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="font-size:20px; font-weight:700; width:32px; text-align:center;">{i+1}</div>
                <div>
                    <div style="font-size:15px; font-weight:600;">{row['ticker']} <span style="font-size:12px; color:#8b949e;">{row['name']}</span></div>
                    <div style="font-size:12px; color:#8b949e;">{row['sector']} | 기관 {row['inst_pct']:.1f}% | 내부자매수 {int(row['insider_buy'])}회</div>
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                <div style="font-size:13px; {change_color}">{change_sign}{row['change_pct']:.2f}%</div>
                <div style="font-size:12px; color:#58a6ff; font-weight:500;">수급점수: {row['score']:.1f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab3:
    st.subheader("최근 내부자 매수 발생 종목")
    insider_df = df[df['insider_buy'] > 0].sort_values('insider_buy', ascending=False)

    if insider_df.empty:
        st.info("최근 30일 내 내부자 매수 데이터가 없는 종목입니다.")
    else:
        for _, row in insider_df.iterrows():
            st.markdown(f"""
            <div class="metric-card" style="border-left: 3px solid #3fb950;">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:16px; font-weight:600;">{row['ticker']} {row['name']}</div>
                        <div style="font-size:12px; color:#8b949e;">{row['sector']}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                        <div style="font-size:13px; color:#3fb950; font-weight:500;">내부자 매수 {int(row['insider_buy'])}회</div>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:12px; color:#8b949e;">
                    기관 보유 {row['inst_pct']:.1f}% | 컨센서스: {row['rec_key']} | 목표주가 ${row['target_mean']:.0f}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("내부자 거래는 SEC Form 4 신고 기준 최근 30일 데이터입니다. 실제로는 더 많은 거래가 있을 수 있습니다.")

with tab4:
    st.subheader("기관 보유 증가 종목")
    inst_df = df[df['inst_change'] > 0].sort_values('inst_change', ascending=False)

    if inst_df.empty:
        st.info("최근 기관 보유 증가 데이터가 없는 종목입니다.")
    else:
        for _, row in inst_df.iterrows():
            st.markdown(f"""
            <div class="metric-card" style="border-left: 3px solid #58a6ff;">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:16px; font-weight:600;">{row['ticker']} {row['name']}</div>
                        <div style="font-size:12px; color:#8b949e;">{row['sector']}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                        <div style="font-size:13px; color:#58a6ff; font-weight:500;">기관 +{row['inst_change']:.2f}%p</div>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:12px; color:#8b949e;">
                    기관 보유 {row['inst_pct']:.1f}% | 내부자매수 {int(row['insider_buy'])}회 | 컨센서스: {row['rec_key']}
                </div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")
st.caption("본 대시보드는 Yahoo Finance 데이터를 기반으로 합니다. 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.")

# 자동 새로고침
st.markdown("""
<script>
    setTimeout(function(){
        window.location.reload();
    }, 30000);
</script>
""", unsafe_allow_html=True)
