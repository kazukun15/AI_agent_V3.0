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

# ▼ 画像解析用（ViTモデル）
import torch
from transformers import AutoFeatureExtractor, ViTForImageClassification
# ▲

from streamlit_chat import message  # streamlit-chat のメッセージ表示用関数

# =============================================================================
# 1. 基本設定・スタイル設定
# =============================================================================
st.set_page_config(page_title="ぼくのともだち", layout="wide")
st.title("ぼくのともだち V3.0 + 画像解析＆検索")

# config.toml からテーマ設定を読み込み
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

# =============================================================================
# 2. ユーザー入力とサイドバー設定
# =============================================================================
# ユーザー名とAIの年齢入力（AIの年齢は10歳以上）
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")
ai_age = st.number_input("AIの年齢を指定してください", min_value=10, value=30, step=1, key="ai_age")
# ※ st.text_input は内部で st.session_state["user_name"] に値を保存するため、追加代入は不要です

# サイドバー設定
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
        st.session_state["messages"] = []
    st.session_state["messages"].append({"role": "クイズ", "content": "クイズ: " + quiz["question"]})

st.sidebar.header("画像解析")
uploaded_image = st.sidebar.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"], key="file_uploader_key")

use_internet = st.sidebar.checkbox("インターネット検索を使用する", value=True, key="internet_search_checkbox_1")
st.sidebar.info("※スマホの場合は、画面左上のハンバーガーメニューからサイドバーにアクセスできます。")

# =============================================================================
# 3. キャラクター定義・セッション初期化
# =============================================================================
# キャラクター名の定数（固定メンバー）
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
YUKARI_NAME = "ゆかり"
SHINYA_NAME = "しんや"
MINORU_NAME = "みのる"
NEW_CHAR_NAME = "新キャラクター"
NAMES = [YUKARI_NAME, SHINYA_NAME, MINORU_NAME]

# 新キャラクターは一度だけ生成してセッションに保存
if "new_char" not in st.session_state:
    def generate_new_character():
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
    st.session_state.new_char = generate_new_character()
new_name, new_personality = st.session_state.new_char

# APIキー、モデル設定（Gemini API）
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"

# セッション初期化（メッセージ履歴、画像解析キャッシュ、その他）
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "analyzed_images" not in st.session_state:
    st.session_state["analyzed_images"] = {}
if "last_uploaded_hash" not in st.session_state:
    st.session_state.last_uploaded_hash = None
if "search_cache" not in st.session_state:
    st.session_state.search_cache = {}
if "gemini_status" not in st.session_state:
    st.session_state.gemini_status = ""
if "tavily_status" not in st.session_state:
    st.session_state.tavily_status = ""
if "chat_index" not in st.session_state:
    st.session_state.chat_index = 0
# 画像アップロードに対する会話生成が既に実施済みかを判定するフラグ
if "image_conversation_done" not in st.session_state:
    st.session_state.image_conversation_done = False

# =============================================================================
# 4. アイコン画像の読み込み（同じディレクトリの avatars フォルダを参照）
# =============================================================================
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
    NEW_CHAR_NAME: img_newchar,
    ASSISTANT_NAME: "🤖",
    "クイズ": "❓",
    "画像解析": "🖼️",
}

