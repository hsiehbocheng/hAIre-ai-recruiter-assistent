import json
import boto3
import uuid
import re
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

# 初始化 AWS 服務
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# 環境變數
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME', 'benson-haire-job-posting')
TEAMS_TABLE_NAME = os.environ.get('TEAMS_TABLE_NAME', 'benson-haire-teams')
S3_BUCKET = os.environ.get('BACKUP_S3_BUCKET', 'benson-haire-static-site-e36d5aee')

# DynamoDB 表格
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)
teams_table = dynamodb.Table(TEAMS_TABLE_NAME)

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

def validate_job_data(data: Dict[str, Any], is_update: bool = False) -> Optional[str]:
    """驗證職缺資料格式"""
    required_fields = ['team_id', 'job_title', 'employment_type', 'location', 'responsibilities', 'required_skills']
    
    # 檢查必填欄位
    if not is_update:
        for field in required_fields:
            if field not in data or not data[field]:
                return f"缺少必填欄位: {field}"
    
    # 驗證 team_id 格式 (修正為新格式)
    if 'team_id' in data and data['team_id']:
        if not re.match(r'^[A-Z0-9]{2,8}-[A-Z0-9]{2,10}-[A-Z0-9]{2,8}$', data['team_id']):
            return "team_id 格式不正確，應為 {公司代碼}-{部門代碼}-{科別代碼}"
    
    # 驗證聘用類型
    if 'employment_type' in data and data['employment_type']:
        valid_types = ['全職', '兼職', '約聘', '實習', '顧問']
        if data['employment_type'] not in valid_types:
            return f"聘用類型無效，可選值: {', '.join(valid_types)}"
    
    # 驗證薪資範圍
    if 'salary_min' in data and 'salary_max' in data:
        if data['salary_min'] and data['salary_max']:
            try:
                min_salary = int(data['salary_min'])
                max_salary = int(data['salary_max'])
                if min_salary < 0 or max_salary < 0:
                    return "薪資不能為負數"
                if min_salary > max_salary:
                    return "最低薪資不能高於最高薪資"
            except (ValueError, TypeError):
                return "薪資格式不正確"
    
    # 驗證年資要求
    if 'min_experience_years' in data and data['min_experience_years']:
        try:
            years = int(data['min_experience_years'])
            if years < 0 or years > 50:
                return "年資要求必須在 0-50 年之間"
        except (ValueError, TypeError):
            return "年資格式不正確"
    
    # 驗證學歷要求
    if 'education_required' in data and data['education_required']:
        valid_education = ['高中以上', '專科以上', '大學以上', '碩士以上', '博士以上']
        if data['education_required'] not in valid_education:
            return f"學歷要求無效，可選值: {', '.join(valid_education)}"
    
    # 驗證職缺狀態
    if 'status' in data and data['status']:
        valid_status = ['active', 'paused', 'closed']
        if data['status'] not in valid_status:
            return f"職缺狀態無效，可選值: {', '.join(valid_status)}"
    
    return None

def check_team_exists(team_id: str) -> Optional[Dict[str, Any]]:
    """檢查團隊是否存在"""
    try:
        response = teams_table.get_item(Key={'team_id': team_id})
        return response.get('Item')
    except Exception as e:
        print(f"檢查團隊失敗: {str(e)}")
        return None

