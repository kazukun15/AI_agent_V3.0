import streamlit as st
import requests
import re
import random
import time
import json
import base64
from io import BytesIO
from PIL import Image

# ==========================
# ヘルパー関数
# ==========================
def load_config():
    try:
        try:
            import tomllib  # Python 3.11以降用
        except ImportError:
            import toml as tomllib
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)
        theme_config = config.get("theme", {})
        return {
            "primaryColor": theme_config.get("primaryColor", "#729075"),
            "backgroundColor": theme_config.get("backgroundColor", "#f1ece3"),
            "secondaryBackgroundColor": theme_config.get("secondaryBackgroundColor", "#fff8ef"),
            "textColor": theme_config.get("textColor", "#5e796a"),
            "font": theme_config.get("font", "monospace")
        }
    except Exception:
        return {
            "primaryColor": "#729075",
            "backgroundColor": "#f1ece3",
            "secondaryBackgroundColor": "#fff8ef",
            "textColor": "#5e796a",
            "font": "monospace"
        }

def img_to_base64(img: Image.Image) -> str:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# ==========================
# 定数・初期設定
# ==========================
# キャラクター名（すべてひらがな／日本語）
USER_NAME = "user"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "あたらしいともだち"

# Gemini API 用キャラクターリスト（あたらしいともだち以外）
CHARACTER_LIST = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# ==========================
# ページ設定＆タイトル
# ==========================
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

config_values = load_config()
st.markdown(f"""
    <style>
    body {{
        background-color: {config_values['backgroundColor']};
        font-family: {config_values['font']}, sans-serif;
        color: {config_values['textColor']};
    }}
    /* 固定キャラクター表示エリア */
    .character-container {{
        display: flex;
        justify-content: space-around;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }}
    .character-wrapper {{
        text-align: center;
        margin: 10px;
    }}
    /* 吹き出し（キャラクターの最新発言） - 横幅300px */
    .speech-bubble {{
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid #ccc;
        border-radius: 10px;
        padding: 12px 16px;
        display: inline-block;
        max-width: 300px;
        margin-bottom: 5px;
        font-size: 16px;
        line-height: 1.5;
        word-wrap: break-word;
    }}
    .character-image {{
        width: 120px;
    }}
    /* スマホ向けレスポンシブ設定 */
    @media only screen and (max-width: 768px) {{
        .character-container {{
            flex-direction: column;
            align-items: center;
        }}
    }}
    </style>
""", unsafe_allow_html=True)

# ==========================
# サイドバー入力（名前とAI年齢）
# ==========================
user_name = st.sidebar.text_input("あなたの名前", value="ユーザー", key="user_name")
ai_age = st.sidebar.number_input("AIの年齢", min_value=1, value=30, step=1, key="ai_age")
st.sidebar.info("スマホの場合、画面左上のハンバーガーメニューからアクセスしてください。")

# サイドバーに会話をまとめるボタンを追加
if st.sidebar.button("会話をまとめる"):
    history_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in st.session_state.get("messages", []))
    summary = generate_summary(history_text)
    st.sidebar.markdown("### 会話のまとめ")
    st.sidebar.markdown(summary)

# ==========================
# APIキー、モデル設定
# ==========================
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"

# ==========================
# セッション初期化（会話履歴）
# ==========================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================
# ライフイベント自動生成（30秒毎、デモ用）
# ==========================
if "last_event_time" not in st.session_state:
    st.session_state.last_event_time = time.time()
event_interval = 30
current_time = time.time()
if current_time - st.session_state.last_event_time > event_interval:
    events = [
        "ちょっと散歩してきたよ。",
        "お茶を飲んでリラックス中。",
        "少しお昼寝してたの。",
        "ニュースをチェックしてるよ。",
        "運動して汗かいちゃった！"
    ]
    msg = random.choice(events)
    who = random.choice(CHARACTER_LIST)
    st.session_state.messages.append({"role": who, "content": msg})
    st.session_state.last_event_time = current_time

# ==========================
# キャラクター画像の読み込み
# ==========================
def load_avatars():
    avatar_imgs = {}
    avatar_imgs[USER_NAME] = "👤"
    mapping = {
        YUKARI_NAME: "yukari.png",
        SHINYA_NAME: "shinya.png",
        MINORU_NAME: "minoru.png",
        NEW_CHAR_NAME: "new_character.png"
    }
    for role, fname in mapping.items():
        try:
            img = Image.open(f"avatars/{fname}")
            avatar_imgs[role] = img
        except Exception as e:
            st.error(f"{role} の画像読み込みエラー: {e}")
            avatar_imgs[role] = None
    return avatar_imgs

avatar_img_dict = load_avatars()

# ==========================
# 最新の発言取得関数
# ==========================
def get_latest_message(role_name: str) -> str:
    for msg in reversed(st.session_state.messages):
        if msg["role"] == role_name:
            return msg["content"]
    defaults = {
        YUKARI_NAME: "こんにちは！",
        SHINYA_NAME: "やあ、調子はどう？",
        MINORU_NAME: "元気だよ！",
        NEW_CHAR_NAME: "はじめまして！"
    }
    return defaults.get(role_name, "・・・")

