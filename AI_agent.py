import streamlit as st
import requests
import re
import random

# ------------------------
# ページ設定
# ------------------------
st.set_page_config(page_title="ぼくのともだち", layout="wide")

# タイトルの表示
st.title("ぼくのともだち V2.2")

# ------------------------
# ユーザーの名前入力（画面上部に表示）
# ------------------------
user_name = st.text_input("あなたの名前を入力してください", value="ユーザー", key="user_name")

# ------------------------
# 定数／設定
# ------------------------
API_KEY = st.secrets["general"]["api_key"]
MODEL_NAME = "gemini-2.0-flash-001"  # 必要に応じて変更
# 既存のキャラクター
NAMES = ["ゆかり", "しんや", "みのる"]

# ------------------------
# 新キャラクター生成用関数
# ------------------------
def generate_new_character() -> tuple:
    """
    新キャラクターをランダムで生成する。
    性格は既存の3人（ゆかり、しんや、みのる）とは全く異なる特徴を持つように設定する。
    """
    candidates = [
        ("たけし", "冷静沈着で皮肉屋、どこか孤高な雰囲気"),
        ("さとる", "率直で物事を突き詰める、時に辛辣な現実主義者"),
        ("りさ", "自由奔放で独創的、常識にとらわれない斬新な視点"),
        ("けんじ", "クールで分析的、冷静かつ合理的な判断力を持つ"),
        ("なおみ", "柔軟でユーモアにあふれ、独自の哲学を語る")
    ]
    return random.choice(candidates)

# ------------------------
# 関数定義（既存の処理）
# ------------------------
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

