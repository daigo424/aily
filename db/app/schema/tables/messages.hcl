table "messages" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "chat_id" {
    null = false
    type = integer
  }

  column "direction" {
    null = false
    type = varchar(16)
  }

  column "message_type" {
    null = false
    type = varchar(32)
  }

  column "text_content" {
    null = true
    type = text
  }

  column "raw_llm_result" {
    null    = false
    type    = jsonb
    default = sql("'{}'::jsonb")
  }

  column "created_at" {
    null    = false
    type    = timestamptz
    default = sql("now()")
  }

  primary_key {
    columns = [column.id]
  }

  foreign_key "fk_messages_chat_id" {
    columns     = [column.chat_id]
    ref_columns = [table.chats.column.id]
    on_delete   = CASCADE
  }

  index "ix_messages_chat_id" {
    columns = [column.chat_id]
  }
}
