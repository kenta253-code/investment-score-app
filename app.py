import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="投資環境スコア・ダッシュボード", layout="wide")

st.title("📈 金利を見れば投資はうまくいく - 投資環境スコア自動計算アプリ")
st.write("本書（第9章）に基づく米国マクロ経済データの投資環境スコアを自動計算・判定します。")

# サイドバーにAPIキー入力欄（安全設計）
st.sidebar.header("🔑 設定")
api_key = st.sidebar.text_input("FRED APIキー（32文字）を入力", type="password")

if not api_key:
    st.warning("左側のサイドバーにFREDのAPIキーを入力してください。")
    st.info("※APIキーをお持ちでない場合は、セントルイス連銀のサイトから無料で取得できます。")
else:
    # データ取得関数
    def fetch_fred_data(series_id):
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=400"
        res = requests.get(url).json()
        if "observations" not in res:
            return None
        obs = [o for o in res["observations"] if o["value"] != "."]
        if not obs:
            return None
        
        latest = float(obs[0]["value"])
        latest_date = datetime.strptime(obs[0]["date"], "%Y-%m-%d")
        target_date = latest_date.replace(year=latest_date.year - 1)
        
        ago = float(obs[-1]["value"])
        min_diff = float("inf")
        for o in obs:
            d = datetime.strptime(o["date"], "%Y-%m-%d")
            diff = abs((d - target_date).days)
            if diff < min_diff:
                min_diff = diff
                ago = float(o["value"])
        return {"latest": latest, "ago": ago}

    if st.button("🔄 最新データを取得してスコアを計算する", type="primary"):
        with st.spinner("FREDから最新データを取得・分析中..."):
            fed = fetch_fred_data("FEDFUNDS")
            dgs10 = fetch_fred_data("DGS10")
            baa10y = fetch_fred_data("BAA10Y")
            twexb = fetch_fred_data("TWEXBGSMTH")

            if not fed or not dgs10 or not baa10y or not twexb:
                st.error("データの取得に失敗しました。APIキーが正しいか確認してください。")
            else:
                # スコア計算ロジック
                fed_diff = fed["latest"] - fed["ago"]
                score1 = 2 if fed_diff <= 0.25 else -2

                spread_level = dgs10["latest"] - fed["latest"]
                score2 = 2 if spread_level >= 1.0 else (-2 if spread_level < 0 else 0)

                dgs10_diff = dgs10["latest"] - dgs10["ago"]
                score3 = 2 if dgs10_diff >= 0 else -2

                baa_diff = baa10y["latest"] - baa10y["ago"]
                score4 = 2 if baa_diff <= 0 else -2

                usd_ratio = twexb["latest"] / twexb["ago"]
                score5 = 2 if usd_ratio <= 1.0 else -2

                total_score = score1 + score2 + score3 + score4 + score5

                # 画面表示（プロっぽいメトリクスカード）
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric(label="現在の投資環境総合スコア (-10 〜 +10)", value=f"{total_score} 点")
                
                with col2:
                    season = "【春・夏】 景気回復・拡大局面"
                    if total_score <= -6:
                        season = "【冬】 景気後退局面 (危険水域) ⚠️"
                    elif dgs10_diff < 0 and spread_level < 0.5:
                        season = "【晩秋】 冬の一歩手前 (資産配分見直し推奨) 🍁"
                    elif total_score <= 0:
                        season = "【秋】 景気減速局面"
                    st.metric(label="現在の景気サイクル判定", value=season)

                st.markdown("---")
                st.subheader("📊 5つの項目の詳細内訳")
                
                df_data = [
                    {"項目": "1. 政策金利", "指標": "FF金利 (%)", "直近値": fed["latest"], "1年前": fed["ago"], "変化 (前年差/比)": f"{fed_diff:+.2f}", "個別スコア": score1},
                    {"項目": "2. 長短金利差", "指標": "10年債 - 政策金利 (%)", "直近値": spread_level, "1年前": "-", "変化 (前年差/比)": "-", "個別スコア": score2},
                    {"項目": "3. 長期金利", "指標": "10年国債利回り (%)", "直近値": dgs10["latest"], "1年前": dgs10["ago"], "変化 (前年差/比)": f"{dgs10_diff:+.2f}", "個別スコア": score3},
                    {"項目": "4. 社債スプレッド", "指標": "Baa社債 - 10年債 (%)", "直近値": baa10y["latest"], "1年前": baa10y["ago"], "変化 (前年差/比)": f"{baa_diff:+.2f}", "個別スコア": score4},
                    {"項目": "5. 米ドル指数", "指標": "名目実効為替レート", "直近値": twexb["latest"], "1年前": twexb["ago"], "変化 (前年差/比)": f"{usd_ratio:.2f}倍", "個別スコア": score5},
                ]
                st.dataframe(pd.DataFrame(df_data), use_container_width=True)
