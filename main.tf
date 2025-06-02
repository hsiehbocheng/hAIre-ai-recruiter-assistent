terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "local" {}          # state 檔先放本機
}

provider "aws" {
  region = "ap-southeast-1"   # 新加坡
}

# 共用 Tag
locals {
  common_tags = {
    Project     = "Benson-hAIre-Demo"
    Environment = "dev"
  }
}

# IAM Role
## IAM role for Lambda execution
resource "aws_iam_role" "lambda_exec_bedrock_role" {
    name = "benson-haire-lambda_exec_bedrock_role"
    
    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
        {
            Action = "sts:AssumeRole"
            Effect = "Allow"
            Principal = {
            Service = "lambda.amazonaws.com"
            }
        }
        ]
    })

    tags = merge(local.common_tags, { Name = "benson-haire-lambda_exec_bedrock_role" })
}

## IAM policy
# IAM Policy - 定義 Bedrock Lambda 的權限
resource "aws_iam_role_policy" "lambda_exec_bedrock_policy" {
  name = "benson-haire-lambda-exec-bedrock-policy"
  role = aws_iam_role.lambda_exec_bedrock_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs 權限 - Lambda 基本執行權限
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:ap-southeast-1:*:*"
      },
      # S3 權限 - 限制只能存取專案相關的 buckets（移除危險的 s3:*）
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_resume.arn,
          "${aws_s3_bucket.raw_resume.arn}/*",
          aws_s3_bucket.parsed_resume.arn,
          "${aws_s3_bucket.parsed_resume.arn}/*",
          aws_s3_bucket.job_posting.arn,
          "${aws_s3_bucket.job_posting.arn}/*",
          aws_s3_bucket.team_info.arn,
          "${aws_s3_bucket.team_info.arn}/*",
          aws_s3_bucket.job_requirement.arn,
          "${aws_s3_bucket.job_requirement.arn}/*",
          aws_s3_bucket.static_site.arn,
          "${aws_s3_bucket.static_site.arn}/*"
        ]
      },
      # DynamoDB 權限 - 讀寫履歷和職缺資料
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          module.resume_table.table_arn,
          module.job_posting_table.table_arn,
          module.job_requirement_table.table_arn,
          module.match_result_table.table_arn,
          module.teams_table.table_arn,
          module.jobs_table.table_arn,
          "${module.jobs_table.table_arn}/index/*"
        ]
      },
      # Bedrock 權限 - 限制特定模型，增加成本控制（移除危險的 bedrock:*）
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
        ]
        Condition = {
          NumericLessThan = {
            "bedrock:MaxTokens" = "8000"  # 限制最大 token 數量
          }
        }
      }
    ]
  })
}

# S3 事件觸發 Lambda
resource "aws_s3_bucket_notification" "raw_resume_notification" {
  bucket = aws_s3_bucket.raw_resume.id

  lambda_function {
    lambda_function_arn = module.resume_parser_lambda.lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.allow_bucket]
}

# Lambda 權限讓 S3 可以呼叫
resource "aws_lambda_permission" "allow_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = module.resume_parser_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.raw_resume.arn
}

# 四個 Bucket ─ 依用途拆開
## 履歷 raw 檔
resource "aws_s3_bucket" "raw_resume" {
  bucket        = "benson-haire-raw-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "raw-resume" })
}

## ai 解析後的履歷
resource "aws_s3_bucket" "parsed_resume" {
  bucket        = "benson-haire-parsed-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "parsed-resume" })
}

## 刊登的職缺內容
resource "aws_s3_bucket" "job_posting" {
  bucket        = "benson-haire-job-posting-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "job-posting" })
}

## 團隊資訊
resource "aws_s3_bucket" "team_info" {
  bucket        = "benson-haire-team-info-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "team-info" })
}


## ai 解析後，各履歷的需求內容
resource "aws_s3_bucket" "job_requirement" {
  bucket        = "benson-haire-job-requirement-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "job-requirement" })
}

