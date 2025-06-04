# API Gateway 相關輸出
output "api_gateway_url" {
  description = "API Gateway 的 URL"
  value       = "https://${aws_api_gateway_rest_api.haire_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.haire_api_stage.stage_name}"
}

output "api_key_id" {
  value       = aws_api_gateway_api_key.haire_api_key.id
  description = "API Gateway API Key ID"
  sensitive   = true
}

output "usage_plan_id" {
  value       = aws_api_gateway_usage_plan.haire_usage_plan.id
  description = "API Gateway Usage Plan ID"
}

# S3 Bucket 相關輸出
output "s3_buckets" {
  description = "已創建的 S3 Buckets"
  value = {
    static_site    = aws_s3_bucket.static_site.bucket
    raw_resume     = aws_s3_bucket.raw_resume.bucket
    parsed_resume  = aws_s3_bucket.parsed_resume.bucket
    job_posting    = aws_s3_bucket.job_posting.bucket
    team_info      = aws_s3_bucket.team_info.bucket
    job_requirement = aws_s3_bucket.job_requirement.bucket
  }
}

# CloudFront 相關輸出
output "cloudfront_url" {
  description = "CloudFront 分發的 URL"
  value       = "https://${aws_cloudfront_distribution.static_site_distribution.domain_name}"
}

# DynamoDB 相關輸出
output "dynamodb_tables" {
  description = "已創建的 DynamoDB 表格"
  value = {
    teams         = module.teams_table.table_name
    resume        = module.resume_table.table_name
    job_posting   = module.job_posting_table.table_name
    job_requirement = module.job_requirement_table.table_name
    match_result  = module.match_result_table.table_name
    jobs          = module.jobs_table.table_name
  }
}

# Lambda 相關輸出
output "lambda_functions" {
  description = "已創建的 Lambda 函數"
  value = {
    team_management   = module.team_management_lambda.function_name
    job_management    = module.job_management_lambda.function_name
    resume_parser     = module.resume_parser_lambda.function_name
    resume_upload     = module.resume_upload_lambda.function_name
    resume_management = module.resume_management_lambda.function_name
  }
}

# 前端配置資訊
output "frontend_config" {
  description = "前端應該使用的配置"
  value = {
    api_base_url    = "https://${aws_api_gateway_rest_api.haire_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.haire_api_stage.stage_name}"
    cloudfront_url  = "https://${aws_cloudfront_distribution.static_site_distribution.domain_name}"
    generated_at    = timestamp()
  }
}
