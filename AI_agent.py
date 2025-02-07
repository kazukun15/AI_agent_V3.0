import streamlit as st
import requests
import re

# Gemini API のエンドポイントと API キー（Google Cloud コンソールから発行したキー）
API_KEY = "AIzaSyBTNVkzjKD3sUNVUMlp_tcXWQMO-FpfrSo"

# 初期のベースパラメーター（自動調整用の参考値）
BASE_PARAMS = {
    "temperature": 0.7,
    "style": "標準",
    "detail": "基本的な解説"
}

def analyze_question(question):
    """
    質問内容を解析し、感情やキーワードに応じたスコアを返す関数
    例として、キーワード '困った' や '悩み' が含まれていればスコアを高めにする
    """
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

def adjust_parameters(question):
    """
    質問の内容に応じてペルソナごとのパラメーターを自動調整する関数
    """
    score = analyze_question(question)
    
    persona_params = {}

    if score > 0:
        # 感情寄りの回答を重視する設定
        persona_params["ペルソナ1"] = {"temperature": 0.8, "style": "情熱的", "detail": "感情に寄り添う回答"}
        persona_params["ペルソナ2"] = {"temperature": 0.8, "style": "共感的", "detail": "心情を重視した解説"}
        persona_params["ペルソナ3"] = {"temperature": 0.75, "style": "柔軟", "detail": "状況に合わせた多面的な視点"}
    else:
        # 論理寄りの回答を重視する設定
        persona_params["ペルソナ1"] = {"temperature": 0.6, "style": "論理的", "detail": "具体的な解説を重視"}
        persona_params["ペルソナ2"] = {"temperature": 0.65, "style": "分析的", "detail": "データや事実を踏まえた説明"}
        persona_params["ペルソナ3"] = {"temperature": 0.7, "style": "客観的", "detail": "中立的な視点からの考察"}
    
    return persona_params

def call_gemini_api(prompt, params):
    """
    Google Generative Language API の Gemini モデルを呼び出し、
    指定のプロンプトとパラメーターに基づいた回答を取得する関数

    ※payload では "contents" 内に prompt を配置し、temperature や maxOutputTokens も指定しています。
    ※エンドポイントは models/gemini-2.0-flash-lite-preview-02-05 を利用します。
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-preview-02-05:generateContent?key={API_KEY}"
    payload = {
        # temperature や出力トークン数は、API の仕様に合わせて設定してください
        "temperature": params.get("temperature", 0.7),
        "maxOutputTokens": 150,
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        # Google の API では、生成されたコンテンツが response.json()["candidates"] に格納される場合が多いです。
        candidates = response.json().get("candidates", [])
        if candidates:
            return candidates[0].get("content", "回答が見つかりませんでした。")
        else:
            return "回答が見つかりませんでした。"
    else:
        return f"エラー: {response.status_code} {response.text}"

def generate_initial_answers(question, persona_params):
    """
    ユーザーの初回質問に対して、各ペルソナの回答を生成する関数
    """
    answers = {}
    for persona, params in persona_params.items():
        prompt = f"【{params['style']}な視点】以下の質問に答えてください。\n質問: {question}\n詳細: {params['detail']}"
        answer = call_gemini_api(prompt, params)
        answers[persona] = answer
    return answers

def simulate_persona_discussion(answers):
    """
    初回回答をもとに、ペルソナ同士のディスカッションをシミュレーションする関数
    """
    discussion_prompt = "以下の各ペルソナの回答を踏まえて、ディスカッションをしてください。必要に応じてユーザーに追加で質問をしてください。\n"
    for persona, answer in answers.items():
        discussion_prompt += f"{persona}の回答: {answer}\n"
    discussion_prompt += "この会話の中で、ユーザーに対して『あなたはこの状況についてどう考えますか？』といった質問を含めてください。"
    
    # ここでは、ペルソナ1のパラメーターを利用してディスカッションを生成する例
    discussion = call_gemini_api(discussion_prompt, {"temperature": 0.7, "style": "論理的", "detail": "ディスカッションの促進"})
    return discussion

def generate_followup_question(discussion):
    """
    ペルソナ間のディスカッションの結果から、ユーザーに対するフォローアップ質問を抽出または生成する関数
    """
    if "？" in discussion:
        followup = discussion.split("？")[0] + "？"
    else:
        followup = "この件について、さらに詳しく教えていただけますか？"
    return followup

# --- Streamlit UI ---
st.title("自動パラメーター調整付きペルソナ会話システム（Gemini API 使用）")

# ユーザーからの初回質問入力
question = st.text_area("最初の質問を入力してください", placeholder="ここに質問を入力", height=150)

if st.button("送信"):
    if question:
        # 質問内容に応じたパラメーター自動調整
        persona_params = adjust_parameters(question)
        st.write("### 自動調整された各ペルソナのパラメーター")
        st.json(persona_params)
        
        # 各ペルソナからの初回回答生成
        st.write("### 各ペルソナからの初回回答")
        initial_answers = generate_initial_answers(question, persona_params)
        for persona, answer in initial_answers.items():
            st.markdown(f"**{persona}**: {answer}")

        # ペルソナ間のディスカッションシミュレーション
        st.write("### ペルソナ間のディスカッション")
        discussion = simulate_persona_discussion(initial_answers)
        st.markdown(discussion)

        # フォローアップ質問生成
        st.write("### フォローアップ質問")
        followup_question = generate_followup_question(discussion)
        st.markdown(f"**システムからの質問:** {followup_question}")

        # ユーザーによるフォローアップ回答の入力
        additional_input = st.text_input("上記のフォローアップ質問に対するあなたの回答を入力してください")
        if additional_input:
            st.write("### 追加回答を反映した会話の更新")
            update_prompt = f"ユーザーからの追加回答: {additional_input}\n先ほどのディスカッション: {discussion}\nこの情報を踏まえ、今後の会話の方向性について意見を述べてください。"
            updated_discussion = call_gemini_api(update_prompt, {"temperature": 0.7, "style": "分析的", "detail": "更新された議論のまとめ"})
            st.markdown(updated_discussion)
    else:
        st.warning("質問を入力してください")