## 靜態網站
resource "aws_s3_bucket" "static_site" {
  bucket        = "benson-haire-static-site-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "static-site" })
}

# 隨機字串避免 Bucket 名稱衝突
resource "random_id" "suffix" {
  byte_length = 4
}

## DynamoDB Table

module "resume_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-parsed_resume"
  hash_key   = "resume_id"
  attributes = [
    { name = "resume_id", type = "S" }
  ]
}

module "teams_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-teams"
  hash_key   = "team_id"
  attributes = [
    { name = "team_id", type = "S" }
  ]
}

module "job_posting_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-job-posting"
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" }
  ]
}

module "job_requirement_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-job-requirement"
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" }
  ]
}

module "match_result_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-match-result"
  hash_key   = "job_id"
  range_key  = "resume_id"
  attributes = [
    { name = "job_id", type = "S" },
    { name = "resume_id", type = "S" }
  ]
}

# API Gateway
resource "aws_api_gateway_rest_api" "haire_api" {
  name        = "benson-haire-api"
  description = "hAIre API Gateway"
  
  tags = merge(local.common_tags, { Name = "benson-haire-api" })
}

# API Gateway Resource - /teams
resource "aws_api_gateway_resource" "teams" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "teams"
}

# API Gateway Resource - /teams/{team_id}
resource "aws_api_gateway_resource" "team_id" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.teams.id
  path_part   = "{team_id}"
}

# API Gateway Methods - GET /teams
resource "aws_api_gateway_method" "teams_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - POST /teams
resource "aws_api_gateway_method" "teams_post" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Methods - GET /teams/{team_id}
resource "aws_api_gateway_method" "team_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_id.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - PUT /teams/{team_id}
resource "aws_api_gateway_method" "team_put" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_id.id
  http_method   = "PUT"
  authorization = "NONE"
}

# API Gateway Methods - DELETE /teams/{team_id}
resource "aws_api_gateway_method" "team_delete" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_id.id
  http_method   = "DELETE"
  authorization = "NONE"
}

# OPTIONS for CORS - /teams
resource "aws_api_gateway_method" "teams_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.teams.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# OPTIONS for CORS - /teams/{team_id}
resource "aws_api_gateway_method" "team_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# 團隊管理 Lambda
module "team_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "benson-haire-team-management"
  lambda_package_path = "${path.module}/lambdas/team_management/team_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 30
  
  environment_variables = {
    TEAMS_TABLE_NAME = module.teams_table.table_name
    BACKUP_S3_BUCKET = aws_s3_bucket.team_info.bucket
  }
  
  common_tags = local.common_tags
}

# Team File Management Lambda
module "team_file_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "benson-haire-team-file-management"
  lambda_package_path = "${path.module}/lambdas/team_file_management/team_file_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 30
  
  environment_variables = {
    S3_BUCKET_NAME = aws_s3_bucket.team_info.bucket
  }
  
  common_tags = local.common_tags
}

# API Gateway Integration - 所有 teams 相關請求都導向同一個 Lambda
resource "aws_api_gateway_integration" "teams_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "teams_post_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "team_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "team_put_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_put.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "team_delete_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_delete.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_management_lambda.invoke_arn
}

# CORS Integration
resource "aws_api_gateway_integration" "teams_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "team_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# CORS Integration Response for /teams
resource "aws_api_gateway_integration_response" "teams_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.teams_options_method_response]
}

# CORS Integration Response for /teams/{team_id}
resource "aws_api_gateway_integration_response" "team_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.team_options_method_response]
}

# Method Response for OPTIONS /teams
resource "aws_api_gateway_method_response" "teams_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.teams.id
  http_method = aws_api_gateway_method.teams_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Method Response for OPTIONS /teams/{team_id}
resource "aws_api_gateway_method_response" "team_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_id.id
  http_method = aws_api_gateway_method.team_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Lambda 權限 - 讓 API Gateway 可以呼叫
