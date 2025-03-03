import streamlit as st
import random
from PIL import Image

# ページ設定（最初に呼び出し）
st.set_page_config(page_title="Bubble Over Character", layout="wide")
st.title("キャラクターの上に吹き出しを重ねる例")

# CSS で吹き出しのスタイルを定義（半透明背景、絶対配置など）
st.markdown("""
<style>
.character-wrapper {
    position: relative;
    display: inline-block;
    margin: 10px;
}

/* キャラクター画像 */
.character-image {
    width: 120px;  /* お好みのサイズに調整 */
}

/* 吹き出し（キャラクター画像の上に重ねる） */
.speech-bubble {
    position: absolute;
    top: 10px;   /* 画像に対する吹き出しの位置を調整 */
    left: 10px;
    background: rgba(255, 255, 255, 0.6); /* 半透明 */
    border-radius: 8px;
    padding: 8px;
    max-width: 140px;
    word-wrap: break-word;
    white-space: pre-wrap;
    font-size: 14px;
    line-height: 1.3;
    border: 1px solid #ddd; /* 見やすいように枠をつける */
}

/* 吹き出しの三角部分 */
.speech-bubble:after {
    content: "";
    position: absolute;
    bottom: -10px; /* 吹き出し下部に三角を表示 */
    left: 20px;
    border: 10px solid transparent;
    border-top-color: rgba(255, 255, 255, 0.6); /* 半透明に合わせる */
    border-bottom: 0;
    margin-left: -10px;
}
</style>
""", unsafe_allow_html=True)

# キャラクターの定義
CHARACTERS = ["yukari", "shinya", "minoru", "new_character"]

# 吹き出しに表示するサンプルメッセージ（本来は st.session_state.messages などから取得）
sample_messages = {
    "yukari": "こんにちは、私はゆかりです！",
    "shinya": "しんやだよ、元気？",
    "minoru": "みのるだよ、よろしくね。",
    "new_character": "新キャラクターだよ。"
}

# アバター画像の辞書（ユーザーは絵文字で代用）
avatar_img_dict = {
    "user": "👤",  # ユーザーは画像を使わず絵文字
    "yukari": None,
    "shinya": None,
    "minoru": None,
    "new_character": None
}

# 画像読み込み（存在しない場合は None）
try:
    avatar_img_dict["yukari"] = Image.open("avatars/yukari.png")
    avatar_img_dict["shinya"] = Image.open("avatars/shinya.png")
    avatar_img_dict["minoru"] = Image.open("avatars/minoru.png")
    avatar_img_dict["new_character"] = Image.open("avatars/new_character.png")
except Exception as e:
    st.error(f"画像読み込みエラー: {e}")

# 4人を横並びで表示
col1, col2, col3, col4 = st.columns(4)
cols = [col1, col2, col3, col4]

for i, char in enumerate(CHARACTERS):
    with cols[i]:
        img = avatar_img_dict[char]
        message = sample_messages.get(char, "...")
        if img:
            # HTML で画像と吹き出しを重ねる
            st.markdown(f"""
            <div class="character-wrapper">
                <img src="data:image/png;base64,{img_to_base64(img)}" class="character-image">
                <div class="speech-bubble">
                    {message}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 画像が無い場合は文字で代用
            st.markdown(f"""
            <div class="character-wrapper">
                <div>[{char}]</div>
                <div class="speech-bubble">{message}</div>
            </div>
            """, unsafe_allow_html=True)

# チャットバー（例：st.chat_input で取得）
user_input = st.chat_input("ここにメッセージを入力してください")
if user_input:
    st.write("ユーザーの入力:", user_input)
    # ここで Gemini API に投げて会話生成を行い、
    # 各キャラクターのメッセージを更新するなどの処理を行う。
    # ...
