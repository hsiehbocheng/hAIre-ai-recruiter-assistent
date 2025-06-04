import json
import boto3
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

# 初始化 AWS 服務
dynamodb = boto3.resource('dynamodb')

# 環境變數
RESUME_TABLE_NAME = os.environ.get('RESUME_TABLE_NAME', 'benson-haire-parsed_resume')
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME', 'benson-haire-job-posting')

# DynamoDB 表格
resume_table = dynamodb.Table(RESUME_TABLE_NAME)
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)

class DecimalEncoder(json.JSONEncoder):
    """處理 DynamoDB Decimal 類型的 JSON 編碼器"""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """統一的回應格式"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, cls=DecimalEncoder, ensure_ascii=False)
    }

def get_job_applicants(job_id: str) -> Dict[str, Any]:
    """獲取特定職缺的應徵者履歷資料"""
    try:
        print(f"查詢職缺應徵者 - job_id: {job_id}")
        
        # 檢查職缺是否存在
        job_response = jobs_table.get_item(Key={'job_id': job_id})
        if 'Item' not in job_response:
            print(f"職缺不存在: {job_id}")
            return response(404, {'error': '職缺不存在'})
        
        print(f"職缺存在，開始查詢履歷資料...")
        
        # 使用 GSI 查詢該職缺的所有履歷
        try:
            print(f"執行 GSI 查詢: IndexName=job-index, job_id={job_id}")
            resume_response = resume_table.query(
                IndexName='job-index',
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={
                    ':job_id': job_id
                },
                ScanIndexForward=False  # 按時間倒序排列
            )
            
            resumes = resume_response.get('Items', [])
            print(f"查詢到 {len(resumes)} 筆履歷資料")
            
            if resumes:
                print(f"第一筆履歷資料: {resumes[0].get('resume_id', 'UNKNOWN')}")
            
            # 格式化履歷資料為前端需要的格式
            applicants = []
            for resume in resumes:
                print(f"處理履歷: {resume.get('resume_id', 'UNKNOWN')}")
                
                # 提取履歷基本資訊 - 使用新的 profile 結構
                profile = resume.get('profile', {})  # 新的 profile 結構
                basics = profile.get('basics', {})
                experiences = profile.get('professional_experiences', [])
                educations = profile.get('educations', [])
                
                # 計算總工作經驗
                total_experience = basics.get('total_experience_in_years')
                if total_experience is None and experiences:
                    # 如果沒有總經驗，從工作經歷計算
                    current_year = datetime.now().year
                    total_months = 0
                    for exp in experiences:
                        if exp.get('duration_in_months'):
                            total_months += exp['duration_in_months']
                    total_experience = round(total_months / 12) if total_months > 0 else 0
                
                # 取得最新的教育背景
                latest_education = ''
                if educations:
                    # 按年份排序，取最新的
                    sorted_educations = sorted(educations, key=lambda x: x.get('start_year', 0), reverse=True)
                    latest_edu = sorted_educations[0]
                    org = latest_edu.get('issuing_organization', '')
                    dept = latest_edu.get('department', '')
                    if org and dept:
                        latest_education = f"{org} {dept}"
                    elif org:
                        latest_education = org
                
                # 取得技能列表
                skills = basics.get('skills', [])
                
                # 從候選人名稱中提取，兼容新舊格式
                candidate_name = resume.get('candidate_name', 'Unknown')
                if candidate_name == 'None None' or not candidate_name:
                    # 如果候選人名稱無效，嘗試從 basics 中提取
                    first_name = basics.get('first_name', '')
                    last_name = basics.get('last_name', '')
                    candidate_name = f"{first_name} {last_name}".strip() or 'Unknown'
                
                # 組織應徵者資料
                applicant = {
                    'id': resume['resume_id'],
                    'name': candidate_name,
                    'email': resume.get('candidate_email') or (basics.get('emails', [None])[0] if basics.get('emails') else None) or '未提供',
                    'phone': '未提供',  # 履歷解析中沒有電話號碼
                    'experience': f"{total_experience}年" if total_experience is not None else '未知',
                    'education': latest_education or '未提供',
                    'skills': skills,
                    'current_title': resume.get('current_title') or basics.get('current_title', '') or '未提供',
                    'status': 'applied',  # 預設狀態
                    'applied_at': resume.get('processed_at', ''),
                    'resume_id': resume['resume_id'],
                    'team_id': resume.get('team_id', ''),
                    'job_id': resume.get('job_id', ''),
                    's3_key': resume.get('s3_key', ''),
                    'parsed_data': resume  # 完整的解析資料，供詳細檢視使用
                }
                
                applicants.append(applicant)
                print(f"添加應徵者: {applicant['name']}")
            
            print(f"總共處理了 {len(applicants)} 個應徵者")
            
            return response(200, {
                'message': '成功獲取應徵者資料' if applicants else '目前尚無應徵者',
                'job_id': job_id,
                'total_count': len(applicants),
                'data': applicants
            })
            
        except Exception as query_error:
            print(f"查詢履歷資料失敗: {str(query_error)}")
            import traceback
            print(f"完整錯誤資訊: {traceback.format_exc()}")
            # 如果查詢失敗，返回空列表而不是錯誤
            return response(200, {
                'message': '目前尚無應徵者',
                'job_id': job_id,
                'total_count': 0,
                'data': []
            })
        
    except Exception as e:
        print(f"獲取職缺應徵者失敗: {str(e)}")
        import traceback
        print(f"完整錯誤資訊: {traceback.format_exc()}")
        return response(500, {'error': '獲取應徵者資料失敗'})

def get_resume_detail(resume_id: str) -> Dict[str, Any]:
    """獲取特定履歷的詳細資料"""
    try:
        resume_response = resume_table.get_item(Key={'resume_id': resume_id})
        
        if 'Item' not in resume_response:
            return response(404, {'error': '履歷不存在'})
        
        resume = resume_response['Item']
        
        return response(200, {
            'message': '成功獲取履歷詳情',
            'data': resume
        })
        
    except Exception as e:
        print(f"獲取履歷詳情失敗: {str(e)}")
        return response(500, {'error': '獲取履歷詳情失敗'})

def list_resumes(query_params: Dict[str, str]) -> Dict[str, Any]:
    """列出履歷（支援按團隊、職缺篩選）"""
    try:
        team_id = query_params.get('team_id')
        job_id = query_params.get('job_id')
        page = int(query_params.get('page', 1))
        limit = min(int(query_params.get('limit', 50)), 100)
        
        if job_id:
            # 使用 job-index GSI 查詢特定職缺的履歷
            return get_job_applicants(job_id)
        elif team_id:
            # 使用 team-index GSI 查詢特定團隊的履歷
            try:
                resume_response = resume_table.query(
                    IndexName='team-index',
                    KeyConditionExpression='team_id = :team_id',
                    ExpressionAttributeValues={
                        ':team_id': team_id
                    },
                    ScanIndexForward=False
                )
                
                resumes = resume_response.get('Items', [])
                
                # 分頁
                total = len(resumes)
                start = (page - 1) * limit
                end = start + limit
                paginated_resumes = resumes[start:end]
                
                return response(200, {
                    'message': '成功獲取團隊履歷資料',
                    'team_id': team_id,
                    'total_count': total,
                    'data': paginated_resumes,
                    'pagination': {
                        'current_page': page,
                        'total_pages': (total + limit - 1) // limit if total > 0 else 1,
                        'total_items': total,
                        'items_per_page': limit
                    }
                })
                
            except Exception as query_error:
                print(f"查詢團隊履歷失敗: {str(query_error)}")
                return response(200, {
                    'message': '目前尚無履歷資料',
                    'team_id': team_id,
                    'total_count': 0,
                    'data': []
                })
        else:
            # 掃描所有履歷（限制使用）
            scan_response = resume_table.scan(
                Limit=limit
            )
            
            resumes = scan_response.get('Items', [])
            
            return response(200, {
                'message': '成功獲取履歷列表',
                'total_count': len(resumes),
                'data': resumes
            })
            
    except Exception as e:
        print(f"列出履歷失敗: {str(e)}")
        return response(500, {'error': '列出履歷失敗'})

def lambda_handler(event, context):
    """Lambda 主函數"""
    try:
        # 處理 CORS preflight 請求
        if event['httpMethod'] == 'OPTIONS':
            return response(200, {'message': 'CORS preflight success'})
        
        # 解析路徑和方法
        method = event['httpMethod']
        path = event.get('path', '')
        query_params = event.get('queryStringParameters') or {}
        
        print(f"Resume management - Method: {method}, Path: {path}, Query: {query_params}")
        
        # 路由處理
        if method == 'GET' and path == '/resumes':
            # 列出履歷（支援 job_id 和 team_id 篩選）
            return list_resumes(query_params)
        
        elif method == 'GET' and path == '/resumes/job-applicants':
            # 獲取特定職缺的應徵者
            job_id = query_params.get('job_id')
            if not job_id:
                return response(400, {'error': '缺少 job_id 參數'})
            return get_job_applicants(job_id)
        
        elif method == 'GET' and path.startswith('/resumes/'):
            # 獲取特定履歷詳情
            resume_id = path.split('/')[-1]
            return get_resume_detail(resume_id)
        
        else:
            return response(404, {'error': '找不到指定的路由'})
    
    except Exception as e:
        print(f"Resume management Lambda 執行錯誤: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return response(500, {'error': '伺服器內部錯誤'}) 