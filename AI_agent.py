import streamlit as st
import requests
import re
import random
import time
import json
import base64
from io import BytesIO
from PIL import Image
from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数
from streamlit_autorefresh import st_autorefresh  # 自動リフレッシュ用

# ------------------------------------------------------------------
# st.set_page_config() は最初に呼び出す
# ------------------------------------------------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

# ------------------------------------------------------------------
# config.toml の読み込み（同じディレクトリにある場合）
# ------------------------------------------------------------------
try:
    try:
        import tomllib  # Python 3.11以降
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
    /* チャット履歴用吹き出し */
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
    /* 固定キャラクター表示エリア */
    .character-container {{
        display: flex;
        justify-content: space-around;
        margin-bottom: 20px;
    }}
    .character-box {{
        text-align: center;
    }}
    .character-message {{
        margin-top: 5px;
        background-color: rgba(255, 255, 255, 0.8);
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 5px;
        display: inline-block;
        max-width: 150px;
        word-wrap: break-word;
        white-space: pre-wrap;
        font-size: 14px;
        line-height: 1.3;
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
# ユーザー入力（上部）
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
# ※新キャラクターはサイドバー設定で指定がなければランダム生成

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
# 固定キャラクター表示エリア（上部）：各キャラクターの画像と最新メッセージを表示
# ------------------------------------------------------------------
def get_latest_message(char_role):
    for msg in reversed(st.session_state.messages):
        if msg["role"] == char_role:
            return msg["content"]
    defaults = {
        YUKARI_NAME: "こんにちは！",
        SHINYA_NAME: "やあ、調子はどう？",
        MINORU_NAME: "元気だよ！",
        NEW_CHAR_NAME: "初めまして！"
    }
    return defaults.get(char_role, "")

st.markdown("<div class='character-container'>", unsafe_allow_html=True)
cols = st.columns(4)
with cols[0]:
    try:
        img = Image.open("avatars/yukari.png")
    except:
        img = None
    if img:
        st.image(img, width=100)
    else:
        st.write("yukari")
    st.markdown(f"<div class='character-message'><strong>{YUKARI_NAME}</strong><br>{get_latest_message(YUKARI_NAME)}</div>", unsafe_allow_html=True)
with cols[1]:
    try:
        img = Image.open("avatars/shinya.png")
    except:
        img = None
    if img:
        st.image(img, width=100)
    else:
        st.write("shinya")
    st.markdown(f"<div class='character-message'><strong>{SHINYA_NAME}</strong><br>{get_latest_message(SHINYA_NAME)}</div>", unsafe_allow_html=True)
with cols[2]:
    try:
        img = Image.open("avatars/minoru.png")
    except:
        img = None
    if img:
        st.image(img, width=100)
    else:
        st.write("minoru")
    st.markdown(f"<div class='character-message'><strong>{MINORU_NAME}</strong><br>{get_latest_message(MINORU_NAME)}</div>", unsafe_allow_html=True)
with cols[3]:
    if custom_new_char_name.strip() and custom_new_char_personality.strip():
        new_char_name = custom_new_char_name.strip()
    else:
        new_char_name = NEW_CHAR_NAME
    try:
        img = Image.open("avatars/new_character.png")
    except:
        img = None
    if img:
        st.image(img, width=100)
    else:
        st.write("new_character")
    st.markdown(f"<div class='character-message'><strong>{new_char_name}</strong><br>{get_latest_message(new_char_name)}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Gemini API 呼び出し関連関数
# ------------------------------------------------------------------
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
        return f"エラー: レスポンス解析に失敗しました -> {str(e)}"

# ------------------------------------------------------------------
# 会話生成関連関数
# ------------------------------------------------------------------
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

def adjust_parameters(question: str, ai_age: int) -> dict:
    score = analyze_question(question)
    params = {}
    if ai_age < 30:
        params[YUKARI_NAME] = {"style": "明るくはっちゃけた", "detail": "とにかくエネルギッシュでポジティブな回答"}
        if score > 0:
            params[SHINYA_NAME] = {"style": "共感的", "detail": "若々しい感性で共感しながら答える"}
            params[MINORU_NAME] = {"style": "柔軟", "detail": "自由な発想で斬新な視点から回答する"}
        else:
            params[SHINYA_NAME] = {"style": "分析的", "detail": "新しい視点を持ちつつ、若々しく冷静に答える"}
            params[MINORU_NAME] = {"style": "客観的", "detail": "柔軟な思考で率直に事実を述べる"}
    elif ai_age < 50:
        params[YUKARI_NAME] = {"style": "温かく落ち着いた", "detail": "経験に基づいたバランスの取れた回答"}
        if score > 0:
            params[SHINYA_NAME] = {"style": "共感的", "detail": "深い理解と共感を込めた回答"}
            params[MINORU_NAME] = {"style": "柔軟", "detail": "実務的な視点から多角的な意見を提供"}
        else:
            params[SHINYA_NAME] = {"style": "分析的", "detail": "冷静な視点から根拠をもって説明する"}
            params[MINORU_NAME] = {"style": "客観的", "detail": "理論的かつ中立的な視点で回答する"}
    else:
        params[YUKARI_NAME] = {"style": "賢明で穏やかな", "detail": "豊富な経験と知識に基づいた落ち着いた回答"}
        if score > 0:
            params[SHINYA_NAME] = {"style": "共感的", "detail": "深い洞察と共感で優しく答える"}
            params[MINORU_NAME] = {"style": "柔軟", "detail": "多面的な知見から慎重に意見を述べる"}
        else:
            params[SHINYA_NAME] = {"style": "分析的", "detail": "豊かな経験に基づいた緻密な説明"}
            params[MINORU_NAME] = {"style": "客観的", "detail": "慎重かつ冷静に事実を丁寧に伝える"}
    return params

def generate_new_character() -> tuple:
    if custom_new_char_name.strip() and custom_new_char_personality.strip():
        return custom_new_char_name.strip(), custom_new_char_personality.strip()
    candidates = [
        ("たけし", "冷静沈着で皮肉屋、どこか孤高な存在"),
        ("さとる", "率直かつ辛辣で、常に現実を鋭く指摘する"),
        ("りさ", "自由奔放で斬新なアイデアを持つ、ユニークな感性の持ち主"),
        ("けんじ", "クールで合理的、論理に基づいた意見を率直に述べる"),
        ("なおみ", "独創的で個性的、常識にとらわれず新たな視点を提供する")
    ]
    return random.choice(candidates)

def generate_discussion(question: str, persona_params: dict, ai_age: int) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    prompt += f"このAIは{ai_age}歳として振る舞います。\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    new_name, new_personality = generate_new_character()
    prompt += f"さらに、新キャラクターとして {new_name} は【{new_personality}】な性格です。彼/彼女も会話に加わってください。\n"
    prompt += (
        "\n上記情報を元に、4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        f"ゆかり: 発言内容\n"
        f"しんや: 発言内容\n"
        f"みのる: 発言内容\n"
        f"{new_name}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(additional_input: str, current_discussion: str) -> str:
    prompt = (
        "これまでの会話:\n" + current_discussion + "\n\n" +
        "ユーザーの追加発言: " + additional_input + "\n\n" +
        "上記を踏まえ、4人がさらに自然な会話を続けてください。\n"
        "出力形式は以下の通りです。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        "新キャラクター: 発言内容\n"
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

# ------------------------------------------------------------------
# チャット履歴の表示（従来の形式）
# ------------------------------------------------------------------
# st.chat_message は role が "user" または "assistant" 以外だとエラーになるため、
# それ以外の場合は表示用に "assistant" として扱います。
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    # role_for_chat は "user" と "assistant" の場合はそのまま、その他は "assistant" に変換
    role_for_chat = role if role in ["user", "assistant"] else "assistant"
    display_name = st.session_state.get("user_name", "ユーザー") if role == "user" else role
    with st.chat_message(role_for_chat, avatar=avatar_img_dict.get(role, "🤖")):
        if role == "user":
            st.markdown(
                f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                unsafe_allow_html=True,
            )
        else:
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
            f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{st.session_state.get("user_name", "ユーザー")}</div>{user_input}</div></div>',
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
            role_for_chat = role if role in ["user", "assistant"] else "assistant"
            display_name = st.session_state.get("user_name", "ユーザー") if role == "user" else role
            with st.chat_message(role_for_chat, avatar=avatar_img_dict.get(role, "🤖")):
                if role == "user":
                    st.markdown(
                        f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{content}</div></div>',
                        unsafe_allow_html=True,
                    )
