table "booking_requests" {
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

  column "status" {
    null    = false
    type    = varchar(32)
    default = "collecting"
  }

  column "source_message_id" {
    null = true
    type = integer
  }

  column "requested_date" {
    null = true
    type = date
  }

  column "requested_time" {
    null = true
    type = varchar(16)
  }

  column "notes" {
    null = true
    type = text
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

  index "ix_booking_requests_customer_id" {
    columns = [column.customer_id]
  }

  index "ix_booking_requests_conversation_id" {
    columns = [column.conversation_id]
  }
}
