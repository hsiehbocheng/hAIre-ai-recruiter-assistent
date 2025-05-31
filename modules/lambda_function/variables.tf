variable "function_name" {
  description = "Lambda function name"
  type        = string
}

variable "lambda_package_path" {
  description = "Path to the ZIP file for Lambda code"
  type        = string
}

variable "iam_role_arn" {
  description = "IAM Role ARN for Lambda execution"
  type        = string
}

variable "dynamodb_table_name" {
  description = "Target DynamoDB table for resume storage"
  type        = string
}