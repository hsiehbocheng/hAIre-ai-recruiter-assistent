import os
import json
import logging
import uuid
import base64
from datetime import datetime
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS 服務初始化
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
s3 = boto3.client('s3', region_name='ap-southeast-1')

# 環境變數
TEAMS_TABLE_NAME = os.environ.get('TEAMS_TABLE_NAME', 'benson-haire-teams')
BACKUP_S3_BUCKET = os.environ.get('BACKUP_S3_BUCKET', '')
TEAM_INFO_BUCKET = 'benson-haire-team-info-e36d5aee'

# DynamoDB Table
teams_table = dynamodb.Table(TEAMS_TABLE_NAME)

def lambda_handler(event, context):
    """主要 Lambda 處理函式"""
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        http_method = event.get('httpMethod')
        path = event.get('path', '')
        path_parameters = event.get('pathParameters') or {}
        
        # 處理 CORS preflight 請求
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # 文件管理路由
        if '/upload-team-file' in path:
            return handle_file_upload(event)
        elif '/team-files/' in path:
            team_id = path_parameters.get('team_id')
            return handle_list_files(team_id)
        elif '/download-team-file/' in path:
            file_key = path_parameters.get('file_key')
            return handle_file_download(file_key)
        elif '/delete-team-file' in path:
            return handle_file_delete(event)
        
        # 原有的團隊管理路由
        team_id = path_parameters.get('team_id')
        
        if http_method == 'GET':
            if team_id:
                result = get_team(team_id)
            else:
                result = list_teams()
        elif http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            result = create_team(body)
        elif http_method == 'PUT':
            if not team_id:
                return error_response(400, 'team_id is required for UPDATE')
            body = json.loads(event.get('body', '{}'))
            result = update_team(team_id, body)
        elif http_method == 'DELETE':
            if not team_id:
                return error_response(400, 'team_id is required for DELETE')
            result = delete_team(team_id)
        else:
            return error_response(405, f'Method {http_method} not allowed')
            
        return success_response(result)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return error_response(400, 'Invalid JSON format')
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

def get_team(team_id: str) -> Dict[str, Any]:
    """取得單一團隊資訊"""
    try:
        response = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' not in response:
            raise ValueError(f'Team {team_id} not found')
        return response['Item']
    except ClientError as e:
        logger.error(f"DynamoDB error in get_team: {str(e)}")
        raise

def list_teams() -> Dict[str, Any]:
    """取得所有團隊列表"""
    try:
        response = teams_table.scan()
        return {
            'teams': response.get('Items', []),
            'count': len(response.get('Items', []))
        }
    except ClientError as e:
        logger.error(f"DynamoDB error in list_teams: {str(e)}")
        raise

def create_team(team_data: Dict[str, Any]) -> Dict[str, Any]:
    """新增團隊"""
    # 驗證必要欄位（新增 team_code）
    required_fields = ['company', 'company_code', 'department', 'dept_code', 'team_name', 'team_code']
    for field in required_fields:
        if not team_data.get(field):
            raise ValueError(f'Missing required field: {field}')
    
    # 驗證代碼格式
    import re
    if not re.match(r'^[a-zA-Z0-9]{2,8}$', team_data['company_code']):
        raise ValueError('company_code must be 2-8 alphanumeric characters')
    if not re.match(r'^[a-zA-Z0-9]{2,10}$', team_data['dept_code']):
        raise ValueError('dept_code must be 2-10 alphanumeric characters')
    if not re.match(r'^[a-zA-Z0-9]{2,8}$', team_data['team_code']):
        raise ValueError('team_code must be 2-8 alphanumeric characters')
    
    # 生成 team_id：公司代碼-部門代碼-科別代碼 (移除時間戳)
    team_id = f"{team_data['company_code'].upper()}-{team_data['dept_code'].upper()}-{team_data['team_code'].upper()}"
    
    # 檢查 team_id 是否已存在
    try:
        existing_team = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' in existing_team:
            raise ValueError(f'Team ID {team_id} already exists')
    except ClientError:
        pass  # 如果查詢失敗，可能是因為團隊不存在，這是正常的
    
    current_time = datetime.utcnow().isoformat() + 'Z'
    
    full_team_data = {
        'team_id': team_id,
        'company': team_data['company'],
        'company_code': team_data['company_code'].upper(),
        'department': team_data['department'],
        'dept_code': team_data['dept_code'].upper(),
        'team_name': team_data['team_name'],
        'team_code': team_data['team_code'].upper(),
        'team_description': team_data.get('team_description', ''),
        'created_at': current_time,
        'updated_at': current_time
    }
    try:
        # 寫入 DynamoDB
        teams_table.put_item(Item=full_team_data)
        logger.info(f"Created team in DynamoDB: {team_id}")
        
        # 備份到 S3
        if BACKUP_S3_BUCKET:
            backup_to_s3(team_id, full_team_data)
        
        return full_team_data
        
    except ClientError as e:
        logger.error(f"DynamoDB error in create_team: {str(e)}")
        raise

