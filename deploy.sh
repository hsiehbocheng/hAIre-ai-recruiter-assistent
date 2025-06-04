#!/bin/bash

# hAIre 系統部署腳本
# 此腳本會自動部署系統並更新前端配置中的硬編碼 URL

set -e  # 發生錯誤時立即退出

echo "🚀 hAIre 系統部署開始..."

# 檢查必要工具
command -v terraform >/dev/null 2>&1 || { echo "❌ 需要 terraform 工具"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ 需要 python3"; exit 1; }

# 設置變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📂 工作目錄: $SCRIPT_DIR"

# 函數：打包 Lambda 函數
package_lambdas() {
    echo "📦 打包 Lambda 函數..."
    
    LAMBDA_DIRS=(
        "lambdas/team_management"
        "lambdas/job_management" 
        "lambdas/resume_upload"
        "lambdas/resume_management"
        "lambdas/resume_parser"
    )
    
    for lambda_dir in "${LAMBDA_DIRS[@]}"; do
        if [ -d "$lambda_dir" ]; then
            echo "📦 打包 $lambda_dir..."
            cd "$lambda_dir"
            zip_name=$(basename "$lambda_dir").zip
            zip -r "$zip_name" . -x "*.zip" "*.pyc" "__pycache__/*" "*.git*"
            cd "$SCRIPT_DIR"
            echo "✅ $lambda_dir 打包完成"
        else
            echo "⚠️  目錄不存在: $lambda_dir"
        fi
    done
}

# 函數：初始化 Terraform
init_terraform() {
    echo "🏗️  初始化 Terraform..."
    terraform init
    echo "✅ Terraform 初始化完成"
}

# 函數：驗證 Terraform 配置
validate_terraform() {
    echo "✅ 驗證 Terraform 配置..."
    terraform validate
    echo "✅ Terraform 配置驗證通過"
}

# 函數：計劃部署
plan_deployment() {
    echo "📋 規劃部署..."
    terraform plan -out=tfplan
    echo "✅ 部署計劃已生成"
}

# 函數：執行部署
apply_deployment() {
    echo "🚀 執行部署..."
    terraform apply tfplan
    echo "✅ 部署完成"
}

# 函數：顯示部署結果
show_results() {
    echo ""
    echo "🎉 部署完成！"
    echo ""
    echo "📊 部署資訊："
    terraform output
    echo ""
    echo "📱 前端配置已自動更新"
    echo ""
    echo "✅ 硬編碼 URL 問題已解決："
    echo "- config.js 將由 Terraform 自動生成正確的 URL"
    echo "- API Gateway URL 和 CloudFront URL 會動態設置"
    echo ""
    echo "🔗 重要連結："
    echo "- API Gateway: $(terraform output -raw api_gateway_url)"
    echo "- 靜態網站: $(terraform output -raw cloudfront_url)"
}

# 主要執行流程
main() {
    echo "🚀 開始部署流程..."
    
    package_lambdas
    init_terraform
    validate_terraform
    plan_deployment
    
    echo ""
    echo "⚠️  即將開始部署，這將會:"
    echo "- 創建/更新 AWS 資源"
    echo "- 可能產生 AWS 費用"
    echo "- 自動修正硬編碼 URL 問題"
    echo ""
    read -p "確定要繼續部署嗎? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        apply_deployment
        show_results
    else
        echo "❌ 部署已取消"
        exit 1
    fi
}

# 檢查參數
case "${1:-deploy}" in
    "package")
        package_lambdas
        ;;
    "plan")
        package_lambdas
        init_terraform
        validate_terraform
        plan_deployment
        ;;
    "deploy")
        main
        ;;
    "help"|"-h"|"--help")
        echo "用法: $0 [命令]"
        echo ""
        echo "命令:"
        echo "  deploy (預設)  - 完整部署流程"
        echo "  package        - 只打包 Lambda 函數"
        echo "  plan          - 只規劃部署"
        echo "  help          - 顯示此說明"
        echo ""
        echo "此腳本會自動解決硬編碼 URL 的問題："
        echo "- 使用 Terraform template 動態生成前端配置"
        echo "- 自動上傳正確的 config.js 到 S3"
        echo "- 移除 API Gateway 和 CloudFront 的硬編碼 URL"
        ;;
    *)
        echo "❌ 未知命令: $1"
        echo "使用 '$0 help' 查看可用命令"
        exit 1
        ;;
esac 