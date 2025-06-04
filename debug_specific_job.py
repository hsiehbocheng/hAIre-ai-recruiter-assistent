import boto3
import json
from boto3.dynamodb.conditions import Key

# 初始化 DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')

# 表格名稱
jobs_table = dynamodb.Table('benson-haire-job-posting')

def debug_specific_job():
    """檢查 CXI-DATAAI-CI 職缺的詳細資料"""
    
    print("🔍 開始檢查 CXI-DATAAI-CI 職缺資料...")
    
    try:
        # 查詢所有職缺，找到包含 CXI-DATAAI-CI 的職缺
        response = jobs_table.scan()
        jobs = response.get('Items', [])
        
        print(f"\n📊 總共找到 {len(jobs)} 個職缺")
        
        # 找到 CXI-DATAAI-CI 相關的職缺
        target_jobs = [job for job in jobs if 'CXI-DATAAI-CI' in job.get('job_id', '')]
        
        if not target_jobs:
            print("❌ 未找到 CXI-DATAAI-CI 相關的職缺")
            return
        
        for job in target_jobs:
            print(f"\n🎯 職缺 ID: {job.get('job_id', 'UNKNOWN')}")
            print(f"📋 職缺標題: {job.get('job_title', 'MISSING')}")
            
            # 檢查可能導致 undefined 的欄位
            critical_fields = {
                'employment_type': job.get('employment_type'),
                'location': job.get('location'),
                'status': job.get('status'),
                'team_id': job.get('team_id'),
                'company_code': job.get('company_code'),
                'dept_code': job.get('dept_code'),
                'section_code': job.get('section_code'),
                'job_description': job.get('job_description'),
                'responsibilities': job.get('responsibilities'),
                'required_skills': job.get('required_skills'),
                'nice_to_have_skills': job.get('nice_to_have_skills'),
                'min_experience_years': job.get('min_experience_years'),
                'education_required': job.get('education_required'),
                'majors_required': job.get('majors_required'),
                'salary_min': job.get('salary_min'),
                'salary_max': job.get('salary_max'),
                'salary_note': job.get('salary_note'),
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at')
            }
            
            print("\n🔍 關鍵欄位檢查:")
            for field, value in critical_fields.items():
                if value is None:
                    print(f"  ❌ {field}: None (這會顯示為 undefined)")
                elif value == '':
                    print(f"  ⚠️  {field}: 空字串")
                else:
                    print(f"  ✅ {field}: {value}")
            
            print(f"\n📝 完整資料結構:")
            print(json.dumps(job, indent=2, default=str, ensure_ascii=False))
            print("-" * 50)
        
        # 比較其他正常的職缺
        print(f"\n🔄 比較其他職缺的資料結構...")
        other_jobs = [job for job in jobs if 'CXI-DATAAI-CI' not in job.get('job_id', '')][:2]
        
        for job in other_jobs:
            print(f"\n✅ 正常職缺範例 - ID: {job.get('job_id', 'UNKNOWN')}")
            print(f"  employment_type: {job.get('employment_type')}")
            print(f"  location: {job.get('location')}")
            print(f"  status: {job.get('status')}")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    debug_specific_job() 