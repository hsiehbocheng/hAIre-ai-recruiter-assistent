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
  
  # 前端配置模板變數
  config_template_vars = {
    api_gateway_url = "https://${aws_api_gateway_rest_api.haire_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.haire_api_stage.stage_name}"
    cloudfront_url  = "https://${aws_cloudfront_distribution.static_site_distribution.domain_name}"
    generated_at    = timestamp()
  }
}

# IAM Role
## IAM role for Lambda execution
resource "aws_iam_role" "lambda_exec_bedrock_role" {
    name = "${var.resource_prefix}-lambda_exec_bedrock_role"
    
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

    tags = merge(local.common_tags, { Name = "${var.resource_prefix}-lambda_exec_bedrock_role" })
}

## IAM policy
# IAM Policy - 定義 Bedrock Lambda 的權限 (FullAccess for debugging)
resource "aws_iam_role_policy" "lambda_exec_bedrock_policy" {
  name = "${var.resource_prefix}-lambda-exec-bedrock-policy"
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
      # S3 完整權限 (FullAccess for debugging)
      {
        Effect = "Allow"
        Action = [
          "s3:*"
        ]
        Resource = "*"
      },
      # DynamoDB 權限
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
          "${module.resume_table.table_arn}/index/*",
          module.job_posting_table.table_arn,
          "${module.job_posting_table.table_arn}/index/*",
          module.job_requirement_table.table_arn,
          "${module.job_requirement_table.table_arn}/index/*",
          module.match_result_table.table_arn,
          "${module.match_result_table.table_arn}/index/*",
          module.teams_table.table_arn,
          "${module.teams_table.table_arn}/index/*"
        ]
      },
      # Bedrock 完整權限 (FullAccess for debugging)
      {
        Effect = "Allow"
        Action = [
          "bedrock:*"
        ]
        Resource = "*"
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
  bucket        = "${var.resource_prefix}-raw-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "raw-resume" })
}

## ai 解析後的履歷
resource "aws_s3_bucket" "parsed_resume" {
  bucket        = "${var.resource_prefix}-parsed-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "parsed-resume" })
}

## 刊登的職缺內容
resource "aws_s3_bucket" "job_posting" {
  bucket        = "${var.resource_prefix}-job-posting-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "job-posting" })
}

## 團隊資訊
resource "aws_s3_bucket" "team_info" {
  bucket        = "${var.resource_prefix}-team-info-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "team-info" })
}


## ai 解析後，各履歷的需求內容
resource "aws_s3_bucket" "job_requirement" {
  bucket        = "${var.resource_prefix}-job-requirement-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "job-requirement" })
}

## 靜態網站
resource "aws_s3_bucket" "static_site" {
  bucket        = "${var.resource_prefix}-static-site-${random_id.suffix.hex}"
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
  table_name = "${var.resource_prefix}-parsed_resume"
  hash_key   = "resume_id"
  attributes = [
    { name = "resume_id", type = "S" },
    { name = "team_id", type = "S" },
    { name = "job_id", type = "S" },
    { name = "processed_at", type = "S" }
  ]
  
  global_secondary_indexes = [
    {
      name               = "team-index"
      hash_key           = "team_id"
      range_key          = "processed_at"
      projection_type    = "ALL"
      non_key_attributes = []
    },
    {
      name               = "job-index"
      hash_key           = "job_id"
      range_key          = "processed_at"
      projection_type    = "ALL"
      non_key_attributes = []
    }
  ]
}

module "teams_table" {
  source     = "./modules/dynamodb_table"
  table_name = "${var.resource_prefix}-teams"
  hash_key   = "team_id"
  attributes = [
    { name = "team_id", type = "S" }
  ]
}

module "job_posting_table" {
  source     = "./modules/dynamodb_table"
  table_name = "${var.resource_prefix}-job-posting"
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" }
  ]
}

module "job_requirement_table" {
  source     = "./modules/dynamodb_table"
  table_name = "${var.resource_prefix}-job-requirement"
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" }
  ]
}