def create_job(data: Dict[str, Any]) -> Dict[str, Any]:
    """建立新職缺"""
    # 驗證資料
    validation_error = validate_job_data(data)
    if validation_error:
        return response(400, {'error': validation_error})
    
    # 檢查團隊是否存在
    team_data = check_team_exists(data['team_id'])
    if not team_data:
        return response(404, {'error': '指定的團隊不存在'})
    
    # 生成職缺 ID: {team_id}-{uuid}
    uuid_part = str(uuid.uuid4())[:8]
    job_id = f"{data['team_id']}-{uuid_part}"
    
    # 準備職缺資料
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    # 處理陣列欄位
    responsibilities = data.get('responsibilities', [])
    if isinstance(responsibilities, str):
        responsibilities = [responsibilities]
    
    required_skills = data.get('required_skills', [])
    if isinstance(required_skills, str):
        required_skills = [required_skills]
    
    nice_to_have_skills = data.get('nice_to_have_skills', [])
    if isinstance(nice_to_have_skills, str):
        nice_to_have_skills = [nice_to_have_skills]
    
    majors_required = data.get('majors_required', [])
    if isinstance(majors_required, str):
        majors_required = [majors_required]
    
    language_required = data.get('language_required', [])
    if isinstance(language_required, str):
        language_required = [language_required]
    
    job_data = {
        'job_id': job_id,
        'team_id': data['team_id'],
        # 基本資訊
        'title': data['job_title'],  # 修正欄位名稱為 title
        'job_title': data['job_title'],  # 保留相容性
        'employment_type': data['employment_type'],
        'location': data['location'],
        'description': data.get('description', ''),  # 新增描述欄位
        # 從團隊資料中取得公司資訊（確保使用中文名稱）
        'company': team_data.get('company', ''),
        'company_code': team_data.get('company_code', ''),
        'department': team_data.get('department', ''),
        'dept_code': team_data.get('dept_code', ''),  # 統一使用 dept_code
        'team_name': team_data.get('team_name', ''),
        'team_code': team_data.get('team_code', ''),  # 統一使用 team_code
        # 薪資資訊
        'salary_min': int(data['salary_min']) if data.get('salary_min') else None,
        'salary_max': int(data['salary_max']) if data.get('salary_max') else None,
        'salary_note': data.get('salary_note', ''),
        # 工作內容與技能
        'responsibilities': responsibilities,
        'required_skills': required_skills,
        'nice_to_have_skills': nice_to_have_skills,
        # 要求條件
        'min_experience_years': int(data['min_experience_years']) if data.get('min_experience_years') else None,
        'education_required': data.get('education_required', ''),
        'majors_required': majors_required,
        'language_required': language_required,
        # 狀態和時間戳
        'status': data.get('status', 'active'),
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        # 儲存到 DynamoDB
        jobs_table.put_item(Item=job_data)
        
        # 備份到 S3 (可選)
        if S3_BUCKET:
            backup_key = f"backups/jobs/{job_id}.json"
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=backup_key,
                Body=json.dumps(job_data, cls=DecimalEncoder, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
        
        return response(201, {
            'message': '職缺建立成功',
            'job_id': job_id,
            'data': job_data
        })
        
    except Exception as e:
        print(f"建立職缺失敗: {str(e)}")
        return response(500, {'error': '建立職缺失敗'})

def get_job(job_id: str) -> Dict[str, Any]:
    """取得單一職缺"""
    try:
        response_data = jobs_table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response_data:
            return response(404, {'error': '職缺不存在'})
        
        job_data = response_data['Item']
        return response(200, {
            'message': '職缺取得成功',
            'data': job_data
        })
        
    except Exception as e:
        print(f"取得職缺失敗: {str(e)}")
        return response(500, {'error': '取得職缺失敗'})

def list_jobs(query_params: Dict[str, str]) -> Dict[str, Any]:
    """列出職缺（支援篩選和分頁）"""
    try:
        # 解析查詢參數
        team_id = query_params.get('team_id')
        status = query_params.get('status', 'active')
        employment_type = query_params.get('employment_type')
        experience_level = query_params.get('experience_level')
        remote_option = query_params.get('remote_option')
        search = query_params.get('search', '').lower()
        
        # 分頁參數
        page = int(query_params.get('page', 1))
        limit = min(int(query_params.get('limit', 50)), 100)  # 最大 100 筆
        
        # 基礎掃描
        scan_kwargs = {}
        filter_expressions = []
        expression_values = {}
        expression_names = {}
        
        # 狀態篩選 - 只顯示啟用的職缺給求職者
        if status:
            filter_expressions.append('#status = :status')
            expression_values[':status'] = status
            expression_names['#status'] = 'status'
        
        # 團隊篩選
        if team_id:
            filter_expressions.append('team_id = :team_id')
            expression_values[':team_id'] = team_id
        
        # 就業類型篩選
        if employment_type:
            filter_expressions.append('employment_type = :employment_type')
            expression_values[':employment_type'] = employment_type
        
        # 經驗等級篩選
        if experience_level:
            filter_expressions.append('experience_level = :experience_level')
            expression_values[':experience_level'] = experience_level
        
        # 遠端選項篩選
        if remote_option:
            filter_expressions.append('remote_option = :remote_option')
            expression_values[':remote_option'] = remote_option
        
        # 建構篩選表達式
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_values
            if expression_names:
                scan_kwargs['ExpressionAttributeNames'] = expression_names
        
        # 執行掃描
        response_data = jobs_table.scan(**scan_kwargs)
        items = response_data['Items']
        
        # 文字搜尋（在記憶體中進行）
        if search:
            filtered_items = []
            for item in items:
                searchable_text = f"{item.get('job_title', '')} {item.get('title', '')} {item.get('description', '')} {item.get('company', '')} {item.get('team_name', '')} {' '.join(item.get('responsibilities', []))} {' '.join(item.get('required_skills', []))}".lower()
                if search in searchable_text:
                    filtered_items.append(item)
            items = filtered_items
        
        # 排序（按建立時間倒序）
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # 分頁
        total = len(items)
        start = (page - 1) * limit
        end = start + limit
        paginated_items = items[start:end]
        
        # 確保每個職缺都有必要的欄位給前端顯示
        for item in paginated_items:
            # 確保有 title 欄位
            if 'title' not in item and 'job_title' in item:
                item['title'] = item['job_title']
            # 確保有基本的描述
            if 'description' not in item or not item['description']:
                if 'responsibilities' in item and item['responsibilities']:
                    item['description'] = '主要職責: ' + '; '.join(item['responsibilities'][:2])
                else:
                    item['description'] = '詳細職缺資訊請洽詢人資部門'
        
        return response(200, {
            'success': True,
            'message': '職缺列表取得成功',
            'jobs': paginated_items,  # 前端期望的欄位名稱
            'data': paginated_items,   # 保留相容性
            'pagination': {
                'current_page': page,
                'total_pages': (total + limit - 1) // limit if total > 0 else 1,
                'total_items': total,
                'items_per_page': limit
            }
        })
        
    except Exception as e:
        print(f"列出職缺失敗: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return response(500, {'error': '列出職缺失敗', 'message': str(e)})

def update_job(job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """更新職缺"""
    # 驗證資料
    validation_error = validate_job_data(data, is_update=True)
    if validation_error:
        return response(400, {'error': validation_error})
    
    try:
        # 檢查職缺是否存在
        existing_response = jobs_table.get_item(Key={'job_id': job_id})
        if 'Item' not in existing_response:
            return response(404, {'error': '職缺不存在'})
        
        existing_job = existing_response['Item']
        
        # 如果要更新 team_id，檢查新團隊是否存在
        new_team_data = None
        if 'team_id' in data and data['team_id'] != existing_job['team_id']:
            new_team_data = check_team_exists(data['team_id'])
            if not new_team_data:
                return response(404, {'error': '指定的新團隊不存在'})
            print(f"更新職缺團隊，從 {existing_job['team_id']} 到 {data['team_id']}")
            print(f"新團隊資料: {new_team_data}")
        
        # 準備更新表達式
        update_expression = 'SET #updated_at = :updated_at'
        expression_names = {'#updated_at': 'updated_at'}
        expression_values = {':updated_at': datetime.utcnow().isoformat()}
        
        # 建立可更新欄位列表及其對應的屬性名稱
        updatable_fields = {
            'team_id': 'team_id',
            'job_title': 'job_title',
            'employment_type': 'employment_type',
            'location': 'location',  # 保留字
            'responsibilities': 'responsibilities',
            'required_skills': 'required_skills',
            'nice_to_have_skills': 'nice_to_have_skills',
            'salary_min': 'salary_min',
            'salary_max': 'salary_max',
            'salary_note': 'salary_note',
            'min_experience_years': 'min_experience_years',
            'education_required': 'education_required',
            'majors_required': 'majors_required',
            'language_required': 'language_required',
            'status': 'status'  # 保留字
        }
        
        # 動態建構更新表達式
        for field, attr_name in updatable_fields.items():
            if field in data:
                update_expression += f', #{attr_name} = :{field}'
                expression_names[f'#{attr_name}'] = field
                if field in ['salary_min', 'salary_max'] and data[field] is not None:
                    expression_values[f':{field}'] = int(data[field])
                else:
                    expression_values[f':{field}'] = data[field]
        
        # 如果更新了 team_id，也要更新相關的團隊資訊
        if new_team_data:
            team_fields = {
                'company': 'company',
                'company_code': 'company_code',
                'department': 'department',
                'dept_code': 'dept_code',
                'team_name': 'team_name',
                'team_code': 'team_code'
            }
            for field, attr_name in team_fields.items():
                if field in new_team_data:  # 只更新存在的欄位
                    update_expression += f', #{attr_name} = :{field}'
                    expression_names[f'#{attr_name}'] = field
                    expression_values[f':{field}'] = new_team_data[field]
        
        print(f"更新表達式: {update_expression}")
        print(f"表達式名稱: {expression_names}")
        print(f"表達式值: {expression_values}")
        
        # 執行更新
        jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values
        )
        
        # 取得更新後的資料
        updated_response = jobs_table.get_item(Key={'job_id': job_id})
        updated_job = updated_response['Item']
        
        print(f"更新後的職缺資料: {updated_job}")
        
        # 備份到 S3
        backup_key = f"backups/jobs/{job_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=backup_key,
            Body=json.dumps(updated_job, cls=DecimalEncoder, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        
        return response(200, {
            'message': '職缺更新成功',
            'data': updated_job
        })
        
    except Exception as e:
        print(f"更新職缺失敗: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return response(500, {'error': '更新職缺失敗'})

def delete_job(job_id: str) -> Dict[str, Any]:
    """刪除職缺（軟刪除）"""
    try:
        # 檢查職缺是否存在
        existing_response = jobs_table.get_item(Key={'job_id': job_id})
        if 'Item' not in existing_response:
            return response(404, {'error': '職缺不存在'})
        
        # 軟刪除：更新狀態為 deleted
        jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'deleted',
                ':updated_at': datetime.utcnow().isoformat()
            }
        )
        
        # 取得更新後的資料並備份
        updated_response = jobs_table.get_item(Key={'job_id': job_id})
        updated_job = updated_response['Item']
        
        backup_key = f"backups/jobs/{job_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=backup_key,
            Body=json.dumps(updated_job, cls=DecimalEncoder, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        
        return response(200, {'message': '職缺刪除成功'})
        
    except Exception as e:
        print(f"刪除職缺失敗: {str(e)}")
        return response(500, {'error': '刪除職缺失敗'})

def fix_existing_jobs_team_info() -> Dict[str, Any]:
    """修正現有職缺的團隊資訊，補充缺失的中文名稱"""
    try:
        # 取得所有職缺
        jobs_response = jobs_table.scan()
        jobs = jobs_response['Items']
        
        # 取得所有團隊資料
        teams_response = teams_table.scan()
        teams = {team['team_id']: team for team in teams_response['Items']}
        
        updated_count = 0
        
        for job in jobs:
            job_id = job['job_id']
            team_id = job['team_id']
            
            # 檢查是否需要更新團隊資訊
            needs_update = False
            update_data = {}
            
            if team_id in teams:
                team_data = teams[team_id]
                
                # 檢查並更新缺失的欄位
                if not job.get('company') and team_data.get('company'):
                    update_data['company'] = team_data['company']
                    needs_update = True
                
                if not job.get('department') and team_data.get('department'):
                    update_data['department'] = team_data['department']
                    needs_update = True
                
                if not job.get('team_name') and team_data.get('team_name'):
                    update_data['team_name'] = team_data['team_name']
                    needs_update = True
                
                # 補充代碼欄位
                if not job.get('company_code') and team_data.get('company_code'):
                    update_data['company_code'] = team_data['company_code']
                    needs_update = True
                
                if not job.get('dept_code') and team_data.get('dept_code'):
                    update_data['dept_code'] = team_data['dept_code']
                    needs_update = True
                
                if not job.get('team_code') and team_data.get('team_code'):
                    update_data['team_code'] = team_data['team_code']
                    needs_update = True
            
            # 如果需要更新，執行更新
            if needs_update:
                update_expression = 'SET updated_at = :updated_at'
                expression_values = {':updated_at': datetime.utcnow().isoformat()}
                
                for field, value in update_data.items():
                    update_expression += f', {field} = :{field}'
                    expression_values[f':{field}'] = value
                
                jobs_table.update_item(
                    Key={'job_id': job_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_values
                )
                
                updated_count += 1
                print(f"已更新職缺 {job_id} 的團隊資訊")
        
        return response(200, {
            'message': f'已修正 {updated_count} 個職缺的團隊資訊',
            'updated_count': updated_count
        })
        
    except Exception as e:
        print(f"修正職缺團隊資訊失敗: {str(e)}")
        return response(500, {'error': '修正職缺團隊資訊失敗'})

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
        
        # 解析請求體
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return response(400, {'error': '無效的 JSON 格式'})
        
        # 路由處理
        if method == 'POST' and path == '/jobs':
            # 建立職缺
            return create_job(body)
        
        elif method == 'GET' and path == '/jobs':
            # 列出職缺
            return list_jobs(query_params)
        
        elif method == 'GET' and path.startswith('/jobs/'):
            # 取得單一職缺
            job_id = path.split('/')[-1]
            return get_job(job_id)
        
        elif method == 'PUT' and path.startswith('/jobs/'):
            # 更新職缺
            job_id = path.split('/')[-1]
            return update_job(job_id, body)
        
        elif method == 'DELETE' and path.startswith('/jobs/'):
            # 刪除職缺
            job_id = path.split('/')[-1]
            return delete_job(job_id)
        
        elif method == 'POST' and path == '/jobs/fix-team-info':
            # 修正現有職缺的團隊資訊
            return fix_existing_jobs_team_info()
        
        else:
            return response(404, {'error': '找不到指定的路由'})
    
    except Exception as e:
        print(f"Lambda 執行錯誤: {str(e)}")
        return response(500, {'error': '伺服器內部錯誤'})