resource "aws_lambda_permission" "allow_api_gateway_teams" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.team_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "haire_api_deployment" {
  depends_on = [
    # Teams 相關的整合
    aws_api_gateway_integration.teams_get_integration,
    aws_api_gateway_integration.teams_post_integration,
    aws_api_gateway_integration.team_get_integration,
    aws_api_gateway_integration.team_put_integration,
    aws_api_gateway_integration.team_delete_integration,
    aws_api_gateway_integration.teams_options_integration,
    aws_api_gateway_integration.team_options_integration,
    aws_api_gateway_integration_response.teams_options_integration_response,
    aws_api_gateway_integration_response.team_options_integration_response,
    aws_api_gateway_method_response.teams_options_method_response,
    aws_api_gateway_method_response.team_options_method_response,
    # 文件管理相關的整合
    aws_api_gateway_integration.upload_team_file_integration,
    aws_api_gateway_integration.team_files_get_integration,
    aws_api_gateway_integration.download_team_file_integration,
    aws_api_gateway_integration.delete_team_file_integration,
    aws_api_gateway_integration.upload_team_file_options_integration,
    aws_api_gateway_integration.team_files_options_integration,
    aws_api_gateway_integration.download_team_file_options_integration,
    aws_api_gateway_integration.delete_team_file_options_integration,
    aws_api_gateway_integration_response.upload_team_file_options_integration_response,
    aws_api_gateway_integration_response.team_files_options_integration_response,
    aws_api_gateway_integration_response.download_team_file_options_integration_response,
    aws_api_gateway_integration_response.delete_team_file_options_integration_response,
    aws_api_gateway_method_response.upload_team_file_options_method_response,
    aws_api_gateway_method_response.team_files_options_method_response,
    aws_api_gateway_method_response.download_team_file_options_method_response,
    aws_api_gateway_method_response.delete_team_file_options_method_response,
    # Jobs 相關的整合
    aws_api_gateway_integration.jobs_get_integration,
    aws_api_gateway_integration.jobs_post_integration,
    aws_api_gateway_integration.job_get_integration,
    aws_api_gateway_integration.job_put_integration,
    aws_api_gateway_integration.job_delete_integration,
    aws_api_gateway_integration.jobs_options_integration,
    aws_api_gateway_integration.job_options_integration,
    aws_api_gateway_integration_response.jobs_options_integration_response,
    aws_api_gateway_integration_response.job_options_integration_response,
    aws_api_gateway_method_response.jobs_options_method_response,
    aws_api_gateway_method_response.job_options_method_response,
  ]
  
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  
  # 強制重新部署
  triggers = {
    redeployment = sha1(jsonencode([
      # Teams 資源
      aws_api_gateway_resource.teams.id,
      aws_api_gateway_resource.team_id.id,
      aws_api_gateway_method.teams_get.id,
      aws_api_gateway_method.teams_post.id,
      aws_api_gateway_method.teams_options.id,
      aws_api_gateway_method.team_options.id,
      # 文件管理資源
      aws_api_gateway_resource.upload_team_file.id,
      aws_api_gateway_resource.team_files.id,
      aws_api_gateway_resource.team_files_id.id,
      aws_api_gateway_resource.download_team_file.id,
      aws_api_gateway_resource.download_team_file_key.id,
      aws_api_gateway_resource.delete_team_file.id,
      aws_api_gateway_method.upload_team_file_post.id,
      aws_api_gateway_method.upload_team_file_options.id,
      aws_api_gateway_method.team_files_get.id,
      aws_api_gateway_method.team_files_options.id,
      aws_api_gateway_method.download_team_file_get.id,
      aws_api_gateway_method.download_team_file_options.id,
      aws_api_gateway_method.delete_team_file_delete.id,
      aws_api_gateway_method.delete_team_file_options.id,
      # Jobs 資源  
      aws_api_gateway_resource.jobs.id,
      aws_api_gateway_resource.job_id.id,
      aws_api_gateway_method.jobs_get.id,
      aws_api_gateway_method.jobs_post.id,
      aws_api_gateway_method.job_get.id,
      aws_api_gateway_method.job_put.id,
      aws_api_gateway_method.job_delete.id,
      aws_api_gateway_method.jobs_options.id,
      aws_api_gateway_method.job_options.id,
    ]))
  }
}

