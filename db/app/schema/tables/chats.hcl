table "chats" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "channel" {
    null    = false
    type    = varchar(32)
    default = "web"
  }

  column "sender" {
    null = true
    type = varchar(64)
  }

  column "status" {
    null    = false
    type    = varchar(32)
    default = "active"
  }

  column "title" {
    null = true
    type = varchar(255)
  }

  column "current_intent" {
    null = true
    type = varchar(64)
  }

  column "last_message_at" {
    null    = false
    type    = timestamptz
    default = sql("now()")
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

  index "ix_chats_channel" {
    columns = [column.channel]
  }

  index "ix_chats_sender" {
    columns = [column.sender]
  }

  index "ix_chats_last_message_at" {
    columns = [column.last_message_at]
  }
}
