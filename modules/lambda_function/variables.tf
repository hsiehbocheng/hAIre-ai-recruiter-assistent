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

variable "handler" {
  description = "Lambda function handler"
  type        = string
  default     = "lambda_function.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 900
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "common_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {
    Environment = "dev"
    Project     = "Benson-hAIre-Demo"
  }
}

# 為了向後兼容，保留舊的變數（可選）
variable "dynamodb_table_name" {
  description = "Target DynamoDB table name (legacy)"
  type        = string
  default     = ""
}

variable "parsed_bucket_name" {
  description = "Name of the S3 bucket (legacy)"
  type        = string
  default     = ""
}