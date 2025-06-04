import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
table = dynamodb.Table('benson-haire-parsed_resume')

print("查詢所有履歷記錄...")

# 掃描整個表格
response = table.scan()
items = response['Items']

print(f"總共找到 {len(items)} 筆記錄")
print("\n" + "="*80)

for i, item in enumerate(items, 1):
    print(f"\n記錄 {i}:")
    print(f"  resume_id: {item.get('resume_id', 'N/A')}")
    print(f"  候選人姓名: {item.get('candidate_name', 'N/A')}")
    print(f"  電子郵件: {item.get('candidate_email', 'N/A')}")
    print(f"  現職: {item.get('current_title', 'N/A')}")
    print(f"  team_id: {item.get('team_id', 'N/A')}")
    print(f"  job_id: {item.get('job_id', 'N/A')}")
    print(f"  S3 key: {item.get('s3_key', 'N/A')}")
    print(f"  處理時間: {item.get('processed_at', 'N/A')}")
    print("-" * 60)

# 特別查詢包含 zhang-xiaoming 的記錄
print("\n" + "="*80)
print("查詢包含 'zhang-xiaoming' 的記錄...")

zhang_records = [item for item in items if 'zhang-xiaoming' in item.get('s3_key', '').lower()]
print(f"找到 {len(zhang_records)} 筆包含 zhang-xiaoming 的記錄")

for record in zhang_records:
    print(f"\n張小明的履歷:")
    print(f"  resume_id: {record.get('resume_id')}")
    print(f"  候選人姓名: {record.get('candidate_name')}")
    print(f"  S3 key: {record.get('s3_key')}")
    
    # 檢查解析資料
    parsed_data = record.get('parsed_resume_data', {})
    if parsed_data:
        profile = parsed_data.get('profile', {})
        basics = profile.get('basics', {})
        print(f"  解析姓名: {basics.get('first_name', '')} {basics.get('last_name', '')}")
        print(f"  解析email: {basics.get('emails', [])}")
        print(f"  技能: {basics.get('skills', [])}")
    else:
        print("  沒有解析資料") 