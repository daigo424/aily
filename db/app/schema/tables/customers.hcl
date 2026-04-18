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
    type = varchar(32)
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

  unique "customers_phone_key" {
    columns = [column.phone]
  }
}