# ==========================
# 固定キャラクター表示エリア
# ==========================
def display_characters():
    st.markdown("<div class='character-container'>", unsafe_allow_html=True)
    cols = st.columns(4)
    roles = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME, NEW_CHAR_NAME]
    for i, role_name in enumerate(roles):
        with cols[i]:
            msg_text = get_latest_message(role_name)
            avatar = avatar_img_dict.get(role_name, None)
            if isinstance(avatar, Image.Image):
                base64_str = img_to_base64(avatar)
                st.markdown(f"""
                    <div class="character-wrapper">
                        <div class="speech-bubble">{msg_text}</div>
                        <img src="data:image/png;base64,{base64_str}" class="character-image">
                        <div><strong>{role_name}</strong></div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.write(role_name)
                st.markdown(f"<div class='speech-bubble'>{msg_text}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================
# Gemini API 呼び出し関連関数
# ==========================
def remove_json_artifacts(text: str) -> str:
    if not isinstance(text, str):
        text = str(text) if text else ""
    pattern = r"'parts': \[\{'text':.*?\}\], 'role': 'model'"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()

def call_gemini_api(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers)
    except Exception as e:
        return f"エラー: リクエスト送信時に例外が発生 -> {str(e)}"
    if r.status_code != 200:
        return f"エラー: ステータスコード {r.status_code} -> {r.text}"
    try:
        rjson = r.json()
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
        return f"エラー: レスポンス解析に失敗 -> {str(e)}"

# ==========================
# 会話生成関連関数
# ==========================
def analyze_question(question: str) -> int:
    score = 0
    for w in ["困った", "悩み", "苦しい", "辛い"]:
        if w in question:
            score += 1
    for w in ["理由", "原因", "仕組み", "方法"]:
        if w in question:
            score -= 1
    return score

def adjust_parameters(question: str, age: int) -> dict:
    score = analyze_question(question)
    params = {}
    # ゆかりの性格
    if age < 30:
        params[YUKARI_NAME] = {"style": "明るくフレンドリー", "detail": "若々しいエネルギーと笑顔で親しみやすく答える"}
    elif age < 50:
        params[YUKARI_NAME] = {"style": "温かみのある", "detail": "経験を生かし、柔らかい口調でバランスの取れた回答をする"}
    else:
        params[YUKARI_NAME] = {"style": "穏やかで包容力のある", "detail": "長い経験に裏打ちされた落ち着きと優しさで答える"}
    # しんやの性格
    if analyze_question(question) > 0:
        params[SHINYA_NAME] = {"style": "共感力にあふれる", "detail": "相手の気持ちを理解し、温かい言葉で寄り添う回答をする"}
    else:
        params[SHINYA_NAME] = {"style": "冷静かつ論理的", "detail": "事実やデータをもとに、しっかりと根拠を示しながらも柔らかい口調で答える"}
    # みのるの性格
    if analyze_question(question) > 0:
        params[MINORU_NAME] = {"style": "柔らかく親しみやすい", "detail": "多角的な視点で、優しいアドバイスや提案をする"}
    else:
        params[MINORU_NAME] = {"style": "客観的で現実的", "detail": "冷静かつ中立的な立場で、正確な情報を分かりやすく伝える"}
    return params

def generate_new_character() -> tuple:
    return (NEW_CHAR_NAME, "よろしくね！")

def generate_discussion(question: str, persona_params: dict, age: int) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    prompt += f"このAIは{age}歳として振る舞います。\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}】な視点で、{params['detail']}。\n"
    new_name, new_personality = generate_new_character()
    prompt += f"さらに、あたらしいともだちとして {new_name} は【{new_personality}】な性格です。4人全員が必ず順番に一度以上発言してください。\n"
    prompt += (
        "\n4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通り:\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "あたらしいともだち: 発言内容\n"
        "必ず4人全員が発言し、余計なJSON形式は入れず、自然な日本語のみで出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(user_input: str, current_discussion: str) -> str:
    prompt = (
        f"これまでの会話:\n{current_discussion}\n\n"
        f"ユーザーの追加発言: {user_input}\n\n"
        "4人が友達同士のように、必ず全員が一度以上発言を続けてください。\n"
        "出力形式:\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "あたらしいともだち: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語のみで出力してください。"
    )
    return call_gemini_api(prompt)

def generate_summary(discussion: str) -> str:
    prompt = (
        "以下は4人の会話内容です。\n" + discussion + "\n\n" +
        "この会話を踏まえて、質問に対するまとめ回答を生成してください。\n"
        "自然な日本語文で出力し、余計なJSON形式は不要です。"
    )
    return call_gemini_api(prompt)

# ==========================
# ユーザー入力と会話生成
# ==========================
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    if len(st.session_state.messages) == 1:
        persona_params = adjust_parameters(user_input, ai_age)
        discussion = generate_discussion(user_input, persona_params, ai_age)
    else:
        history = "\n".join(
            f'{m["role"]}: {m["content"]}' for m in st.session_state.messages if m["role"] in CHARACTER_LIST or m["role"] == NEW_CHAR_NAME
        )
        discussion = continue_discussion(user_input, history)
    
    for line in discussion.split("\n"):
        line = line.strip()
        if line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                role, content = parts[0].strip(), parts[1].strip()
            else:
                role, content = "assistant", line
            st.session_state.messages.append({"role": role, "content": content})

# ==========================
# 固定キャラクター表示エリアの更新
# ==========================
display_characters()