def adjust_parameters(question: str) -> dict:
    score = analyze_question(question)
    params = {}
    params["ゆかり"] = {"style": "明るくはっちゃけた", "detail": "楽しい雰囲気で元気な回答"}
    if score > 0:
        params["しんや"] = {"style": "共感的", "detail": "心情を重視した解説"}
        params["みのる"] = {"style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        params["しんや"] = {"style": "分析的", "detail": "データや事実を踏まえた説明"}
        params["みのる"] = {"style": "客観的", "detail": "中立的な視点からの考察"}
    return params

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

def generate_discussion(question: str, persona_params: dict) -> str:
    current_user = st.session_state.get("user_name", "ユーザー")
    prompt = f"【{current_user}さんの質問】\n{question}\n\n"
    for name, params in persona_params.items():
        prompt += f"{name}は【{params['style']}な視点】で、{params['detail']}。\n"
    # 新キャラクターの生成
    new_name, new_personality = generate_new_character()
    prompt += f"さらに、新キャラクターとして {new_name} は【{new_personality}】な性格です。彼/彼女も会話に加わってください。\n"
    prompt += (
        "\n上記情報を元に、4人が友達同士のように自然な会話をしてください。\n"
        "出力形式は以下の通りです。\n"
        "ゆかり: 発言内容\n"
        "しんや: 発言内容\n"
        "みのる: 発言内容\n"
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

def display_line_style(text: str):
    """
    各発言をキャラクターごとの背景色・文字色と、配置（ユーザーは右寄せ、他は左寄せ）で吹き出し表示する。
    新しいメッセージが上部に表示されるよう逆順に表示します。
    """
    lines = text.split("\n")
    # 空行を除いて逆順にする（最新メッセージが上）
    lines = [line.strip() for line in lines if line.strip()]
    lines = list(reversed(lines))
    
    color_map = {
        "ユーザー": {"bg": "#CCE5FF", "color": "#000", "align": "right"},
        "ゆかり": {"bg": "#FFD1DC", "color": "#000", "align": "left"},
        "しんや": {"bg": "#D1E8FF", "color": "#000", "align": "left"},
        "みのる": {"bg": "#D1FFD1", "color": "#000", "align": "left"}
    }
    # 新キャラクターは"新キャラクター"という固定ラベルにする
    new_character_label = "新キャラクター"
    for line in lines:
        matched = re.match(r"^(ゆかり|しんや|みのる|新キャラクター|[^\:]+):\s*(.*)$", line)
        if matched:
            sender = matched.group(1)
            message = matched.group(2)
        else:
            sender = ""
            message = line
        if sender not in color_map:
            # 新キャラクターのスタイル（ユーザーとは異なり、左寄せ）
            style = {"bg": "#FFE4B5", "color": "#000", "align": "left"}
        else:
            style = color_map[sender]
        bubble_html = (
            f'<div style="background-color: {style["bg"]}; border: 1px solid #ddd; border-radius: 10px; '
            f'padding: 8px; margin: 5px; color: {style["color"]}; font-family: Arial, sans-serif; '
            f'text-align: {style["align"]}; max-width: 80%;">'
            f'<strong>{sender}</strong><br>{message}</div>'
        )
        st.markdown(bubble_html, unsafe_allow_html=True)

def generate_new_character() -> tuple:
    """
    ランダムで新キャラクターの名前と性格を生成する。
    既存のキャラクター（ゆかり、しんや、みのる）とは全く異なる性格に設定します。
    """
    candidates = [
        ("たけし", "冷静沈着で皮肉屋、どこか孤高な存在"),
        ("さとる", "率直かつ辛辣で、常に現実を鋭く指摘する"),
        ("りさ", "自由奔放で斬新なアイデアを持つ、ユニークな感性の持ち主"),
        ("けんじ", "クールで合理的、論理に基づいた意見を率直に述べる"),
        ("なおみ", "独創的で個性的、常識にとらわれず新たな視点を提供する")
    ]
    return random.choice(candidates)

# ------------------------
# セッションステートの初期化
# ------------------------
if "chat_log" not in st.session_state:
    st.session_state["chat_log"] = []

# ------------------------
# 会話まとめボタン（会話がある場合のみ）
# ------------------------
if st.button("会話をまとめる"):
    if st.session_state["chat_log"]:
        # 会話全体を結合してまとめ生成
        all_discussion = "\n".join([f'{msg["sender"]}: {msg["message"]}' for msg in st.session_state["chat_log"]])
        summary = generate_summary(all_discussion)
        st.session_state["summary"] = summary
        st.markdown("### まとめ回答\n" + "**まとめ:** " + summary)
    else:
        st.warning("まずは会話を開始してください。")

# ------------------------
# 固定フッター（入力エリア）の配置
# ------------------------
with st.container():
    st.markdown('<div style="position: fixed; bottom: 0; width: 100%; background: #FFF; padding: 10px; box-shadow: 0 -2px 5px rgba(0,0,0,0.1);">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area("新たな発言を入力してください", placeholder="ここに入力", height=100, key="user_input")
        col1, col2 = st.columns(2)
        with col1:
            send_button = st.form_submit_button("送信")
        with col2:
            continue_button = st.form_submit_button("続きを話す")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 送信ボタンの処理
    if send_button:
        if user_input.strip():
            # ユーザー発言（右寄せ）を記録
            st.session_state["chat_log"].append({"sender": "ユーザー", "message": user_input})
            if len(st.session_state["chat_log"]) == 1:
                persona_params = adjust_parameters(user_input)
                discussion = generate_discussion(user_input, persona_params)
                for line in discussion.split("\n"):
                    line = line.strip()
                    if line:
                        parts = line.split(":", 1)
                        sender = parts[0]
                        message = parts[1].strip() if len(parts) > 1 else ""
                        st.session_state["chat_log"].append({"sender": sender, "message": message})
            else:
                new_discussion = continue_discussion(user_input, "\n".join(
                    [f'{msg["sender"]}: {msg["message"]}' for msg in st.session_state["chat_log"] if msg["sender"] in NAMES or msg["sender"]=="新キャラクター"]
                ))
                for line in new_discussion.split("\n"):
                    line = line.strip()
                    if line:
                        parts = line.split(":", 1)
                        sender = parts[0]
                        message = parts[1].strip() if len(parts) > 1 else ""
                        st.session_state["chat_log"].append({"sender": sender, "message": message})
        else:
            st.warning("発言を入力してください。")
    
    # 続きを話すボタンの処理
    if continue_button:
        if st.session_state["chat_log"]:
            default_input = "続きをお願いします。"
            new_discussion = continue_discussion(default_input, "\n".join(
                [f'{msg["sender"]}: {msg["message"]}' for msg in st.session_state["chat_log"] if msg["sender"] in NAMES or msg["sender"]=="新キャラクター"]
            ))
            for line in new_discussion.split("\n"):
                line = line.strip()
                if line:
                    parts = line.split(":", 1)
                    sender = parts[0]
                    message = parts[1].strip() if len(parts) > 1 else ""
                    st.session_state["chat_log"].append({"sender": sender, "message": message})
        else:
            st.warning("まずは会話を開始してください。")

# ------------------------
# 会話ウィンドウの表示（常に表示、会話がない場合はプレースホルダー表示）
# ------------------------
st.header("会話履歴")
if st.session_state["chat_log"]:
    # 最新のメッセージが上に表示されるよう逆順にする
    def display_chat_log(chat_log):
        for msg in reversed(chat_log):
            sender = msg["sender"]
            message = msg["message"]
            style = {"bg": "#F5F5F5", "color": "#000", "align": "left"}
            if sender == "ユーザー":
                style = {"bg": "#CCE5FF", "color": "#000", "align": "right"}
            elif sender == "ゆかり":
                style = {"bg": "#FFD1DC", "color": "#000", "align": "left"}
            elif sender == "しんや":
                style = {"bg": "#D1E8FF", "color": "#000", "align": "left"}
            elif sender == "みのる":
                style = {"bg": "#D1FFD1", "color": "#000", "align": "left"}
            elif sender == "新キャラクター":
                style = {"bg": "#FFE4B5", "color": "#000", "align": "left"}
            bubble_html = (
                f'<div style="background-color: {style["bg"]}; border: 1px solid #ddd; '
                f'border-radius: 10px; padding: 8px; margin: 5px; color: {style["color"]}; '
                f'font-family: Arial, sans-serif; text-align: {style["align"]}; max-width: 80%;">'
                f'<strong>{sender}</strong><br>{message}</div>'
            )
            st.markdown(bubble_html, unsafe_allow_html=True)
    display_chat_log(st.session_state["chat_log"])
else:
    st.markdown("<p style='color: gray;'>ここに会話が表示されます。</p>", unsafe_allow_html=True)
