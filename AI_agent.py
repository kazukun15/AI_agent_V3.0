import streamlit as st
import numpy as np
from PIL import Image
import re
import random

# ------------------------
# ページ設定
# ------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

# ------------------------
# 背景画像やスタイル設定（オプション）
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
# キャラクター定義
# ------------------------
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"

# ------------------------
# AI設定
# ------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"  # 必要に応じて変更

# ------------------------
# セッション初期化
# ------------------------
if "chat_log" not in st.session_state:
    st.session_state["chat_log"] = []

if "initialized" not in st.session_state:
    st.session_state["initialized"] = False

# ------------------------
# アイコンの読み込み
# ------------------------
# 例: ローカル画像 or 絵文字を使う
# "AI_agent_V3.0/avatars/" に画像がある想定
try:
    img_user = Image.open("AI_agent_V3.0/avatars/user.png")
    img_yukari = Image.open("AI_agent_V3.0/avatars/yukari.png")
    img_shinya = Image.open("AI_agent_V3.0/avatars/shinya.png")
    img_minoru = Image.open("AI_agent_V3.0/avatars/minoru.png")
    img_newchar = Image.open("AI_agent_V3.0/avatars/new_character.png")
except:
    # 画像がない場合は絵文字などで代用
    img_user = "👤"
    img_yukari = "🌸"
    img_shinya = "🌊"
    img_minoru = "🍀"
    img_newchar = "⭐"

avator_img_dict = {
    USER_NAME: img_user,
    YUKARI_NAME: img_yukari,
    SHINYA_NAME: img_shinya,
    MINORU_NAME: img_minoru,
    NEW_CHAR_NAME: img_newchar,
    ASSISTANT_NAME: "🤖",  # アシスタント用絵文字
}

# ------------------------
# デバッグ用のAI呼び出し関数（ダミー）
# ------------------------
def call_gemini_api(prompt: str) -> str:
    """
    実際にはAPIを呼び出す処理を書く。
    ここではデバッグ用に固定メッセージを返す。
    """
    # 実際には requests.post などを行う
    return f"AIの応答（ダミー）: {prompt[:20]} ..."

# ------------------------
# 初回起動時に強制会話
# ------------------------
if not st.session_state["initialized"]:
    st.session_state["initialized"] = True
    if len(st.session_state["chat_log"]) == 0:
        # 最初のメッセージを強制的に会話ログへ追加
        first_user_msg = "はじめまして。"
        st.session_state["chat_log"].append({"name": USER_NAME, "msg": first_user_msg})
        # AI側の初回応答を生成（ダミー）
        first_ai_response = call_gemini_api(first_user_msg)
        st.session_state["chat_log"].append({"name": ASSISTANT_NAME, "msg": first_ai_response})

# ------------------------
# これまでの会話ログを表示
# ------------------------
st.header("会話履歴")
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
for chat in st.session_state["chat_log"]:
    with st.chat_message(chat["name"], avatar=avator_img_dict.get(chat["name"], None)):
        st.write(chat["msg"])
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------
# 発言入力
# ------------------------
st.header("発言バー")
user_msg = st.chat_input("ここにメッセージを入力")

if user_msg:
    # ユーザーの発言を表示
    st.session_state["chat_log"].append({"name": USER_NAME, "msg": user_msg})
    with st.chat_message(USER_NAME, avatar=avator_img_dict.get(USER_NAME, None)):
        st.write(user_msg)

    # アシスタントの応答（ダミー）
    assistant_msg = call_gemini_api(user_msg)
    st.session_state["chat_log"].append({"name": ASSISTANT_NAME, "msg": assistant_msg})
    with st.chat_message(ASSISTANT_NAME, avatar=avator_img_dict.get(ASSISTANT_NAME, None)):
        st.write(assistant_msg)

    # 例: ゆかりの応答
    yukari_msg = "ゆかり: こんにちは！"
    st.session_state["chat_log"].append({"name": YUKARI_NAME, "msg": yukari_msg})
    with st.chat_message(YUKARI_NAME, avatar=avator_img_dict.get(YUKARI_NAME, None)):
        st.write(yukari_msg)

    # 例: みのるの応答
    minoru_msg = "みのる: ゆったりと話を聞いていますよ。"
    st.session_state["chat_log"].append({"name": MINORU_NAME, "msg": minoru_msg})
    with st.chat_message(MINORU_NAME, avatar=avator_img_dict.get(MINORU_NAME, None)):
        st.write(minoru_msg)

    # 例: 新キャラクターの応答
    newchar_msg = "新キャラクター: ぼくは中性的な雰囲気だよ。"
    st.session_state["chat_log"].append({"name": NEW_CHAR_NAME, "msg": newchar_msg})
    with st.chat_message(NEW_CHAR_NAME, avatar=avator_img_dict.get(NEW_CHAR_NAME, None)):
        st.write(newchar_msg)

