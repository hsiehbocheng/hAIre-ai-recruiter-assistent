#!/bin/bash

# 檢查 CloudFront invalidation 狀態腳本
# 用途：快速檢查最近的 CloudFront 快取清除請求狀態

set -e

# 從 terraform output 獲取配置
BUCKET_NAME=$(terraform output -json | jq -r '.bucket_names.value.static_site')
DISTRIBUTION_ID=$(aws cloudfront list-distributions --output json | jq -r ".DistributionList.Items[] | select(.Origins.Items[0].DomainName==\"$BUCKET_NAME.s3.ap-southeast-1.amazonaws.com\") | .Id")

if [ -z "$DISTRIBUTION_ID" ]; then
    echo "❌ 錯誤：找不到對應的 CloudFront distribution"
    exit 1
fi

echo "🔍 檢查 CloudFront invalidation 狀態..."
echo "Distribution ID: $DISTRIBUTION_ID"
echo ""

# 如果提供了 invalidation ID 作為參數，檢查特定的 invalidation
if [ ! -z "$1" ]; then
    echo "檢查 Invalidation ID: $1"
    aws cloudfront get-invalidation --distribution-id $DISTRIBUTION_ID --id $1 | jq '.Invalidation | {Status: .Status, CreateTime: .CreateTime, Paths: .InvalidationBatch.Paths.Items}'
else
    # 否則列出最近的 invalidations
    echo "📋 最近的 invalidations："
    aws cloudfront list-invalidations --distribution-id $DISTRIBUTION_ID --max-items 5 | jq '.InvalidationList.Items[] | {Id: .Id, Status: .Status, CreateTime: .CreateTime}'
fi 