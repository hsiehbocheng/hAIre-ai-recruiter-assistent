import os
import json
import logging
import uuid
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

# DynamoDB Table
teams_table = dynamodb.Table(TEAMS_TABLE_NAME)

def lambda_handler(event, context):
    """主要 Lambda 處理函式"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        http_method = event.get('httpMethod')
        path_parameters = event.get('pathParameters') or {}
        team_id = path_parameters.get('team_id')
        
        # 路由到對應的處理函式
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
        return error_response(500, 'Internal server error')

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
    # 驗證必要欄位（新增 company_code 和 dept_code）
    required_fields = ['company', 'company_code', 'department', 'dept_code', 'team_name']
    for field in required_fields:
        if not team_data.get(field):
            raise ValueError(f'Missing required field: {field}')
    
    # 驗證代碼格式（只允許英文數字）
    import re
    if not re.match(r'^[a-zA-Z0-9]{2,8}$', team_data['company_code']):
        raise ValueError('company_code must be 2-8 alphanumeric characters')
    if not re.match(r'^[a-zA-Z0-9]{2,10}$', team_data['dept_code']):
        raise ValueError('dept_code must be 2-10 alphanumeric characters')
    
    # 生成 team_id：公司代碼-部門代碼-時間戳
    timestamp = datetime.utcnow().strftime("%m%d%H%M")
    team_id = f"{team_data['company_code'].upper()}-{team_data['dept_code'].upper()}-{timestamp}"
    
    current_time = datetime.utcnow().isoformat() + 'Z'
    
    # 準備完整的團隊資料
    full_team_data = {
        'team_id': team_id,
        'company': team_data['company'],
        'company_code': team_data['company_code'].upper(),
        'department': team_data['department'],
        'dept_code': team_data['dept_code'].upper(),
        'team_name': team_data['team_name'],
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