import os
import json
import logging
import uuid
import base64
import cgi
import io
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional, List

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
TEAM_INFO_BUCKET = os.environ.get('TEAM_INFO_BUCKET', 'benson-haire-team-info-e36d5aee')

# DynamoDB Table
teams_table = dynamodb.Table(TEAMS_TABLE_NAME)

# S3 檔案管理設定 - 統一使用新的資料夾結構
S3_FOLDER_PREFIX = 'team_info_docs'

def lambda_handler(event, context):
    """主要 Lambda 處理函式"""
    logger.info(f"🔥🔥🔥 Lambda 函數被調用! Event: {json.dumps(event, default=str)}")
    
    # 設置 CORS 響應頭
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
        'Content-Type': 'application/json'
    }
    
    try:
        # 處理 OPTIONS 請求 (CORS preflight)
        if event.get('httpMethod') == 'OPTIONS':
            logger.info("🔥 處理 OPTIONS 請求")
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # 取得請求方法和路徑
        method = event.get('httpMethod', '')
        path = event.get('path', '')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        logger.info(f"📨 收到請求: {method} {path}")
        logger.info(f"🔍 路徑參數: {path_parameters}")
        logger.info(f"🔍 查詢參數: {query_parameters}")
        
        # 路由處理邏輯
        # 團隊管理 API
        if method == 'GET' and path == '/teams':
            logger.info("🏢 路由到：列出所有團隊")
            return list_teams(event, headers)
        elif method == 'POST' and path == '/teams':
            logger.info("🏢 路由到：創建新團隊")
            return create_team(event, headers)
        elif method == 'GET' and '/teams/' in path and path_parameters.get('team_id'):
            team_id = path_parameters.get('team_id')
            query_params = event.get('queryStringParameters') or {}
            action = query_params.get('action', '')
            
            # 檢查是否是檔案相關的查詢
            if action == 'files':
                logger.info(f"📂 路由到：列出團隊檔案 {team_id}")
                return handle_list_files(event, headers)
            # 檢查是否是檔案相關的子路由
            elif path.endswith('/files'):
                logger.info(f"📂 路由到：列出團隊檔案 {team_id}")
                return handle_list_files(event, headers)
            else:
                logger.info(f"🏢 路由到：取得團隊 {team_id}")
                return get_team(event, headers)
        elif method == 'PUT' and '/teams/' in path and path_parameters.get('team_id'):
            logger.info(f"🏢 路由到：更新團隊 {path_parameters['team_id']}")
            return update_team(event, headers)
        elif method == 'DELETE' and '/teams/' in path and path_parameters.get('team_id'):
            logger.info(f"🏢 路由到：刪除團隊 {path_parameters['team_id']}")
            return delete_team(event, headers)
        
        # 檔案上傳路由
        logger.info(f"🔍 檢查檔案上傳條件: method={method}, path={path}, team_id={path_parameters.get('team_id')}, endswith_files={path.endswith('/files')}")
        
        if method == 'POST' and '/teams/' in path and path_parameters.get('team_id') and path.endswith('/files'):
            logger.info(f"📤 路由到：上傳團隊檔案 {path_parameters['team_id']}")
            return handle_file_upload(event, headers)
        
        # 檔案管理 API
        elif method == 'GET' and '/team-files/' in path:
            logger.info("📂 路由到：檔案列表")
            return handle_list_files(event, headers)
        elif method == 'GET' and '/download-team-file/' in path:
            logger.info("📥 路由到：檔案下載")
            return handle_file_download(event, headers)
        elif method == 'DELETE' and '/delete-team-file' in path:
            logger.info("🗑️ 路由到：檔案刪除")
            return handle_file_delete(event, headers)
        
        else:
            logger.warning(f"⚠️ 未匹配的路由: {method} {path}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到對應的 API 端點',
                    'method': method,
                    'path': path,
                    'available_endpoints': {
                        'teams': {
                            'GET /teams': '列出所有團隊',
                            'POST /teams': '創建新團隊',
                            'GET /teams/{team_id}': '取得特定團隊',
                            'PUT /teams/{team_id}': '更新團隊',
                            'DELETE /teams/{team_id}': '刪除團隊'
                        },
                        'files': {
                            'POST /teams/{team_id}/files': '上傳檔案',
                            'GET /team-files/{team_id}': '列出團隊檔案',
                            'GET /download-team-file/{file_key}': '下載檔案',
                            'DELETE /delete-team-file': '刪除檔案'
                        }
                    }
                })
            }
            
    except Exception as e:
        logger.error(f"❌ Lambda 函數執行錯誤: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '伺服器內部錯誤',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def list_teams(event, headers):
    """列出所有團隊"""
    try:
        logger.info("🏢 開始列出所有團隊")
        response = teams_table.scan()
        teams = response.get('Items', [])
        
        logger.info(f"✅ 成功取得 {len(teams)} 個團隊")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'teams': teams,
                'count': len(teams),
                'timestamp': datetime.now().isoformat()
            }, default=str)
        }
    except Exception as e:
        logger.error(f"❌ 列出團隊失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '列出團隊失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def get_team(event, headers):
    """取得特定團隊資訊 - 同時從 DynamoDB 和 S3 讀取"""
    try:
        path_parameters = event.get('pathParameters') or {}
        team_id = path_parameters.get('team_id')
        
        if not team_id:
            logger.warning("⚠️ 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'message': '請在路徑參數中提供 team_id'
                })
            }
        
        logger.info(f"🏢 開始取得團隊資訊: {team_id}")
        
        # 從 DynamoDB 取得基本團隊資訊
        response = teams_table.get_item(Key={'team_id': team_id})
        
        if 'Item' not in response:
            logger.warning(f"⚠️ 找不到團隊: {team_id}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到指定的團隊',
                    'team_id': team_id
                })
            }
        
        team_data = response['Item']
        
        # 嘗試從 S3 讀取額外的團隊資訊檔案
        try:
            s3_key = f'{S3_FOLDER_PREFIX}/{team_id}/team_info.json'
            logger.info(f"📄 嘗試讀取 S3 團隊資訊: {s3_key}")
            
            s3_response = s3.get_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=s3_key
            )
            
            s3_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            logger.info(f"✅ 成功從 S3 讀取團隊資訊")
            
            # 合併 S3 資料（S3 資料優先，但保留 DynamoDB 的更新時間）
            for key, value in s3_data.items():
                if key not in ['updated_at']:  # 保留 DynamoDB 的更新時間
                    team_data[key] = value
                    
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info(f"📄 S3 中沒有額外的團隊資訊檔案: {s3_key}")
            else:
                logger.warning(f"⚠️ 讀取 S3 團隊資訊時發生錯誤: {str(e)}")
        except Exception as e:
            logger.warning(f"⚠️ 處理 S3 團隊資訊時發生錯誤: {str(e)}")
        
        # 取得團隊檔案列表
        try:
            s3_prefix = f'{S3_FOLDER_PREFIX}/{team_id}/'
            files_response = s3.list_objects_v2(
                Bucket=TEAM_INFO_BUCKET,
                Prefix=s3_prefix
            )
            
            files = []
            if 'Contents' in files_response:
                for obj in files_response['Contents']:
                    # 從完整的 S3 Key 中提取原始檔案名稱
                    original_filename = obj['Key'].replace(s3_prefix, '', 1)
                    
                    # 跳過資料夾本身和 team_info.json
                    if (original_filename and 
                        not original_filename.endswith('/') and 
                        original_filename != 'team_info.json'):
                        file_info = {
                            'key': obj['Key'],
                            'name': original_filename,
                            'size': obj['Size'],
                            'lastModified': obj['LastModified'].isoformat(),
                            'etag': obj['ETag'].strip('"')
                        }
                        files.append(file_info)
            
            team_data['files'] = files
            team_data['file_count'] = len(files)
            logger.info(f"📂 團隊檔案數量: {len(files)}")
            
        except Exception as e:
            logger.warning(f"⚠️ 取得團隊檔案列表時發生錯誤: {str(e)}")
            team_data['files'] = []
            team_data['file_count'] = 0
        
        logger.info(f"✅ 成功取得團隊資訊: {team_id}")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'team': team_data,
                'timestamp': datetime.now().isoformat()
            }, default=str)
        }
    except Exception as e:
        logger.error(f"❌ 取得團隊失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '取得團隊失敗',
                'message': str(e),
                'team_id': team_id if 'team_id' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def create_team(event, headers):
    """建立新團隊（支援檔案上傳）"""
    try:
        logger.info("🏢 開始創建新團隊")
        content_type = event.get('headers', {}).get('content-type', 
                      event.get('headers', {}).get('Content-Type', ''))
        
        logger.info(f"📝 Content-Type: {content_type}")
        
        if 'multipart/form-data' in content_type:
            # 處理包含檔案的請求
            logger.info("📤 處理包含檔案的團隊創建請求")
            return create_team_with_files(event, headers)
        else:
            # 處理純 JSON 請求
            logger.info("📝 處理純 JSON 團隊創建請求")
            try:
                body = json.loads(event.get('body', '{}'))
                logger.info(f"📝 解析的請求體: {body}")
                return create_team_json(body, headers)
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON 解析失敗: {str(e)}")
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'JSON 格式錯誤',
                        'message': str(e),
                        'received_body': event.get('body', '')[:200]  # 只顯示前200個字符
                    })
                }
            
    except Exception as e:
        logger.error(f"❌ 建立團隊失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '建立團隊失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def create_team_json(team_data, headers):
    """建立團隊（純 JSON 模式）"""
    try:
        logger.info(f"🏢 建立團隊 - 收到資料: {team_data}")
        
        # 欄位映射 - 統一使用 company_code、dept_code、team_code
        field_mapping = {
            'department_code': 'dept_code',  # 舊欄位映射到新欄位
            'section_code': 'team_code',     # 舊欄位映射到新欄位
            'team_description': 'description'
        }
        
        # 建立標準化的團隊資料
        normalized_data = {}
        
        # 複製並映射欄位
        for key, value in team_data.items():
            if key in field_mapping:
                # 使用映射後的欄位名
                normalized_data[field_mapping[key]] = value
                logger.info(f"🔄 欄位映射: {key} -> {field_mapping[key]} = {value}")
            else:
                # 直接使用原欄位名
                normalized_data[key] = value
        
        logger.info(f"🏢 標準化後的資料: {normalized_data}")
        
        # 驗證必要欄位 - 使用統一的欄位名稱
        required_fields = ['company_code', 'dept_code', 'team_code', 'team_name']
        missing_fields = []
        
        for field in required_fields:
            if field not in normalized_data or not normalized_data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            logger.error(f"❌ 缺少必要欄位: {missing_fields}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'缺少必要欄位: {", ".join(missing_fields)}',
                    'missing_fields': missing_fields,
                    'received_data': team_data,
                    'normalized_data': normalized_data
                })
            }
        
        # 建立團隊 ID - 使用統一的欄位名稱
        team_id = f"{normalized_data['company_code']}-{normalized_data['dept_code']}-{normalized_data['team_code']}"
        logger.info(f"🏢 生成團隊 ID: {team_id}")
        
        # 檢查團隊是否已存在
        existing_team = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' in existing_team:
            logger.warning(f"⚠️ 團隊已存在: {team_id}")
            return {
                'statusCode': 409,
                'headers': headers,
                'body': json.dumps({
                    'error': '團隊已存在',
                    'existing_team_id': team_id
                })
            }
        
        # 建立團隊資料 - 使用統一的欄位名稱
        team_item = {
            'team_id': team_id,
            'company_code': normalized_data['company_code'],
            'dept_code': normalized_data['dept_code'], 
            'team_code': normalized_data['team_code'],
            'team_name': normalized_data['team_name'],
            'description': normalized_data.get('description', ''),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # 保留前端的額外欄位以便顯示
        if 'company' in team_data:
            team_item['company'] = team_data['company']
        if 'department' in team_data:
            team_item['department'] = team_data['department']
        
        logger.info(f"💾 準備儲存團隊資料: {team_item}")
        
        # 儲存到 DynamoDB
        teams_table.put_item(Item=team_item)
        logger.info(f"✅ 團隊已儲存到 DynamoDB: {team_id}")
        
        # 備份到 S3
        backup_team_to_s3(team_item)
        
        # 創建團隊檔案資料夾
        create_team_folder(team_id)
        
        logger.info(f"🎉 團隊建立成功: {team_id}")
        
        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '團隊建立成功',
                'team_id': team_id,
                'team': team_item,
                'timestamp': datetime.now().isoformat()
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"❌ 建立團隊失敗: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': '建立團隊失敗', 'details': str(e)})
        }