module "match_result_table" {
  source     = "./modules/dynamodb_table"
  table_name = "${var.resource_prefix}-match-result"
  hash_key   = "job_id"
  range_key  = "resume_id"
  attributes = [
    { name = "job_id", type = "S" },
    { name = "resume_id", type = "S" }
  ]
}

# API Gateway
resource "aws_api_gateway_rest_api" "haire_api" {
  name        = "${var.resource_prefix}-api"
  description = "hAIre API Gateway"
  
  tags = merge(local.common_tags, { Name = "${var.resource_prefix}-api" })
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

# 新增：API Gateway Resource - /teams/{team_id}/files （檔案上傳專用）
resource "aws_api_gateway_resource" "team_files_upload" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.team_id.id
  path_part   = "files"
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

# 新增：POST /teams/{team_id}/files （檔案上傳）
resource "aws_api_gateway_method" "team_files_upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_files_upload.id
  http_method   = "POST"
  authorization = "NONE"
}

# 新增：OPTIONS /teams/{team_id}/files （CORS）
resource "aws_api_gateway_method" "team_files_upload_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.team_files_upload.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# 團隊管理 Lambda
module "team_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "${var.resource_prefix}-team-management"
  lambda_package_path = "${path.module}/lambdas/team_management/team_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 900
  
  environment_variables = {
    TEAMS_TABLE_NAME = module.teams_table.table_name
    BACKUP_S3_BUCKET = aws_s3_bucket.raw_resume.bucket
    TEAM_INFO_BUCKET = aws_s3_bucket.team_info.bucket
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

# /teams/{team_id}/files POST integration (檔案上傳)
resource "aws_api_gateway_integration" "team_files_upload_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_upload.id
  http_method = aws_api_gateway_method.team_files_upload_post.http_method
  
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

# 新增：/teams/{team_id}/files OPTIONS integration (CORS)
resource "aws_api_gateway_integration" "team_files_upload_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_upload.id
  http_method = aws_api_gateway_method.team_files_upload_options.http_method
  
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

# 新增：Method Response for OPTIONS /teams/{team_id}/files
resource "aws_api_gateway_method_response" "team_files_upload_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_upload.id
  http_method = aws_api_gateway_method.team_files_upload_options.http_method
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

# API Gateway Deployment
resource "aws_api_gateway_deployment" "haire_api_deployment" {
  depends_on = [
    # Teams 相關的整合
    aws_api_gateway_integration.teams_get_integration,
    aws_api_gateway_integration.teams_post_integration,
    aws_api_gateway_integration.team_get_integration,
    aws_api_gateway_integration.team_put_integration,
    aws_api_gateway_integration.team_delete_integration,
    aws_api_gateway_integration.team_files_upload_integration,
    aws_api_gateway_integration.teams_options_integration,
    aws_api_gateway_integration.team_options_integration,
    aws_api_gateway_integration.team_files_upload_options_integration,
    aws_api_gateway_integration_response.teams_options_integration_response,
    aws_api_gateway_integration_response.team_options_integration_response,
    aws_api_gateway_integration_response.team_files_upload_options_integration_response,
    aws_api_gateway_method_response.teams_options_method_response,
    aws_api_gateway_method_response.team_options_method_response,
    aws_api_gateway_method_response.team_files_upload_options_method_response,
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
    # 履歷上傳相關的整合
    aws_api_gateway_integration.upload_resume_post_integration,
    aws_api_gateway_integration.upload_resume_options_integration,
    aws_api_gateway_integration_response.upload_resume_options_integration_response,
    aws_api_gateway_method_response.upload_resume_options_method_response,
    # 履歷管理相關的整合
    aws_api_gateway_integration.resumes_get_integration,
    aws_api_gateway_integration.resumes_job_applicants_get_integration,
    aws_api_gateway_integration.resume_get_integration,
    aws_api_gateway_integration.resumes_options_integration,
    aws_api_gateway_integration.resumes_job_applicants_options_integration,
    aws_api_gateway_integration.resume_options_integration,
    aws_api_gateway_integration_response.resumes_options_integration_response,
    aws_api_gateway_integration_response.resumes_job_applicants_options_integration_response,
    aws_api_gateway_integration_response.resume_options_integration_response,
    aws_api_gateway_method_response.resumes_options_method_response,
    aws_api_gateway_method_response.resumes_job_applicants_options_method_response,
    aws_api_gateway_method_response.resume_options_method_response,
  ]
  
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  
  # 解決 API Gateway deployment 更新問題
  lifecycle {
    create_before_destroy = true
  }
  
  # 強制重新部署
  triggers = {
    redeployment = sha1(jsonencode([
      # Teams 資源
      aws_api_gateway_resource.teams.id,
      aws_api_gateway_resource.team_id.id,
      aws_api_gateway_resource.team_files_upload.id,
      aws_api_gateway_method.teams_get.id,
      aws_api_gateway_method.teams_post.id,
      aws_api_gateway_method.teams_options.id,
      aws_api_gateway_method.team_options.id,
      aws_api_gateway_method.team_files_upload_post.id,
      aws_api_gateway_method.team_files_upload_options.id,
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
      # 履歷上傳資源
      aws_api_gateway_resource.upload_resume.id,
      aws_api_gateway_method.upload_resume_post.id,
      aws_api_gateway_method.upload_resume_options.id,
      # 履歷管理資源
      aws_api_gateway_resource.resumes.id,
      aws_api_gateway_resource.resumes_job_applicants.id,
      aws_api_gateway_resource.resume_id.id,
      aws_api_gateway_method.resumes_get.id,
      aws_api_gateway_method.resumes_job_applicants_get.id,
      aws_api_gateway_method.resume_get.id,
      aws_api_gateway_method.resumes_options.id,
      aws_api_gateway_method.resumes_job_applicants_options.id,
      aws_api_gateway_method.resume_options.id,
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
  name         = "${var.resource_prefix}-usage-plan"
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
  name        = "${var.resource_prefix}-api-key"
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

# 動態打包 resume_parser Lambda 程式碼
data "archive_file" "resume_parser_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambdas/resume_parser"
  output_path = "${path.module}/lambdas/resume_parser/resume_parser.zip"
}

module "resume_parser_lambda" {
  source = "./modules/lambda_function"

  function_name       = "${var.resource_prefix}-resume-parser"
  lambda_package_path = data.archive_file.resume_parser_zip.output_path
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
  name                              = "${var.resource_prefix}-static-site-oac"
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

  tags = merge(local.common_tags, { Name = "${var.resource_prefix}-cloudfront" })
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
  table_name = "haire-jobs"  # 保持原來的名稱不變
  hash_key   = "job_id"
  attributes = [
    { name = "job_id", type = "S" },
    { name = "team_id", type = "S" },
    { name = "status", type = "S" },
    { name = "created_at", type = "S" }
  ]
  
  global_secondary_indexes = [
    {
      name               = "team-index"
      hash_key           = "team_id"
      range_key          = "created_at"
      projection_type    = "ALL"
      non_key_attributes = []
    },
    {
      name               = "status-index"
      hash_key           = "status"
      range_key          = "created_at"
      projection_type    = "ALL"
      non_key_attributes = []
    }
  ]
}

# 職缺管理 Lambda
module "job_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "${var.resource_prefix}-job-management"
  lambda_package_path = "${path.module}/lambdas/job_management/job_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 900
  
  environment_variables = {
    JOBS_TABLE_NAME  = module.jobs_table.table_name
    TEAMS_TABLE_NAME = module.teams_table.table_name
    BACKUP_S3_BUCKET = aws_s3_bucket.raw_resume.bucket
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

  depends_on = [aws_api_gateway_method_response.jobs_options_method_response]
}

resource "aws_api_gateway_integration_response" "job_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.job_id.id
  http_method = aws_api_gateway_method.job_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.job_options_method_response]
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

# API Gateway Resource - /upload-resume
resource "aws_api_gateway_resource" "upload_resume" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "upload-resume"
}

# API Gateway Methods - POST /upload-resume
resource "aws_api_gateway_method" "upload_resume_post" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.upload_resume.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Methods - OPTIONS /upload-resume
resource "aws_api_gateway_method" "upload_resume_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.upload_resume.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# 履歷上傳 Lambda
module "resume_upload_lambda" {
  source = "./modules/lambda_function"

  function_name       = "${var.resource_prefix}-resume-upload"
  lambda_package_path = "${path.module}/lambdas/resume_upload/resume_upload.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 900
  
  environment_variables = {
    RAW_BUCKET    = aws_s3_bucket.raw_resume.bucket
    PARSED_BUCKET = aws_s3_bucket.parsed_resume.bucket
  }
  
  common_tags = local.common_tags
}

# API Gateway Integration - 履歷上傳
resource "aws_api_gateway_integration" "upload_resume_post_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_resume.id
  http_method = aws_api_gateway_method.upload_resume_post.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.resume_upload_lambda.invoke_arn
}

# CORS Integration for /upload-resume
resource "aws_api_gateway_integration" "upload_resume_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_resume.id
  http_method = aws_api_gateway_method.upload_resume_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# Method Response for OPTIONS /upload-resume
resource "aws_api_gateway_method_response" "upload_resume_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_resume.id
  http_method = aws_api_gateway_method.upload_resume_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration Response for OPTIONS /upload-resume
resource "aws_api_gateway_integration_response" "upload_resume_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.upload_resume.id
  http_method = aws_api_gateway_method.upload_resume_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.upload_resume_options_method_response]
}

