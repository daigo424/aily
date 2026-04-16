table "reservations" {
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

  column "booking_request_id" {
    null = true
    type = integer
  }

  column "reservation_code" {
    null = false
    type = varchar(32)
  }

  column "status" {
    null    = false
    type    = varchar(32)
    default = "pending"
  }

  column "reserved_for" {
    null = false
    type = timestamptz
  }

  column "notes" {
    null = true
    type = text
  }

  column "cancelled_at" {
    null = true
    type = timestamptz
  }

  column "voided_at" {
    null = true
    type = timestamptz
  }

  column "completed_at" {
    null = true
    type = timestamptz
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

  foreign_key "reservations_conversation_id_fkey" {
    columns     = [column.conversation_id]
    ref_columns = [table.conversations.column.id]
    on_delete   = CASCADE
  }

  foreign_key "reservations_customer_id_fkey" {
    columns     = [column.customer_id]
    ref_columns = [table.customers.column.id]
    on_delete   = CASCADE
  }

  foreign_key "reservations_booking_request_id_fkey" {
    columns     = [column.booking_request_id]
    ref_columns = [table.booking_requests.column.id]
    on_delete   = SET_NULL
  }

  unique "uq_reservations_reservation_code" {
    columns = [column.reservation_code]
  }

  index "ix_reservations_customer_id" {
    columns = [column.customer_id]
  }

  index "ix_reservations_conversation_id" {
    columns = [column.conversation_id]
  }

  index "ix_reservations_reserved_for" {
    columns = [column.reserved_for]
  }
}
