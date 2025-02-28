import streamlit as st
import requests
import re
import time
import random
import base64
from io import BytesIO
from streamlit_chat import message  # pip install streamlit-chat
from PIL import Image

# ------------------------
# ページ設定（最初に実行） – st.set_page_config は最初に呼び出す！
# ------------------------
st.set_page_config(page_title="メンタルケアボット", layout="wide")

# ------------------------
# カスタムCSSの挿入（柔らかい薄いピンク・黄色）
# ------------------------
st.markdown(
    """
    <style>
    /* メイン画面の背景を薄いピンクに設定 */
    .reportview-container {
        background: #FFF0F5;
    }
    /* サイドバーの背景を柔らかい黄色に設定 */
    .sidebar .sidebar-content {
        background: #FFF5EE;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------
# タイトル表示（ユーザー情報入力の上部に表示）
# ------------------------
st.title("メンタルケアボット")

# ------------------------
# ユーザー情報入力（画面上部）
# ------------------------
user_name = st.text_input("あなたの名前を入力してください", value="愛媛県庁職員", key="user_name")
col1, col2 = st.columns([3, 1])
with col1:
    consult_type = st.radio("相談タイプを選択してください", 
                            ("本人の相談", "他者の相談", "デリケートな相談"), key="consult_type")
with col2:
    if st.button("選択式相談フォームを開く", key="open_form"):
        st.session_state["show_selection_form"] = True

# ------------------------
# 定数／設定
# ------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"  # 必要に応じて変更
ROLES = ["精神科医師", "カウンセラー", "メンタリスト", "内科医"]

# ------------------------
# セッションステート初期化（会話ターン管理）
# ------------------------
if "conversation_turns" not in st.session_state:
    st.session_state["conversation_turns"] = []
if "chat_log" not in st.session_state:
    st.session_state["chat_log"] = []  # chat_log を別途管理する場合
if "show_selection_form" not in st.session_state:
    st.session_state["show_selection_form"] = False

# ------------------------
# アバター画像の読み込み
# ------------------------
try:
    img_user = Image.open("AI_agent_Ver2.0/avatars/user.png")
    img_yukari = Image.open("AI_agent_Ver2.0/avatars/yukari.png")
    img_shinya = Image.open("AI_agent_Ver2.0/avatars/shinya.png")
    img_minoru = Image.open("AI_agent_Ver2.0/avatars/minoru.png")
except Exception as e:
    st.error(f"画像読み込みエラー: {e}")
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

def get_image_base64(image):
    if isinstance(image, str):
        return image  # 絵文字の場合
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

# ------------------------
# ヘルパー関数（チャット生成・表示）
# ------------------------
def truncate_text(text, max_length=400):
    return text if len(text) <= max_length else text[:max_length] + "…"

def split_message(message: str, chunk_size=200) -> list:
    chunks = []
    while len(message) > chunk_size:
        break_point = -1
        for punct in ["。", "！", "？"]:
            pos = message.rfind(punct, 0, chunk_size)
            if pos > break_point:
                break_point = pos
        if break_point == -1:
            break_point = chunk_size
        else:
            break_point += 1
        chunks.append(message[:break_point].strip())
        message = message[break_point:].strip()
    if message:
        chunks.append(message)
    return chunks

def remove_json_artifacts(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text else ""
    pattern = r"'parts': \[\{'text':.*?\}\], 'role': 'model'"
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini_api(prompt: str) -> str:
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
            return "回答が見つかりませんでした。"
        candidate0 = candidates[0]
        content_val = candidate0.get("content", "")
        if isinstance(content_val, dict):
            parts = content_val.get("parts", [])
            content_str = " ".join([p.get("text", "") for p in parts])
        else:
            content_str = str(content_val)
        content_str = content_str.strip()
        if not content_str:
            return "回答が見つかりませんでした。"
        return remove_json_artifacts(content_str)
    except Exception as e:
        return f"エラー: レスポンス解析に失敗しました -> {str(e)}"

def adjust_parameters(question: str) -> dict:
    params = {}
    params["ゆかり"] = {"style": "明るくはっちゃけた", "detail": "楽しい雰囲気で元気な回答"}
    if analyze_question(question) > 0:
        params["しんや"] = {"style": "共感的", "detail": "心情を重視した解説"}
        params["みのる"] = {"style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        params["しんや"] = {"style": "分析的", "detail": "データや事実を踏まえた説明"}
        params["みのる"] = {"style": "客観的", "detail": "中立的な視点からの考察"}
    return params

def generate_discussion(question: str, persona_params: dict) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    prompt += (
        "\n上記情報を元に、4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(additional_input: str, current_discussion: str) -> str:
    prompt = (
        "これまでの会話の流れ:\n" + current_discussion + "\n\n" +
        "ユーザーの追加発言: " + additional_input + "\n\n" +
        "上記を踏まえ、さらに自然な会話として、専門家としての見解を踏まえた回答を生成してください。"
        "回答は300～400文字程度で、自然な日本語で出力してください。"
    )
    return call_gemini_api(prompt)

def generate_summary(discussion: str) -> str:
    prompt = (
        "以下は4人の統合された会話内容です:\n" + discussion + "\n\n" +
        "この内容を踏まえて、愛媛県庁職員向けのメンタルヘルスケアに関するまとめレポートを、"
        "分かりやすいマークダウン形式で生成してください。"
    )
    return call_gemini_api(prompt)

def display_chat_bubble(sender: str, message: str, align: str):
    avatar_html = ""
    display_sender = sender
    if sender == "あなた":
        display_sender = "ユーザー"
    if display_sender in avatar_dict:
        avatar = avatar_dict[display_sender]
        if isinstance(avatar, str):
            avatar_html = f"<span style='font-size: 24px;'>{avatar}</span> "
        else:
            img_str = get_image_base64(avatar)
            avatar_html = f"<img src='data:image/png;base64,{img_str}' style='width:30px; height:30px; margin-right:5px;'>"
    if align == "right":
        bubble_html = f"""
        <div style="
            background-color: #DCF8C6;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 8px;
            margin: 5px 0;
            color: #000;
            font-family: Arial, sans-serif;
            text-align: right;
            width: 50%;
            float: right;
            clear: both;
        ">
            {avatar_html}<strong>{display_sender}</strong>: {message} 😊
        </div>
        """
    else:
        bubble_html = f"""
        <div style="
            background-color: #FFFACD;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 8px;
            margin: 5px 0;
            color: #000;
            font-family: Arial, sans-serif;
            text-align: left;
            width: 50%;
            float: left;
            clear: both;
        ">
            {avatar_html}<strong>{display_sender}</strong>: {message} 👍
        </div>
        """
    st.markdown(bubble_html, unsafe_allow_html=True)

def display_conversation_turns(turns: list):
    for turn in reversed(turns):
        display_chat_bubble("あなた", turn["user"], "right")
        answer_chunks = split_message(turn["answer"], 200)
        for i, chunk in enumerate(answer_chunks):
            suffix = " 👉" if i < len(answer_chunks) - 1 else ""
            # ここでは回答の送信者名がAPIからの返答として、最初の単語を使う想定
            display_chat_bubble("回答", chunk + suffix, "left")

# タイプライター風に表示するための関数
def create_bubble(sender: str, message: str, align: str) -> str:
    avatar_html = ""
    display_sender = sender
    if sender == "あなた":
        display_sender = "ユーザー"
    if display_sender in avatar_dict:
        avatar = avatar_dict[display_sender]
        if isinstance(avatar, str):
            avatar_html = f"<span style='font-size: 24px;'>{avatar}</span> "
        else:
            img_str = get_image_base64(avatar)
            avatar_html = f"<img src='data:image/png;base64,{img_str}' style='width:30px; height:30px; margin-right:5px;'>"
    if align == "right":
        return f"""
        <div style="
            background-color: #DCF8C6;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 8px;
            margin: 5px 0;
            color: #000;
            font-family: Arial, sans-serif;
            text-align: right;
            width: 50%;
            float: right;
            clear: both;
        ">
            {avatar_html}<strong>{display_sender}</strong>: {message} 😊
        </div>
        """
    else:
        return f"""
        <div style="
            background-color: #FFFACD;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 8px;
            margin: 5px 0;
            color: #000;
            font-family: Arial, sans-serif;
            text-align: left;
            width: 50%;
            float: left;
            clear: both;
        ">
            {avatar_html}<strong>{display_sender}</strong>: {message} 👍
        </div>
        """

def typewriter_bubble(sender: str, full_text: str, align: str, delay: float = 0.05):
    container = st.empty()
    displayed_text = ""
    for char in full_text:
        displayed_text += char
        container.markdown(create_bubble(sender, displayed_text, align), unsafe_allow_html=True)
        time.sleep(delay)
    container.markdown(create_bubble(sender, full_text, align), unsafe_allow_html=True)

# ------------------------
# Streamlit アプリ本体
# ------------------------
st.title("メンタルケアボット")
st.header("会話履歴")
conversation_container = st.empty()

if st.button("改善策のレポート"):
    if st.session_state.get("conversation_turns", []):
        all_turns = "\n".join([f"あなた: {turn['user']}\n回答: {turn['answer']}" for turn in st.session_state["conversation_turns"]])
        summary = generate_summary(all_turns)
        st.session_state["summary"] = summary
        st.markdown("### 改善策のレポート\n" + "**まとめ:**\n" + summary)
    else:
        st.warning("まずは会話を開始してください。")

if st.button("続きを読み込む"):
    if st.session_state.get("conversation_turns", []):
        context = "\n".join([f"あなた: {turn['user']}\n回答: {turn['answer']}" 
                             for turn in st.session_state["conversation_turns"]])
        new_answer = continue_discussion("続きをお願いします。", context)
        st.session_state["conversation_turns"].append({"user": "続き", "answer": new_answer})
        conversation_container.markdown("### 会話履歴")
        display_conversation_turns(st.session_state["conversation_turns"])
    else:
        st.warning("会話がありません。")

st.header("メッセージ入力")
with st.form("chat_form", clear_on_submit=True):
    user_message = st.text_area("新たな発言を入力してください", placeholder="ここに入力", height=100, key="user_input")
    submitted = st.form_submit_button("送信")

if submitted:
    if user_message.strip():
        if "conversation_turns" not in st.session_state or not isinstance(st.session_state["conversation_turns"], list):
            st.session_state["conversation_turns"] = []
        user_text = user_message
        persona_params = adjust_parameters(user_message)
        if len(st.session_state["conversation_turns"]) == 0:
            answer_text = generate_combined_answer(user_message, persona_params)
        else:
            context = "\n".join([f"あなた: {turn['user']}\n回答: {turn['answer']}" 
                                 for turn in st.session_state["conversation_turns"]])
            answer_text = continue_discussion(user_message, context)
        st.session_state["conversation_turns"].append({"user": user_text, "answer": answer_text})
        conversation_container.markdown("### 会話履歴")
        # 既存の会話は通常表示
        if len(st.session_state["conversation_turns"]) > 1:
            display_conversation_turns(st.session_state["conversation_turns"][:-1])
        # 最新の回答はタイプライター風に表示
        display_chat_bubble("あなた", user_text, "right")
        typewriter_bubble("回答", answer_text, "left")
    else:
        st.warning("発言を入力してください。")
