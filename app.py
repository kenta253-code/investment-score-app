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


st.title(
    "📈 金利を見れば投資はうまくいく -"
    " 投資環境スコア自動計算アプリ（個別詳細分離版）"
)
st.write(
    "本書（第9章）に基づく米国マクロ経済データの投資環境スコアを自動計算します（A格版とハイイールド版を個別に表示）。"
)

# サイドバーにAPIキー入力欄（保存機能付き）
st.sidebar.header("🔑 設定")
saved_key = load_saved_key()

api_key = ""
if saved_key:
  st.sidebar.success("APIキーが保存されています ✅")
  if not st.sidebar.checkbox("APIキーを変更する"):
    api_key = saved_key

if not api_key:
  entered_key = st.sidebar.text_input(
      "FRED APIキー（32文字）を入力",
      value=saved_key if saved_key else "",
      type="password",
  )
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
    url = (
        f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=400"
    )
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
      baa10y = fetch_fred_data("BAA10Y")  # A格(Baa)社債スプレッド
      twexb = fetch_fred_data("TWEXBGSMTH")
      hy_spread = fetch_fred_data(
          "BAMLH0A0HYM2"
      )  # ハイイールド社債スプレッド

      if not fed or not dgs10 or not baa10y or not twexb or not hy_spread:
        st.error(
            "データの取得に失敗しました。APIキーが正しいか確認してください。"
        )
      else:
        # 共通指標の計算
        fed_diff = fed["latest"] - fed["ago"]
        score1 = 2 if fed_diff <= 0.25 else -2

        spread_level = dgs10["latest"] - fed["latest"]
        score2 = (
            2 if spread_level >= 1.0 else (-2 if spread_level < 0 else 0)
        )

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

        titles = {
            "spring": "🌸 【春】 景気回復局面",
            "summer": "☀️ 【夏】 景気過熱・利上げ局面",
            "autumn": "🍂 【秋】 景気減速局面",
            "late_autumn": "🍁 【晩秋】 冬の一歩手前",
            "winter": "❄️ 【冬】 景気後退局面 (危険水域)",
        }

        # A格版の季節判定
        if total_score_baa <= -6:
          season_baa = "winter"
        elif dgs10_diff < 0 and spread_level < 0.5:
          season_baa = "late_autumn"
        elif total_score_baa <= 0:
          season_baa = "autumn"
        else:
          season_baa = "summer" if total_score_baa > 4 else "spring"

        # ハイイールド版の季節判定
        if total_score_hy <= -6:
          season_hy = "winter"
        elif dgs10_diff < 0 and spread_level < 0.5:
          season_hy = "late_autumn"
        elif total_score_hy <= 0:
          season_hy = "autumn"
        else:
          season_hy = "summer" if total_score_hy > 4 else "spring"

        # ━━━ セクション1：A格（Baa）スプレッド版 ━━━
        st.markdown("---")
        st.header("📌 A格（Baa）スプレッド版 ダッシュボード")

        col1, col2 = st.columns(2)
        with col1:
          st.markdown(
              f"""
                    <div style="padding: 15px; background-color: #262730; border-left: 8px solid #1f77b4; border-radius: 8px; color: #ffffff;">
                        <div style="font-size: 0.8em; color: #b0b0b0;">総合スコア (-10 〜 +10)</div>
                        <div style="font-size: 2.5em; font-weight: 800; color: #ffffff;">{total_score_baa} 点</div>
                    </div>
                    """,
              unsafe_allow_html=True,
          )
        with col2:
          st.markdown(
              f"""
                    <div style="padding: 15px; background-color: #262730; border-radius: 8px; border: 1px solid #404040; color: #ffffff;">
                        <div style="font-size: 0.75em; color: #b0b0b0;">景気サイクル判定</div>
                        <div style="font-size: 1.1em; font-weight: bold; color: #ffffff;">{titles[season_baa]}</div>
                    </div>
                    """,
              unsafe_allow_html=True,
          )

        st.subheader("📊 A格版：5つの項目の詳細内訳")
        df_baa_items = [
            {
                "項目": "1. 政策金利",
                "指標": "FF金利 (%)
