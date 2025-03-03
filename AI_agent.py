import streamlit as st
import requests
import re
import random
import time
import json
import base64
from io import BytesIO
from PIL import Image
from streamlit_autorefresh import st_autorefresh  # 自動リフレッシュ用

# ==========================
# ヘルパー関数
# ==========================
def load_config():
    """config.toml を読み込み、テーマ用の設定を返す。"""
    try:
        try:
            import tomllib  # Python 3.11以降
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
# キャラクター名
USER_NAME = "user"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"

# 4人のうち、新キャラクター以外をリスト化（Gemini API 用）
CHARACTER_LIST = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# ==========================
# ページ設定＆タイトル
# ==========================
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

config_values = load_config()
st.markdown(
    f"""
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
    }}
    .character-wrapper {{
        text-align: center;
        margin: 10px;
    }}
    /* 吹き出し（キャラクターの最新発言） */
    .speech-bubble {{
        background: rgba(255, 255, 255, 0.8);
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 8px;
        display: inline-block;
        max-width: 140px;
        margin-bottom: 5px;
        font-size: 14px;
        line-height: 1.3;
        word-wrap: break-word;
    }}
    .character-image {{
        width: 120px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================
# 自動リフレッシュ（ライフイベント用）
# ==========================
st_autorefresh(interval=30000, limit=1000, key="autorefresh")

# ==========================
# サイドバー入力
# ==========================
user_name = st.sidebar.text_input("あなたの名前", value="ユーザー", key="user_name")
ai_age = st.sidebar.number_input("AIの年齢", min_value=1, value=30, step=1, key="ai_age")
st.sidebar.info("スマホの場合、画面左上のハンバーガーメニューからアクセスしてください。")

# ==========================
# APIキー、モデル設定
# ==========================
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"

# ==========================
# セッション初期化（チャット履歴）
# ==========================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================
# ライフイベント自動生成（デモ用）
# ==========================
if "last_event_time" not in st.session_state:
    st.session_state.last_event_time = time.time()

event_interval = 30  # 30秒ごとにイベントを生成
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
    # ユーザーは絵文字
    avatar_imgs[USER_NAME] = "👤"
    # 他キャラクターはファイル名に対応
    # 例: "ゆかり" -> "yukari.png" など
    # ここではファイル名は英語、内部名は日本語とする
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
# 最新の発言を取得
# ==========================
def get_latest_message(role_name: str) -> str:
    for msg in reversed(st.session_state.messages):
        if msg["role"] == role_name:
            return msg["content"]
    # 見つからなかった場合の初期メッセージ
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
    roles = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME, NEW_CHAR_NAME]
    cols = st.columns(4)

    for i, role_name in enumerate(roles):
        with cols[i]:
            msg_text = get_latest_message(role_name)
            avatar_obj = avatar_img_dict.get(role_name, None)
            if isinstance(avatar_obj, Image.Image):
                # 画像がある場合
                base64_str = img_to_base64(avatar_obj)
                st.markdown(f"""
                    <div class="character-wrapper">
                        <div class="speech-bubble">{msg_text}</div>
                        <img src="data:image/png;base64,{base64_str}" class="character-image">
                        <div><strong>{role_name}</strong></div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # 画像がない場合
                st.write(role_name)
                st.markdown(f"<div class='speech-bubble'>{msg_text}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================
# Gemini API 呼び出し用
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
# 会話生成ロジック
# ==========================
def analyze_question(question: str) -> int:
    score = 0
    emotional = ["困った", "悩み", "苦しい", "辛い"]
    logical = ["理由", "原因", "仕組み", "方法"]
    for w in emotional:
        if w in question:
            score += 1
    for w in logical:
        if w in question:
            score -= 1
    return score

def adjust_parameters(question: str, age: int) -> dict:
    score = analyze_question(question)
    params = {}
    # ゆかり
    if age < 30:
        params[YUKARI_NAME] = {"style": "明るくはっちゃけた", "detail": "とにかくエネルギッシュでポジティブな回答"}
    elif age < 50:
        params[YUKARI_NAME] = {"style": "温かく落ち着いた", "detail": "経験に基づいたバランスの取れた回答"}
    else:
        params[YUKARI_NAME] = {"style": "賢明で穏やかな", "detail": "豊富な経験に基づいた落ち着いた回答"}

    # しんや
    if score > 0:
        params[SHINYA_NAME] = {"style": "共感的", "detail": "気持ちに寄り添いながら答える"}
    else:
        params[SHINYA_NAME] = {"style": "分析的", "detail": "冷静に根拠を示して答える"}

    # みのる
    if score > 0:
        params[MINORU_NAME] = {"style": "柔軟", "detail": "多面的な視点で優しくアドバイス"}
    else:
        params[MINORU_NAME] = {"style": "客観的", "detail": "中立的な立場で率直に意見を述べる"}

    return params

def generate_new_character() -> tuple:
    return (NEW_CHAR_NAME, "よろしくね！")

def generate_discussion(question: str, persona_params: dict, ai_age: int) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    prompt += f"このAIは{ai_age}歳として振る舞います。\n"
    for name, val in persona_params.items():
        prompt += f"{name}は【{val['style']}】視点で、{val['detail']}。\n"
    new_name, new_personality = generate_new_character()
    # 4人が最低1回ずつ発言するように明示的に指示
    prompt += f"さらに、新キャラクターとして {new_name} は【{new_personality}】な性格です。4人全員が順番に最低1回は発言してください。\n"
    prompt += (
        "\n4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "新キャラクター: 発言内容\n"
        "必ず4人全員が発言し、余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(user_input: str, current_discussion: str) -> str:
    prompt = (
        f"これまでの会話:\n{current_discussion}\n\n"
        f"ユーザーの追加発言: {user_input}\n\n"
        "4人が友達同士のように、順番に最低1回ずつは発言を続けてください。\n"
        "出力形式:\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "新キャラクター: 発言内容\n"
        "必ず4人全員が発言し、余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

# ==========================
# ユーザー入力と会話生成
# ==========================
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    # ユーザーのメッセージを履歴に追加
    st.session_state.messages.append({"role": "user", "content": user_input})

    if len(st.session_state.messages) == 1:
        # 最初の発言
        persona_params = adjust_parameters(user_input, ai_age)
        discussion = generate_discussion(user_input, persona_params, ai_age)
    else:
        # 2回目以降
        # これまでの会話（キャラクターの発言のみ）を結合
        history_text = "\n".join(
            f'{m["role"]}: {m["content"]}'
            for m in st.session_state.messages
            if m["role"] in CHARACTER_LIST or m["role"] == NEW_CHAR_NAME
        )
        discussion = continue_discussion(user_input, history_text)

    # Gemini API の結果を行単位で解析して履歴に追加
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
# 固定キャラクター表示エリアを更新
# ==========================
display_characters()
