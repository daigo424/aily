table "conversation_flow_cancel_items" {
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

  column "reservation_id" {
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

  foreign_key "conversation_flow_cancel_items_conversation_id_fkey" {
    columns     = [column.conversation_id]
    ref_columns = [table.conversations.column.id]
    on_delete   = CASCADE
  }

  foreign_key "conversation_flow_cancel_items_reservation_id_fkey" {
    columns     = [column.reservation_id]
    ref_columns = [table.reservations.column.id]
    on_delete   = CASCADE
  }

  index "ix_conversation_flow_cancel_items_conversation_id" {
    columns = [column.conversation_id]
  }
}
