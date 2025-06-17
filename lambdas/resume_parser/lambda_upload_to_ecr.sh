#!/bin/bash
set -e

export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="ap-southeast-1"
export REPO_NAME="resume_parser"
TAG="latest"
IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$TAG"

# 登入 ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# 確保 repo 存在
aws ecr describe-repositories --repository-names "$REPO_NAME" \
  --region $AWS_REGION || \
  aws ecr create-repository --repository-name "$REPO_NAME" --region $AWS_REGION

# 建立 buildx builder（只需執行一次）
docker buildx create --use --name lambda-builder || docker buildx use lambda-builder

# Build 並 load 到本機
docker buildx build --platform linux/amd64 -t $IMAGE_URI . --load

# Push 到 ECR
docker push $IMAGE_URI

# 更新 Lambda
aws lambda update-function-code \
  --function-name benson-haire-resume-parser-v2 \
  --image-uri $IMAGE_URI \
  --region $AWS_REGION

echo "✅ Lambda 已成功更新：$IMAGE_URI"