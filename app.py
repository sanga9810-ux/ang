import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="미국주식 수급 대시보드", layout="wide")

st.title("미국주식 수급 대시보드")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST")

DEFAULT_TICKERS = "AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD, NFLX, CRM, AVGO, INTC, QCOM, JPM, BAC, XOM, JNJ, V, MA, DIS"

with st.sidebar:
    st.header("설정")
    tickers_input = st.text_area("관심 종목 (쉼표 구분)", value=DEFAULT_TICKERS, height=80)
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    st.markdown("---")
    st.markdown("**데이터 출처**: Yahoo Finance (15~20분 지연)")

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
        avg_volume_10d = info.get("averageVolume10days", volume)
        volume_ratio = volume / avg_volume_10d if avg_volume_10d > 0 else 1
        volume_spike = volume_ratio >= 2.0
        inst_pct = info.get("heldPercentInstitutions", 0) * 100
        rec_mean = info.get("recommendationMean", 3)
        rec_key = info.get("recommendationKey", "hold")
        target_mean = info.get("targetMeanPrice", current_price)
        num_analysts = info.get("numberOfAnalystOpinions", 0)
        gap_pct = ((target_mean - current_price) / current_price) * 100 if current_price > 0 else 0
        per = info.get("trailingPE", info.get("forwardPE", None))
        pbr = info.get("priceToBook", None)
        roe = info.get("returnOnEquity", None)
        if roe: roe = roe * 100
        days_to_earnings = None
        try:
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                future = ed[ed.index > datetime.now()]
                if not future.empty:
                    earnings_date = future.index[0]
                    days_to_earnings = (earnings_date.date() - datetime.now().date()).days
        except:
            pass
        insider_buy = 0
        try:
            insider_df = stock.insider_transactions
            if insider_df is not None and not insider_df.empty:
                recent = insider_df[insider_df.index >= (datetime.now() - timedelta(days=30))]
                if not recent.empty and "Transaction" in recent.columns:
                    insider_buy = len(recent[recent["Transaction"].str.contains("Buy", case=False, na=False)])
        except:
            pass
        inst_change = 0
        try:
            inst_df = stock.institutional_holders
            if inst_df is not None and not inst_df.empty and "pctChange" in inst_df.columns:
                inst_change = inst_df["pctChange"].sum()
        except:
            pass
        news_list = []
        try:
            raw_news = stock.news
            if raw_news:
                for n in raw_news[:3]:
                    title = n.get("title", "")
                    publisher = n.get("publisher", "")
                    if title:
                        news_list.append(f"{title} | {publisher}")
        except:
            pass
        score = 0
        score += min(inst_change * 50, 20)
        score += insider_buy * 10
        score += (3 - rec_mean) * 5 if rec_mean else 0
        score += (target_mean / current_price - 1) * 20 if current_price > 0 else 0
        return {
            "ticker": ticker, "name": info.get("shortName", ticker), "price": current_price,
            "change_pct": change_pct, "volume": volume, "volume_ratio": volume_ratio,
            "volume_spike": volume_spike, "market_cap": info.get("marketCap", 0),
            "inst_pct": inst_pct, "inst_change": inst_change, "insider_buy": insider_buy,
            "rec_key": rec_key, "target_mean": target_mean, "num_analysts": num_analysts,
            "gap_pct": gap_pct, "per": per, "pbr": pbr, "roe": roe,
            "days_to_earnings": days_to_earnings, "news_list": news_list,
            "score": score, "sector": info.get("sector", "기타"),
        }
    except:
        return None

progress = st.progress(0)
all_data = []
for i, t in enumerate(tickers):
    progress.progress((i + 1) / len(tickers), text=f"{t} 데이터 수집 중...")
    data = fetch_stock_data(t)
    if data:
        all_data.append(data)
progress.empty()

if not all_data:
    st.error("데이터를 가져올 수 없습니다.")
    st.stop()

