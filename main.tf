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
      # S3 完整權限 - 可以對所有 S3 buckets 進行任何操作
      {
        Effect = "Allow"
        Action = [
          "s3:*",
          "s3-object-lambda:*"
        ]
        Resource = "*"
      },
      # DynamoDB 權限 - 讀寫履歷和職缺資料
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          module.resume_table.table_arn,
          module.job_posting_table.table_arn,
          module.job_requirement_table.table_arn,
          module.match_result_table.table_arn
        ]
      },
      # Bedrock 完整權限 - 可以呼叫任何 Bedrock 服務
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

## 刊登的職缺內容
resource "aws_s3_bucket" "job_team_info" {
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

## Lambda Function

module "resume_parser_lambda" {
  source = "./modules/lambda_function"

  function_name       = "benson-haire-resume-parser"
  lambda_package_path = "${path.module}/lambdas/resume_parser/resume_parser.zip"
  iam_role_arn        = aws_iam_role.lambda_exec_bedrock_role.arn
  dynamodb_table_name = "benson-haire-parsed_resume"
  parsed_bucket_name  = aws_s3_bucket.parsed_resume.bucket
}

output "bucket_names" {
  value = {
    raw_resume    = aws_s3_bucket.raw_resume.bucket
    parsed_resume = aws_s3_bucket.parsed_resume.bucket
    job_posting   = aws_s3_bucket.job_posting.bucket
    static_site   = aws_s3_bucket.static_site.bucket
  }
}