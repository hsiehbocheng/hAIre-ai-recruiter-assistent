# 📊 Benson-hAIre 智能招募系統資料架構

## 🎯 系統資料流程圖

```mermaid
sequenceDiagram
    participant HR
    participant Frontend
    participant S3
    participant Lambda_Parse
    participant DynamoDB
    participant StepFn_Match
    participant Bedrock
    participant OpenSearch
    participant SNS
    participant Email

    HR->>Frontend: 上傳職缺/團隊資訊
    Frontend->>S3: 儲存 JSON (job-postings/)
    S3-->>Lambda_Parse: 觸發 AI 條件萃取
    Lambda_Parse->>Bedrock: 呼叫 LLM 萃取條件
    Bedrock-->>Lambda_Parse: 回傳條件列表
    Lambda_Parse->>DynamoDB: 儲存於 JobPosting 表

    求職者->>Frontend: 投遞履歷
    Frontend->>S3: 儲存履歷檔案 (raw-resumes/{team_id}/{job_id}/yyyymmdd/resume_id.pdf)
    S3-->>Lambda_Parse: 觸發履歷解析 Lambda
    Lambda_Parse->>Bedrock: 呼叫 LLM 萃取摘要
    Lambda_Parse->>DynamoDB: 寫入 Resume 表

    Lambda_Parse->>StepFn_Match: 依模式決定是否即時比對
    StepFn_Match->>OpenSearch: 向量比對職缺需求
    StepFn_Match->>DynamoDB: 寫入 JobMatch 表
    StepFn_Match->>SNS: 若推薦，通知主管
    SNS->>Email: 發送候選人摘要信件
```

## 🧱 資料表 Schema

---

### 🗂️ JobPosting 表（DynamoDB）

主鍵：`job_id`（string）

| 欄位名                 | 資料型別  | 說明                         |
|------------------------|-----------|------------------------------|
| `job_id`               | string    | 職缺 ID，UUID 格式           |
| `team_id`              | string    | 部門/單位代碼                |
| `job_title`            | string    | 職稱                         |
| `job_description`      | string    | 原始 HR 上傳內容             |
| `extracted_requirements` | map/list | AI 萃取條件，包含技能、年資等 |
| `status`               | string    | 開啟狀態（open/closed）      |
| `created_at`           | string    | 建立時間（ISO 8601）         |

---

### 🗂️ Resume 表（DynamoDB）

主鍵：`resume_id`（string）

| 欄位名             | 資料型別 | 說明                              |
|--------------------|----------|-----------------------------------|
| `resume_id`        | string   | 履歷 ID，UUID                     |
| `candidate_name`   | string   | 求職者姓名                        |
| `email`            | string   | 聯絡信箱                          |
| `source`           | string   | 來源（104、自投等）               |
| `job_id`           | string   | 投遞目標職缺 ID                   |
| `team_id`          | string   | 投遞目標部門                      |
| `raw_resume_s3`    | string   | 履歷檔案在 S3 的完整路徑         |
| `parsed_profile`   | map      | AI 解析欄位（技能、學歷、經歷等）|
| `submitted_at`     | string   | 投遞時間（ISO 8601）              |

---

### 🗂️ JobMatch 表（DynamoDB）

複合鍵：`job_id`（PK）+ `resume_id`（SK）

| 欄位名               | 資料型別 | 說明                              |
|----------------------|----------|-----------------------------------|
| `job_id`             | string   | 職缺 ID（對應職缺）              |
| `resume_id`          | string   | 履歷 ID（對應候選人）            |
| `match_score`        | number   | AI 計算的相似度分數（0–1）       |
| `recommended`        | boolean  | 是否推薦                          |
| `notified`           | boolean  | 是否已通知主管                    |
| `interview_feedback` | string   | 面談或主管備註                    |
| `last_updated`       | string   | 最後更新時間（ISO 8601）         |