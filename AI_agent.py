import streamlit as st
import re
import random
from PIL import Image
from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数

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
    body {
        background-color: #f0f2f6;
    }
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px;
        background-color: #ffffffaa;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------
# ユーザーの名前入力
# ------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")

# ------------------------
# キャラクター名定義
# ------------------------
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"

# ------------------------
# AI設定（APIキーなど）
# ------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"  # 適宜変更
NAMES = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME, NEW_CHAR_NAME]

# ------------------------
# セッション初期化
# ------------------------
if "chat_log" not in st.session_state:
    st.session_state["chat_log"] = []

# ------------------------
# アイコン画像の読み込み
# ------------------------
try:
    img_user = Image.open("avatars/user.png")
    img_yukari = Image.open("avatars/yukari.png")
    img_shinya = Image.open("avatars/shinya.png")
    img_minoru = Image.open("avatars/minoru.png")
    img_newchar = Image.open("avatars/new_character.png")
except Exception as e:
    st.error(f"画像読み込みエラー: {e}")
    img_user = "👤"
    img_yukari = "🌸"
    img_shinya = "🌊"
    img_minoru = "🍀"
    img_newchar = "⭐"

avatar_img_dict = {
    USER_NAME: img_user,
    YUKARI_NAME: img_yukari,
    SHINYA_NAME: img_shinya,
    MINORU_NAME: img_minoru,
    NEW_CHAR_NAME: img_newchar,
    ASSISTANT_NAME: "🤖",  # 絵文字で代用
}