# 履歷管理 Lambda
module "resume_management_lambda" {
  source = "./modules/lambda_function"

  function_name       = "${var.resource_prefix}-resume-management"
  lambda_package_path = "${path.module}/lambdas/resume_management/resume_management.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  handler             = "lambda_function.lambda_handler"
  runtime             = "python3.11"
  timeout             = 900
  
  environment_variables = {
    RESUME_TABLE     = module.resume_table.table_name
    PARSED_BUCKET    = aws_s3_bucket.parsed_resume.bucket
  }
  
  common_tags = local.common_tags
}

# API Gateway Resource - /resumes
resource "aws_api_gateway_resource" "resumes" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_rest_api.haire_api.root_resource_id
  path_part   = "resumes"
}

# API Gateway Resource - /resumes/job-applicants
resource "aws_api_gateway_resource" "resumes_job_applicants" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.resumes.id
  path_part   = "job-applicants"
}

# API Gateway Resource - /resumes/{resume_id}
resource "aws_api_gateway_resource" "resume_id" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  parent_id   = aws_api_gateway_resource.resumes.id
  path_part   = "{resume_id}"
}

# API Gateway Methods - GET /resumes
resource "aws_api_gateway_method" "resumes_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resumes.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - GET /resumes/job-applicants
resource "aws_api_gateway_method" "resumes_job_applicants_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resumes_job_applicants.id
  http_method   = "GET"
  authorization = "NONE"
}

