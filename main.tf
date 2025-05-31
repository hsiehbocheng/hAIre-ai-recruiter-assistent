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

# 四個 Bucket ─ 依用途拆開
resource "aws_s3_bucket" "raw_resume" {
  bucket        = "benson-haire-raw-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "raw-resume" })
}

resource "aws_s3_bucket" "parsed_resume" {
  bucket        = "benson-haire-parsed-resume-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "parsed-resume" })
}

resource "aws_s3_bucket" "job_posting" {
  bucket        = "benson-haire-job-posting-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "job-posting" })
}

resource "aws_s3_bucket" "static_site" {
  bucket        = "benson-haire-static-site-${random_id.suffix.hex}"
  force_destroy = true
  tags          = merge(local.common_tags, { Name = "static-site" })
}

# 隨機字串避免 Bucket 名稱衝突
resource "random_id" "suffix" {
  byte_length = 4
}

module "resume_table" {
  source     = "./modules/dynamodb_table"
  table_name = "benson-haire-resume"
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

output "bucket_names" {
  value = {
    raw_resume    = aws_s3_bucket.raw_resume.bucket
    parsed_resume = aws_s3_bucket.parsed_resume.bucket
    job_posting   = aws_s3_bucket.job_posting.bucket
    static_site   = aws_s3_bucket.static_site.bucket
  }
}