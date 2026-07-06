table "events" {
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

  column "draft_id" {
    null = true
    type = integer
  }

  column "title" {
    null = false
    type = varchar(255)
  }

  column "starts_at" {
    null = false
    type = timestamptz
  }

  column "ends_at" {
    null = false
    type = timestamptz
  }

  column "notes" {
    null = true
    type = text
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

  index "ix_events_chat_id" {
    columns = [column.chat_id]
  }

  index "ix_events_starts_at" {
    columns = [column.starts_at]
  }
}
