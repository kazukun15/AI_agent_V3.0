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
# 関数定義（まずは必要な関数を定義）
# ------------------------------------------------------------------

def analyze_question(question: str) -> int:
    """質問文から感情キーワードと論理キーワードを解析し、スコアを返す"""
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
    """
    質問とAIの年齢に応じて、各キャラクターのプロンプトパラメータを生成する
    ※若年層、中年層、シニア層で回答のスタイルを変えています。
    """
    score = analyze_question(question)
    params = {}
    if ai_age < 30:
        params["ゆかり"] = {"style": "明るくはっちゃけた", "detail": "とにかくエネルギッシュでポジティブな回答"}
        if score > 0:
            params["しんや"] = {"style": "共感的", "detail": "若々しい感性で共感しながら答える"}
            params["みのる"] = {"style": "柔軟", "detail": "自由な発想で斬新な視点から回答する"}
        else:
            params["しんや"] = {"style": "分析的", "detail": "新しい視点を持ちつつ、若々しく冷静に答える"}
            params["みのる"] = {"style": "客観的", "detail": "柔軟な思考で率直に事実を述べる"}
    elif ai_age < 50:
        params["ゆかり"] = {"style": "温かく落ち着いた", "detail": "経験に基づいたバランスの取れた回答"}
        if score > 0:
            params["しんや"] = {"style": "共感的", "detail": "深い理解と共感を込めた回答"}
            params["みのる"] = {"style": "柔軟", "detail": "実務的な視点から多角的な意見を提供"}
        else:
            params["しんや"] = {"style": "分析的", "detail": "冷静な視点から根拠をもって説明する"}
            params["みのる"] = {"style": "客観的", "detail": "理論的かつ中立的な視点で回答する"}
    else:
        params["ゆかり"] = {"style": "賢明で穏やかな", "detail": "豊富な経験と知識に基づいた落ち着いた回答"}
        if score > 0:
            params["しんや"] = {"style": "共感的", "detail": "深い洞察と共感で優しく答える"}
            params["みのる"] = {"style": "柔軟", "detail": "多面的な知見から慎重に意見を述べる"}
        else:
            params["しんや"] = {"style": "分析的", "detail": "豊かな経験に基づいた緻密な説明"}
            params["みのる"] = {"style": "客観的", "detail": "慎重かつ冷静に事実を丁寧に伝える"}
    return params

def remove_json_artifacts(text: str, pattern: str = r"'parts': \[\{'text':.*?\}\], 'role': 'model'") -> str:
    """不要な文字列を正規表現で除去（patternは引数で変更可能）"""
    if not isinstance(text, str):
        text = str(text) if text else ""
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini_api(prompt: str) -> str:
    """Gemini API を呼び出して生成テキストを返す"""
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
    """ViTで画像分類を行い、上位3クラスを文字列化（RGB変換済み）"""
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
# インターネット検索実行（tavily API利用＋キャッシュ＆非同期処理）
# ------------------------------------------------------------------
from concurrent.futures import ThreadPoolExecutor

@st.cache_data(show_spinner=False)
def cached_get_search_info(query: str) -> str:
    url = "https://api.tavily.com/search"
    # secret の形式は [tavily] api_key = "○○○" と仮定
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

# ------------------------------------------------------------------
# クラス定義：各エージェント（キャラクター）ごとに応答生成を行う
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# 並列実行用：エージェントごとの応答生成（並列化で高速化）
# ------------------------------------------------------------------
def generate_discussion_parallel(question: str, persona_params: dict, ai_age: int, search_info: str = "") -> str:
    agents = []
    for name, params in persona_params.items():
        agents.append(ChatAgent(name, params["style"], params["detail"]))
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

# ------------------------------------------------------------------
# 既存のチャットメッセージを表示（st.chat_input 形式）
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
# ユーザー入力の取得（st.chat_input）
# ------------------------------------------------------------------
user_input = st.chat_input("何か質問や話したいことがありますか？")
if user_input:
    # インターネット検索利用（tavily API） ※チェックボックスは先に定義した use_internet を利用
    search_info = async_get_search_info(user_input) if use_internet else ""
    
    if st.session_state.get("quiz_active", False):
        if user_input.strip().lower() == st.session_state.quiz_answer.strip().lower():
            quiz_result = "正解です！おめでとうございます！"
        else:
            quiz_result = f"残念、不正解です。正解は {st.session_state.quiz_answer} です。"
        st.session_state.messages.append({"role": "クイズ", "content": quiz_result})
        with st.chat_message("クイズ", avatar=avatar_img_dict.get("クイズ", "❓")):
            st.markdown(
                f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">クイズ</div>{quiz_result}</div></div>',
                unsafe_allow_html=True,
            )
        st.session_state.quiz_active = False
    else:
        with st.chat_message("user", avatar=avatar_img_dict.get(USER_NAME)):
            st.markdown(
                f'<div style="text-align: right;"><div class="chat-bubble"><div class="chat-header">{user_name}</div>{user_input}</div></div>',
                unsafe_allow_html=True,
            )
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # AI応答生成（並列処理を利用）
        if len(st.session_state.messages) == 1:
            persona_params = adjust_parameters(user_input, ai_age)
            discussion = generate_discussion_parallel(user_input, persona_params, ai_age, search_info=search_info)
        else:
            history = "\n".join(
                f'{msg["role"]}: {msg["content"]}'
                for msg in st.session_state.messages
                if msg["role"] in NAMES or msg["role"] == NEW_CHAR_NAME
            )
            discussion = continue_discussion_parallel(user_input, history, ai_age, search_info=search_info)
        
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

# ------------------------------------------------------------------
# 画像アップロードがあれば、かつ新しい画像の場合のみ解析し会話開始
# ------------------------------------------------------------------
if not st.session_state.get("quiz_active", False) and uploaded_image is not None:
    image_bytes = uploaded_image.getvalue()
    image_hash = hashlib.md5(image_bytes).hexdigest()
    if st.session_state.last_uploaded_hash != image_hash:
        st.session_state.last_uploaded_hash = image_hash
        if image_hash in st.session_state.analyzed_images:
            analysis_text = st.session_state.analyzed_images[image_hash]
        else:
            pil_img = Image.open(BytesIO(image_bytes))
            label_text = analyze_image_with_vit(pil_img)  # ViTで解析
            analysis_text = f"{label_text}"
            st.session_state.analyzed_images[image_hash] = analysis_text

        st.session_state.messages.append({"role": "画像解析", "content": analysis_text})
        with st.chat_message("画像解析", avatar=avatar_img_dict.get("画像解析", "🖼️")):
            st.markdown(
                f'<div style="text-align: left;"><div class="chat-bubble"><div class="chat-header">画像解析</div>{analysis_text}</div></div>',
                unsafe_allow_html=True,
            )

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

# ------------------------------------------------------------------
# APIステータスの表示（サイドバー）
# ------------------------------------------------------------------
st.sidebar.header("APIステータス")
st.sidebar.write("【Gemini API】", st.session_state.gemini_status)
st.sidebar.write("【tavily API】", st.session_state.tavily_status)
