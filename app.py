from datetime import datetime
import json
import os
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="投資環境スコア・ダッシュボード", layout="wide")

# APIキー永続化のためのファイル名
KEY_FILE = "apikey.json"

def load_saved_key():
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "r") as f:
                data = json.load(f)
                return data.get("api_key", "")
        except:
            return ""
    return ""

def save_key(key):
    with open(KEY_FILE, "w") as f:
        json.dump({"api_key": key}, f)

st.title("📈 投資環境スコア判定アプリ")
st.write("米国マクロ経済データの投資環境スコアを自動計算します（A格版およびハイイールド版）。")

# サイドバーにAPIキー入力欄（保存機能付き）
st.sidebar.header("🔑 設定")
saved_key = load_saved_key()

api_key = ""
if saved_key:
    st.sidebar.success("APIキーが保存されています ✅")
    if not st.sidebar.checkbox("APIキーを変更する"):
        api_key = saved_key

if not api_key:
    entered_key = st.sidebar.text_input("FRED APIキー（32文字）を入力", value=saved_key if saved_key else "", type="password")
    if st.sidebar.button("APIキーを保存する"):
        if entered_key:
            save_key(entered_key)
            st.sidebar.success("保存しました！画面を更新してください。")
            api_key = entered_key
        else:
            st.sidebar.warning("キーを入力してください。")

if not api_key:
    st.warning("左側のサイドバーにFREDのAPIキーを入力して保存してください。")
    st.info("※APIキーをお持ちでない場合は、セントルイス連銀のサイトから無料で取得できます。")
