import streamlit as st
import requests
import re
import random
from PIL import Image

# ------------------------
# ページ設定
# ------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

# ------------------------
# 背景・スタイル（オプション）
# ------------------------
st.markdown(
    """
    <style>
    /* ページ全体の背景色 */
    body {
        background-color: #f0f2f6;
    }

    /* 会話表示用のコンテナ */
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px;
        background-color: #ffffffaa;
    }

    /* 固定フッターの配置 */
    .fixed-footer {
        position: sticky;
        bottom: 0;
        background-color: #ffffff;
        padding: 10px 0;
        margin-top: 20px;
        border-top: 1px solid #ccc;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------
# ユーザーの名前入力（画面上部）
# ------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")

# ------------------------
# 定数／設定
# ------------------------
API_KEY = st.secrets["general"]["api_key"]  # .streamlit/secrets.toml で設定
MODEL_NAME = "gemini-2.0-flash-001"         # 必要に応じて変更
CHAR_NAMES = ["ゆかり", "しんや", "みのる"]

# ------------------------
# 画像の読み込み
# ------------------------
try:
    img_user = Image.open("avatars/user.png")
    img_yukari = Image.open("avatars/yukari.png")
    img_shinya = Image.open("avatars/shinya.png")
    img_minoru = Image.open("avatars/minoru.png")
except Exception as e:
    st.error(f"画像読み込みエラー: {e}")
    # 画像が読み込めなかった場合のフォールバック
    img_user = "👤"
    img_yukari = "🌸"
    img_shinya = "🌊"
    img_minoru = "🍀"

avatar_dict = {
    "ユーザー": img_user,
    "ゆかり": img_yukari,
    "しんや": img_shinya,
    "みのる": img_minoru
}

# ------------------------
# 各種関数
# ------------------------
def analyze_question(question: str) -> int:
    """
    ユーザの発言から感情スコアを算出している例。
    ポジティブ要素ならスコアプラス、ロジカルな要素ならマイナス...など用途に応じて調整。
    """
    score = 0
    keywords_emotional = ["困った", "悩み", "苦しい", "辛い"]
    keywords_logical = ["理由", "原因", "仕組み", "方法"]
    for word in keywords_emotional:
        if re.search(word, question):
            score += 1
    for word in keywords_logical:
        if re.search(word, question):
            score -= 1
    return score

def adjust_parameters(question: str) -> dict:
    """
    感情スコアに応じて、それぞれのキャラクターの"性格・口調"を変える例。
    """
    score = analyze_question(question)
    params = {}
    # ゆかり: 常に明るくはっちゃけた
    params["ゆかり"] = {
        "style": "明るくはっちゃけた", 
        "detail": "楽しい雰囲気で元気な回答"
    }
    # しんや & みのる はスコアで分岐
    if score > 0:
        params["しんや"] = {"style": "共感的", "detail": "心情を重視した解説"}
        params["みのる"] = {"style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        params["しんや"] = {"style": "分析的", "detail": "データや事実を踏まえた説明"}
        params["みのる"] = {"style": "客観的", "detail": "中立的な視点からの考察"}
    return params

def remove_json_artifacts(text: str) -> str:
    """
    余計なJSON表現などを除去するための例。
    必要に応じて調整可。
    """
    if not isinstance(text, str):
        text = str(text) if text else ""
    pattern = r"'parts': \[\{'text':.*?\}\], 'role': 'model'"
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini_api(prompt: str) -> str:
    """
    GeminiのAPIをコールし、生成結果をテキストで返す。
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
    except Exception as e:
        return f"エラー: リクエスト送信時に例外が発生しました -> {str(e)}"

    if response.status_code != 200:
        return f"エラー: ステータスコード {response.status_code} -> {response.text}"

    try:
        rjson = response.json()
        candidates = rjson.get("candidates", [])
        if not candidates:
            return "回答が見つかりませんでした。(candidatesが空)"
        candidate0 = candidates[0]
        content_val = candidate0.get("content", "")
        if isinstance(content_val, dict):
            parts = content_val.get("parts", [])
            content_str = " ".join([p.get("text", "") for p in parts])
        else:
            content_str = str(content_val)

        content_str = content_str.strip()
        if not content_str:
            return "回答が見つかりませんでした。(contentが空)"

        return remove_json_artifacts(content_str)

    except Exception as e:
        return f"エラー: レスポンス解析に失敗しました -> {str(e)}"

def generate_three_person_conversation(user_input: str, entire_conversation: str) -> str:
    """
    毎回のユーザー発言を受けて、3人の会話を生成する。
    - entire_conversation: これまでの会話 (全員の発言) をテキストで保持
    """
    # 今回の発言からパラメータを生成
    persona_params = adjust_parameters(user_input)

    # current_user (ユーザー名) はUIから入力済み
    current_user_name = st.session_state.get("user_name", "ユーザー")

    # ここで実際のプロンプトを組み立てる
    prompt = f"ユーザー({current_user_name})の最新メッセージ: {user_input}\n\n"
    prompt += "これまでの会話:\n" + entire_conversation + "\n\n"

    prompt += "キャラクター設定:\n"
    for name, detail in persona_params.items():
        style = detail["style"]
        extra = detail["detail"]
        prompt += f"{name}は【{style}】性格で、{extra}。\n"

    prompt += (
        "\n以上を踏まえ、3人がそれぞれの視点で連続して発言してください。\n"
        "必ず下記の形式（半角コロン+スペース）で出力してください:\n"
        "ゆかり: ○○○\n"
        "しんや: ○○○\n"
        "みのる: ○○○\n"
        "余計なJSONや解説は不要で、会話のみ出力してください。"
    )

    return call_gemini_api(prompt)

def generate_summary(entire_conversation: str) -> str:
    """
    会話全体を要約する。
    """
    prompt = (
        "以下は3人の会話内容です。\n" + entire_conversation + "\n\n" +
        "この内容を踏まえて、ユーザーに向けたまとめ回答を生成してください。\n"
        "自然な日本語文で出力し、余計なJSON形式は不要です。"
    )
    return call_gemini_api(prompt)

def display_line_style(text: str):
    """
    各発言をキャラクターごとの背景色と文字色で吹き出し表示する。
    """
    lines = text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]  # 空行除去

    # 上から古い発言、下が最新発言
    color_map = {
        "ゆかり": {"bg": "#FFD1DC", "color": "#000"},
        "しんや": {"bg": "#D1E8FF", "color": "#000"},
        "みのる": {"bg": "#D1FFD1", "color": "#000"},
        # 該当しないキャラはデフォルト
    }

    for line in lines:
        matched = re.match(r"^(ゆかり|しんや|みのる):\s*(.*)$", line)
        if matched:
            name = matched.group(1)
            message = matched.group(2)
        else:
            name = ""
            message = line

        styles = color_map.get(name, {"bg": "#F5F5F5", "color": "#000"})
        bubble_html = f"""
        <div style="
            background-color: {styles['bg']};
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 8px;
            margin: 5px 0;
            color: {styles['color']};
            font-family: Arial, sans-serif;
        ">
            <strong>{name}</strong><br>
            {message}
        </div>
        """
        st.markdown(bubble_html, unsafe_allow_html=True)

