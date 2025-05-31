terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "local" {}  # 本機儲存 state
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-1"  # 新加坡
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "static_site" {
  bucket        = "benson-haire-demo-${random_id.suffix.hex}"
  force_destroy = true

  tags = {
    Name        = "Benson-hAIre-Demo"
    Environment = "dev"
  }
}

output "bucket_name" {
  value = aws_s3_bucket.static_site.bucket
}