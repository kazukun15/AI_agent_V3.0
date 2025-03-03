import streamlit as st
import base64
from io import BytesIO
from PIL import Image

# ページ設定（最初に呼び出す）
st.set_page_config(page_title="Bubble Over Character", layout="wide")
st.title("キャラクター上部に吹き出し表示の例")

# 画像を Base64 に変換する関数
def img_to_base64(img: Image.Image) -> str:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode()

# CSS でキャラクターと吹き出しのスタイルを定義
st.markdown("""
<style>
.character-wrapper {
    text-align: center;
    margin: 10px;
}
.speech-bubble {
    background: rgba(255, 255, 255, 0.8); /* 半透明の背景 */
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 8px;
    display: inline-block;
    max-width: 140px;
    margin-bottom: 5px;
    font-size: 14px;
    line-height: 1.3;
    word-wrap: break-word;
}
.character-image {
    width: 120px;  /* 適宜サイズを調整 */
}
</style>
""", unsafe_allow_html=True)

# キャラクター名とサンプルメッセージ
CHARACTERS = ["yukari", "shinya", "minoru", "new_character"]
sample_messages = {
    "yukari": "こんにちは、ゆかりです！",
    "shinya": "やあ、しんやだよ！",
    "minoru": "みのるだよ、よろしくね。",
    "new_character": "新キャラです！よろしく！"
}

# キャラクター画像の読み込み（avatars フォルダ内に配置）
avatar_img_dict = {}
for char in CHARACTERS:
    try:
        avatar_img_dict[char] = Image.open(f"avatars/{char}.png")
    except Exception as e:
        st.error(f"{char}の画像読み込みエラー: {e}")
        avatar_img_dict[char] = None

# 4人のキャラクターを横並びに表示するために4つのカラムを作成
cols = st.columns(4)

for i, char in enumerate(CHARACTERS):
    with cols[i]:
        # 吹き出しを上部に表示
        message_text = sample_messages.get(char, "...")
        st.markdown(f"""
            <div class="character-wrapper">
                <div class="speech-bubble">{message_text}</div>
                {"<img src='data:image/png;base64," + img_to_base64(avatar_img_dict[char]) + "' class='character-image'>" if avatar_img_dict[char] else f"<div>[{char}画像なし]</div>"}
            </div>
            """, unsafe_allow_html=True)
