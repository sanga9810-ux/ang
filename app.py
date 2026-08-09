import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="미국주식 수급 대시보드 v2", layout="wide", initial_sidebar_state="collapsed")

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
    .badge-alert { background: rgba(248,81,73,0.15); color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
    .badge-flow { background: rgba(47,129,247,0.15); color: #58a6ff; border: 1px solid rgba(47,129,247,0.3); }
    .badge-value { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
    .insider-buy { color: #3fb950; font-weight: 500; }
    .insider-sell { color: #f85149; font-weight: 500; }
    .rank-1 { background: rgba(255,215,0,0.1); border-left: 3px solid #ffd700; }
    .rank-2 { background: rgba(192,192,192,0.1); border-left: 3px solid #c0c0c0; }
    .rank-3 { background: rgba(205,127,50,0.1); border-left: 3px solid #cd7f32; }
    .news-item { font-size: 12px; color: #8b949e; padding: 4px 0; border-bottom: 1px solid #21262d; }
    .news-item:last-child { border-bottom: none; }
    .news-title { color: #58a6ff; }
    .countdown { font-size: 12px; color: #d29922; font-weight: 500; }
    .countdown-soon { font-size: 12px; color: #f85149; font-weight: 600; }
    .countdown-far { font-size: 12px; color: #8b949e; }
    .gap-positive { color: #3fb950; }
    .gap-negative { color: #f85149; }
    div[data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 600 !important; }
    div[data-testid="stMetricDelta"] { font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

st.title("미국주식 수급 대시보드")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST | 30초마다 자동 갱신")

DEFAULT_TICKERS = "AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD, NFLX, CRM, AVGO, INTC, QCOM, JPM, BAC, XOM, JNJ, V, MA, DIS"

with st.sidebar:
    st.header("설정")
    tickers_input = st.text_area("관심 종목 (쉼표 구분)", value=DEFAULT_TICKERS, height=80)
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    st.markdown("---")
    st.markdown("**기능 설명**")
    st.markdown("1. 실적 발표일 카운트다운")
    st.markdown("2. 거래량 급증 뱃지")
    st.markdown("3. 목표주가 대비 괴리율")
    st.markdown("4. 섹터별 그룹화")
    st.markdown("5. 최근 뉴스 헤드라인")
    st.markdown("6. PER / PBR / ROE 지표")

    st.markdown("---")
    st.markdown("**데이터 출처**: Yahoo Finance")
    st.markdown("**지연**: 15~20분 지연")

@st.cache_data(ttl=60)
def fetch_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="30d")

        if hist.empty:
            return None

        current_price = hist["Close"].iloc[-1]
        prev_close = info.get("previousClose", hist["Close"].iloc[-2] if len(hist) > 1 else current_price)
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
        volume = hist["Volume"].iloc[-1]
        avg_volume = info.get("averageVolume", volume)
        avg_volume_10d = info.get("averageVolume10days", avg_volume)

        # 거래량 급증 여부
        volume_ratio = volume / avg_volume_10d if avg_volume_10d > 0 else 1
        volume_spike = volume_ratio >= 2.0

        # 기관/내부자
        inst_pct = info.get("heldPercentInstitutions", 0) * 100
        insider_pct = info.get("heldPercentInsiders", 0) * 100

        # 컨센서스
        rec_mean = info.get("recommendationMean", 3)
        rec_key = info.get("recommendationKey", "hold")
        target_mean = info.get("targetMeanPrice", current_price)
        target_high = info.get("targetHighPrice", current_price)
        target_low = info.get("targetLowPrice", current_price)
        num_analysts = info.get("numberOfAnalystOpinions", 0)

        # 목표주가 괴리율
        gap_pct = ((target_mean - current_price) / current_price) * 100 if current_price > 0 else 0

        # 재무지표
        per = info.get("trailingPE", info.get("forwardPE", None))
        pbr = info.get("priceToBook", None)
        roe = info.get("returnOnEquity", None)
        if roe: roe = roe * 100

        # 실적 발표일
        earnings_date = None
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                earnings_date = cal.index[0] if hasattr(cal.index[0], 'strftime') else None
        except:
            pass

        if not earnings_date:
            try:
                ed = stock.earnings_dates
                if ed is not None and not ed.empty:
                    future = ed[ed.index > datetime.now()]
                    if not future.empty:
                        earnings_date = future.index[0]
            except:
                pass

        days_to_earnings = None
        if earnings_date:
            try:
                if isinstance(earnings_date, str):
                    earnings_date = pd.to_datetime(earnings_date)
                days_to_earnings = (earnings_date.date() - datetime.now().date()).days
            except:
                pass

        # 내부자 거래
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

        # 기관 보유 변화
        inst_change = 0
        try:
            inst_df = stock.institutional_holders
            if inst_df is not None and not inst_df.empty and "pctChange" in inst_df.columns:
                inst_change = inst_df["pctChange"].sum()
        except:
            pass

        # 뉴스
        news_list = []
        try:
            raw_news = stock.news
            if raw_news:
                for n in raw_news[:3]:
                    title = n.get("title", "")
                    publisher = n.get("publisher", "")
                    news_list.append(f"{title} | {publisher}")
        except:
            pass

        # 수급 점수
        score = 0
        score += min(inst_change * 50, 20)
        score += insider_buy * 10
        score -= insider_sell * 5
        score += (3 - rec_mean) * 5 if rec_mean else 0
        score += (target_mean / current_price - 1) * 20 if current_price > 0 else 0

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": current_price,
            "change_pct": change_pct,
            "volume": volume,
            "avg_volume": avg_volume,
            "avg_volume_10d": avg_volume_10d,
            "volume_ratio": volume_ratio,
            "volume_spike": volume_spike,
            "market_cap": info.get("marketCap", 0),
            "inst_pct": inst_pct,
            "insider_pct": insider_pct,
            "inst_change": inst_change,
            "insider_buy": insider_buy,
            "insider_sell": insider_sell,
            "rec_mean": rec_mean,
            "rec_key": rec_key,
            "target_mean": target_mean,
            "target_high": target_high,
            "target_low": target_low,
            "num_analysts": num_analysts,
            "gap_pct": gap_pct,
            "per": per,
            "pbr": pbr,
            "roe": roe,
            "earnings_date": earnings_date,
            "days_to_earnings": days_to_earnings,
            "news_list": news_list,
            "score": score,
            "sector": info.get("sector", "기타"),
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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["전체 현황", "수급 랭킹", "섹터별", "내부자 매수", "기관 매수"])

with tab1:
    st.subheader("전체 종목 현황")

    cols = st.columns(4)
    metrics = [
        ("평균 등락률", f"{df['change_pct'].mean():+.2f}%", "전 종목 평균"),
        ("상승 종목", f"{(df['change_pct'] > 0).sum()}개", f"/{len(df)}개"),
        ("내부자 매수 발생", f"{(df['insider_buy'] > 0).sum()}개", "최근 30일"),
        ("거래량 급증", f"{(df['volume_spike'] == True).sum()}개", "평균 2배 이상"),
    ]
    for col, (label, value, help_text) in zip(cols, metrics):
        with col:
            st.metric(label, value, help=help_text)

    st.markdown("---")

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

                    # 실적 카운트다운
                    countdown_html = ""
                    if row['days_to_earnings'] is not None:
                        if row['days_to_earnings'] <= 7:
                            countdown_html = f'<span class="countdown-soon">실적 D-{row["days_to_earnings"]}일</span>'
                        elif row['days_to_earnings'] <= 30:
                            countdown_html = f'<span class="countdown">실적 D-{row["days_to_earnings"]}일</span>'
                        else:
                            countdown_html = f'<span class="countdown-far">실적 D-{row["days_to_earnings"]}일</span>'

                    # 거래량 급증 뱃지
                    spike_html = ""
                    if row['volume_spike']:
                        spike_html = '<span class="badge badge-flow">거래량 급증</span>'

                    # 목표주가 괴리율
                    gap_class = "gap-positive" if row['gap_pct'] > 0 else "gap-negative"
                    gap_sign = "+" if row['gap_pct'] > 0 else ""

                    # 재무지표
                    per_str = f"{row['per']:.1f}" if row['per'] else "N/A"
                    pbr_str = f"{row['pbr']:.1f}" if row['pbr'] else "N/A"
                    roe_str = f"{row['roe']:.1f}%" if row['roe'] else "N/A"

                    # 뉴스
                    news_html = ""
                    if row['news_list']:
                        news_items = "<br>".join([f'<span class="news-title">{n.split(" | ")[0]}</span> <span style="color:#484f58;">| {n.split(" | ")[1]}</span>' for n in row['news_list']])
                        news_html = f'<div style="margin-top:8px; padding-top:8px; border-top:1px solid #21262d;">{news_items}</div>'

                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:16px; font-weight:600;">{row['ticker']}</span>
                            <div style="display:flex; gap:4px;">
                                <span class="badge {rec_badge}">{rec_text}</span>
                                {spike_html}
                            </div>
                        </div>
                        <div style="font-size:12px; color:#8b949e; margin-bottom:4px;">{row['name']} | {row['sector']}</div>
                        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px;">
                            <span class="metric-value">${row['price']:.2f}</span>
                            <span class="{change_color}">{change_sign}{row['change_pct']:.2f}%</span>
                        </div>
                        <div style="margin-top:8px; font-size:12px; color:#8b949e; display:grid; grid-template-columns:1fr 1fr; gap:4px;">
                            <div>시총: {cap_str}</div>
                            <div>거래량: {row['volume']/1e6:.1f}M ({row['volume_ratio']:.1f}x)</div>
                            <div>PER: {per_str} | PBR: {pbr_str}</div>
                            <div>ROE: {roe_str}</div>
                            <div>기관: {row['inst_pct']:.1f}%</div>
                            <div>내부자매수: <span class="{'insider-buy' if row['insider_buy']>0 else ''}">{int(row['insider_buy'])}회</span></div>
                            <div>목표주가: ${row['target_mean']:.0f}</div>
                            <div class="{gap_class}">괴리율: {gap_sign}{row['gap_pct']:.1f}%</div>
                        </div>
                        <div style="margin-top:6px;">{countdown_html}</div>
                        {news_html}
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

        spike_badge = '<span class="badge badge-flow">거래량 급증</span>' if row['volume_spike'] else ''

        gap_class = "gap-positive" if row['gap_pct'] > 0 else "gap-negative"
        gap_sign = "+" if row['gap_pct'] > 0 else ""

        per_str = f"{row['per']:.1f}" if row['per'] else "N/A"

        countdown_html = ""
        if row['days_to_earnings'] is not None:
            if row['days_to_earnings'] <= 7:
                countdown_html = f'<span class="countdown-soon">D-{row["days_to_earnings"]}일</span>'
            else:
                countdown_html = f'<span class="countdown">D-{row["days_to_earnings"]}일</span>'

        st.markdown(f"""
        <div class="metric-card {rank_class}" style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="font-size:20px; font-weight:700; width:32px; text-align:center;">{i+1}</div>
                <div>
                    <div style="font-size:15px; font-weight:600;">{row['ticker']} <span style="font-size:12px; color:#8b949e;">{row['name']}</span></div>
                    <div style="font-size:12px; color:#8b949e;">{row['sector']} | PER {per_str} | 기관 {row['inst_pct']:.1f}% | 내부자매수 {int(row['insider_buy'])}회 {countdown_html}</div>
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                <div style="font-size:13px; {change_color}">{change_sign}{row['change_pct']:.2f}%</div>
                <div style="font-size:12px; {gap_class}">목표대비 {gap_sign}{row['gap_pct']:.1f}%</div>
                <div style="font-size:12px; color:#58a6ff; font-weight:500;">수급점수: {row['score']:.1f}</div>
                {spike_badge}
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab3:
    st.subheader("섹터별 그룹화")
    sectors = sorted(df['sector'].unique())

    for sector in sectors:
        sector_df = df[df['sector'] == sector].sort_values('change_pct', ascending=False)
        with st.expander(f"{sector} ({len(sector_df)}개 종목)", expanded=True):
            cols = st.columns(min(len(sector_df), 4))
            for idx, (_, row) in enumerate(sector_df.iterrows()):
                col = cols[idx % 4]
                with col:
                    change_color = "metric-change-up" if row['change_pct'] >= 0 else "metric-change-down"
                    change_sign = "+" if row['change_pct'] >= 0 else ""

                    spike_html = '<span class="badge badge-flow">급증</span>' if row['volume_spike'] else ''

                    countdown_html = ""
                    if row['days_to_earnings'] is not None:
                        if row['days_to_earnings'] <= 7:
                            countdown_html = f'<span class="countdown-soon">D-{row["days_to_earnings"]}</span>'
                        else:
                            countdown_html = f'<span class="countdown">D-{row["days_to_earnings"]}</span>'

                    per_str = f"{row['per']:.1f}" if row['per'] else "N/A"

                    st.markdown(f"""
                    <div class="metric-card" style="padding:10px;">
                        <div style="font-size:14px; font-weight:600;">{row['ticker']}</div>
                        <div style="font-size:11px; color:#8b949e;">{row['name']}</div>
                        <div style="font-size:16px; font-weight:600; margin:4px 0;">${row['price']:.2f}</div>
                        <div class="{change_color}">{change_sign}{row['change_pct']:.2f}%</div>
                        <div style="font-size:11px; color:#8b949e; margin-top:4px;">PER {per_str} | 기관 {row['inst_pct']:.1f}%</div>
                        <div style="margin-top:4px;">{spike_html} {countdown_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

with tab4:
    st.subheader("최근 내부자 매수 발생 종목")
    insider_df = df[df['insider_buy'] > 0].sort_values('insider_buy', ascending=False)

    if insider_df.empty:
        st.info("최근 30일 내 내부자 매수 데이터가 없는 종목입니다.")
    else:
        for _, row in insider_df.iterrows():
            gap_class = "gap-positive" if row['gap_pct'] > 0 else "gap-negative"
            gap_sign = "+" if row['gap_pct'] > 0 else ""
            per_str = f"{row['per']:.1f}" if row['per'] else "N/A"

            st.markdown(f"""
            <div class="metric-card" style="border-left: 3px solid #3fb950;">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:16px; font-weight:600;">{row['ticker']} {row['name']}</div>
                        <div style="font-size:12px; color:#8b949e;">{row['sector']} | PER {per_str}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                        <div style="font-size:13px; color:#3fb950; font-weight:500;">내부자 매수 {int(row['insider_buy'])}회</div>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:12px; color:#8b949e;">
                    기관 보유 {row['inst_pct']:.1f}% | 컨센서스: {row['rec_key']} | 목표주가 ${row['target_mean']:.0f} | <span class="{gap_class}">괴리 {gap_sign}{row['gap_pct']:.1f}%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

with tab5:
    st.subheader("기관 보유 증가 종목")
    inst_df = df[df['inst_change'] > 0].sort_values('inst_change', ascending=False)

    if inst_df.empty:
        st.info("최근 기관 보유 증가 데이터가 없는 종목입니다.")
    else:
        for _, row in inst_df.iterrows():
            gap_class = "gap-positive" if row['gap_pct'] > 0 else "gap-negative"
            gap_sign = "+" if row['gap_pct'] > 0 else ""
            per_str = f"{row['per']:.1f}" if row['per'] else "N/A"

            st.markdown(f"""
            <div class="metric-card" style="border-left: 3px solid #58a6ff;">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:16px; font-weight:600;">{row['ticker']} {row['name']}</div>
                        <div style="font-size:12px; color:#8b949e;">{row['sector']} | PER {per_str}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:18px; font-weight:600;">${row['price']:.2f}</div>
                        <div style="font-size:13px; color:#58a6ff; font-weight:500;">기관 +{row['inst_change']:.2f}%p</div>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:12px; color:#8b949e;">
                    기관 보유 {row['inst_pct']:.1f}% | 내부자매수 {int(row['insider_buy'])}회 | 컨센서스: {row['rec_key']} | <span class="{gap_class}">괴리 {gap_sign}{row['gap_pct']:.1f}%</span>
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