def update_team(team_id: str, team_data: Dict[str, Any]) -> Dict[str, Any]:
    """更新團隊資訊"""
    # 先檢查團隊是否存在
    existing_team = get_team(team_id)
    
    # 準備更新資料
    current_time = datetime.utcnow().isoformat() + 'Z'
    
    # 只更新提供的欄位
    update_expression = "SET updated_at = :updated_at"
    expression_values = {':updated_at': current_time}
    
    updateable_fields = ['company', 'department', 'team_name', 'team_description']
    for field in updateable_fields:
        if field in team_data:
            update_expression += f", {field} = :{field}"
            expression_values[f':{field}'] = team_data[field]
    
    try:
        # 更新 DynamoDB
        response = teams_table.update_item(
            Key={'team_id': team_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )
        
        updated_team = response['Attributes']
        logger.info(f"Updated team in DynamoDB: {team_id}")
        
        # 備份到 S3
        if BACKUP_S3_BUCKET:
            backup_to_s3(team_id, updated_team)
        
        return updated_team
        
    except ClientError as e:
        logger.error(f"DynamoDB error in update_team: {str(e)}")
        raise

def delete_team(team_id: str) -> Dict[str, Any]:
    """刪除團隊"""
    # 先檢查團隊是否存在
    existing_team = get_team(team_id)
    
    try:
        # 從 DynamoDB 刪除
        teams_table.delete_item(Key={'team_id': team_id})
        logger.info(f"Deleted team from DynamoDB: {team_id}")
        
        return {'message': f'Team {team_id} deleted successfully'}
        
    except ClientError as e:
        logger.error(f"DynamoDB error in delete_team: {str(e)}")
        raise

def generate_team_id(team_data: Dict[str, Any]) -> str:
    """生成團隊 ID"""
    # 基於公司和部門生成友善的 ID
    company = team_data['company'].lower().replace(' ', '').replace('股份有限公司', '').replace('有限公司', '')
    department = team_data['department'].lower().replace(' ', '').replace('部', '').replace('科', '')
    
    # 簡化中文轉換（可以後續改善）
    company_short = company[:3] if len(company) > 3 else company
    dept_short = department[:5] if len(department) > 5 else department
    
    # 加上短 UUID 避免衝突
    short_uuid = str(uuid.uuid4())[:8]
    
    return f"{company_short}-{dept_short}-{short_uuid}"

def backup_to_s3(team_id: str, team_data: Dict[str, Any]) -> None:
    """備份團隊資料到 S3"""
    try:
        s3_key = f"teams/{team_id}.json"
        s3.put_object(
            Bucket=BACKUP_S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(team_data, ensure_ascii=False).encode('utf-8'),
            ContentType='application/json; charset=utf-8'
        )
        logger.info(f"Backed up team to S3: {s3_key}")
    except ClientError as e:
        logger.error(f"S3 backup error: {str(e)}")
        # S3 備份失敗不影響主流程，只記錄錯誤

def success_response(data: Any) -> Dict[str, Any]:
    """成功回應格式"""
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps(data, ensure_ascii=False)
    }

def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """錯誤回應格式"""
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'error': message,
            'statusCode': status_code
        }, ensure_ascii=False)
    }

