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
  shared_credentials_files = ["~/.aws/credentials"]
  profile = "default"
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "static_site" {
  bucket        = "benson-haire-demo-${random_id.suffix.hex}"
  force_destroy = true

  tags = {
    Name        = var.aws_resource_tag
    Environment = "dev"
  }
}

output "bucket_name" {
  value = aws_s3_bucket.static_site.bucket
}