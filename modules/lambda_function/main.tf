# modules/lambda_function/main.tf

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  handler       = "main.lambda_handler"
  runtime       = "python3.11"
  role          = var.iam_role_arn

  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  timeout = 900 # 15 minutes

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
    }
  }

  tags = {
    Name        = var.function_name
    Environment = "dev"
    Project     = "Benson-hAIre-Demo"
  }
}