else:
    def fetch_fred_data(series_id):
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=400"
        res = requests.get(url).json()
        if "observations" not in res: return None
        obs = [o for o in res["observations"] if o["value"] != "."]
        if not obs: return None
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
            baa10y = fetch_fred_data("BAA10Y")       # A格(Baa)社債スプレッド
            twexb = fetch_fred_data("TWEXBGSMTH")
            hy_spread = fetch_fred_data("BAMLH0A0HYM2") # ハイイールド社債スプレッド

            if not fed or not dgs10 or not baa10y or not twexb or not hy_spread:
                st.error("データの取得に失敗しました。APIキーが正しいか確認してください。")
            else:
                # 共通指標の計算
                fed_diff = fed["latest"] - fed["ago"]
                score1 = 2 if fed_diff <= 0.25 else -2
                
                spread_level = dgs10["latest"] - fed["latest"]
                score2 = 2 if spread_level >= 1.0 else (-2 if spread_level < 0 else 0)
                
                dgs10_diff = dgs10["latest"] - dgs10["ago"]
                score3 = 2 if dgs10_diff >= 0 else -2
                
                usd_ratio = twexb["latest"] / twexb["ago"]
                score5 = 2 if usd_ratio <= 1.0 else -2

                # 1. A格（Baa）版の計算
                baa_diff = baa10y["latest"] - baa10y["ago"]
                score4_baa = 2 if baa_diff <= 0 else -2
                total_score_baa = score1 + score2 + score3 + score4_baa + score5

                # 2. ハイイールド版の計算
                hy_diff = hy_spread["latest"] - hy_spread["ago"]
                score4_hy = 2 if hy_diff <= 0 else -2
                total_score_hy = score1 + score2 + score3 + score4_hy + score5

                # 季節判定の定義
                titles = {
                    "spring": "🌸 【春】 景気回復局面", 
                    "summer": "☀️ 【夏】 景気過熱・利上げ局面", 
                    "autumn": "🍂 【秋】 景気減速局面", 
                    "late_autumn": "🍁 【晩秋】 冬の一歩手前", 
                    "winter": "❄️ 【冬】 景気後退局面 (危険水域)"
                }

                # A格版の季節判定
                if total_score_baa <= -6: season_baa = "winter"
                elif dgs10_diff < 0 and spread_level < 0.5: season_baa = "late_autumn"
                elif total_score_baa <= 0: season_baa = "autumn"
                else: season_baa = "summer" if total_score_baa > 4 else "spring"

                # ハイイールド版の季節判定
                if total_score_hy <= -6: season_hy = "winter"
                elif dgs10_diff < 0 and spread_level < 0.5: season_hy = "late_autumn"
                elif total_score_hy <= 0: season_hy = "autumn"
                else: season_hy = "summer" if total_score_hy > 4 else "spring"

                # ━━━ 画面上部：2つのスコアを左右に並べて表示 ━━━
                col_baa, col_hy = st.columns(2)

                with col_baa:
                    st.markdown("### 📌 A格（Baa）スプレッド版")
                    st.markdown(f"""
                    <div style="padding: 15px; background-color: #262730; border-left: 8px solid #1f77b4; border-radius: 8px; color: #ffffff; margin-bottom: 10px;">
                        <div style="font-size: 0.8em; color: #b0b0b0;">総合スコア (-10 〜 +10)</div>
                        <div style="font-size: 2.5em; font-weight: 800; color: #ffffff;">{total_score_baa} 点</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="padding: 12px; background-color: #262730; border-radius: 8px; border: 1px solid #404040; color: #ffffff;">
                        <div style="font-size: 0.75em; color: #b0b0b0;">景気サイクル判定</div>
                        <div style="font-size: 1.1em; font-weight: bold; color: #ffffff;">{titles[season_baa]}</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_hy:
                    st.markdown("### 📌 ハイイールドスプレッド版")
                    st.markdown(f"""
                    <div style="padding: 15px; background-color: #262730; border-left: 8px solid #ff7f0e; border-radius: 8px; color: #ffffff; margin-bottom: 10px;">
                        <div style="font-size: 0.8em; color: #b0b0b0;">総合スコア (-10 〜 +10)</div>
                        <div style="font-size: 2.5em; font-weight: 800; color: #ffffff;">{total_score_hy} 点</div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="padding: 12px; background-color: #262730; border-radius: 8px; border: 1px solid #404040; color: #ffffff;">
                        <div style="font-size: 0.75em; color: #b0b0b0;">景気サイクル判定</div>
                        <div style="font-size: 1.1em; font-weight: bold; color: #ffffff;">{titles[season_hy]}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")

                # ━━━ 5つの項目の詳細内訳 (A格/Baa版) ━━━
                st.subheader("📊 5つの項目の詳細内訳 (A格/Baa社債版)")
                df_data_baa = [
                    {"項目": "1. 政策金利", "指標": "FF金利 (%)", "直近値": fed["latest"], "1年前": fed["ago"], "変化 (前年差)": f"{fed_diff:+.2f}", "個別スコア": score1, "判定の理由": "利上げ局面は抑制" if score1 == -2 else "緩和・安定"},
                    {"項目": "2. 長短金利差", "指標": "10年債 - 政策金利 (%)", "直近値": spread_level, "1年前": "-", "変化 (前年差)": "-", "個別スコア": score2, "判定の理由": "逆イールド警戒" if score2 == -2 else ("正常サイクル" if score2 == 2 else "中立")},
                    {"項目": "3. 長期金利", "指標": "10年国債利回り (%)", "直近値": dgs10["latest"], "1年前": dgs10["ago"], "変化 (前年差)": f"{dgs10_diff:+.2f}", "個別スコア": score3, "判定の理由": "成長織り込み上昇" if score3 == 2 else "減速先取り低下"},
                    {"項目": "4. 社債スプレッド", "指標": "Baa社債 - 10年債 (%)", "直近値": baa10y["latest"], "1年前": baa10y["ago"], "変化 (前年差)": f"{baa_diff:+.2f}", "個別スコア": score4_baa, "判定の理由": "健全" if score4_baa == 2 else "信用リスク上昇・警戒"},
                    {"項目": "5. 米ドル指数", "指標": "名目実効為替レート", "直近値": twexb["latest"], "1年前": twexb["ago"], "変化 (前年比)": f"{usd_ratio:.2f}倍", "個別スコア": score5, "判定の理由": "グローバル寛容" if score5 == 2 else "引き締め圧力"}
                ]
                st.dataframe(pd.DataFrame(df_data_baa), use_container_width=True)

                # ━━━ 5つの項目の詳細内訳 (ハイイールド版) ━━━
                st.markdown("---")
                st.subheader("📊 5つの項目の詳細内訳 (ハイイールド社債版)")
                df_data_hy = [
                    {"項目": "1. 政策金利", "指標": "FF金利 (%)", "直近値": fed["latest"], "1年前": fed["ago"], "変化 (前年差)": f"{fed_diff:+.2f}", "個別スコア": score1, "判定の理由": "利上げ局面は抑制" if score1 == -2 else "緩和・安定"},
                    {"項目": "2. 長短金利差", "指標": "10年債 - 政策金利 (%)", "直近値": spread_level, "1年前": "-", "変化 (前年差)": "-", "個別スコア": score2, "判定の理由": "逆イールド警戒" if score2 == -2 else ("正常サイクル" if score2 == 2 else "中立")},
                    {"項目": "3. 長期金利", "指標": "10年国債利回り (%)", "直近値": dgs10["latest"], "1年前": dgs10["ago"], "変化 (前年差)": f"{dgs10_diff:+.2f}", "個別スコア": score3, "判定の理由": "成長織り込み上昇" if score3 == 2 else "減速先取り低下"},
                    {"項目": "4. ハイイールドスプレッド", "指標": "ICE BofA US HY OAS (%)", "直近値": hy_spread["latest"], "1年前": hy_spread["ago"], "変化 (前年差)": f"{hy_diff:+.2f}", "個別スコア": score4_hy, "判定の理由": "健全" if score4_hy == 2 else "リスク拡大・警戒信号"},
                    {"項目": "5. 米ドル指数", "指標": "名目実効為替レート", "直近値": twexb["latest"], "1年前": twexb["ago"], "変化 (前年比)": f"{usd_ratio:.2f}倍", "個別スコア": score5, "判定の理由": "グローバル寛容" if score5 == 2 else "引き締め圧力"}
                ]
                st.dataframe(pd.DataFrame(df_data_hy), use_container_width=True)

                st.markdown("---")
                with st.expander("📖 景気局面（四季）の全体像と解説（本書のまとめ）"):
                    st.markdown("本書『金利を見れば投資はうまくいく』における、景気サイクルの基本的な考え方です。")
                    st.table(pd.DataFrame({
                        "季節": ["春", "夏", "秋", "晩秋", "冬"],
                        "景況感": ["回復", "過熱", "減速", "冬支度", "後退"],
                        "金利データの特徴": ["金利横ばい", "利上げ開始", "長期金利低下", "長短金利差急縮小", "利下げ開始"],
                        "投資の心構え": ["株式仕込み時", "上昇を享受", "資産配分見直し", "現金化・防御", "仕込みの準備"]
                    }))
                    st.markdown("**投資の心得（本書より）**\n1. **金利は“売買”ではなく“使う”**：現状を客観的に捉えるために使いましょう。\n2. **全ては循環する**：軸をぶらさず、サイクルの法則に従って冷静に行動することが、大失敗を防ぐ唯一の道です。")