df = pd.DataFrame(all_data)
REC_MAP = {"strong_buy": "강력매수", "buy": "매수", "hold": "중립", "sell": "매도", "strong_sell": "강력매도"}

cols = st.columns(4)
metrics = [("평균 등락률", f"{df['change_pct'].mean():+.2f}%"), ("상승 종목", f"{(df['change_pct'] > 0).sum()}개 / {len(df)}개"), ("내부자 매수", f"{(df['insider_buy'] > 0).sum()}개"), ("거래량 급증", f"{(df['volume_spike'] == True).sum()}개")]
for col, (label, value) in zip(cols, metrics):
    with col:
        st.metric(label, value)

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["전체 현황", "수급 랭킹", "섹터별", "내부자 매수", "기관 매수"])

with tab1:
    st.subheader("전체 종목 현황")
    for i in range(0, len(df), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(df):
                row = df.iloc[idx]
                with col:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.markdown(f"**{row['ticker']}**  `{row['name']}`")
                        with c2:
                            rec_text = REC_MAP.get(row['rec_key'], row['rec_key'])
                            badges = [f"🟢 {rec_text} ({int(row['num_analysts'])}명)"]
                            if row['volume_spike']:
                                badges.append("🔥 거래량 급증")
                            st.markdown("<br>".join(badges), unsafe_allow_html=True)
                        change_emoji = "🟢" if row['change_pct'] >= 0 else "🔴"
                        st.markdown(f"### ${row['price']:.2f}  {change_emoji} {row['change_pct']:+.2f}%")
                        if row['days_to_earnings'] is not None:
                            if row['days_to_earnings'] <= 7:
                                st.error(f"📅 실적 발표 D-{row['days_to_earnings']}일")
                            elif row['days_to_earnings'] <= 30:
                                st.warning(f"📅 실적 발표 D-{row['days_to_earnings']}일")
                            else:
                                st.info(f"📅 실적 발표 D-{row['days_to_earnings']}일")
                        m1, m2, m3, m4 = st.columns(4)
                        cap_b = row['market_cap'] / 1e9
                        cap_str = f"{cap_b:.1f}B" if cap_b >= 1 else f"{row['market_cap']/1e6:.1f}M"
                        with m1: st.metric("시총", cap_str)
                        with m2: st.metric("PER", f"{row['per']:.1f}" if row['per'] else "N/A")
                        with m3: st.metric("PBR", f"{row['pbr']:.1f}" if row['pbr'] else "N/A")
                        with m4: st.metric("ROE", f"{row['roe']:.1f}%" if row['roe'] else "N/A")
                        c1, c2, c3 = st.columns(3)
                        with c1: st.metric("거래량", f"{row['volume']/1e6:.1f}M", f"{row['volume_ratio']:.1f}x")
                        with c2: st.metric("기관 보유", f"{row['inst_pct']:.1f}%")
                        with c3: st.metric("내부자매수", f"{int(row['insider_buy'])}회" if row['insider_buy'] > 0 else "0회")
                        gap_sign = "+" if row['gap_pct'] > 0 else ""
                        st.metric("목표주가 괴리율", f"{gap_sign}{row['gap_pct']:.1f}%", f"목표 ${row['target_mean']:.0f}")
                        if row['news_list']:
                            with st.expander("📰 최근 뉴스"):
                                for news in row['news_list']:
                                    st.markdown(f"- {news}")

with tab2:
    st.subheader("수급 점수 랭킹")
    df_rank = df.sort_values("score", ascending=False).reset_index(drop=True)
    for i, (_, row) in enumerate(df_rank.iterrows()):
        medal = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}."))
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 2])
            with c1: st.markdown(f"### {medal}")
            with c2:
                st.markdown(f"**{row['ticker']}** `{row['name']}`  |  {row['sector']}")
                per_str = f"{row['per']:.1f}" if row['per'] else "N/A"
                st.markdown(f"PER {per_str} | 기관 {row['inst_pct']:.1f}% | 내부자매수 {int(row['insider_buy'])}회")
                if row['days_to_earnings'] is not None:
                    st.caption(f"실적 D-{row['days_to_earnings']}일")
            with c3:
                change_emoji = "🟢" if row['change_pct'] >= 0 else "🔴"
                st.markdown(f"**${row['price']:.2f}**  {change_emoji} {row['change_pct']:+.2f}%")
                gap_sign = "+" if row['gap_pct'] > 0 else ""
                st.markdown(f"목표대비 {gap_sign}{row['gap_pct']:.1f}%")
                st.markdown(f"**수급점수: {row['score']:.1f}**")

