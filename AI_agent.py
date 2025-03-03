import streamlit as st
import base64
from io import BytesIO
from PIL import Image

# 画像を Base64 エンコードする関数を定義
def img_to_base64(img: Image.Image) -> str:
    """PIL Image を Base64 文字列に変換する。"""
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode()

st.set_page_config(page_title="Bubble Over Character", layout="wide")
st.title("キャラクターの上に吹き出しを重ねる例")

# CSS で吹き出しのスタイルを定義
st.markdown("""
<style>
.character-wrapper {
    position: relative;
    display: inline-block;
    margin: 10px;
}
.character-image {
    width: 120px;  /* お好みのサイズに調整 */
}
/* 吹き出し（キャラクター画像の上に重ねる） */
.speech-bubble {
    position: absolute;
    top: 10px;   
    left: 10px;
    background: rgba(255, 255, 255, 0.6); /* 半透明 */
    border-radius: 8px;
    padding: 8px;
    max-width: 140px;
    word-wrap: break-word;
    white-space: pre-wrap;
    font-size: 14px;
    line-height: 1.3;
    border: 1px solid #ddd;
}
.speech-bubble:after {
    content: "";
    position: absolute;
    bottom: -10px; 
    left: 20px;
    border: 10px solid transparent;
    border-top-color: rgba(255, 255, 255, 0.6); 
    border-bottom: 0;
    margin-left: -10px;
}
</style>
""", unsafe_allow_html=True)

# キャラクター画像の読み込み
CHARACTERS = ["yukari", "shinya", "minoru", "new_character"]
avatar_img_dict = {}
for char in CHARACTERS:
    try:
        avatar_img_dict[char] = Image.open(f"avatars/{char}.png")
    except:
        avatar_img_dict[char] = None

# サンプルのメッセージ（本来は会話履歴などから取得）
sample_messages = {
    "yukari": "こんにちは、ゆかりです！",
    "shinya": "やあ、しんやだよ！",
    "minoru": "みのるだよ、よろしく！",
    "new_character": "新キャラです！"
}

cols = st.columns(4)
for i, char in enumerate(CHARACTERS):
    img = avatar_img_dict[char]
    msg = sample_messages.get(char, "・・・")
    with cols[i]:
        if img:
            img_str = img_to_base64(img)
            st.markdown(f"""
            <div class="character-wrapper">
                <img src="data:image/png;base64,{img_str}" class="character-image">
                <div class="speech-bubble">
                    {msg}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="character-wrapper">
                <div>[{char}の画像なし]</div>
                <div class="speech-bubble">{msg}</div>
            </div>
            """, unsafe_allow_html=True)

# ここから先はユーザー入力や Gemini API を使った会話生成などを実装可能
user_input = st.chat_input("ここにメッセージを入力してください")
if user_input:
    st.write("ユーザーの入力:", user_input)
    # Gemini API などで会話を生成して吹き出しを更新するなどの処理を行う