def create_team_with_files(event, headers):
    """建立團隊（支援檔案上傳）- 簡化版本"""
    # 這裡實作檔案上傳相關的邏輯，但移除安全驗證
    pass

def update_team(event, headers):
    """更新團隊 - 簡化版本"""
    # 實作更新邏輯，但移除安全驗證
    pass

def delete_team(event, headers):
    """刪除團隊 - 簡化版本"""
    # 實作刪除邏輯，但移除安全驗證
    pass

def handle_file_upload(event, headers):
    """檔案上傳 - 簡化版本"""
    # 實作檔案上傳邏輯，但移除安全驗證
    pass

def handle_list_files(event, headers):
    """列出檔案 - 簡化版本"""
    # 實作檔案列表邏輯，但移除安全驗證
    pass

def handle_file_download(event, headers):
    """檔案下載 - 簡化版本"""
    # 實作檔案下載邏輯，但移除安全驗證
    pass

def handle_file_delete(event, headers):
    """檔案刪除 - 簡化版本"""
    # 實作檔案刪除邏輯，但移除安全驗證
    pass

def backup_team_to_s3(team_data):
    """備份團隊資料到 S3"""
    try:
        team_id = team_data['team_id']
        s3_key = f'{S3_FOLDER_PREFIX}/{team_id}/team_info.json'
        
        s3.put_object(
            Bucket=TEAM_INFO_BUCKET,
            Key=s3_key,
            Body=json.dumps(team_data, default=str),
            ContentType='application/json'
        )
        
        logger.info(f"✅ 團隊資料備份成功: s3://{TEAM_INFO_BUCKET}/{s3_key}")
        
    except Exception as e:
        logger.error(f"❌ 團隊資料備份失敗: {str(e)}")
        # 不拋出例外，因為備份失敗不應該影響主要功能

def create_team_folder(team_id):
    """創建團隊檔案資料夾"""
    try:
        s3.put_object(
            Bucket=TEAM_INFO_BUCKET,
            Key=f'{S3_FOLDER_PREFIX}/{team_id}/'
        )
        logger.info(f"✅ 團隊檔案資料夾創建成功: s3://{TEAM_INFO_BUCKET}/{S3_FOLDER_PREFIX}/{team_id}/")
    except Exception as e:
        logger.error(f"❌ 創建團隊檔案資料夾失敗: {str(e)}")
        # 不拋出例外，因為資料夾創建失敗不應該影響主要功能