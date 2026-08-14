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


st.title("📈 金利を見れば投資はうまくいく - 投資環境スコア自動計算アプリ")
st.write(
    "本書（第9章）に基づく米国マクロ経済データの投資環境スコアを自動計算・判定します"
    "。"
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
  # データ取得関数
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
      baa10y = fetch_fred_data("BAA10Y")
      twexb = fetch_fred_data("TWEXBGSMTH")

      if not fed or not dgs10 or not baa10y or not twexb:
        st.error(
            "データの取得に失敗しました。APIキーが正しいか確認してください。"
        )
      else:
        # スコア計算ロジック
        fed_diff = fed["latest"] - fed["ago"]
        score1 = 2 if fed_diff <= 0.25 else -2

        spread_level = dgs10["latest"] - fed["latest"]
        score2 = (
            2 if spread_level >= 1.0 else (-2 if spread_level < 0 else 0)
        )

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
          st.metric(
              label="現在の投資環境総合スコア (-10 〜 +10)",
              value=f"{total_score} 点",
          )

        # 季節判定とアドバイスの決定
        season_key = "spring"
        if total_score <= -6:
          season_key = "winter"
        elif dgs10_diff < 0 and spread_level < 0.5:
          season_key = "late_autumn"
        elif total_score <= 0:
          season_key = "autumn"
        else:
          season_key = "summer"  # 基本は春か夏

        with col2:
          titles = {
              "spring": "🌸 【春】 景気回復局面",
              "summer": "☀️ 【夏】 景気過熱・利上げ局面",
              "autumn": "🍂 【秋】 景気減速局面",
              "late_autumn": "🍁 【晩秋】 冬の一歩手前",
              "winter": "❄️ 【冬】 景気後退局面 (危険水域)",
          }
          st.metric(label="現在の景気サイクル判定", value=titles[season_key])

        # 季節ごとのアドバイス表示枠
        st.markdown("---")
        st.subheader("💡 現在の季節における投資判断アドバイス")

        advices = {
            "spring": {
                "caution": (
                    "中央銀行はまだ金融政策の「様子見」を続けており[cite: 2],"
                    " 景気が本当に底を打ったのか慎重に見極める期間です。"
                ),
                "action": (
                    "景気回復初期に優位に立つ「REIT」や「ハイイールド社債」、"
                    "そして「株式」の仕込み（買い場）を検討するタイミングです"
                    "[cite: 2]。"
                ),
            },
            "summer": {
                "caution": (
                    "本格的な利上げ（金融引き締め）が進行し[cite: 2],"
                    " マーケットは好調に見えますが、長短金利差の縮小（フラットニング）が始まっていないか警戒が必要です"
                    "[cite: 2]。"
                ),
                "action": (
                    "株高の恩恵を受けつつも、やがて訪れる「秋（減速）」のサイン（長短金利差の縮小や逆転現象）を見逃さないよう金利データを注視します"
                    "[cite: 2]。"
                ),
            },
            "autumn": {
                "caution": (
                    "長期金利の低下や長短金利差の縮小が進み、景気減速のサインが点灯します"
                    "[cite: 2]。株価が高く見えても、レバレッジ局面の罠（株高と社債スプレッド拡大の乖離）に注意が必要です"
                    "[cite: 2]。"
                ),
                "action": (
                    "本書が説く通り**「冬支度だけは忘れないで！！」**。株から安全な債券へ、新興国から先進国へと資産配分の見直しを検討し始めます"
                    "[cite: 2]。"
                ),
            },
            "late_autumn": {
                "caution": (
                    "長期金利が前年比で低下し、長短金利差が0.5%を割込むなど"
                    "[cite: 2]、景気後退（冬）が目前に迫っている危険なサインです"
                    "[cite: 2]。"
                ),
                "action": (
                    "資産配分見直しの最終局面です[cite: 2]。下落に強い商品（公益株や債券など）への入れ替えや、一部を現金化して本格的な下落に備えます"
                    "[cite: 2]。"
                ),
            },
            "winter": {
                "caution": (
                    "ほぼ全ての市場が下落する避けられない下落局面です。恐怖に負けたパニック売りを避け、「いかに損を少なくするか」を心がけます"
                    "[cite: 2]。"
                ),
                "action": (
                    "投資環境スコアが底（ボトム）を打つのを待ち、次の「春（景気回復）」に向けた優良商品の選定や仕込みの準備を行います"
                    "[cite: 2]。"
                ),
            },
        }

        current_advice = advices[season_key]
        st.info(f"**⚠️ 注意すべきこと:**\n\n{current_advice['caution']}")
        st.success(f"**🛠️ 準備・実行すべきこと:**\n\n{current_advice['action']}")

        st.markdown("---")
        st.subheader("📊 5つの項目の詳細内訳")

        
          # 📊 5つの項目の詳細内訳（ここを書き換えてください）
        df_data = [
            {
                "項目": "1. 政策金利", "指標": "FF金利 (%)", "直近値": fed["latest"], "1年前": fed["ago"], 
                "変化 (前年差/比)": f"{fed_diff:+.2f}", "個別スコア": score1,
                "判定の理由": "利上げ局面は景気抑制のサイン" if score1 == -2 else "緩和・安定局面"
            },
            {
                "項目": "2. 長短金利差", "指標": "10年債 - 政策金利 (%)", "直近値": spread_level, "1年前": "-", 
                "変化 (前年差/比)": "-", "個別スコア": score2,
                "判定の理由": "景気後退の警告信号 (逆イールド)" if score2 == -2 else ("成長サイクル正常" if score2 == 2 else "中立")
            },
            {
                "項目": "3. 長期金利", "指標": "10年国債利回り (%)", "直近値": dgs10["latest"], "1年前": dgs10["ago"], 
                "変化 (前年差/比)": f"{dgs10_diff:+.2f}", "個別スコア": score3,
                "判定の理由": "経済成長を織り込む上昇" if score3 == 2 else "景気減速を先取りする低下"
            },
            {
                "項目": "4. 社債スプレッド", "指標": "Baa社債 - 10年債 (%)", "直近値": baa10y["latest"], "1年前": baa10y["ago"], 
                "変化 (前年差/比)": f"{baa_diff:+.2f}", "個別スコア": score4,
                "判定の理由": "企業信用は健全" if score4 == 2 else "信用リスク上昇・警戒信号"
            },
            {
                "項目": "5. 米ドル指数", "指標": "名目実効為替レート", "直近値": twexb["latest"], "1年前": twexb["ago"], 
                "変化 (前年差/比)": f"{usd_ratio:.2f}倍", "個別スコア": score5,
                "判定の理由": "グローバル流動性に寛容" if score5 == 2 else "世界的な資金引き締め圧力"
            },
        ]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
     