# =============================================================================
# 5. 各種API呼び出し、画像解析、検索処理
# =============================================================================
def remove_json_artifacts(text: str, pattern: str = r"'parts': \[\{'text':.*?\}\], 'role': 'model'") -> str:
    if not isinstance(text, str):
        text = str(text) if text else ""
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini_api(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            st.session_state.gemini_status = "Gemini API: OK"
        else:
            st.session_state.gemini_status = f"Gemini API Error {response.status_code}: {response.text}"
    except Exception as e:
        st.session_state.gemini_status = f"Gemini API Exception: {str(e)}"
        return f"エラー: リクエスト送信時に例外が発生しました -> {str(e)}"
    try:
        rjson = response.json()
        candidates = rjson.get("candidates", [])
        if not candidates:
            st.session_state.gemini_status = "Gemini API Error: candidatesが空"
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
            st.session_state.gemini_status = "Gemini API Error: contentが空"
            return "回答が見つかりませんでした。(contentが空)"
        st.session_state.gemini_status = "Gemini API: OK"
        return remove_json_artifacts(content_str)
    except Exception as e:
        st.session_state.gemini_status = f"Gemini API 応答解析エラー: {str(e)}"
        return f"エラー: レスポンス解析に失敗しました -> {str(e)}"

# ★ 高精度モデルとして ViT-Large を使用
@st.cache_resource
def load_image_classification_model():
    model_name = "google/vit-large-patch16-224"  # ViT-Large
    extractor = AutoFeatureExtractor.from_pretrained(model_name)
    model = ViTForImageClassification.from_pretrained(model_name)
    model.eval()
    return extractor, model

extractor, vit_model = load_image_classification_model()

# ★ TTA とアンサンブル手法を導入した画像解析関数
def analyze_image_with_vit(pil_image: Image.Image) -> str:
    # RGB変換
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    
    # torchvision.transforms を利用して前処理・データ拡張（TTA）
    from torchvision import transforms as T
    augmentation_transforms = [
         T.Compose([]),  # オリジナル
         T.Compose([T.RandomHorizontalFlip(p=1.0)]),
         T.Compose([T.RandomRotation(degrees=15)]),
         # 必要に応じて他の拡張も追加
    ]
    
    all_logits = []
    for aug in augmentation_transforms:
         augmented_img = aug(pil_image)
         inputs = extractor(augmented_img, return_tensors="pt")
         with torch.no_grad():
             outputs = vit_model(**inputs)
         all_logits.append(outputs.logits)
    
    # 各拡張画像の logits を平均（アンサンブル）
    avg_logits = sum(all_logits) / len(all_logits)
    probs = torch.nn.functional.softmax(avg_logits, dim=1)[0]
    
    # 上位3件の予測結果
    topk = avg_logits.topk(3, dim=1)
    top_indices = topk.indices[0].tolist()
    labels = vit_model.config.id2label
    result_str = []
    for idx in top_indices:
         label_name = labels[idx]
         confidence = probs[idx].item()
         result_str.append(f"{label_name} ({confidence*100:.1f}%)")
    return ", ".join(result_str)

from concurrent.futures import ThreadPoolExecutor

@st.cache_data(show_spinner=False)
def cached_get_search_info(query: str) -> str:
    url = "https://api.tavily.com/search"
    api_key = st.secrets["tavily"]["api_key"]
    headers = {
         "Authorization": f"Bearer {api_key}",
         "Content-Type": "application/json"
    }
    payload = {
         "query": query,
         "topic": "general",
         "search_depth": "basic",
         "max_results": 1,
         "time_range": None,
         "days": 3,
         "include_answer": True,
         "include_raw_content": False,
         "include_images": False,
         "include_image_descriptions": False,
         "include_domains": [],
         "exclude_domains": []
    }
    try:
         response = requests.post(url, headers=headers, json=payload)
         if response.status_code == 200:
             st.session_state.tavily_status = "tavily API: OK"
         else:
             st.session_state.tavily_status = f"tavily API Error {response.status_code}: {response.text}"
         data = response.json()
         result = data.get("answer", "")
         return result
    except Exception as e:
         st.session_state.tavily_status = f"tavily API Exception: {str(e)}"
         return ""

executor = ThreadPoolExecutor(max_workers=1)

def async_get_search_info(query: str) -> str:
    with st.spinner("最新情報を検索中…"):
        future = executor.submit(cached_get_search_info, query)
        return future.result()

# =============================================================================
# 6-2. 画像解析結果に基づく会話開始用関数（Gemini API を活用）
# =============================================================================
def discuss_image_analysis(analysis_text: str, ai_age: int) -> str:
    """
    画像解析結果に基づき、Gemini API を利用して詳細な説明・意見を生成する。
    """
    prompt = (
        f"以下の画像解析結果に基づいて、この画像について詳しく説明し、感想を述べてください。\n"
        f"画像解析結果: {analysis_text}\n\n"
        f"あなたの回答のみを出力してください。"
    )
    return call_gemini_api(prompt)

# =============================================================================
# 6. AI応答生成用関数（エージェントクラスなど）
# =============================================================================
def adjust_parameters(input_text, ai_age):
    # 簡易実装。必要に応じて詳細なロジックに変更してください。
    return {
       "ゆかり": {"style": "温かく優しい", "detail": "いつも明るい回答をします"},
       "しんや": {"style": "冷静沈着", "detail": "事実に基づいた分析を行います"},
       "みのる": {"style": "ユーモアたっぷり", "detail": "軽妙なジョークを交えた回答をします"}
    }

class ChatAgent:
    def __init__(self, name, style, detail):
        self.name = name
        self.style = style
        self.detail = detail

    def generate_response(self, question: str, ai_age: int, search_info: str = "") -> str:
        current_user = st.session_state.get("user_name", "ユーザー")
        prompt = f"【{current_user}さんの質問】\n{question}\n\n"
        if search_info:
            prompt += f"最新の情報によると、{search_info}という報告があります。\n"
        prompt += f"このAIは{ai_age}歳として振る舞います。\n"
        prompt += f"{self.name}は【{self.style}な視点】で、{self.detail}。\n"
        prompt += "あなたの回答のみを出力してください。"
        response = call_gemini_api(prompt)
        return response

def generate_discussion_parallel(question: str, persona_params: dict, ai_age: int, search_info: str = "") -> str:
    agents = []
    for name, params in persona_params.items():
        agents.append(ChatAgent(name, params["style"], params["detail"]))
    # 新キャラクターも追加
    new_agent = ChatAgent(new_name, new_personality, "")
    agents.append(new_agent)
    responses = {}
    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        future_to_agent = {executor.submit(agent.generate_response, question, ai_age, search_info): agent for agent in agents}
        for future in future_to_agent:
            agent = future_to_agent[future]
            responses[agent.name] = future.result()
    conversation = "\n".join([f"{agent.name}: {responses[agent.name]}" for agent in agents])
    return conversation

def continue_discussion_parallel(additional_input: str, history: str, ai_age: int, search_info: str = "") -> str:
    persona_params = adjust_parameters(additional_input, ai_age)
    agents = []
    for name, params in persona_params.items():
        agents.append(ChatAgent(name, params["style"], params["detail"]))
    new_agent = ChatAgent(new_name, new_personality, "")
    agents.append(new_agent)
    responses = {}
    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        future_to_agent = {executor.submit(agent.generate_response, additional_input, ai_age, search_info): agent for agent in agents}
        for future in future_to_agent:
            agent = future_to_agent[future]
            responses[agent.name] = future.result()
    conversation = "\n".join([f"{agent.name}: {responses[agent.name]}" for agent in agents])
    return conversation

# =============================================================================
# 7. 既存のチャットメッセージの表示
# =============================================================================
for msg in st.session_state["messages"]:
    role = msg["role"]
    content = msg["content"]
    display_name = user_name if role == "user" else role
    if role == "user":
        with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
            st.markdown(
                f'<div style="text-align: right;">'
                f'<div class="chat-bubble">'
                f'<div class="chat-header">{display_name}</div>{content}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    else:
        with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
            st.markdown(
                f'<div style="text-align: left;">'
                f'<div class="chat-bubble">'
                f'<div class="chat-header">{display_name}</div>{content}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# =============================================================================
# 8. ユーザー入力の取得とAI応答生成
# =============================================================================
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    search_info = async_get_search_info(user_input) if use_internet else ""
    
    if st.session_state.get("quiz_active", False):
        if user_input.strip().lower() == st.session_state.quiz_answer.strip().lower():
            quiz_result = "正解です！おめでとうございます！"
        else:
            quiz_result = f"残念、不正解です。正解は {st.session_state.quiz_answer} です。"
        st.session_state["messages"].append({"role": "クイズ", "content": quiz_result})
        with st.chat_message("クイズ", avatar=avatar_img_dict.get("クイズ", "❓")):
            st.markdown(
                f'<div style="text-align: left;">'
                f'<div class="chat-bubble">'
                f'<div class="chat-header">クイズ</div>{quiz_result}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        st.session_state.quiz_active = False
    else:
        with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
            st.markdown(
                f'<div style="text-align: right;">'
                f'<div class="chat-bubble">'
                f'<div class="chat-header">{user_name}</div>{user_input}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        st.session_state["messages"].append({"role": "user", "content": user_input})
        
        if len(st.session_state["messages"]) == 1:
            persona_params = adjust_parameters(user_input, ai_age)
            discussion = generate_discussion_parallel(user_input, persona_params, ai_age, search_info=search_info)
        else:
            history = "\n".join(
                f'{msg["role"]}: {msg["content"]}'
                for msg in st.session_state["messages"]
                if msg["role"] in NAMES or msg["role"] == NEW_CHAR_NAME
            )
            discussion = continue_discussion_parallel(user_input, history, ai_age, search_info=search_info)
        
        for line in discussion.split("\n"):
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                role = parts[0]
                content = parts[1].strip() if len(parts) > 1 else ""
                st.session_state["messages"].append({"role": role, "content": content})
                display_name = user_name if role == "user" else role
                if role == "user":
                    with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
                        st.markdown(
                            f'<div style="text-align: right;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{display_name}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
                        st.markdown(
                            f'<div style="text-align: left;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{display_name}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                time.sleep(random.uniform(3, 10))  # ランダムな遅延（3～10秒）

# =============================================================================
# 9. 画像アップロード時の処理：画像解析と会話開始（1回のみ）
# =============================================================================
if not st.session_state.get("quiz_active", False) and uploaded_image is not None:
    image_bytes = uploaded_image.getvalue()
    image_hash = hashlib.md5(image_bytes).hexdigest()
    # 新規画像の場合はフラグをリセット
    if st.session_state.last_uploaded_hash != image_hash:
        st.session_state.last_uploaded_hash = image_hash
        st.session_state.image_conversation_done = False
    # 画像会話がまだ行われていなければ実施
    if not st.session_state.get("image_conversation_done", False):
        if image_hash in st.session_state["analyzed_images"]:
            analysis_text = st.session_state["analyzed_images"][image_hash]
        else:
            pil_img = Image.open(BytesIO(image_bytes))
            label_text = analyze_image_with_vit(pil_img)  # 高精度モデル＋TTA・アンサンブル
            analysis_text = f"{label_text}"
            st.session_state["analyzed_images"][image_hash] = analysis_text

        # 画像解析結果の表示
        st.session_state["messages"].append({"role": "画像解析", "content": analysis_text})
        with st.chat_message("画像解析", avatar=avatar_img_dict.get("画像解析", "🖼️")):
            st.markdown(
                f'<div style="text-align: left;">'
                f'<div class="chat-bubble">'
                f'<div class="chat-header">画像解析</div>{analysis_text}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        
        # 友達全員で画像について意見を出す会話を開始する（1回のみ）
        conversation_among_friends = generate_discussion_parallel(
            question=f"この画像についてどう思いますか？ 画像解析結果: {analysis_text}",
            persona_params=adjust_parameters(analysis_text, ai_age),
            ai_age=ai_age,
            search_info=""
        )
        for line in conversation_among_friends.split("\n"):
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                role = parts[0]
                content = parts[1].strip() if len(parts) > 1 else ""
                st.session_state["messages"].append({"role": role, "content": content})
                if role == "user":
                    with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
                        st.markdown(
                            f'<div style="text-align: right;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{user_name}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
                        st.markdown(
                            f'<div style="text-align: left;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{role}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                time.sleep(random.uniform(3, 10))
        
        # さらに、Gemini API を活用して詳細な補完コメントを取得し、会話に追加
        detailed_comment = discuss_image_analysis(analysis_text, ai_age)
        for line in detailed_comment.split("\n"):
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                role = parts[0]
                content = parts[1].strip() if len(parts) > 1 else ""
                st.session_state["messages"].append({"role": role, "content": content})
                if role == "user":
                    with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
                        st.markdown(
                            f'<div style="text-align: right;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{user_name}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    with st.chat_message(role, avatar=avatar_img_dict.get(role, "🤖")):
                        st.markdown(
                            f'<div style="text-align: left;">'
                            f'<div class="chat-bubble">'
                            f'<div class="chat-header">{role}</div>{content}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                time.sleep(random.uniform(3, 10))
        
        # 画像アップロード時の会話生成は1回だけ実施する
        st.session_state.image_conversation_done = True
        
        # 画像アップロード処理が終わったら、アップロードウィジェットをクリア（キーの値を None に設定）
        st.session_state["file_uploader_key"] = None

# =============================================================================
# 10. チャット履歴の表示
# =============================================================================
st.header("会話履歴")
if st.session_state["messages"]:
    for msg in reversed(st.session_state["messages"]):
        display_name = user_name if msg["role"] == "user" else msg["role"]
        if msg["role"] == "user":
            with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
                st.markdown(
                    f'<div style="text-align: right;">'
                    f'<div class="chat-bubble">'
                    f'<div class="chat-header">{display_name}</div>{msg["content"]}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            with st.chat_message(msg["role"], avatar=avatar_img_dict.get(msg["role"], "🤖")):
                st.markdown(
                    f'<div style="text-align: left;">'
                    f'<div class="chat-bubble">'
                    f'<div class="chat-header">{display_name}</div>{msg["content"]}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
else:
    st.markdown("<p style='color: gray;'>ここに会話が表示されます。</p>", unsafe_allow_html=True)

# =============================================================================
# 11. APIステータスの表示（サイドバー）
# =============================================================================
st.sidebar.header("APIステータス")
st.sidebar.write("【Gemini API】", st.session_state.gemini_status)
st.sidebar.write("【tavily API】", st.session_state.tavily_status)
st.sidebar.success("OK")
