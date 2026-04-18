table "messages" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "conversation_id" {
    null = false
    type = integer
  }

  column "customer_id" {
    null = false
    type = integer
  }

  column "wamid" {
    null = true
    type = varchar(255)
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

  column "raw_payload" {
    null    = false
    type    = jsonb
    default = sql("'{}'::jsonb")
  }

  column "normalized_payload" {
    null    = false
    type    = jsonb
    default = sql("'{}'::jsonb")
  }

  column "gemini_result" {
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

  foreign_key "messages_conversation_id_fkey" {
    columns     = [column.conversation_id]
    ref_columns = [table.conversations.column.id]
    on_delete   = CASCADE
  }

  foreign_key "messages_customer_id_fkey" {
    columns     = [column.customer_id]
    ref_columns = [table.customers.column.id]
    on_delete   = CASCADE
  }

  unique "messages_wamid_key" {
    columns = [column.wamid]
  }

  index "messages_conversation_id_key" {
    columns = [column.conversation_id]
  }

  index "messages_customer_id_key" {
    columns = [column.customer_id]
  }
}