# API Gateway Stage 加上速率限制
resource "aws_api_gateway_stage" "haire_api_stage" {
  deployment_id = aws_api_gateway_deployment.haire_api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  stage_name    = "dev"
  
  tags = merge(local.common_tags, { Name = "haire-api-dev-stage" })
}

# 添加使用計劃和 API Key 用於更嚴格的控制
resource "aws_api_gateway_usage_plan" "haire_usage_plan" {
  name         = "benson-haire-usage-plan"
  description  = "Usage plan for hAIre API"

  api_stages {
    api_id = aws_api_gateway_rest_api.haire_api.id
    stage  = aws_api_gateway_stage.haire_api_stage.stage_name
  }

  quota_settings {
    limit  = 10000  # 每日最多 10,000 次請求
    period = "DAY"
  }
  
  throttle_settings {
    rate_limit  = 50   # 每秒 50 次請求
    burst_limit = 100  # 突發 100 次請求
  }
}

# 創建 API Key（可選用於管理 API）
resource "aws_api_gateway_api_key" "haire_api_key" {
  name        = "benson-haire-api-key"
  description = "API key for hAIre application"
  enabled     = true
  
  tags = merge(local.common_tags, { Name = "haire-api-key" })
}

# 將 API Key 與使用計劃關聯
resource "aws_api_gateway_usage_plan_key" "haire_usage_plan_key" {
  key_id        = aws_api_gateway_api_key.haire_api_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.haire_usage_plan.id
}

# 輸出 API Gateway URL
output "api_gateway_url" {
  value = aws_api_gateway_stage.haire_api_stage.invoke_url
  description = "API Gateway endpoint URL for dev stage"
}

module "resume_parser_lambda" {
  source = "./modules/lambda_function"

  function_name       = "benson-haire-resume-parser"
  lambda_package_path = "${path.module}/lambdas/resume_parser/resume_parser.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 900
  
  environment_variables = {
    DYNAMODB_TABLE = module.resume_table.table_name
    PARSED_BUCKET  = aws_s3_bucket.parsed_resume.bucket
  }
  
  common_tags = local.common_tags
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "static_site_oac" {
  name                              = "benson-haire-static-site-oac"
  description                       = "OAC for static site S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront 分發 - 使用 OAC
resource "aws_cloudfront_distribution" "static_site_distribution" {
  origin {
    domain_name              = aws_s3_bucket.static_site.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.static_site.bucket}"
    origin_access_control_id = aws_cloudfront_origin_access_control.static_site_oac.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.static_site.bucket}"
    viewer_protocol_policy = "redirect-to-https"
    compress              = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(local.common_tags, { Name = "benson-haire-cloudfront" })
}

# S3 Bucket Policy - 只允許 CloudFront 存取
resource "aws_s3_bucket_policy" "static_site_policy" {
  bucket = aws_s3_bucket.static_site.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.static_site.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.static_site_distribution.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_cloudfront_distribution.static_site_distribution]
}

output "bucket_names" {
  value = {
    raw_resume    = aws_s3_bucket.raw_resume.bucket
    parsed_resume = aws_s3_bucket.parsed_resume.bucket
    job_posting   = aws_s3_bucket.job_posting.bucket
    static_site   = aws_s3_bucket.static_site.bucket
  }
}

output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.static_site_distribution.domain_name}"
}

# API Gateway Resource - /jobs
resource "aws_api_gateway_resource" "jobs" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "jobs"
}

# API Gateway Resource - /jobs/{job_id}
resource "aws_api_gateway_resource" "job_id" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.jobs.id
  path_part   = "{job_id}"
}

