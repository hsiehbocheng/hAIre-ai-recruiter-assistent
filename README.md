# hAIre AI 招募助理系統

這是一個使用 Terraform 部署的雲端 AI 招募助理系統，包含 Lambda 函數、API Gateway、DynamoDB 和靜態網站。

## 📋 系統架構

- **API Gateway**: RESTful API 端點
- **Lambda 函數**: 
  - 團隊管理
  - 工作管理
  - 履歷上傳與解析
  - 履歷管理
- **DynamoDB**: 數據存儲
- **S3**: 靜態網站和檔案存儲
- **CloudFront**: CDN 分發

## 🔧 部署前準備

### 必要工具
- AWS CLI（已配置）
- Terraform >= 1.8.0
- Python 3.11+
- zip 工具

### AWS 設定
```bash
aws configure
# 設定您的 AWS 認證資訊
```

## 🚀 部署方式

### 自動部署（推薦）
使用我們提供的部署腳本：

```bash
# 完整部署
./deploy.sh

# 只打包 Lambda 函數
./deploy.sh package

# 只規劃部署
./deploy.sh plan

# 查看說明
./deploy.sh help
```

### 手動部署
```bash
# 1. 打包 Lambda 函數
cd lambdas/team_management && zip -r team_management.zip . && cd ../..
cd lambdas/job_management && zip -r job_management.zip . && cd ../..
cd lambdas/resume_upload && zip -r resume_upload.zip . && cd ../..
cd lambdas/resume_management && zip -r resume_management.zip . && cd ../..
cd lambdas/resume_parser && zip -r resume_parser.zip . && cd ../..

# 2. 初始化 Terraform
terraform init

# 3. 規劃部署
terraform plan

# 4. 執行部署
terraform apply
```

## 🔗 硬編碼 URL 問題的解決方案

### 問題描述
原本的程式碼中存在硬編碼的 API 端點和 CloudFront URL：
- `https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev`
- `https://d34pb6c7ehwsy2.cloudfront.net`

### 解決方案
我們使用 Terraform 模板功能自動生成正確的配置：

1. **動態配置生成**: `static-site/js/config.js` 使用 Terraform 模板變數
2. **自動 URL 替換**: 部署時自動將實際的 URL 替換到配置中
3. **版本控制**: 生成的配置會自動上傳到 S3

### 配置檔案結構
```javascript
// static-site/js/config.js
window.CONFIG = {
    API_BASE_URL: '${api_gateway_url}',     // 由 Terraform 替換
    CLOUDFRONT_URL: '${cloudfront_url}',    // 由 Terraform 替換
    GENERATED_AT: '${generated_at}',        // 生成時間戳
    VERSION: '1.0.0'
};
```

## 📊 部署後檢查

部署完成後，您可以通過以下命令查看部署資訊：

```bash
# 查看所有輸出
terraform output

# 查看特定 URL
terraform output api_gateway_url
terraform output cloudfront_url
```

## 🔄 更新部署

如果需要更新系統：

```bash
# 重新部署
./deploy.sh

# 或者手動更新
terraform plan
terraform apply
```

## 📱 前端配置

前端會自動使用正確的 URL，不需要手動配置。系統會：
1. 優先使用 Terraform 生成的 URL
2. 如果模板變數尚未替換，會顯示警告並使用開發環境預設值
3. 在瀏覽器控制台顯示當前使用的配置

## ⚠️ 注意事項

1. **AWS 費用**: 部署會產生 AWS 使用費用
2. **資源清理**: 不需要時請執行 `terraform destroy` 清理資源
3. **備份**: 系統會自動備份資料到 S3
4. **CORS 設定**: API 端點支援跨來源請求

## 🔍 故障排除

### 常見問題

**Q: 前端顯示 404 錯誤**
A: 檢查 CloudFront 分發是否完成部署（通常需要 10-15 分鐘）

**Q: API 請求失敗**
A: 檢查 API Gateway URL 是否正確，以及 Lambda 函數是否正常運行

**Q: 配置檔案沒有更新**
A: 重新執行 `terraform apply` 以更新 S3 上的配置檔案

### 日誌查看
```bash
# 查看 Lambda 函數日誌
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/benson-haire"

# 查看特定 Lambda 的日誌
aws logs tail /aws/lambda/benson-haire-team-management --follow
```

## 📞 支援

如有問題，請檢查：
1. AWS 認證設定是否正確
2. Terraform 版本是否符合要求
3. 所有必要的 AWS 權限是否已配置

---

✅ **硬編碼 URL 問題已解決**: 系統現在會自動生成和使用正確的 API Gateway 和 CloudFront URL，無需手動配置。