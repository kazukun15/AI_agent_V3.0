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
# ユーザーの名前入力（画面上部に表示）
# ------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")

# ------------------------
# 定数／設定
# ------------------------
API_KEY = st.secrets["general"]["api_key"]  # .streamlit/secrets.toml で設定
MODEL_NAME = "gemini-2.0-flash-001"         # 必要に応じて変更
NAMES = ["ゆかり", "しんや", "みのる"]

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

# 必要に応じてアバターを使う場合のマッピング
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
    score = analyze_question(question)
    params = {}
    # ゆかり: 常に明るくはっちゃけた
    params["ゆかり"] = {"style": "明るくはっちゃけた", "detail": "楽しい雰囲気で元気な回答"}
    if score > 0:
        params["しんや"] = {"style": "共感的", "detail": "心情を重視した解説"}
        params["みのる"] = {"style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        params["しんや"] = {"style": "分析的", "detail": "データや事実を踏まえた説明"}
        params["みのる"] = {"style": "客観的", "detail": "中立的な視点からの考察"}
    return params

def remove_json_artifacts(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text else ""
    pattern = r"'parts': \[\{'text':.*?\}\], 'role': 'model'"
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini_api(prompt: str) -> str:
    """
    GeminiのAPIをコールし、生成結果（キャラ同士の会話）をテキストで返す。
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

def generate_discussion(question: str, persona_params: dict) -> str:
    """
    初回会話用プロンプト生成
    """
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    # ここで、半角コロン+改行形式を徹底して伝える
    prompt += (
        "\n上記情報を元に、3人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通り（必ず名前の後は半角コロン+スペースを使うこと）。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(additional_input: str, current_discussion: str) -> str:
    """
    続き会話用プロンプト生成
    """
    prompt = (
        "これまでの会話:\n" + current_discussion + "\n\n" +
        "ユーザーの追加発言: " + additional_input + "\n\n" +
        "上記を踏まえ、3人がさらに自然な会話を続けてください。\n"
        "出力形式は以下の通り（必ず名前の後は半角コロン+スペースを使うこと）。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def generate_summary(discussion: str) -> str:
    prompt = (
        "以下は3人の会話内容です。\n" + discussion + "\n\n" +
        "この会話を踏まえて、質問に対するまとめ回答を生成してください。\n"
        "自然な日本語文で出力し、余計なJSON形式は不要です。"
    )
    return call_gemini_api(prompt)

def display_line_style(text: str):
    """
    各発言をキャラクターごとの背景色と文字色で吹き出し形式に表示する。
    上から古い発言、下が最新発言。
    """
    lines = text.split("\n")
    # 空行を除外
    lines = [line.strip() for line in lines if line.strip()]

    # 色のマッピング
    color_map = {
        "ゆかり": {"bg": "#FFD1DC", "color": "#000"},
        "しんや": {"bg": "#D1E8FF", "color": "#000"},
        "みのる": {"bg": "#D1FFD1", "color": "#000"}
    }
    for line in lines:
        matched = re.match(r"^(ゆかり|しんや|みのる):\s*(.*)$", line)
        if matched:
            name = matched.group(1)
            message = matched.group(2)
        else:
            # キャラ名がマッチしなかった行も一応表示
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
# セッションステートの初期化
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
        st.warning("まずは会話を開始してください。")

# ------------------------
# 入力フォーム
# ------------------------
st.write("---")
st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area("新たな発言を入力してください", placeholder="ここに入力", height=80, key="user_input")
    col1, col2 = st.columns(2)
    with col1:
        send_button = st.form_submit_button("送信")
    with col2:
        continue_button = st.form_submit_button("続きを話す")
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------
# 送信ボタンが押されたとき
# ------------------------
if send_button:
    if user_input.strip():
        # 初回会話かどうかで処理分岐
        if not st.session_state["discussion"]:
            # 新規会話を開始
            persona_params = adjust_parameters(user_input)
            discussion = generate_discussion(user_input, persona_params)

            # デバッグ出力（初回応答）
            st.write("**[DEBUG] 初回AI応答**")
            st.write(discussion)

            st.session_state["discussion"] = discussion
        else:
            # 既存会話を続ける
            new_discussion = continue_discussion(user_input, st.session_state["discussion"])

            # デバッグ出力（2回目以降の応答）
            st.write("**[DEBUG] 追加発言に対するAI応答**")
            st.write(new_discussion)

            if not new_discussion.strip():
                st.warning("AI応答が空でした。")
            elif "エラー:" in new_discussion or "回答が見つかりません" in new_discussion:
                st.warning("AIがエラーまたは無回答を返しました:\n" + new_discussion)

            # 改行で繋げて追記
            st.session_state["discussion"] += "\n" + new_discussion
    else:
        st.warning("発言を入力してください。")

# ------------------------
# 続きを話すボタンが押されたとき
# ------------------------
if continue_button:
    if st.session_state["discussion"]:
        # "続きをお願いします" という追加発言を送って継続
        default_input = "続きをお願いします。"
        new_discussion = continue_discussion(default_input, st.session_state["discussion"])

        st.write("**[DEBUG] '続きをお願いします' に対するAI応答**")
        st.write(new_discussion)

        if not new_discussion.strip():
            st.warning("AI応答が空でした。")
        elif "エラー:" in new_discussion or "回答が見つかりません" in new_discussion:
            st.warning("AIがエラーまたは無回答を返しました:\n" + new_discussion)

        st.session_state["discussion"] += "\n" + new_discussion
    else:
        st.warning("まずは会話を開始してください。")

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