with tab3:
    st.subheader("섹터별 그룹화")
    for sector in sorted(df['sector'].unique()):
        sector_df = df[df['sector'] == sector].sort_values('change_pct', ascending=False)
        with st.expander(f"{sector} ({len(sector_df)}개 종목)", expanded=True):
            for _, row in sector_df.iterrows():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                with c1:
                    st.markdown(f"**{row['ticker']}**")
                    st.caption(row['name'])
                with c2:
                    change_emoji = "🟢" if row['change_pct'] >= 0 else "🔴"
                    st.markdown(f"${row['price']:.2f} {change_emoji} {row['change_pct']:+.2f}%")
                with c3:
                    per_str = f"{row['per']:.1f}" if row['per'] else "N/A"
                    st.markdown(f"PER {per_str} | 기관 {row['inst_pct']:.1f}%")
                with c4:
                    if row['volume_spike']: st.markdown("🔥 **거래량 급증**")
                    if row['days_to_earnings'] is not None and row['days_to_earnings'] <= 14:
                        st.markdown(f"📅 D-{row['days_to_earnings']}일")

with tab4:
    st.subheader("최근 내부자 매수 발생 종목")
    insider_df = df[df['insider_buy'] > 0].sort_values('insider_buy', ascending=False)
    if insider_df.empty:
        st.info("최근 30일 내 내부자 매수 데이터가 없는 종목입니다.")
    else:
        for _, row in insider_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"**{row['ticker']}** `{row['name']}`  |  {row['sector']}")
                    per_str = f"{row['per']:.1f}" if row['per'] else "N/A"
                    st.markdown(f"PER {per_str} | 기관 {row['inst_pct']:.1f}% | 컨센서스: {REC_MAP.get(row['rec_key'], row['rec_key'])}")
                with c2:
                    st.markdown(f"**${row['price']:.2f}**")
                    st.markdown(f"🟢 내부자 매수 **{int(row['insider_buy'])}회**")
                    gap_sign = "+" if row['gap_pct'] > 0 else ""
                    st.markdown(f"목표주가 ${row['target_mean']:.0f} | 괴리 {gap_sign}{row['gap_pct']:.1f}%")

with tab5:
    st.subheader("기관 보유 증가 종목")
    inst_df = df[df['inst_change'] > 0].sort_values('inst_change', ascending=False)
    if inst_df.empty:
        st.info("최근 기관 보유 증가 데이터가 없는 종목입니다.")
    else:
        for _, row in inst_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"**{row['ticker']}** `{row['name']}`  |  {row['sector']}")
                    per_str = f"{row['per']:.1f}" if row['per'] else "N/A"
                    st.markdown(f"PER {per_str} | 내부자매수 {int(row['insider_buy'])}회 | 컨센서스: {REC_MAP.get(row['rec_key'], row['rec_key'])}")
                with c2:
                    st.markdown(f"**${row['price']:.2f}**")
                    st.markdown(f"🔵 기관 보유 **+{row['inst_change']:.2f}%p**")
                    gap_sign = "+" if row['gap_pct'] > 0 else ""
                    st.markdown(f"목표주가 ${row['target_mean']:.0f} | 괴리 {gap_sign}{row['gap_pct']:.1f}%")

st.divider()
st.caption("본 대시보드는 Yahoo Finance 데이터를 기반으로 합니다. 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.")