# ------------------------
# 会話生成関連関数
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
    params = {
        YUKARI_NAME: {"style": "明るくはっちゃけた", "detail": "楽しい雰囲気で元気な回答"}
    }
    if score > 0:
        params[SHINYA_NAME] = {"style": "共感的", "detail": "心情を重視した解説"}
        params[MINORU_NAME] = {"style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        params[SHINYA_NAME] = {"style": "分析的", "detail": "データや事実を踏まえた説明"}
        params[MINORU_NAME] = {"style": "客観的", "detail": "中立的な視点からの考察"}
    # 新キャラクターには独創的な視点を付与
    params[NEW_CHAR_NAME] = {"style": "独創的", "detail": "自由な発想で意見を述べる"}
    return params

def call_gemini_api(prompt: str) -> str:
    # 実際には Gemini API を呼び出す処理を記述します
    return f"{prompt[:20]} ...（応答）"

def generate_discussion(question: str, persona_params: dict) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    prompt += (
        "\n上記情報を元に、4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        f"{YUKARI_NAME}: 発言内容\n"
        f"{SHINYA_NAME}: 発言内容\n"
        f"{MINORU_NAME}: 発言内容\n"
        f"{NEW_CHAR_NAME}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(additional_input: str, current_discussion: str) -> str:
    prompt = (
        "これまでの会話:\n" + current_discussion + "\n\n" +
        "ユーザーの追加発言: " + additional_input + "\n\n" +
        "上記を踏まえ、4人がさらに自然な会話を続けてください。\n"
        "出力形式は以下の通りです。\n"
        f"{YUKARI_NAME}: 発言内容\n"
        f"{SHINYA_NAME}: 発言内容\n"
        f"{MINORU_NAME}: 発言内容\n"
        f"{NEW_CHAR_NAME}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def generate_summary(discussion: str) -> str:
    prompt = (
        "以下は4人の会話内容です。\n" + discussion + "\n\n" +
        "この会話を踏まえて、質問に対するまとめ回答を生成してください。\n"
        "自然な日本語文で出力し、余計なJSON形式は不要です。"
    )
    return call_gemini_api(prompt)

def generate_new_character() -> tuple:
    candidates = [
        ("たけし", "冷静沈着で皮肉屋、どこか孤高な存在"),
        ("さとる", "率直かつ辛辣で、常に現実を鋭く指摘する"),
        ("りさ", "自由奔放で斬新なアイデアを持つ、ユニークな感性の持ち主"),
        ("けんじ", "クールで合理的、論理に基づいた意見を率直に述べる"),
        ("なおみ", "独創的で個性的、常識にとらわれず新たな視点を提供する")
    ]
    return random.choice(candidates)

def display_chat_log(chat_log: list):
    """
    chat_log の各メッセージを、各キャラクターのアバター画像とともに表示します。
    最新の発言が入力バーの直上に表示されるよう、上から下に向かって追加されます。
    """
    avatar_map = {
        USER_NAME: "avatars/user.png",
        YUKARI_NAME: "avatars/yukari.png",
        SHINYA_NAME: "avatars/shinya.png",
        MINORU_NAME: "avatars/minoru.png",
        NEW_CHAR_NAME: "avatars/new_character.png",
        ASSISTANT_NAME: "🤖"
    }
    style_map = {
        USER_NAME: {"bg": "#E0FFFF", "align": "right"},
        YUKARI_NAME: {"bg": "#FFB6C1", "align": "left"},
        SHINYA_NAME: {"bg": "#ADD8E6", "align": "left"},
        MINORU_NAME: {"bg": "#90EE90", "align": "left"},
        NEW_CHAR_NAME: {"bg": "#FFFACD", "align": "left"},
        ASSISTANT_NAME: {"bg": "#F0F0F0", "align": "left"}
    }
    for msg in chat_log:
        sender = msg.get("name", "不明")
        text = msg.get("msg", "")
        avatar = avatar_map.get(sender, "")
        style = style_map.get(sender, {"bg": "#F5F5F5", "align": "left"})
        if sender == USER_NAME:
            html_content = f"""
            <div style="display: flex; justify-content: flex-end; align-items: center; margin: 5px 0;">
                <div style="max-width: 70%; background-color: {style['bg']}; border: 1px solid #ddd; border-radius: 10px; padding: 8px; margin-right: 10px;">
                    {text}
                </div>
                <img src="{avatar}" style="width:40px; height:40px; border-radius:50%;">
            </div>
            """
        else:
            html_content = f"""
            <div style="display: flex; justify-content: flex-start; align-items: center; margin: 5px 0;">
                <img src="{avatar}" style="width:40px; height:40px; border-radius:50%; margin-right: 10px;">
                <div style="max-width: 70%; background-color: {style['bg']}; border: 1px solid #ddd; border-radius: 10px; padding: 8px;">
                    {sender}: {text}
                </div>
            </div>
            """
        st.markdown(html_content, unsafe_allow_html=True)

# ------------------------
# 会話ログの表示（上部：スクロール可能な領域）
# ------------------------
st.markdown(
    """
    <style>
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px;
        background-color: #ffffffaa;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.header("会話履歴")
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
if st.session_state["chat_log"]:
    display_chat_log(st.session_state["chat_log"])
else:
    st.markdown("<p style='color: gray;'>ここに会話が表示されます。</p>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------
# 発言入力（下部）
# ------------------------
st.header("発言バー")
user_msg = st.chat_input("ここにメッセージを入力")

if user_msg:
    # ユーザーの発言を保存して表示
    st.session_state["chat_log"].append({"name": USER_NAME, "msg": user_msg})
    with st.chat_message(USER_NAME, avatar=avatar_img_dict.get(USER_NAME)):
        st.write(user_msg)

    # 友達の応答生成（ダミー API 呼び出し）
    if len(st.session_state["chat_log"]) == 1:
        persona_params = adjust_parameters(user_msg)
        discussion = generate_discussion(user_msg, persona_params)
    else:
        history = "\n".join(
            f'{chat["name"]}: {chat["msg"]}'
            for chat in st.session_state["chat_log"]
            if chat["name"] in [YUKARI_NAME, SHINYA_NAME, MINORU_NAME, NEW_CHAR_NAME]
        )
        discussion = continue_discussion(user_msg, history)

    for line in discussion.split("\n"):
        line = line.strip()
        if line:
            parts = line.split(":", 1)
            sender = parts[0]
            message_text = parts[1].strip() if len(parts) > 1 else ""
            st.session_state["chat_log"].append({"name": sender, "msg": message_text})
    try:
        st.experimental_rerun()
    except AttributeError:
        pass
