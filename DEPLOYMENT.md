# hAIre AI 招聘助手 - 部署指南

## 🚀 快速部署

### 前置需求
- AWS CLI 已安裝並配置
- Terraform >= 1.8.0
- Python 3.12+
- jq (JSON 處理工具)

### 一鍵部署
```bash
# 完整的基礎設施和靜態網站部署
./deploy-infrastructure.sh
```

### 單獨部署靜態網站
```bash
# 僅同步靜態網站到 S3 並清除 CloudFront 快取
./deploy.sh
```

## 🔧 實用工具

### 檢查 CloudFront 快取清除狀態
```bash
# 檢查最近的 invalidations
./check-invalidation.sh

# 檢查特定的 invalidation
./check-invalidation.sh I2V2UKJAR1P531IXTPBT7N6V3Y
```

### 其他有用指令
```bash
# 查看部署的資源資訊
terraform output

# 查看詳細的 Terraform 狀態
terraform show

# 銷毀所有資源（謹慎使用）
terraform destroy
```

## 📁 檔案說明

- `deploy-infrastructure.sh` - 完整的基礎設施部署腳本
- `deploy.sh` - 靜態網站部署腳本
- `check-invalidation.sh` - CloudFront 快取清除狀態檢查
- `main.tf` - Terraform 主要配置
- `static-site/` - 靜態網站檔案目錄

## 🌐 部署後的資源

部署完成後，您將獲得：

1. **S3 Buckets** - 儲存各種類型的資料
2. **CloudFront Distribution** - 全球 CDN 分發靜態網站
3. **API Gateway** - RESTful API 端點
4. **Lambda Functions** - 後端業務邏輯處理
5. **DynamoDB Tables** - NoSQL 資料庫

## ⚠️ 注意事項

- CloudFront 快取清除通常需要 5-15 分鐘完成
- 首次部署可能需要 10-20 分鐘，因為需要建立大量 AWS 資源
- 確保 AWS 帳戶有足夠的權限建立所有必要的資源
- 部署前請檢查 AWS 服務限額，避免超出免費額度

## 🔒 安全考量

- 所有敏感資訊都透過 AWS IAM 角色管理
- S3 bucket 只允許 CloudFront 存取
- API Gateway 使用 CORS 設定確保安全
- Lambda 函數權限遵循最小權限原則 