table "conversations" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "customer_id" {
    null = false
    type = integer
  }

  column "channel" {
    null    = false
    type    = varchar(32)
    default = "whatsapp"
  }

  column "status" {
    null    = false
    type    = varchar(32)
    default = "active"
  }

  column "current_intent" {
    null = true
    type = varchar(64)
  }

  column "state" {
    null    = false
    type    = jsonb
    default = sql("'{}'::jsonb")
  }

  column "cancel_flow" {
    null = true
    type = jsonb
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

  foreign_key "conversations_customer_id_fkey" {
    columns     = [column.customer_id]
    ref_columns = [table.customers.column.id]
    on_delete   = CASCADE
  }

  index "conversations_customer_id_key" {
    columns = [column.customer_id]
  }
}
