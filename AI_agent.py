import streamlit as st
import requests
import re
import random
import time
import json
from PIL import Image
from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数
from streamlit_autorefresh import st_autorefresh  # 自動リフレッシュ用（ライフイベント等用）

# ------------------------------------------------------------------
# st.set_page_config() は最初に呼び出す
# ------------------------------------------------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

# ------------------------------------------------------------------
# config.toml の読み込み（同じディレクトリの場合）
# ------------------------------------------------------------------
try:
    try:
        import tomllib  # Python 3.11以降の場合
    except ImportError:
        import toml as tomllib
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)
    theme_config = config.get("theme", {})
    primaryColor = theme_config.get("primaryColor", "#729075")
    backgroundColor = theme_config.get("backgroundColor", "#f1ece3")
    secondaryBackgroundColor = theme_config.get("secondaryBackgroundColor", "#fff8ef")
    textColor = theme_config.get("textColor", "#5e796a")
    font = theme_config.get("font", "monospace")
except Exception as e:
    primaryColor = "#729075"
    backgroundColor = "#f1ece3"
    secondaryBackgroundColor = "#fff8ef"
    textColor = "#5e796a"
    font = "monospace"

# ------------------------------------------------------------------
# 背景・共通スタイルの設定（テーマ設定を反映）
# ------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    body {{
        background-color: {backgroundColor};
        font-family: {font}, sans-serif;
        color: {textColor};
    }}
    .chat-container {{
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px;
        background-color: {secondaryBackgroundColor};
    }}
    /* バブルチャット用のスタイル */
    .chat-bubble {{
        background-color: #d4f7dc;
        border-radius: 10px;
        padding: 8px;
        display: inline-block;
        max-width: 80%;
        word-wrap: break-word;
        white-space: pre-wrap;
        margin: 4px 0;
    }}
    .chat-header {{
        font-weight: bold;
        margin-bottom: 4px;
        color: {primaryColor};
    }}
    /* 固定キャラクター表示用のスタイル */
    .character-container {{
        text-align: center;
        margin-bottom: 20px;
    }}
    .character-message {{
        margin-top: 5px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------------
# 自動リフレッシュ（ライフイベント用：デモでは30秒毎）
# ------------------------------------------------------------------
st_autorefresh(interval=30000, limit=1000, key="autorefresh")

# ------------------------------------------------------------------
# ユーザー入力
# ------------------------------------------------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")
ai_age = st.number_input("AIの年齢を指定してください", min_value=1, value=30, step=1, key="ai_age")

# ------------------------------------------------------------------
# サイドバー：カスタム新キャラクター設定（ミニゲーム機能は排除）
# ------------------------------------------------------------------
st.sidebar.header("カスタム新キャラクター設定")
custom_new_char_name = st.sidebar.text_input("新キャラクターの名前（未入力ならランダム）", value="", key="custom_new_char_name")
custom_new_char_personality = st.sidebar.text_area("新キャラクターの性格・特徴（未入力ならランダム）", value="", key="custom_new_char_personality")
st.sidebar.info("※スマホの場合は、画面左上のハンバーガーメニューからサイドバーにアクセスできます。")

# ------------------------------------------------------------------
# キャラクター定義（固定メンバー）
# ------------------------------------------------------------------
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "yukari"
SHINYA_NAME = "shinya"
MINORU_NAME = "minoru"
NEW_CHAR_NAME = "new_character"

# ------------------------------------------------------------------
# 定数／設定（APIキー、モデル）
# ------------------------------------------------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"
NAMES = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]
# ※新キャラクターはサイドバーで指定がなければランダム生成

# ------------------------------------------------------------------
# セッション初期化（チャット履歴）
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------------------------------------------------------
# ライフイベント自動生成（一定間隔でランダムイベントを投稿）
# ------------------------------------------------------------------
if "last_event_time" not in st.session_state:
    st.session_state.last_event_time = time.time()

event_interval = 30  # 30秒毎（デモ用）
current_time = time.time()
if current_time - st.session_state.last_event_time > event_interval:
    life_events = [
        "お茶を淹れてリラックス中。",
        "散歩に出かけたよ。",
        "ちょっとお昼寝中…",
        "ニュースをチェックしてるよ。",
        "少しストレッチしたよ！"
    ]
    event_message = random.choice(life_events)
    life_char = random.choice(NAMES)
    st.session_state.messages.append({"role": life_char, "content": event_message})
    st.session_state.last_event_time = current_time

# ------------------------------------------------------------------
# 固定キャラクターの表示（画面上部）
# ------------------------------------------------------------------
st.markdown("<div class='character-container'>", unsafe_allow_html=True)
cols = st.columns(4)
# 各キャラクターの最新発言を、チャット履歴から抽出（なければ初期メッセージ）
def get_latest_message(char_role):
    # 最新のメッセージがあれば返す、なければデフォルトメッセージ
    for msg in reversed(st.session_state.messages):
        if msg["role"] == char_role:
            return msg["content"]
    default_messages = {
        YUKARI_NAME: "こんにちは！",
        SHINYA_NAME: "やあ、調子はどう？",
        MINORU_NAME: "元気だよ！",
        NEW_CHAR_NAME: "初めまして！"
    }
    return default_messages.get(char_role, "")
    
with cols[0]:
    if st.session_state.get("img_yukari", None) is None:
        try:
            img_yukari = Image.open("avatars/yukari.png")
        except:
            img_yukari = None
    st.image(img_yukari, width=100)
    st.markdown(f"<div class='chat-bubble character-message'><div class='chat-header'>{YUKARI_NAME}</div>{get_latest_message(YUKARI_NAME)}</div>", unsafe_allow_html=True)

with cols[1]:
    if st.session_state.get("img_shinya", None) is None:
        try:
            img_shinya = Image.open("avatars/shinya.png")
        except:
            img_shinya = None
    st.image(img_shinya, width=100)
    st.markdown(f"<div class='chat-bubble character-message'><div class='chat-header'>{SHINYA_NAME}</div>{get_latest_message(SHINYA_NAME)}</div>", unsafe_allow_html=True)

with cols[2]:
    if st.session_state.get("img_minoru", None) is None:
        try:
            img_minoru = Image.open("avatars/minoru.png")
        except:
            img_minoru = None
    st.image(img_minoru, width=100)
    st.markdown(f"<div class='chat-bubble character-message'><div class='chat-header'>{MINORU_NAME}</div>{get_latest_message(MINORU_NAME)}</div>", unsafe_allow_html=True)

with cols[3]:
    # new_characterはサイドバーでカスタム指定があればそれを、なければランダム生成
    new_char_name, new_char_personality = (custom_new_char_name.strip(), custom_new_char_personality.strip()) if (custom_new_char_name.strip() and custom_new_char_personality.strip()) else ("new_character", "よろしくね！")
    st.image(Image.open("avatars/new_character.png"), width=100)
    st.markdown(f"<div class='chat-bubble character-message'><div class='chat-header'>{new_char_name}</div>{get_latest_message(new_char_name)}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# チャット履歴の表示（従来の形式）
# ------------------------------------------------------------------
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    display_name = user_name if role == "user" else role
    if role == "user":
        with st.chat_message(role, avatar="👤"):
            st.markdown(
                f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
            st.markdown(
                f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                unsafe_allow_html=True,
            )

# ------------------------------------------------------------------
# ユーザー入力の取得（st.chat_input）
# ------------------------------------------------------------------
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    with st.chat_message("user", avatar="👤"):
        st.markdown(
            f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{user_name}</div>{user_input}</div></div>',
            unsafe_allow_html=True,
        )
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    if len(st.session_state.messages) == 1:
        persona_params = adjust_parameters(user_input, ai_age)
        discussion = generate_discussion(user_input, persona_params, ai_age)
    else:
        history = "\n".join(
            f'{msg["role"]}: {msg["content"]}'
            for msg in st.session_state.messages
            if msg["role"] in NAMES or msg["role"] == NEW_CHAR_NAME
        )
        discussion = continue_discussion(user_input, history)
    
    for line in discussion.split("\n"):
        line = line.strip()
        if line:
            parts = line.split(":", 1)
            role = parts[0]
            content = parts[1].strip() if len(parts) > 1 else ""
            st.session_state.messages.append({"role": role, "content": content})
            display_name = user_name if role == "user" else role
            if role == "user":
                with st.chat_message(role, avatar="👤"):
                    st.markdown(
                        f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
                    st.markdown(
                        f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                        unsafe_allow_html=True,
                    )
