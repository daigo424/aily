table "message_attachments" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "message_id" {
    null = false
    type = integer
  }

  column "file_name" {
    null = false
    type = varchar(255)
  }

  column "storage_key" {
    null = false
    type = varchar(1024)
  }

  column "mime_type" {
    null = false
    type = varchar(128)
  }

  column "file_size" {
    null = false
    type = integer
  }

  column "created_at" {
    null    = false
    type    = timestamptz
    default = sql("now()")
  }

  primary_key {
    columns = [column.id]
  }

  foreign_key "fk_message_attachments_message_id" {
    columns     = [column.message_id]
    ref_columns = [table.messages.column.id]
    on_update   = NO_ACTION
    on_delete   = CASCADE
  }

  index "ix_message_attachments_message_id" {
    columns = [column.message_id]
  }
}