# ------------------------
# セッションステート初期化
# ------------------------
if "discussion" not in st.session_state:
    st.session_state["discussion"] = ""

if "summary" not in st.session_state:
    st.session_state["summary"] = ""

# ------------------------
# 「会話をまとめる」ボタン
# ------------------------
st.write("---")
if st.button("会話をまとめる"):
    if st.session_state["discussion"]:
        summary = generate_summary(st.session_state["discussion"])
        st.session_state["summary"] = summary
        st.markdown("### まとめ回答\n" + "**まとめ:** " + summary)
    else:
        st.warning("まだ会話がありません。")

# ------------------------
# 入力フォーム
# ------------------------
st.write("---")
st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area("新たな発言を入力してください", placeholder="ここに入力", height=80)
    # ボタン
    send_button = st.form_submit_button("送信")
st.markdown('</div>', unsafe_allow_html=True)

# 送信ボタンが押されたとき
if send_button:
    if user_input.strip():
        # Gemini APIを呼び出し、3人の会話を生成
        new_response = generate_three_person_conversation(user_input, st.session_state["discussion"])

        # デバッグ表示（必要であればコメントアウト可）
        st.write("**[DEBUG] AI応答**")
        st.write(new_response)

        # 応答が空の場合の警告
        if not new_response.strip():
            st.warning("AI応答が空でした。")
        elif "エラー:" in new_response or "回答が見つかりません" in new_response:
            st.warning(f"AIがエラーまたは無回答を返しました:\n{new_response}")

        # 会話ログに追記
        # ここではユーザ発言も保存したい場合、好きなフォーマットでどうぞ
        # 例: 「ユーザー: ...」 を入れたい場合は以下を追加
        # st.session_state["discussion"] += f"\nユーザー: {user_input}"
        # ただし display_line_style で正規表現がマッチしないので表示はお好みで

        # 3人の応答だけを必ず会話ログに追記
        st.session_state["discussion"] += "\n" + new_response

    else:
        st.warning("発言を入力してください。")

# ------------------------
# 会話ウィンドウの表示
# ------------------------
st.write("---")
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
if st.session_state["discussion"]:
    display_line_style(st.session_state["discussion"])
else:
    st.markdown("<p style='color: gray;'>ここに会話が表示されます。</p>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------
# まとめ表示（ある場合のみ）
# ------------------------
if st.session_state["summary"]:
    st.markdown("### まとめ回答")
    st.write(st.session_state["summary"])
