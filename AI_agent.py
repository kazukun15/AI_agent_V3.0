import os
import streamlit as st
import requests
import re
import random
import json
import hashlib  # 画像ハッシュ用
import time    # 遅延用
from io import BytesIO
from PIL import Image
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ▼ 画像解析用に追加（ViTモデル）
import torch
from transformers import AutoFeatureExtractor, ViTForImageClassification
# ▲

from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数

# ------------------------------------------------------------------
# st.set_page_config() は最初に呼び出す
# ------------------------------------------------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0 + 画像解析＆検索")

# ------------------------------------------------------------------
# config.toml の読み込み（テーマ設定）
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
except Exception:
    primaryColor = "#729075"
    backgroundColor = "#f1ece3"
    secondaryBackgroundColor = "#fff8ef"
    textColor = "#5e796a"
    font = "monospace"

# ------------------------------------------------------------------
# 背景・共通スタイルの設定
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
# ユーザーの名前・AIの年齢入力
# ------------------------------------------------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")
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

# ------------------------------------------------------------------
# サイドバー：画像解析用アップロード
# ------------------------------------------------------------------
st.sidebar.header("画像解析")
uploaded_image = st.sidebar.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

# ------------------------------------------------------------------
# サイドバー：インターネット検索利用のON/OFF
# ------------------------------------------------------------------
use_internet = st.sidebar.checkbox("インターネット検索を使用する", value=True)

# ------------------------------------------------------------------
# サイドバー：APIステータス確認
# ------------------------------------------------------------------
st.sidebar.header("APIステータス確認")
def check_gemini_api_status():
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": "ステータスチェック"}]}]}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
    except Exception as e:
        return f"エラー: リクエスト送信時に例外が発生しました -> {str(e)}"
    if response.status_code != 200:
        return f"エラー: ステータスコード {response.status_code} -> {response.text}"
    return "OK"

def check_tavily_api_status():
    url = "https://api.tavily.com/search"
    params = {
        "q": "test",
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }
    try:
        response = requests.get(url, params=params)
    except Exception as e:
        return f"エラー: リクエスト送信時に例外が発生しました -> {str(e)}"
    if response.status_code != 200:
        return f"エラー: ステータスコード {response.status_code} -> {response.text}"
    return "OK"

if st.sidebar.button("APIステータス確認"):
    gemini_status = check_gemini_api_status()
    tavily_status = check_tavily_api_status()
    st.sidebar.write("Gemini API: ", gemini_status)
    st.sidebar.write("Tavily API: ", tavily_status)

# ------------------------------------------------------------------
# キャラクター定義
# ------------------------------------------------------------------
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"  # 表示用のキー
NAMES = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# ------------------------------------------------------------------
# 新キャラクター情報の初期化（アプリ起動時に一度だけ生成）
# ------------------------------------------------------------------
if "new_char" not in st.session_state:
    if custom_new_char_name.strip() and custom_new_char_personality.strip():
        st.session_state.new_char = (custom_new_char_name.strip(), custom_new_char_personality.strip())
    else:
        candidates = [
            ("たけし", "冷静沈着で皮肉屋、どこか孤高な存在"),
            ("さとる", "率直かつ辛辣で、常に現実を鋭く指摘する"),
            ("りさ", "自由奔放で斬新なアイデアを持つ、ユニークな感性の持ち主"),
            ("けんじ", "クールで合理的、論理に基づいた意見を率直に述べる"),
            ("なおみ", "独創的で個性的、常識にとらわれず新たな視点を提供する")
        ]
        st.session_state.new_char = random.choice(candidates)

# ------------------------------------------------------------------
# APIキー、モデル設定（Gemini API）
# ------------------------------------------------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"

# ------------------------------------------------------------------
# セッション初期化：チャット履歴、画像解析キャッシュ、最後の画像ハッシュ、検索結果キャッシュ
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "analyzed_images" not in st.session_state:
    st.session_state.analyzed_images = {}
if "last_uploaded_hash" not in st.session_state:
    st.session_state.last_uploaded_hash = None
if "search_cache" not in st.session_state:
    st.session_state.search_cache = {}

# ------------------------------------------------------------------
# アバター画像の読み込み
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
avatar_dir = os.path.join(BASE_DIR, "avatars")
try:
    img_user = Image.open(os.path.join(avatar_dir, "user.png"))
    img_yukari = Image.open(os.path.join(avatar_dir, "yukari.png"))
    img_shinya = Image.open(os.path.join(avatar_dir, "shinya.png"))
    img_minoru = Image.open(os.path.join(avatar_dir, "minoru.png"))
    img_newchar = Image.open(os.path.join(avatar_dir, "new_character.png"))
