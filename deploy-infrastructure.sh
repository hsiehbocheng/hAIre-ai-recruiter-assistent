#!/bin/bash

# 完整的基礎設施部署腳本
# 用途：部署 AWS 資源並同步靜態網站

set -e

echo "🏗️  開始部署 hAIre AI 招聘助手基礎設施..."
echo ""

# 檢查必要的工具
echo "🔧 檢查必要工具..."
command -v terraform >/dev/null 2>&1 || { echo "❌ 需要安裝 Terraform"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "❌ 需要安裝 AWS CLI"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "❌ 需要安裝 jq"; exit 1; }

# 檢查 AWS 配置
echo "🔑 檢查 AWS 認證..."
aws sts get-caller-identity >/dev/null 2>&1 || { echo "❌ AWS 認證失敗，請檢查 AWS 配置"; exit 1; }
echo "✅ AWS 認證成功"

# 檢查 Lambda 打包
echo "📦 檢查 Lambda 函數打包..."
LAMBDA_DIRS=("lambdas/resume_parser" "lambdas/team_management" "lambdas/job_management")

for dir in "${LAMBDA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        ZIP_FILE="$dir/$(basename $dir).zip"
        if [ ! -f "$ZIP_FILE" ]; then
            echo "📦 打包 $(basename $dir) Lambda 函數..."
            cd "$dir"
            zip -r "$(basename $dir).zip" . -x "*.git*" "*.DS_Store*" "__pycache__*"
            cd - >/dev/null
        fi
        echo "✅ $(basename $dir).zip 已準備"
    fi
done

# Terraform 初始化
echo "⚙️  初始化 Terraform..."
terraform init

# Terraform 規劃
echo "📋 產生 Terraform 執行計畫..."
terraform plan -out=tfplan

# 確認是否要繼續
echo ""
read -p "🤔 是否要繼續部署？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 部署已取消"
    rm -f tfplan
    exit 1
fi

# Terraform 部署
echo "🚀 部署 AWS 資源..."
terraform apply tfplan
rm -f tfplan

echo "✅ AWS 資源部署完成"
echo ""

# 等待一小段時間讓資源完全啟動
echo "⏳ 等待資源初始化..."
sleep 30

# 執行靜態網站部署
echo "🌐 部署靜態網站..."
if [ -f "deploy.sh" ]; then
    ./deploy.sh
else
    echo "❌ 找不到 deploy.sh 腳本"
    exit 1
fi

# 顯示重要的輸出資訊
echo ""
echo "🎉 所有部署完成！"
echo ""
echo "📊 重要資源資訊："
terraform output

echo ""
echo "🔧 實用指令："
echo "  檢查 invalidation 狀態: ./check-invalidation.sh"
echo "  重新部署靜態網站: ./deploy.sh"
echo "  查看 Terraform 狀態: terraform show"
echo "  銷毀資源: terraform destroy" 