def get_cors_headers() -> Dict[str, str]:
    """CORS 標頭"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Content-Type': 'application/json; charset=utf-8'
    }

def handle_file_upload(event: Dict[str, Any]) -> Dict[str, Any]:
    """處理文件上傳"""
    try:
        logger.info("處理文件上傳請求")
        
        # 從查詢參數取得 teamId (因為 FormData 中的參數可能不容易解析)
        query_params = event.get('queryStringParameters') or {}
        team_id = query_params.get('teamId', '')
        
        if not team_id:
            return error_response(400, '缺少 teamId 參數')
        
        # 解析 multipart/form-data (簡化版本)
        content_type = event.get('headers', {}).get('content-type', '') or event.get('headers', {}).get('Content-Type', '')
        
        if 'multipart/form-data' not in content_type:
            return error_response(400, '需要 multipart/form-data 格式')
        
        # 模擬文件上傳 (實際環境中需要完整的 multipart 解析)
        current_time = datetime.utcnow().isoformat()
        file_key = f"team_docs/{team_id}-example_document_{current_time}.txt"
        
        # 模擬上傳到 S3
        logger.info(f"模擬上傳文件到 S3: {file_key}")
        
        # 在實際環境中，這裡會解析 multipart 數據並上傳到 S3：
        # s3.put_object(
        #     Bucket=TEAM_INFO_BUCKET,
        #     Key=file_key,
        #     Body=file_content,
        #     ContentType=file_content_type
        # )
        
        return success_response({
            'success': True,
            'message': '文件上傳成功 (模擬)',
            'key': file_key,
            'bucket': TEAM_INFO_BUCKET,
            'uploaded_at': current_time
        })
        
    except Exception as e:
        logger.error(f"文件上傳失敗: {str(e)}")
        return error_response(500, f'文件上傳失敗: {str(e)}')

def handle_list_files(team_id: str) -> Dict[str, Any]:
    """列出團隊文件"""
    try:
        if not team_id:
            return error_response(400, '缺少團隊 ID')
        
        logger.info(f"列出團隊文件: {team_id}")
        
        prefix = f'team_docs/{team_id}-'
        
        # 列出 S3 文件
        response = s3.list_objects_v2(
            Bucket=TEAM_INFO_BUCKET,
            Prefix=prefix
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                files.append({
                    'key': obj['Key'],
                    'name': obj['Key'].replace(prefix, ''),
                    'size': obj['Size'],
                    'lastModified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"')
                })
        
        logger.info(f"找到 {len(files)} 個文件")
        
        return success_response({
            'files': files,
            'count': len(files),
            'team_id': team_id
        })
        
    except Exception as e:
        logger.error(f"列出文件失敗: {str(e)}")
        return error_response(500, f'列出文件失敗: {str(e)}')

def handle_file_download(file_key: str) -> Dict[str, Any]:
    """處理文件下載"""
    try:
        if not file_key:
            return error_response(400, '缺少文件 key')
        
        logger.info(f"下載文件: {file_key}")
        
        # 生成預簽名 URL 用於下載
        download_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': TEAM_INFO_BUCKET, 'Key': file_key},
            ExpiresIn=3600  # 1小時有效期
        )
        
        logger.info("生成下載 URL 成功")
        
        return success_response({
            'downloadUrl': download_url,
            'expiresIn': 3600,
            'key': file_key
        })
        
    except Exception as e:
        logger.error(f"文件下載失敗: {str(e)}")
        return error_response(500, f'文件下載失敗: {str(e)}')

def handle_file_delete(event: Dict[str, Any]) -> Dict[str, Any]:
    """處理文件刪除"""
    try:
        # 解析請求體
        body = json.loads(event.get('body', '{}'))
        file_key = body.get('key', '')
        bucket_name = body.get('bucket', TEAM_INFO_BUCKET)
        
        if not file_key:
            return error_response(400, '缺少文件 key')
        
        logger.info(f"刪除文件: {file_key}")
        
        # 刪除 S3 文件
        s3.delete_object(
            Bucket=bucket_name,
            Key=file_key
        )
        
        logger.info("文件刪除成功")
        
        return success_response({
            'success': True,
            'message': '文件刪除成功',
            'key': file_key,
            'deleted_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"文件刪除失敗: {str(e)}")
        return error_response(500, f'文件刪除失敗: {str(e)}')