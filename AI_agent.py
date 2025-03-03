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
# 1. テーマ設定ファイルの読み込み
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

# ==========================
# 2. キャラクター名と対応する画像ファイル
# ==========================
# すべてひらがな／日本語の名前で扱う
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"

USER_NAME = "user"

# 実際のファイル名（英語）との対応表
AVATAR_FILENAMES = {
    YUKARI_NAME: "yukari.png",
    SHINYA_NAME: "shinya.png",
    MINORU_NAME: "minoru.png",
    NEW_CHAR_NAME: "new_character.png"
}

# ==========================
# Gemini API で会話させるキャラクター一覧（新キャラクター以外）
# ==========================
CHARACTER_LIST = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# ==========================
# 3. Streamlit ページ設定
# ==========================
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

# テーマ設定を読み込み、CSS に反映
config_values = load_config()
st.markdown(
    f"""
    <style>
    body {{
        background-color: {config_values['backgroundColor']};
        font-family: {config_values['font']}, sans-serif;
        color: {config_values['textColor']};
    }}
    .character-container {{
        display: flex;
        justify-content: space-around;
        margin-bottom: 20px;
    }}
    .character-wrapper {{
        text-align: center;
        margin: 10px;
    }}
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
# 4. 自動リフレッシュ（ライフイベント用）
# ==========================
st_autorefresh(interval=30000, limit=1000, key="autorefresh")

# ==========================
# 5. サイドバーに名前とAI年齢を入力
# ==========================
user_name = st.sidebar.text_input("あなたの名前", value="ユーザー", key="user_name")
ai_age = st.sidebar.number_input("AIの年齢", min_value=1, value=30, step=1, key="ai_age")
st.sidebar.info("スマホの場合、画面左上のハンバーガーメニューからアクセスしてください。")

# ==========================
# 6. Gemini API の設定
# ==========================
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"

# ==========================
# 7. セッション初期化（会話履歴）
# ==========================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================
# 8. ライフイベント自動生成
# ==========================
if "last_event_time" not in st.session_state:
    st.session_state.last_event_time = time.time()

event_interval = 30  # 30秒毎
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
# 9. キャラクター画像の読み込み
# ==========================
def load_avatars():
    avatar_dict = {}
    # ユーザーは絵文字
    avatar_dict[USER_NAME] = "👤"
    # 他キャラクターはファイル名に対応
    for role, filename in AVATAR_FILENAMES.items():
        try:
            img = Image.open(f"avatars/{filename}")
            avatar_dict[role] = img
        except Exception as e:
            st.error(f"{role} の画像読み込みエラー: {e}")
            avatar_dict[role] = None
    return avatar_dict

avatar_img_dict = load_avatars()

# ==========================
# 10. 各キャラクターの最新メッセージを取得
# ==========================
def get_latest_message(char_role: str) -> str:
    # 会話履歴を逆順に走査し、最初に見つかった char_role の発言を返す
    for msg in reversed(st.session_state.messages):
        if msg["role"] == char_role:
            return msg["content"]
    # 見つからない場合は初期メッセージ
    defaults = {
        YUKARI_NAME: "こんにちは！",
        SHINYA_NAME: "やあ、調子はどう？",
        MINORU_NAME: "元気だよ！",
        NEW_CHAR_NAME: "はじめまして！"
    }
    return defaults.get(char_role, "・・・")

# ==========================
# 11. 固定キャラクター表示エリア
# ==========================
def display_characters():
    st.markdown("<div class='character-container'>", unsafe_allow_html=True)
    # 4列レイアウト
    col_list = st.columns(4)
    roles = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME, NEW_CHAR_NAME]

    for i, role_name in enumerate(roles):
        with col_list[i]:
            # 最新の吹き出しメッセージ
            msg_text = get_latest_message(role_name)
            # アバター画像
            avatar = avatar_img_dict.get(role_name, None)
            if isinstance(avatar, Image.Image):
                # 画像がある場合
                st.markdown(f"""
                    <div class="character-wrapper">
                        <div class="speech-bubble">{msg_text}</div>
                        <img src="data:image/png;base64,{img_to_base64(avatar)}" class="character-image">
                        <div><strong>{role_name}</strong></div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # 画像が無い場合
                st.write(role_name)
                st.markdown(f"<div class='speech-bubble'>{msg_text}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================
# 12. Gemini API 呼び出し用関数
# ==========================
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
        resp = requests.post(url, json=payload, headers=headers)
    except Exception as e:
        return f"エラー: リクエスト送信時に例外が発生 -> {str(e)}"

    if resp.status_code != 200:
        return f"エラー: ステータスコード {resp.status_code} -> {resp.text}"

    try:
        rjson = resp.json()
        candidates = rjson.get("candidates", [])
        if not candidates:
            return "回答が見つかりません。(candidatesが空)"
        candidate0 = candidates[0]
        content_val = candidate0.get("content", "")
        if isinstance(content_val, dict):
            parts = content_val.get("parts", [])
            content_str = " ".join([p.get("text", "") for p in parts])
        else:
            content_str = str(content_val)
        content_str = content_str.strip()
        if not content_str:
            return "回答が見つかりません。(contentが空)"
        return remove_json_artifacts(content_str)
    except Exception as e:
        return f"エラー: レスポンス解析に失敗 -> {str(e)}"

# ==========================
# 13. 会話生成関連
# ==========================
def analyze_question(question: str) -> int:
    # 質問を簡易的に分析し、scoreを返す
    score = 0
    emotional_words = ["困った", "悩み", "苦しい", "辛い"]
    logical_words = ["理由", "原因", "仕組み", "方法"]
    for w in emotional_words:
        if w in question:
            score += 1
    for w in logical_words:
        if w in question:
            score -= 1
    return score

def adjust_parameters(question: str, age: int) -> dict:
    """AIの年齢(age)と質問(question)から、各キャラクターの性格パラメータを返す。"""
    score = analyze_question(question)
    params = {}
    # ゆかり
    if age < 30:
        params[YUKARI_NAME] = {"style": "明るくはっちゃけた", "detail": "エネルギッシュでポジティブな回答"}
    elif age < 50:
        params[YUKARI_NAME] = {"style": "温かく落ち着いた", "detail": "経験に基づいたバランスの取れた回答"}
    else:
        params[YUKARI_NAME] = {"style": "賢明で穏やかな", "detail": "豊富な経験に基づいた落ち着いた回答"}

    # しんや
    if score > 0:
        # 感情的な質問
        params[SHINYA_NAME] = {"style": "共感的", "detail": "気持ちに寄り添いながら答える"}
    else:
        # 論理的な質問
        params[SHINYA_NAME] = {"style": "分析的", "detail": "データや根拠を示しながら冷静に答える"}

    # みのる
    if score > 0:
        params[MINORU_NAME] = {"style": "柔軟", "detail": "多面的な視点から優しくアドバイス"}
    else:
        params[MINORU_NAME] = {"style": "客観的", "detail": "事実を重視した中立的な回答"}

    return params

def generate_new_character() -> tuple:
    return (NEW_CHAR_NAME, "よろしくね！")

def generate_discussion(question: str, persona_params: dict, age: int) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    prompt += f"このAIは{age}歳として振る舞います。\n"
    for name, val in persona_params.items():
        prompt += f"{name}は【{val['style']}】視点で、{val['detail']}。\n"
    new_name, new_personality = generate_new_character()
    prompt += f"さらに、新キャラクターとして {new_name} は【{new_personality}】な性格です。彼/彼女も会話に加わってください。\n"
    prompt += (
        "\n4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通り:\n"
        f"{YUKARI_NAME}: 発言内容\n"
        f"{SHINYA_NAME}: 発言内容\n"
        f"{MINORU_NAME}: 発言内容\n"
        f"{NEW_CHAR_NAME}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語のみで出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(user_input: str, current_discussion: str) -> str:
    prompt = (
        f"これまでの会話:\n{current_discussion}\n\n"
        f"ユーザーの追加発言: {user_input}\n\n"
        f"上記を踏まえ、4人がさらに自然な会話を続けてください。\n"
        "出力形式:\n"
        f"{YUKARI_NAME}: 発言内容\n"
        f"{SHINYA_NAME}: 発言内容\n"
        f"{MINORU_NAME}: 発言内容\n"
        f"{NEW_CHAR_NAME}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語のみで出力してください。"
    )
    return call_gemini_api(prompt)

# ==========================
# 14. ユーザー入力→会話生成→セッションに保存
# ==========================
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    # ユーザーのメッセージを保存
    st.session_state.messages.append({"role": "user", "content": user_input})

    if len(st.session_state.messages) == 1:
        # 最初のやりとり
        persona_params = adjust_parameters(user_input, ai_age)
        result = generate_discussion(user_input, persona_params, ai_age)
    else:
        # 2回目以降
        # キャラクターの発言のみ抽出
        history = "\n".join(
            f'{m["role"]}: {m["content"]}'
            for m in st.session_state.messages
            if m["role"] in CHARACTER_LIST or m["role"] == NEW_CHAR_NAME
        )
        result = continue_discussion(user_input, history)

    # Gemini API の出力結果を行単位で分割し、セッションに追加
    for line in result.split("\n"):
        line = line.strip()
        if line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                role, content = parts[0], parts[1].strip()
            else:
                role, content = "assistant", line
            st.session_state.messages.append({"role": role, "content": content})

# ==========================
# 15. 上部のキャラクターエリアを表示
# ==========================
display_characters()
