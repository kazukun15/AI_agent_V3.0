import os
import streamlit as st
import requests
import re
import random
import json
from PIL import Image
from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数

# ------------------------------------------------------------------
# config.toml の読み込み（同一ディレクトリにある場合）
# ------------------------------------------------------------------
try:
    try:
        import tomllib  # Python 3.11以降の場合
    except ImportError:
        import toml as tomllib
    with open("config.toml", "rb") as f:
        config_data = tomllib.load(f)
    theme_config = config_data.get("theme", {})
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
# ページ設定
# ------------------------------------------------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0")

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
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------------
# ユーザーの名前入力（上部）
# ------------------------------------------------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")

# ------------------------------------------------------------------
# AIの年齢入力（上部）
# ------------------------------------------------------------------
ai_age = st.number_input("AIの年齢を指定してください", min_value=1, value=30, step=1, key="ai_age")

# ------------------------------------------------------------------
# サイドバー：カスタム新キャラクター設定＆クイズ機能
# ------------------------------------------------------------------
st.sidebar.header("カスタム新キャラクター設定")
custom_new_char_name = st.sidebar.text_input("新キャラクターの名前（未入力ならランダム）", value="", key="custom_new_char_name")
custom_new_char_personality = st.sidebar.text_area("新キャラクターの性格・特徴（未入力ならランダム）", value="", key="custom_new_char_personality")

st.sidebar.header("ミニゲーム／クイズ")
if st.sidebar.button("クイズを開始する", key="quiz_start_button"):
    quiz_list = [
        {"question": "日本の首都は？", "answer": "東京"},
        {"question": "富士山の標高は何メートル？", "answer": "3776"},
        {"question": "寿司の主な具材は何？", "answer": "酢飯"},
        {"question": "桜の花言葉は？", "answer": "美しさ"}
    ]
    quiz = random.choice(quiz_list)
    st.session_state.quiz_active = True
    st.session_state.quiz_question = quiz["question"]
    st.session_state.quiz_answer = quiz["answer"]
    if "messages" not in st.session_state:
        st.session_state.messages = []
    st.session_state.messages.append({"role": "クイズ", "content": "クイズ: " + quiz["question"]})

st.sidebar.info("※スマホの場合は、画面左上のハンバーガーメニューからサイドバーにアクセスできます。")

# ------------------------------------------------------------------
# キャラクター定義（固定メンバー）
# ------------------------------------------------------------------
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"

# ------------------------------------------------------------------
# 定数／設定（APIキー、モデル）
# ------------------------------------------------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"
NAMES = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# ------------------------------------------------------------------
# セッション初期化（チャット履歴：messages）
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------------------------------------------------------
# アイコン画像の読み込み（AI_agent_V3.0/avatars/ に配置）
# ------------------------------------------------------------------
# このスクリプトの絶対パスを基準に、avatars ディレクトリを指定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
avatar_dir = os.path.join(BASE_DIR, "AI_agent_V3.0", "avatars")
try:
    img_user = Image.open(os.path.join(avatar_dir, "user.png"))
    img_yukari = Image.open(os.path.join(avatar_dir, "yukari.png"))
    img_shinya = Image.open(os.path.join(avatar_dir, "shinya.png"))
    img_minoru = Image.open(os.path.join(avatar_dir, "minoru.png"))
    img_newchar = Image.open(os.path.join(avatar_dir, "new_character.png"))
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
    ASSISTANT_NAME: "🤖",
}

# ------------------------------------------------------------------
# Gemini API 呼び出し関数（requests 使用）
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
    """サイドバーで入力があればそれを使い、なければランダム"""
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

def display_chat_log(chat_log: list):
    """
    chat_log の各メッセージを、LINE風のチャットバブル形式で表示する。
    ユーザーの発言は右寄せ、友達の発言は左寄せで表示され、テキストは自動で折り返されます。
    最新のメッセージが入力バーの直上に表示されるよう、チャットログは逆順に表示します。
    """
    from streamlit_chat import message as st_message
    for msg in reversed(chat_log):
        # "role"/"content" または "sender"/"message" に対応
        sender = msg.get("role", msg.get("sender", "不明"))
        text = msg.get("content", msg.get("message", ""))
        if sender == "user":
            st_message(text, is_user=True)
        else:
            st_message(f"{sender}: {text}", is_user=False)

# ------------------------------------------------------------------
# 初回会話の自動生成は削除（ユーザーが発言したときのみ応答）
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 固定フッター（入力エリア）の配置
# ------------------------------------------------------------------
with st.container():
    st.markdown(
        '<div style="position: fixed; bottom: 0; width: 100%; background: #FFF; padding: 10px; box-shadow: 0 -2px 5px rgba(0,0,0,0.1);">',
        unsafe_allow_html=True,
    )
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area("新たな発言を入力してください", placeholder="ここに入力", height=100, key="user_input")
        col1, col2 = st.columns(2)
        with col1:
            send_button = st.form_submit_button("送信")
        with col2:
            continue_button = st.form_submit_button("続きを話す")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 送信ボタンの処理
    if send_button:
        if user_input.strip():
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
        else:
            st.warning("発言を入力してください。")
    
    # 続きを話すボタンの処理
    if continue_button:
        if st.session_state.messages:
            default_input = "続きをお願いします。"
            history = "\n".join(
                f'{msg["role"]}: {msg["content"]}'
                for msg in st.session_state.messages
                if msg["role"] in NAMES or msg["role"] == NEW_CHAR_NAME
            )
            new_discussion = continue_discussion(default_input, history)
            for line in new_discussion.split("\n"):
                line = line.strip()
                if line:
                    parts = line.split(":", 1)
                    role = parts[0]
                    content = parts[1].strip() if len(parts) > 1 else ""
                    st.session_state.messages.append({"role": role, "content": content})
        else:
            st.warning("まずは会話を開始してください。")

# ------------------------------------------------------------------
# チャット履歴の表示
# ------------------------------------------------------------------
st.header("会話履歴")
if st.session_state.messages:
    for msg in reversed(st.session_state.messages):
        display_name = user_name if msg["role"] == "user" else msg["role"]
        if msg["role"] == "user":
            with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
                st.markdown(
                    f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{msg["content"]}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            with st.chat_message(msg["role"], avatar=avatar_img_dict.get(msg["role"], "🤖")):
                st.markdown(
                    f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">{display_name}</div>{msg["content"]}</div></div>',
                    unsafe_allow_html=True,
                )
else:
    st.markdown("<p style='color: gray;'>ここに会話が表示されます。</p>", unsafe_allow_html=True)
