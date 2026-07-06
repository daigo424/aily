from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from packages.core.config import settings
from packages.core.infrastructure import llm
from packages.core.schemas import ScheduleExtraction

TZ = ZoneInfo(settings.timezone)


def _to_api_messages(messages: list[BaseMessage]) -> list[dict]:
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


def execute(
    text: str,
    history: list[BaseMessage] | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
) -> dict[str, Any]:
    now_text = datetime.now(tz=TZ).strftime("%Y-%m-%d %H:%M")

    system_prompt = f"""現在日時は {now_text}（{settings.timezone}）です。

ユーザーのメッセージから意図を読み取り、予定・タスク情報を抽出し、返答文を生成してください。
会話履歴がある場合は文脈として参照し、直近のやり取りほど重視すること。

intent の選び方:
- 予定またはタスクを記録したい → "add_schedule"
- 記録済みの予定・タスクを確認したい → "list_schedule"
- 挨拶・雑談・気持ちの吐露・その他の会話 → "smalltalk"
- それ以外 → "unknown"

各フィールドの抽出ルール:
- item_type: "event"（予定）または "task"（タスク）。会話から判断できない場合は null。
- title: 予定またはタスクの名前・内容。明示されていなければ null。
- scheduled_date: 具体的な日付が確定している場合のみ YYYY-MM-DD で設定。不明なら null。
- start_time: HH:MM 形式。ユーザーが会話の中で開始時刻を明示した場合のみ設定。述べていなければ必ず null。推測・補完・デフォルト値の設定は絶対に禁止。
- end_time: HH:MM 形式。ユーザーが会話の中で終了時刻を明示した場合のみ設定。述べていなければ必ず null。推測・補完・デフォルト値の設定は絶対に禁止。
- follow_up_question: intent が "add_schedule" のときのみ使用。以下の優先順位で1つだけ聞く質問文を入れる。それ以外の intent では必ず null。
  1. item_type が null → 予定かタスクかを聞く
  2. title が null → タイトルを聞く
  3. scheduled_date が null → 日付を聞く
  4. start_time が null → 開始時刻を聞く
  5. end_time が null → 終了時刻を聞く
  6. 全部揃っている → null

reply の生成ルール:
- **必ずユーザーのメッセージと同じ言語で書くこと**
- intent が "add_schedule" で全情報が揃っていれば「〇〇を記録しました。」旨を返す
- 不足情報があれば follow_up_question と同じ内容を reply にも書く。**不足している項目を一度に複数聞かないこと。1回につき1項目だけ。**
- intent が "list_schedule" であれば確認中の旨を返す（実際のデータはシステムが付加する）
- intent が "smalltalk" または "unknown" の場合:
  - 相手が言ったことに対して素直に反応するだけでよい
  - **質問を返さないこと**
  - 予定・タスクの話題は自分から持ち出さないこと
  - 「何かあれば」「お気軽に」「いつでも」といった締めの常套句は使わないこと

出力前に、思考の中で以下を3回繰り返して自己検証すること:
1. この返答はユーザーが言ったことに正確に応じているか
2. 不自然な言い回しや余計な一言が入っていないか
3. もっと端的・自然に言える表現がないか
検証を通過した最終回答のみを reply に出力すること。"""

    api_history = _to_api_messages(history) if history else None

    response = llm.client.gen_json(
        prompt=text,
        schema=ScheduleExtraction.model_json_schema(),
        temperature=0.1,
        image_base64=image_base64,
        image_mime_type=image_mime_type,
        history=api_history,
        system_prompt=system_prompt,
    )
    extraction = ScheduleExtraction.model_validate(response)
    return extraction.model_dump(mode="json")
