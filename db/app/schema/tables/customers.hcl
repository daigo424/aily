table "customers" {
  schema = schema.public

  column "id" {
    null = false
    type = integer
    identity {
      generated = ALWAYS
    }
  }

  column "phone" {
    null = false
    type = varchar(64)
  }

  column "name" {
    null = true
    type = varchar(255)
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

  unique "uq_customers_phone" {
    columns = [column.phone]
  }
}