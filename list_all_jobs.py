import boto3
import json

# 初始化 DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')

# 表格名稱
jobs_table = dynamodb.Table('benson-haire-job-posting')

def list_all_jobs():
    """列出所有職缺的基本資訊"""
    
    print("🔍 列出所有職缺...")
    
    try:
        response = jobs_table.scan()
        jobs = response.get('Items', [])
        
        print(f"\n📊 總共找到 {len(jobs)} 個職缺")
        
        for i, job in enumerate(jobs, 1):
            job_id = job.get('job_id', 'UNKNOWN')
            job_title = job.get('job_title', 'MISSING')
            employment_type = job.get('employment_type', 'MISSING')
            location = job.get('location', 'MISSING')
            status = job.get('status', 'MISSING')
            team_id = job.get('team_id', 'MISSING')
            
            print(f"\n{i}. 職缺 ID: {job_id}")
            print(f"   標題: {job_title}")
            print(f"   聘用類型: {employment_type}")
            print(f"   地點: {location}")
            print(f"   狀態: {status}")
            print(f"   團隊 ID: {team_id}")
            
            # 如果是 CXI 相關職缺，顯示更詳細的資訊
            if 'CXI' in job_id:
                print(f"   🎯 這是 CXI 相關職缺！")
                print(f"   詳細資料: {json.dumps(job, indent=4, default=str, ensure_ascii=False)}")
            
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    list_all_jobs() 