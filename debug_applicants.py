import boto3
import json
from boto3.dynamodb.conditions import Key

# 初始化 DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')

# 表格名稱
resume_table = dynamodb.Table('benson-haire-parsed_resume')
jobs_table = dynamodb.Table('benson-haire-job-posting')

def debug_applicants():
    """檢查應徵者數據和職缺匹配的問題"""
    
    print("🔍 開始檢查應徵者數據...")
    
    # 1. 查看所有應徵者的 job_id
    try:
        resume_response = resume_table.scan()
        resumes = resume_response.get('Items', [])
        
        print(f"\n📊 總共找到 {len(resumes)} 筆履歷記錄")
        
        job_id_counts = {}
        for resume in resumes:
            job_id = resume.get('job_id', 'UNKNOWN')
            job_id_counts[job_id] = job_id_counts.get(job_id, 0) + 1
            
            print(f"  - 履歷 {resume.get('resume_id', 'UNKNOWN')} -> job_id: {job_id}")
        
        print(f"\n📈 各職缺的應徵者統計:")
        for job_id, count in job_id_counts.items():
            print(f"  - {job_id}: {count} 個應徵者")
            
    except Exception as e:
        print(f"❌ 掃描應徵者數據失敗: {str(e)}")
    
    # 2. 查看所有職缺的 job_id
    try:
        jobs_response = jobs_table.scan()
        jobs = jobs_response.get('Items', [])
        
        print(f"\n📊 總共找到 {len(jobs)} 個職缺")
        
        for job in jobs:
            job_id = job.get('job_id', 'UNKNOWN')
            job_title = job.get('job_title', 'UNKNOWN')
            team_id = job.get('team_id', 'UNKNOWN')
            print(f"  - 職缺 {job_id}: {job_title} (團隊: {team_id})")
            
    except Exception as e:
        print(f"❌ 掃描職缺數據失敗: {str(e)}")
    
    # 3. 測試 GSI 查詢
    print(f"\n🔍 測試 GSI 查詢...")
    
    # 取得第一個有應徵者的 job_id 進行測試
    if job_id_counts:
        test_job_id = next(iter(job_id_counts.keys()))
        if test_job_id != 'UNKNOWN':
            print(f"🧪 測試查詢職缺 {test_job_id} 的應徵者...")
            
            try:
                gsi_response = resume_table.query(
                    IndexName='job-index',
                    KeyConditionExpression=Key('job_id').eq(test_job_id)
                )
                
                applicants = gsi_response.get('Items', [])
                print(f"✅ GSI 查詢成功，找到 {len(applicants)} 個應徵者")
                
                for applicant in applicants:
                    print(f"  - {applicant.get('candidate_name', 'UNKNOWN')} ({applicant.get('resume_id', 'UNKNOWN')})")
                    
            except Exception as e:
                print(f"❌ GSI 查詢失敗: {str(e)}")
        else:
            print("⚠️ 沒有有效的 job_id 可以測試")
    else:
        print("⚠️ 沒有找到任何應徵者數據")

if __name__ == "__main__":
    debug_applicants() 