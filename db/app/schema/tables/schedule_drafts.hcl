table "schedule_drafts" {
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

  column "source_message_id" {
    null = true
    type = integer
  }

  column "item_type" {
    null = true
    type = varchar(16)
  }

  column "title" {
    null = true
    type = varchar(255)
  }

  column "scheduled_date" {
    null = true
    type = date
  }

  column "start_time" {
    null = true
    type = varchar(16)
  }

  column "end_time" {
    null = true
    type = varchar(16)
  }

  column "notes" {
    null = true
    type = text
  }

  column "status" {
    null    = false
    type    = varchar(32)
    default = "collecting"
  }

  column "extracted_entities" {
    null    = false
    type    = jsonb
    default = sql("'{}'::jsonb")
  }

  column "created_at" {
    null    = false
    type    = timestamptz
    default = sql("now()")
  }

  column "updated_at" {
    null    = false
    type    = timestamptz
    default = sql("now()")
  }

  primary_key {
    columns = [column.id]
  }

  index "ix_schedule_drafts_chat_id" {
    columns = [column.chat_id]
  }
}