# API Gateway Methods - GET /resumes/{resume_id}
resource "aws_api_gateway_method" "resume_get" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resume_id.id
  http_method   = "GET"
  authorization = "NONE"
}

# OPTIONS for CORS - /resumes
resource "aws_api_gateway_method" "resumes_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resumes.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# OPTIONS for CORS - /resumes/job-applicants
resource "aws_api_gateway_method" "resumes_job_applicants_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resumes_job_applicants.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# OPTIONS for CORS - /resumes/{resume_id}
resource "aws_api_gateway_method" "resume_options" {
  rest_api_id   = aws_api_gateway_rest_api.haire_api.id
  resource_id   = aws_api_gateway_resource.resume_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway Integration - 履歷管理相關請求
resource "aws_api_gateway_integration" "resumes_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes.id
  http_method = aws_api_gateway_method.resumes_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.resume_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "resumes_job_applicants_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes_job_applicants.id
  http_method = aws_api_gateway_method.resumes_job_applicants_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.resume_management_lambda.invoke_arn
}

resource "aws_api_gateway_integration" "resume_get_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resume_id.id
  http_method = aws_api_gateway_method.resume_get.http_method
  
  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = module.resume_management_lambda.invoke_arn
}

# CORS Integration for /resumes
resource "aws_api_gateway_integration" "resumes_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes.id
  http_method = aws_api_gateway_method.resumes_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "resumes_job_applicants_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes_job_applicants.id
  http_method = aws_api_gateway_method.resumes_job_applicants_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_integration" "resume_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resume_id.id
  http_method = aws_api_gateway_method.resume_options.http_method
  
  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# CORS Integration Response for /resumes
