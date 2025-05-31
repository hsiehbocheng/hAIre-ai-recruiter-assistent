variable "aws_resource_tag" {
  description = "Value of the Name tag for the demo aws resource"
  type        = string
  default     = "Benson_hAIre_Demo"
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "ap-southeast-1"  # 新加坡
}

variable "function_name" {
  type = string
}

variable "lambda_package_path" {
  type = string
}

variable "iam_role_arn" {
  type = string
}

variable "dynamodb_table_name" {
  type = string
}