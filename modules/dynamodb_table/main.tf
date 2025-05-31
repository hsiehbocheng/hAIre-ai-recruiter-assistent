variable "table_name" {}
variable "hash_key" {}
variable "range_key" {
  default = null
}
variable "attributes" {
  type = list(object({
    name = string
    type = string
  }))
}

resource "aws_dynamodb_table" "this" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = var.hash_key
  range_key = var.range_key != null ? var.range_key : null

  dynamic "attribute" {
    for_each = var.attributes
    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  tags = {
    Name        = var.table_name
    Environment = "dev"
    Project     = "Benson-hAIre-Demo"
  }
}