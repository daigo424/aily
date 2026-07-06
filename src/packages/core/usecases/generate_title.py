from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from packages.core.infrastructure import llm


def execute(messages: list[BaseMessage]) -> str:
    lines = []
    for msg in messages[:8]:
        content = str(msg.content)[:120]
        if isinstance(msg, HumanMessage):
            lines.append(f"ユーザー: {content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"AI: {content}")

    history = "\n".join(lines)
    result = llm.client.gen_text(
        prompt=f"""以下の会話の内容を表す短いタイトルを15文字以内で生成してください。タイトルのみを返してください。説明・引用符・句点は不要です。

会話:
{history}

タイトル:""",
        temperature=0.3,
    )
    return result.strip()[:20]
