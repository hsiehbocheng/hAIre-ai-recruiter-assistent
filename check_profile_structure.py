import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
table = dynamodb.Table('benson-haire-parsed_resume')

print("檢查最新履歷的 profile 結構...")

# 查詢陳大明的履歷
response = table.scan(
    FilterExpression="contains(candidate_name, :name)",
    ExpressionAttributeValues={':name': '陳'}
)

items = response['Items']

if items:
    item = items[0]  # 取第一筆記錄
    print(f"\n=== 履歷 ID: {item.get('resume_id', 'N/A')} ===")
    print(f"候選人: {item.get('candidate_name', 'N/A')}")
    print(f"Email: {item.get('candidate_email', 'N/A')}")
    
    # 檢查是否有 profile 欄位
    if 'profile' in item:
        profile = item['profile']
        print(f"\n✅ Profile 結構存在")
        
        # 檢查 basics
        if 'basics' in profile:
            basics = profile['basics']
            print(f"\n🔍 Basics 欄位:")
            print(f"  - first_name: {basics.get('first_name', 'N/A')}")
            print(f"  - last_name: {basics.get('last_name', 'N/A')}")
            print(f"  - gender: {basics.get('gender', 'N/A')}")
            print(f"  - emails: {basics.get('emails', [])}")
            print(f"  - urls: {basics.get('urls', [])}")
            print(f"  - date_of_birth: {basics.get('date_of_birth', {})}")
            print(f"  - age: {basics.get('age', 'N/A')}")
            print(f"  - total_experience_in_years: {basics.get('total_experience_in_years', 'N/A')}")
            print(f"  - current_title: {basics.get('current_title', 'N/A')}")
            print(f"  - skills 數量: {len(basics.get('skills', []))}")
        
        # 檢查各個陣列
        print(f"\n🔍 陣列欄位:")
        print(f"  - educations: {len(profile.get('educations', []))} 項")
        print(f"  - trainings_and_certifications: {len(profile.get('trainings_and_certifications', []))} 項")
        print(f"  - professional_experiences: {len(profile.get('professional_experiences', []))} 項")
        print(f"  - awards: {len(profile.get('awards', []))} 項")
        
        # 顯示第一個教育經歷的詳細內容
        if profile.get('educations'):
            edu = profile['educations'][0]
            print(f"\n📚 第一個教育經歷:")
            print(f"  - start_year: {edu.get('start_year', 'N/A')}")
            print(f"  - end_year: {edu.get('end_year', 'N/A')}")
            print(f"  - is_current: {edu.get('is_current', 'N/A')}")
            print(f"  - issuing_organization: {edu.get('issuing_organization', 'N/A')}")
            print(f"  - study_type: {edu.get('study_type', 'N/A')}")
            print(f"  - department: {edu.get('department', 'N/A')}")
            print(f"  - description: {edu.get('description', 'N/A')}")
        
        # 顯示第一個工作經歷的詳細內容
        if profile.get('professional_experiences'):
            exp = profile['professional_experiences'][0]
            print(f"\n💼 第一個工作經歷:")
            print(f"  - start_year: {exp.get('start_year', 'N/A')}")
            print(f"  - start_month: {exp.get('start_month', 'N/A')}")
            print(f"  - end_year: {exp.get('end_year', 'N/A')}")
            print(f"  - end_month: {exp.get('end_month', 'N/A')}")
            print(f"  - is_current: {exp.get('is_current', 'N/A')}")
            print(f"  - duration_in_months: {exp.get('duration_in_months', 'N/A')}")
            print(f"  - company: {exp.get('company', 'N/A')}")
            print(f"  - location: {exp.get('location', 'N/A')}")
            print(f"  - title: {exp.get('title', 'N/A')}")
            print(f"  - description 長度: {len(exp.get('description', ''))}")
        
        # 顯示第一個證照
        if profile.get('trainings_and_certifications'):
            cert = profile['trainings_and_certifications'][0]
            print(f"\n🏆 第一個證照:")
            print(f"  - year: {cert.get('year', 'N/A')}")
            print(f"  - issuing_organization: {cert.get('issuing_organization', 'N/A')}")
            print(f"  - description: {cert.get('description', 'N/A')}")
        
        # 顯示第一個獎項
        if profile.get('awards'):
            award = profile['awards'][0]
            print(f"\n🏅 第一個獎項:")
            print(f"  - year: {award.get('year', 'N/A')}")
            print(f"  - title: {award.get('title', 'N/A')}")
            print(f"  - description: {award.get('description', 'N/A')}")
            
    else:
        print("\n❌ 沒有找到 profile 欄位")
        
    # 檢查是否還有舊的 parsed_resume_data 欄位
    if 'parsed_resume_data' in item:
        print(f"\n⚠️  舊的 parsed_resume_data 欄位仍然存在")
    else:
        print(f"\n✅ 舊的 parsed_resume_data 欄位已移除")
        
else:
    print("❌ 沒有找到陳大明的履歷記錄") 