resource "aws_api_gateway_integration_response" "resumes_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes.id
  http_method = aws_api_gateway_method.resumes_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.resumes_options_method_response]
}

resource "aws_api_gateway_integration_response" "resumes_job_applicants_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes_job_applicants.id
  http_method = aws_api_gateway_method.resumes_job_applicants_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.resumes_job_applicants_options_method_response]
}

resource "aws_api_gateway_integration_response" "resume_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resume_id.id
  http_method = aws_api_gateway_method.resume_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.resume_options_method_response]
}

# CORS Method Response for /resumes
resource "aws_api_gateway_method_response" "resumes_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes.id
  http_method = aws_api_gateway_method.resumes_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "resumes_job_applicants_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resumes_job_applicants.id
  http_method = aws_api_gateway_method.resumes_job_applicants_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_method_response" "resume_options_method_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.resume_id.id
  http_method = aws_api_gateway_method.resume_options.http_method
  status_code = "200"
  
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# SNS 主題用於成本警報
resource "aws_sns_topic" "cost_alerts" {
  name = "${var.resource_prefix}-cost-alerts"
  
  tags = merge(local.common_tags, { Name = "cost-alerts" })
}

# 自動生成前端配置檔案
resource "local_file" "frontend_config" {
  content = templatefile("${path.module}/static-site/js/config.js", local.config_template_vars)
  filename = "${path.module}/static-site/js/config-generated.js"
  
  depends_on = [
    aws_api_gateway_rest_api.haire_api,
    aws_api_gateway_stage.haire_api_stage,
    aws_cloudfront_distribution.static_site_distribution
  ]
}

# 上傳生成的配置檔案到 S3
resource "aws_s3_object" "frontend_config" {
  bucket = aws_s3_bucket.static_site.bucket
  key    = "js/config.js"
  content = templatefile("${path.module}/static-site/js/config.js", local.config_template_vars)
  content_type = "application/javascript"
  
  depends_on = [
    aws_api_gateway_rest_api.haire_api,
    aws_api_gateway_stage.haire_api_stage,
    aws_cloudfront_distribution.static_site_distribution
  ]
  
  tags = merge(local.common_tags, { Name = "frontend-config" })
}

# 新增：CORS Integration Response for /teams/{team_id}/files
resource "aws_api_gateway_integration_response" "team_files_upload_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.haire_api.id
  resource_id = aws_api_gateway_resource.team_files_upload.id
  http_method = aws_api_gateway_method.team_files_upload_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,DELETE'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_method_response.team_files_upload_options_method_response]
}

# Lambda 權限 - 讓 API Gateway 可以呼叫各個 Lambda 函數
resource "aws_lambda_permission" "allow_api_gateway_teams" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.team_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_api_gateway_jobs" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.job_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_api_gateway_resume_upload" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.resume_upload_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_api_gateway_resumes" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.resume_management_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.haire_api.execution_arn}/*/*"
}

# 成本控制和監控
resource "aws_cloudwatch_metric_alarm" "high_cost_alarm" {
  alarm_name          = "${var.resource_prefix}-high-cost-alarm"
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