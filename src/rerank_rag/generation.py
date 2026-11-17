import os
from openai import OpenAI


def generate_answer(question: str, hits: list[dict]) -> str:
    """根据检索结果调用生成模型，返回最终回答。"""
    if not question.strip():
        raise ValueError("问题不能为空")

    if not hits:
        return "没有检索到可供回答问题的相关资料。"

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("根目录 .env 中没有配置 OPENAI_API_KEY")

    base_url = os.getenv("OPENAI_BASE_URL")

    if base_url:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        )
    else:
        client = OpenAI(api_key=api_key)

    context = "\n\n".join(
        f"[{number}] 来源：{hit['source']}，Chunk ID：{hit['id']}\n{hit['text']}"
        for number, hit in enumerate(hits, start=1)
    )

    prompt = f"""请根据下面的 Context 回答问题。

回答规则：
1. 只能使用 Context 中提供的信息。
2. 不要编造 Context 之外的内容。
3. 如果 Context 不足以回答，请明确说明资料不足。
4. 使用资料时标注引用编号，例如 [1]。

Context:
{context}

Question:
{question}
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "你是一个严格依据给定资料回答问题的助手。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.choices[0].message.content or ""