# API Gateway Methods - GET /jobs
resource "aws_api_gateway_method" "jobs_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.jobs.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - POST /jobs
resource "aws_api_gateway_method" "jobs_post" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.jobs.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Methods - GET /jobs/{job_id}
resource "aws_api_gateway_method" "job_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.job_id.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - PUT /jobs/{job_id}
resource "aws_api_gateway_method" "job_put" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.job_id.id
  http_method   = "PUT"
  authorization = "NONE"
}

# API Gateway Methods - DELETE /jobs/{job_id}
resource "aws_api_gateway_method" "job_delete" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.job_id.id
  http_method   = "DELETE"
  authorization = "NONE"
}

# OPTIONS for CORS - /jobs
resource "aws_api_gateway_method" "jobs_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.jobs.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# OPTIONS for CORS - /jobs/{job_id}
resource "aws_api_gateway_method" "job_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.job_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# 新增職缺管理 DynamoDB 表格
module "jobs_table" {
  source     = "./modules/dynamodb_table"
  table_name = "haire-jobs"
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" },
    { name = "team_id", type = "S" },
    { name = "status", type = "S" },
    { name = "created_at", type = "S" }
  ]
  
  global_secondary_indexes = [
    {
      name     = "team-index"
      hash_key = "team_id"
      range_key = "created_at"
      projection_type = "ALL"
    },
    {
      name     = "status-index"
      hash_key = "status"
      range_key = "created_at"
      projection_type = "ALL"
    }
  ]
}

# 職缺管理 Lambda
module "job_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "benson-haire-job-management"
  lambda_package_path = "${path.module}/lambdas/job_management/job_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 30
  
  environment_variables = {
    JOBS_TABLE_NAME  = module.jobs_table.table_name
    TEAMS_TABLE_NAME = module.teams_table.table_name
    BACKUP_S3_BUCKET = aws_s3_bucket.static_site.bucket
  }
  
  common_tags = local.common_tags
}

# API Gateway Integration - 所有 jobs 相關請求都導向職缺管理 Lambda
resource "aws_api_gateway_integration" "jobs_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.job_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "jobs_post_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.job_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "job_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.job_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "job_put_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_put.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.job_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "job_delete_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_delete.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.job_management_lambda.invoke_arn
}

# CORS Integration for /jobs
resource "aws_api_gateway_integration" "jobs_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "job_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# CORS Integration Response for /jobs
resource "aws_api_gateway_integration_response" "jobs_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  status_code = aws_api_gateway_method_response.jobs_options_method_response.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

resource "aws_api_gateway_integration_response" "job_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_options.http_method
  status_code = aws_api_gateway_method_response.job_options_method_response.status_code
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# CORS Method Response for /jobs
resource "aws_api_gateway_method_response" "jobs_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.jobs.id
  http_method = aws_api_gateway_method.jobs_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "job_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Lambda Permission for API Gateway to invoke job management function
resource "aws_lambda_permission" "allow_api_gateway_jobs" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.job_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

# 生成前端配置文件
resource "local_file" "frontend_config" {
  content = templatefile("${path.module}/templates/config.js.tpl", {
    api_gateway_url = aws_api_gateway_stage.haire_api_stage.invoke_url
    cloudfront_url  = aws_cloudfront_distribution.static_site_distribution.domain_name
  })
  filename = "${path.module}/static-site/js/config.js"
}

# 團隊文件管理 API 資源
resource "aws_api_gateway_resource" "upload_team_file" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "upload-team-file"
}

resource "aws_api_gateway_resource" "team_files" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "team-files"
}

resource "aws_api_gateway_resource" "team_files_id" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.team_files.id
  path_part   = "{team_id}"
}

resource "aws_api_gateway_resource" "download_team_file" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "download-team-file"
}

resource "aws_api_gateway_resource" "download_team_file_key" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.download_team_file.id
  path_part   = "{file_key}"
}

resource "aws_api_gateway_resource" "delete_team_file" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "delete-team-file"
}