except Exception as e:
    st.error(f"画像読み込みエラー: {e}")
    img_user, img_yukari, img_shinya, img_minoru, img_newchar = "👤", "🌸", "🌊", "🍀", "⭐"

avatar_img_dict = {
    USER_NAME: img_user,
    YUKARI_NAME: img_yukari,
    SHINYA_NAME: img_shinya,
    MINORU_NAME: img_minoru,
    NEW_CHAR_NAME: img_newchar,  # 新キャラクターの画像は固定
    ASSISTANT_NAME: "🤖",
    "クイズ": "❓",
    "画像解析": "🖼️",
}

# ------------------------------------------------------------------
# Gemini API 呼び出し関数
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
# ViTモデルを用いた画像解析モデルのロード（キャッシュ）
# ------------------------------------------------------------------
@st.cache_resource
def load_image_classification_model():
    model_name = "google/vit-base-patch16-224"
    extractor = AutoFeatureExtractor.from_pretrained(model_name)
    model = ViTForImageClassification.from_pretrained(model_name)
    model.eval()
    return extractor, model

extractor, vit_model = load_image_classification_model()

def analyze_image_with_vit(pil_image: Image.Image) -> str:
    """ViTで画像分類を行い、上位3クラスを文字列化。RGB変換済み"""
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    inputs = extractor(pil_image, return_tensors="pt")
    with torch.no_grad():
        outputs = vit_model(**inputs)
    logits = outputs.logits
    topk = logits.topk(3)
    top_indices = topk.indices[0].tolist()
    probs = torch.nn.functional.softmax(logits, dim=1)[0]
    labels = vit_model.config.id2label
    result_str = []
    for idx in top_indices:
        label_name = labels[idx]
        confidence = probs[idx].item()
        result_str.append(f"{label_name} ({confidence*100:.1f}%)")
    return ", ".join(result_str)

# ------------------------------------------------------------------
# インターネット検索結果取得（Tavily API利用＋キャッシュ＆非同期処理）
# ------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_get_search_info(query: str) -> str:
    url = "https://api.tavily.com/search"
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        result = data.get("AbstractText", "")
        return result
    except Exception as e:
        return ""

executor = ThreadPoolExecutor(max_workers=1)

def async_get_search_info(query: str) -> str:
    with st.spinner("最新情報を検索中…"):
        future = executor.submit(cached_get_search_info, query)
        return future.result()

# ------------------------------------------------------------------
# 会話生成関連の関数
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