# API Gateway 方法 - 文件上傳
resource "aws_api_gateway_method" "upload_team_file_post" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.upload_team_file.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "upload_team_file_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.upload_team_file.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway 方法 - 文件列表
resource "aws_api_gateway_method" "team_files_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_files_id.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "team_files_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_files_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway 方法 - 文件下載
resource "aws_api_gateway_method" "download_team_file_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.download_team_file_key.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "download_team_file_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.download_team_file_key.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway 方法 - 文件刪除
resource "aws_api_gateway_method" "delete_team_file_delete" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.delete_team_file.id
  http_method   = "DELETE"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "delete_team_file_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.delete_team_file.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway 整合 - 文件管理
resource "aws_api_gateway_integration" "upload_team_file_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_team_file.id
  http_method = aws_api_gateway_method.upload_team_file_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_file_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "team_files_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_id.id
  http_method = aws_api_gateway_method.team_files_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_file_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "download_team_file_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.download_team_file_key.id
  http_method = aws_api_gateway_method.download_team_file_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_file_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "delete_team_file_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.delete_team_file.id
  http_method = aws_api_gateway_method.delete_team_file_delete.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.team_file_management_lambda.invoke_arn
}

# CORS 整合 - 文件管理
resource "aws_api_gateway_integration" "upload_team_file_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_team_file.id
  http_method = aws_api_gateway_method.upload_team_file_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "team_files_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_id.id
  http_method = aws_api_gateway_method.team_files_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "download_team_file_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.download_team_file_key.id
  http_method = aws_api_gateway_method.download_team_file_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "delete_team_file_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.delete_team_file.id
  http_method = aws_api_gateway_method.delete_team_file_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# Method Response - 文件管理 OPTIONS
resource "aws_api_gateway_method_response" "upload_team_file_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_team_file.id
  http_method = aws_api_gateway_method.upload_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "team_files_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_id.id
  http_method = aws_api_gateway_method.team_files_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "download_team_file_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.download_team_file_key.id
  http_method = aws_api_gateway_method.download_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "delete_team_file_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.delete_team_file.id
  http_method = aws_api_gateway_method.delete_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration Response - 文件管理 OPTIONS
resource "aws_api_gateway_integration_response" "upload_team_file_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_team_file.id
  http_method = aws_api_gateway_method.upload_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.upload_team_file_options_method_response]
}

resource "aws_api_gateway_integration_response" "team_files_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_id.id
  http_method = aws_api_gateway_method.team_files_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.team_files_options_method_response]
}

resource "aws_api_gateway_integration_response" "download_team_file_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.download_team_file_key.id
  http_method = aws_api_gateway_method.download_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.download_team_file_options_method_response]
}

resource "aws_api_gateway_integration_response" "delete_team_file_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.delete_team_file.id
  http_method = aws_api_gateway_method.delete_team_file_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.delete_team_file_options_method_response]
}

# Lambda 權限 - 讓 API Gateway 可以呼叫 team_file_management
resource "aws_lambda_permission" "allow_api_gateway_team_files" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.team_file_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

# 成本控制和監控
resource "aws_cloudwatch_metric_alarm" "high_cost_alarm" {
  alarm_name          = "benson-haire-high-cost-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24 hours
  statistic           = "Maximum"
  threshold           = "50"     # 當月花費超過 $50 USD 時警報
  alarm_description   = "This metric monitors AWS bill"
  alarm_actions       = [aws_sns_topic.cost_alerts.arn]
  
  dimensions = {
    Currency = "USD"
  }
  
  tags = merge(local.common_tags, { Name = "high-cost-alarm" })
}

# SNS 主題用於成本警報
resource "aws_sns_topic" "cost_alerts" {
  name = "benson-haire-cost-alerts"
  
  tags = merge(local.common_tags, { Name = "cost-alerts" })
}

# 輸出 API Key 以供前端使用（如果需要的話）
output "api_key_id" {
  value = aws_api_gateway_api_key.haire_api_key.id
  description = "API Gateway API Key ID"
  sensitive = true
}

output "usage_plan_id" {
  value = aws_api_gateway_usage_plan.haire_usage_plan.id
  description = "API Gateway Usage Plan ID"
}