def generate_discussion(question: str, persona_params: dict, ai_age: int, search_info: str = "") -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    new_name, new_personality = st.session_state.new_char
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    if search_info:
        prompt += f"最新の情報によると、{search_info}という報告があります。\n"
    prompt += f"このAIは{ai_age}歳として振る舞います。\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    prompt += f"さらに、新キャラクターとして {new_name} は【{new_personality}】な性格です。彼/彼女も会話に加わってください。\n"
    prompt += (
        "\n※ユーザーの発言は記録されますが、他のキャラクターはユーザーの発言を引用せず、自分の意見だけで回答してください。\n"
        "上記情報を元に、4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        f"ゆかり: 発言内容\n"
        f"しんや: 発言内容\n"
        f"みのる: 発言内容\n"
        f"{new_name}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def continue_discussion(additional_input: str, current_discussion: str, search_info: str = "") -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    new_name, _ = st.session_state.new_char
    prompt = (
        "これまでの会話:\n" + current_discussion + "\n\n" +
        "ユーザーの追加発言: " + additional_input + "\n\n"
    )
    if search_info:
        prompt += f"最新の情報によると、{search_info}という報告もあります。\n"
    prompt += (
        "\n※ユーザーの発言は記録されますが、他のキャラクターはユーザーの発言を引用せず、自分の意見だけで回答してください。\n"
        "上記を踏まえ、4人がさらに自然な会話を続けてください。\n"
        "出力形式は以下の通りです。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
        f"{new_name}: 発言内容\n"
        "余計なJSON形式は入れず、自然な日本語の会話のみを出力してください。"
    )
    return call_gemini_api(prompt)

def discuss_image_analysis(analysis_text: str, persona_params: dict, ai_age: int) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    new_name, new_personality = st.session_state.new_char
    prompt = (
        f"【{current_user}さんが画像をアップロードしました】\n"
        f"画像の推定結果: {analysis_text}\n\n"
        "この画像に関連しそうな話題について、4人の友達（ゆかり、しんや、みのる、"
        f"{new_name}）が気軽に雑談を始めてください。\n"
        "画像そのものの詳細な分析ではなく、画像を見たときの印象や連想されるエピソードを自由に話してください。\n"
        "出力形式は以下の通りです。\n"
        f"ゆかり: 発言内容\n"
        f"しんや: 発言内容\n"
        f"みのる: 発言内容\n"
        f"{new_name}: 発言内容\n"
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
# 既存のチャットメッセージを表示
# ------------------------------------------------------------------
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    display_name = user_name if role == "user" else role
    if role == "user":
        with st.chat_message(role, avatar=avatar_img_dict.get(USER_NAME)):
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
# 画像アップロードがあれば、かつ新しい画像の場合のみ解析し会話開始
# ------------------------------------------------------------------
if uploaded_image is not None:
    image_bytes = uploaded_image.getvalue()
    image_hash = hashlib.md5(image_bytes).hexdigest()
    if st.session_state.last_uploaded_hash != image_hash:
        st.session_state.last_uploaded_hash = image_hash
        if image_hash in st.session_state.analyzed_images:
            analysis_text = st.session_state.analyzed_images[image_hash]
        else:
            pil_img = Image.open(BytesIO(image_bytes))
            label_text = analyze_image_with_vit(pil_img)  # ViTで解析（RGB変換済み）
            analysis_text = f"{label_text}"
            st.session_state.analyzed_images[image_hash] = analysis_text

        # (A) 解析結果をチャットログへ追加＆表示
        st.session_state.messages.append({"role": "画像解析", "content": analysis_text})
        with st.chat_message("画像解析", avatar=avatar_img_dict["画像解析"]):
            st.markdown(
                f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">画像解析</div>{analysis_text}</div></div>',
                unsafe_allow_html=True,
            )

        # (B) 画像に関連する話題を友達が始める
        persona_params = adjust_parameters("image analysis", ai_age)
        discussion_about_image = discuss_image_analysis(analysis_text, persona_params, ai_age)
        for line in discussion_about_image.split("\n"):
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                role = parts[0]
                content = parts[1].strip() if len(parts) > 1 else ""
                st.session_state.messages.append({"role": role, "content": content})
                display_name = user_name if role == "user" else role
                if role == "user":
                    with st.chat_message(role, avatar=avatar_img_dict.get(USER_NAME)):
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
                time.sleep(random.uniform(3, 10))  # ランダムな遅延（3～10秒）

# ------------------------------------------------------------------
# テキスト入力（st.chat_input）による通常会話
# ------------------------------------------------------------------
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    # インターネット検索を利用する場合は、キャッシュ＆非同期処理で結果を取得
    search_info = async_get_search_info(user_input) if use_internet else ""
    
    if st.session_state.get("quiz_active", False):
        if user_input.strip().lower() == st.session_state.quiz_answer.strip().lower():
            quiz_result = "正解です！おめでとうございます！"
        else:
            quiz_result = f"残念、不正解です。正解は {st.session_state.quiz_answer} です。"
        st.session_state.messages.append({"role": "クイズ", "content": quiz_result})
        with st.chat_message("クイズ", avatar=avatar_img_dict["クイズ"]):
            st.markdown(
                f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">クイズ</div>{quiz_result}</div></div>',
                unsafe_allow_html=True,
            )
        st.session_state.quiz_active = False
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
            st.markdown(
                f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{user_name}</div>{user_input}</div></div>',
                unsafe_allow_html=True,
            )
        if len(st.session_state.messages) == 1:
            persona_params = adjust_parameters(user_input, ai_age)
            discussion = generate_discussion(user_input, persona_params, ai_age, search_info=search_info)
        else:
            history = "\n".join(
                f'{msg["role"]}: {msg["content"]}'
                for msg in st.session_state.messages
                if msg["role"] in NAMES or msg["role"] == NEW_CHAR_NAME
            )
            discussion = continue_discussion(user_input, history, search_info=search_info)
        for line in discussion.split("\n"):
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                role = parts[0]
                content = parts[1].strip() if len(parts) > 1 else ""
                st.session_state.messages.append({"role": role, "content": content})
                display_name = user_name if role == "user" else role
                if role == "user":
                    with st.chat_message(role, avatar=avatar_img_dict.get(USER_NAME)):
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
                time.sleep(random.uniform(3, 10))  # ランダムな遅延（3～10秒）
