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

# 統一的 CORS headers
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token, X-Requested-With',
    'Access-Control-Expose-Headers': 'Content-Disposition',
    'Content-Type': 'application/json'
}

def lambda_handler(event, context):
    """主要 Lambda 處理函式"""
    logger.info(f"?????? Lambda 函數被調用! Event: {json.dumps(event, default=str)}")
    
    try:
        # 特殊調試：檢查 event body 的內容
        event_body = event.get('body', '')
        logger.info(f"?? 調試 - Event body type: {type(event_body)}")
        logger.info(f"?? 調試 - Event body length: {len(event_body) if event_body else 0}")
        logger.info(f"?? 調試 - Event body preview: '{event_body[:100]}...' (前100字符)")
        logger.info(f"?? 調試 - isBase64Encoded: {event.get('isBase64Encoded', False)}")
        
        # 檢查是否包含 JSON 解析錯誤的關鍵字
        if event_body and ('Expecting value: line 1 column 1' in str(event_body) or event_body.strip() == ''):
            logger.warning(f"?? 檢測到可能導致 JSON 錯誤的請求體")
        
    except Exception as debug_e:
        logger.warning(f"?? 調試檢查失敗: {str(debug_e)}")
    
    try:
        # 處理 OPTIONS 請求 (CORS preflight)
        if event.get('httpMethod') == 'OPTIONS':
            logger.info("?? 處理 OPTIONS 請求")
            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # 取得請求方法和路徑
        method = event.get('httpMethod', '')
        path = event.get('path', '')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        logger.info(f"?? 收到請求: {method} {path}")
        logger.info(f"?? 路徑參數: {path_parameters}")
        logger.info(f"?? 查詢參數: {query_parameters}")
        
        # 路由處理邏輯
        # 團隊管理 API
        if method == 'GET' and path == '/teams':
            logger.info("?? 路由到：列出所有團隊")
            return list_teams(event, CORS_HEADERS)
        elif method == 'POST' and path == '/teams':
            logger.info("?? 路由到：創建新團隊")
            return create_team(event, CORS_HEADERS)
        elif method == 'GET' and '/teams/' in path and path_parameters.get('team_id'):
            team_id = path_parameters.get('team_id')
            query_params = event.get('queryStringParameters') or {}
            action = query_params.get('action', '')
            
            # 檢查是否是檔案相關的查詢
            if action == 'files':
                logger.info(f"?? 路由到：列出團隊檔案 {team_id}")
                return handle_list_files(event, CORS_HEADERS)
            # 檢查是否是檔案相關的子路由
            elif path.endswith('/files'):
                logger.info(f"?? 路由到：列出團隊檔案 {team_id}")
                return handle_list_files(event, CORS_HEADERS)
            else:
                logger.info(f"?? 路由到：取得團隊 {team_id}")
                return get_team(event, CORS_HEADERS)
        elif method == 'PUT' and '/teams/' in path and path_parameters.get('team_id'):
            logger.info(f"?? 路由到：更新團隊 {path_parameters['team_id']}")
            return update_team(event, CORS_HEADERS)
        elif method == 'DELETE' and '/teams/' in path and path_parameters.get('team_id'):
            logger.info(f"?? 路由到：刪除團隊 {path_parameters['team_id']}")
            return delete_team(event, CORS_HEADERS)
        
        # 檔案上傳路由
        logger.info(f"?? 檢查檔案上傳條件: method={method}, path={path}, team_id={path_parameters.get('team_id')}, endswith_files={path.endswith('/files')}")
        
        if method == 'POST' and '/teams/' in path and path_parameters.get('team_id') and path.endswith('/files'):
            logger.info(f"?? 路由到：上傳團隊檔案 {path_parameters['team_id']}")
            return handle_file_upload(event, CORS_HEADERS)
        
        # 檔案管理 API
        elif method == 'GET' and '/team-files/' in path:
            logger.info("?? 路由到：檔案列表")
            return handle_list_files(event, CORS_HEADERS)
        elif method == 'GET' and '/download-team-file/' in path:
            logger.info("?? 路由到：檔案下載")
            return handle_file_download(event, CORS_HEADERS)
        elif method == 'DELETE' and '/delete-team-file' in path:
            logger.info("??? 路由到：檔案刪除")
            return handle_file_delete(event, CORS_HEADERS)
        
        else:
            logger.warning(f"?? 未匹配的路由: {method} {path}")
            return {
                'statusCode': 404,
                'headers': CORS_HEADERS,
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
            
    except json.JSONDecodeError as json_e:
        logger.error(f"? JSON 解析錯誤: {str(json_e)}")
        logger.error(f"? 錯誤位置: line {json_e.lineno}, column {json_e.colno}")
        logger.error(f"? 錯誤文檔: '{json_e.doc[:200]}...' (前200字符)")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': 'JSON 格式錯誤',
                'message': str(json_e),
                'line': json_e.lineno,
                'column': json_e.colno,
                'problematic_content': json_e.doc[:200] if hasattr(json_e, 'doc') else '',
                'timestamp': datetime.now().isoformat()
            })
        }
    except Exception as e:
        logger.error(f"? Lambda 函數執行錯誤: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': '伺服器內部錯誤',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def list_teams(event, headers):
    """列出所有團隊"""
    try:
        logger.info("?? 開始列出所有團隊")
        response = teams_table.scan()
        teams = response.get('Items', [])
        
        logger.info(f"? 成功取得 {len(teams)} 個團隊")
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
        logger.error(f"? 列出團隊失敗: {str(e)}")
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
            logger.warning("?? 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'message': '請在路徑參數中提供 team_id'
                })
            }
        
        logger.info(f"?? 開始取得團隊資訊: {team_id}")
        
        # 從 DynamoDB 取得基本團隊資訊
        response = teams_table.get_item(Key={'team_id': team_id})
        
        if 'Item' not in response:
            logger.warning(f"?? 找不到團隊: {team_id}")
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
            logger.info(f"?? 嘗試讀取 S3 團隊資訊: {s3_key}")
            
            s3_response = s3.get_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=s3_key
            )
            
            s3_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            logger.info(f"? 成功從 S3 讀取團隊資訊")
            
            # 合併 S3 資料（S3 資料優先，但保留 DynamoDB 的更新時間）
            for key, value in s3_data.items():
                if key not in ['updated_at']:  # 保留 DynamoDB 的更新時間
                    team_data[key] = value
                    
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info(f"?? S3 中沒有額外的團隊資訊檔案: {s3_key}")
            else:
                logger.warning(f"?? 讀取 S3 團隊資訊時發生錯誤: {str(e)}")
        except Exception as e:
            logger.warning(f"?? 處理 S3 團隊資訊時發生錯誤: {str(e)}")
        
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
                    
                    # 跳過資料夾本身，但保留所有檔案
                    if (original_filename and 
                        not original_filename.endswith('/')):
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
            logger.info(f"?? 團隊檔案數量: {len(files)}")
            
        except Exception as e:
            logger.warning(f"?? 取得團隊檔案列表時發生錯誤: {str(e)}")
            team_data['files'] = []
            team_data['file_count'] = 0
        
        logger.info(f"? 成功取得團隊資訊: {team_id}")
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
        logger.error(f"? 取得團隊失敗: {str(e)}")
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
        logger.info("?? 開始創建新團隊")
        headers_dict = event.get('headers', {})
        content_type = (
            headers_dict.get('Content-Type', '') or
            headers_dict.get('content-type', '') or
            headers_dict.get('Content-type', '') or
            headers_dict.get('CONTENT-TYPE', '')
        ).lower()
        
        logger.info(f"?? Content-Type: {content_type}")
        logger.info(f"?? 所有 headers: {headers_dict}")
        
        if 'multipart/form-data' in content_type:
            # 處理包含檔案的請求
            logger.info("?? 處理包含檔案的團隊創建請求")
            return create_team_with_files(event, headers)
        else:
            # 處理純 JSON 請求
            logger.info("?? 處理純 JSON 團隊創建請求")
            try:
                body_str = event.get('body', '{}')
                logger.info(f"?? 原始請求體: '{body_str[:100]}...' (前100字符)")
                
                if not body_str or body_str.strip() == '':
                    logger.warning("?? 請求體為空，使用預設值")
                    body = {}
                else:
                    body = json.loads(body_str)
                    logger.info(f"?? 成功解析請求體: {body}")
                
                return create_team_json(body, headers)
            except json.JSONDecodeError as e:
                logger.error(f"? JSON 解析失敗: {str(e)}")
                logger.error(f"? 問題內容: '{event.get('body', '')[:200]}...' (前200字符)")
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'JSON 格式錯誤',
                        'message': str(e),
                        'received_body': event.get('body', '')[:200],  # 只顯示前200個字符
                        'content_type': content_type
                    })
                }
            
    except Exception as e:
        logger.error(f"? 建立團隊失敗: {str(e)}")
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
        logger.info(f"?? 建立團隊 - 收到資料: {team_data}")
        
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
                logger.info(f"?? 欄位映射: {key} -> {field_mapping[key]} = {value}")
            else:
                # 直接使用原欄位名
                normalized_data[key] = value
        
        logger.info(f"?? 標準化後的資料: {normalized_data}")
        
        # 驗證必要欄位 - 使用統一的欄位名稱
        required_fields = ['company_code', 'dept_code', 'team_code', 'team_name']
        missing_fields = []
        
        for field in required_fields:
            if field not in normalized_data or not normalized_data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            logger.error(f"? 缺少必要欄位: {missing_fields}")
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
        logger.info(f"?? 生成團隊 ID: {team_id}")
        
        # 檢查團隊是否已存在
        existing_team = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' in existing_team:
            logger.warning(f"?? 團隊已存在: {team_id}")
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
        
        logger.info(f"?? 準備儲存團隊資料: {team_item}")
        
        # 儲存到 DynamoDB
        teams_table.put_item(Item=team_item)
        logger.info(f"? 團隊已儲存到 DynamoDB: {team_id}")
        
        # 備份到 S3
        backup_team_to_s3(team_item)
        
        # 創建團隊檔案資料夾
        create_team_folder(team_id)
        
        logger.info(f"?? 團隊建立成功: {team_id}")
        
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
        logger.error(f"? 建立團隊失敗: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': '建立團隊失敗', 'details': str(e)})
        }

def create_team_with_files(event, headers):
    """建立團隊（支援檔案上傳）"""
    try:
        logger.info("?? 開始處理包含檔案的團隊創建請求")
        
        # 調試：記錄完整的事件資訊
        logger.info(f"?? 調試 - Event headers: {event.get('headers', {})}")
        logger.info(f"?? 調試 - isBase64Encoded: {event.get('isBase64Encoded', False)}")
        
        # 解析 multipart/form-data
        content_type = event.get('headers', {}).get('content-type', 
                      event.get('headers', {}).get('Content-Type', ''))
        logger.info(f"?? 調試 - Content-Type: '{content_type}'")
        
        if not content_type or 'multipart/form-data' not in content_type:
            logger.error("? 不支援的內容類型")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '不支援的內容類型',
                    'message': '請使用 multipart/form-data 格式上傳檔案'
                })
            }
        
        # 解析 boundary
        boundary = None
        if 'boundary=' in content_type:
            boundary = content_type.split('boundary=')[1].split(';')[0].strip()
            # 移除可能的引號
            boundary = boundary.strip('"')
        
        logger.info(f"?? 調試 - Boundary: '{boundary}'")
        
        if not boundary:
            logger.error("? 找不到 multipart boundary")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '無效的 multipart 請求',
                    'message': '找不到 boundary'
                })
            }
        
        # 解析請求體
        body = event.get('body', '')
        logger.info(f"?? 調試 - Body length: {len(body) if body else 0}")
        
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
            logger.info(f"?? 調試 - 解碼後 Body length: {len(body)}")
        else:
            body = body.encode('utf-8') if isinstance(body, str) else body
        
        parsed_data = parse_multipart_data(body, boundary)
        logger.info(f"?? 調試 - 解析結果 keys: {list(parsed_data.keys())}")
        
        # 提取團隊資料
        team_data_str = parsed_data.get('team_data', '{}')
        logger.info(f"?? 原始 team_data 字串: '{team_data_str}'")
        
        # 處理空字符串或無效 JSON 的情況
        if not team_data_str or team_data_str.strip() == '':
            logger.warning("?? team_data 為空，使用預設值")
            team_data = {}
        else:
            try:
                team_data = json.loads(team_data_str)
                logger.info(f"?? 成功解析團隊資料: {team_data}")
            except json.JSONDecodeError as e:
                logger.error(f"? 解析團隊資料失敗: {str(e)}")
                logger.error(f"? 問題字串: '{team_data_str[:100]}...' (前100字符)")
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': '團隊資料格式錯誤',
                        'message': str(e),
                        'received_data': team_data_str[:100] if len(team_data_str) > 100 else team_data_str
                    })
                }
        
        # 檢查是否有足夠的團隊資料來建立團隊
        if not team_data:
            logger.error("? 沒有團隊資料無法建立團隊")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊資料',
                    'message': '建立團隊需要提供基本資訊',
                    'required_fields': ['company_code', 'dept_code', 'team_code', 'team_name']
                })
            }
        
        # 先建立團隊
        create_result = create_team_json(team_data, headers)
        if create_result['statusCode'] != 201:
            return create_result
        
        # 取得建立的團隊資訊
        try:
            team_info = json.loads(create_result['body'])
            team_id = team_info['team_id']
            logger.info(f"? 成功解析建立團隊的回應: {team_id}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"? 解析建立團隊回應失敗: {str(e)}")
            logger.error(f"? 回應內容: '{create_result['body'][:200]}...'")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': '解析團隊建立結果失敗',
                    'message': str(e),
                    'create_result': create_result
                })
            }
        
        # 處理檔案上傳
        uploaded_files = []
        
        # 處理多個檔案
        files_to_upload = []
        if 'files_list' in parsed_data:
            files_to_upload = parsed_data['files_list']
        elif 'files' in parsed_data and isinstance(parsed_data['files'], dict):
            files_to_upload = [parsed_data['files']]
        
        logger.info(f"?? 準備上傳 {len(files_to_upload)} 個檔案到團隊 {team_id}")
        
        for file_data in files_to_upload:
            filename = file_data.get('filename', 'unknown_file')
            content = file_data.get('content', b'')
            content_type_file = file_data.get('content_type', 'application/octet-stream')
            
            if content and filename:
                try:
                    # 生成 S3 key
                    file_extension = filename.split('.')[-1] if '.' in filename else 'txt'
                    s3_key = f"{S3_FOLDER_PREFIX}/{team_id}/{uuid.uuid4().hex}.{file_extension}"
                    
                    # 上傳到 S3
                    s3.put_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=s3_key,
                        Body=content,
                        ContentType=content_type_file,
                        Metadata={
                            'original_filename': filename,
                            'team_id': team_id,
                            'upload_time': datetime.now().isoformat()
                        }
                    )
                    
                    uploaded_files.append({
                        'key': s3_key,
                        'filename': filename,
                        'size': len(content),
                        'content_type': content_type_file
                    })
                    
                    logger.info(f"? 檔案上傳成功: {filename} -> {s3_key}")
                    
                except Exception as e:
                    logger.error(f"? 檔案上傳失敗: {filename} - {str(e)}")
        
        # 返回成功結果
        try:
            result_data = json.loads(create_result['body'])
            result_data['uploaded_files'] = uploaded_files
            result_data['uploaded_file_count'] = len(uploaded_files)
            logger.info(f"? 成功合併檔案上傳結果")
        except json.JSONDecodeError as e:
            logger.error(f"? 解析建立結果失敗: {str(e)}")
            # 如果解析失敗，回傳基本的成功資訊
            result_data = {
                'success': True,
                'message': '團隊建立成功（含檔案上傳）',
                'team_id': team_id,
                'uploaded_files': uploaded_files,
                'uploaded_file_count': len(uploaded_files),
                'timestamp': datetime.now().isoformat()
            }
        
        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps(result_data, default=str)
        }
        
    except Exception as e:
        logger.error(f"? 建立團隊（含檔案）失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '建立團隊（含檔案）失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def update_team(event, headers):
    """更新團隊 - 統一處理文字和檔案"""
    try:
        path_parameters = event.get('pathParameters') or {}
        team_id = path_parameters.get('team_id')
        
        if not team_id:
            logger.warning("?? 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        logger.info(f"?? 開始更新團隊: {team_id}")
        
        # 檢查團隊是否存在
        try:
            team_response = teams_table.get_item(Key={'team_id': team_id})
            if 'Item' not in team_response:
                logger.warning(f"?? 找不到團隊: {team_id}")
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({
                        'error': '找不到指定的團隊',
                        'team_id': team_id,
                        'timestamp': datetime.now().isoformat()
                    })
                }
        except Exception as e:
            logger.error(f"? 查詢團隊失敗: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': '查詢團隊失敗',
                    'message': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        # 檢查請求類型 - 支援多種 header 大小寫格式
        headers_dict = event.get('headers', {})
        content_type = (
            headers_dict.get('Content-Type', '') or
            headers_dict.get('content-type', '') or
            headers_dict.get('Content-type', '') or
            headers_dict.get('CONTENT-TYPE', '')
        ).lower()
        
        logger.info(f"?? 檢測到 Content-Type: '{content_type}'")
        logger.info(f"?? 所有 headers: {headers_dict}")
        
        if 'multipart/form-data' in content_type:
            logger.info("?? 檢測到 multipart 請求，包含檔案操作")
            return update_team_with_files(event, headers, team_id)
        else:
            logger.info("?? 檢測到 JSON 請求，純文字更新")
            return update_team_text_only(event, headers, team_id)
            
    except Exception as e:
        logger.error(f"? 更新團隊失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '更新團隊失敗',
                'message': str(e),
                'team_id': team_id if 'team_id' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def update_team_text_only(event, headers, team_id):
    """純文字更新團隊"""
    try:
        body_str = event.get('body', '{}')
        logger.info(f"?? 原始請求體: '{body_str[:100]}...' (前100字符)")
        
        if not body_str or body_str.strip() == '':
            logger.warning("?? 請求體為空，使用預設值")
            body = {}
        else:
            try:
                body = json.loads(body_str)
                logger.info(f"?? 成功解析請求體: {body}")
            except json.JSONDecodeError as e:
                logger.error(f"? JSON 解析失敗: {str(e)}")
                logger.error(f"? 問題內容: '{body_str[:200]}...' (前200字符)")
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'JSON 格式錯誤',
                        'message': str(e),
                        'received_body': body_str[:200],
                        'timestamp': datetime.now().isoformat()
                    })
                }
        
        # 處理檔案刪除（如果有的話）
        files_to_delete = body.pop('files_to_delete', [])
        if files_to_delete:
            logger.info(f"??? 處理檔案刪除: {len(files_to_delete)} 個檔案")
            for file_key in files_to_delete:
                try:
                    s3.delete_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=file_key
                    )
                    logger.info(f"? 檔案刪除成功: {file_key}")
                except Exception as e:
                    logger.warning(f"?? 檔案刪除失敗: {file_key} - {str(e)}")
        
        # 準備更新資料
        update_data = {}
        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # 更新基本欄位
        updateable_fields = [
            'company', 'company_code', 'department', 'dept_code',
            'team_name', 'team_code', 'description'
        ]
        
        for field in updateable_fields:
            if field in body:
                update_expression_parts.append(f'#{field} = :{field}')
                expression_attribute_names[f'#{field}'] = field
                expression_attribute_values[f':{field}'] = body[field]
                update_data[field] = body[field]
        
        # 如果沒有基本欄位要更新，但有檔案刪除，也算是有效操作
        if not update_expression_parts and not files_to_delete:
            logger.warning("?? 沒有要更新的欄位")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '沒有要更新的資料',
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        # 如果有基本欄位要更新，執行 DynamoDB 更新
        if update_expression_parts:
            # 添加更新時間
            update_expression_parts.append('#updated_at = :updated_at')
            expression_attribute_names['#updated_at'] = 'updated_at'
            expression_attribute_values[':updated_at'] = datetime.now().isoformat()
            
            # 執行更新
            teams_table.update_item(
                Key={'team_id': team_id},
                UpdateExpression='SET ' + ', '.join(update_expression_parts),
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            
            logger.info(f"? 團隊文字資料更新成功: {team_id}")
            
            # 備份到 S3
            backup_data = {
                'team_id': team_id,
                **update_data,
                'updated_at': datetime.now().isoformat()
            }
            backup_team_to_s3(backup_data)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'team_id': team_id,
                'message': '團隊更新成功',
                'updated_fields': list(update_data.keys()),
                'deleted_files': files_to_delete,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"? JSON 解析失敗: {str(e)}")
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({
                'error': 'JSON 格式錯誤',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }
    except Exception as e:
        logger.error(f"? 文字更新失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '團隊文字更新失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def update_team_with_files(event, headers, team_id):
    """更新團隊包含檔案操作"""
    try:
        logger.info(f"?? 開始處理團隊檔案更新: {team_id}")
        
        # 調試：記錄完整的事件資訊
        logger.info(f"?? 調試 - Event headers: {event.get('headers', {})}")
        logger.info(f"?? 調試 - isBase64Encoded: {event.get('isBase64Encoded', False)}")
        
        # 解析 multipart 資料
        content_type = event.get('headers', {}).get('Content-Type', '') or event.get('headers', {}).get('content-type', '')
        logger.info(f"?? 調試 - Content-Type: '{content_type}'")
        
        boundary = None
        if 'boundary=' in content_type:
            boundary = content_type.split('boundary=')[1].split(';')[0].strip()
            # 移除可能的引號
            boundary = boundary.strip('"')
        
        logger.info(f"?? 調試 - Boundary: '{boundary}'")
        
        if not boundary:
            logger.error("? 找不到 multipart boundary")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '無效的 multipart 請求',
                    'message': '找不到 boundary',
                    'content_type': content_type,
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        body = event.get('body', '')
        logger.info(f"?? 調試 - Body length: {len(body) if body else 0}")
        
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
            logger.info(f"?? 調試 - 解碼後 Body length: {len(body)}")
        else:
            body = body.encode('utf-8') if isinstance(body, str) else body
        
        parsed_data = parse_multipart_data(body, boundary)
        logger.info(f"?? 調試 - 解析結果 keys: {list(parsed_data.keys())}")
        
        # 提取團隊資料
        team_data_str = parsed_data.get('team_data', '{}')
        logger.info(f"?? 原始 team_data 字串: '{team_data_str}'")
        
        # 處理空字符串或無效 JSON 的情況
        if not team_data_str or team_data_str.strip() == '':
            logger.warning("?? team_data 為空，使用預設值")
            team_data = {}
        else:
            try:
                team_data = json.loads(team_data_str)
                logger.info(f"?? 成功解析團隊資料: {team_data}")
            except json.JSONDecodeError as e:
                logger.warning(f"?? 解析團隊資料失敗，使用預設值: {str(e)}")
                logger.warning(f"?? 問題字串: '{team_data_str[:100]}...' (前100字符)")
                team_data = {}
        
        # 提取要刪除的檔案列表
        files_to_delete = []
        if 'files_to_delete' in parsed_data:
            files_to_delete_str = parsed_data['files_to_delete']
            logger.info(f"?? 原始 files_to_delete 字串: '{files_to_delete_str}'")
            
            if files_to_delete_str and files_to_delete_str.strip():
                try:
                    files_to_delete = json.loads(files_to_delete_str)
                    logger.info(f"??? 從 multipart 解析到刪除檔案列表: {files_to_delete}")
                except json.JSONDecodeError as e:
                    logger.warning(f"?? 無法解析 files_to_delete，使用空列表: {str(e)}")
                    logger.warning(f"?? 問題字串: '{files_to_delete_str[:100]}...'")
                    files_to_delete = []
            else:
                logger.info("?? files_to_delete 為空或空白，使用空列表")
        
        # 先更新文字資料（如果有的話）
        if team_data and any(key in team_data for key in ['company', 'company_code', 'department', 'dept_code', 'team_name', 'team_code', 'description']):
            logger.info("?? 更新團隊文字資料")
            text_update_event = {
                **event,
                'body': json.dumps(team_data)
            }
            text_result = update_team_text_only(text_update_event, headers, team_id)
            if text_result['statusCode'] != 200:
                return text_result
        else:
            logger.info("?? 跳過團隊文字資料更新（沒有相關欄位）")
        
        # 處理檔案刪除
        if files_to_delete:
            logger.info(f"??? 刪除 {len(files_to_delete)} 個檔案")
            for file_key in files_to_delete:
                try:
                    s3.delete_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=file_key
                    )
                    logger.info(f"? 檔案刪除成功: {file_key}")
                except Exception as e:
                    logger.warning(f"?? 檔案刪除失敗: {file_key} - {str(e)}")
        
        # 處理新檔案上傳
        uploaded_files = []
        
        # 處理多個檔案
        files_to_upload = []
        if 'files_list' in parsed_data:
            files_to_upload = parsed_data['files_list']
        elif 'files' in parsed_data and isinstance(parsed_data['files'], dict):
            files_to_upload = [parsed_data['files']]
        
        logger.info(f"?? 準備上傳 {len(files_to_upload)} 個檔案")
        
        for file_data in files_to_upload:
            filename = file_data.get('filename', 'unknown_file')
            content = file_data.get('content', b'')
            content_type_file = file_data.get('content_type', 'application/octet-stream')
            
            if content and filename:
                try:
                    # 生成 S3 key
                    filenameArr = filename.split('.')
                    originalFilename = filenameArr[0]
                    file_extension = filenameArr[-1] if '.' in filename else 'txt'
                    s3_key = f"{S3_FOLDER_PREFIX}/{team_id}/{originalFilename}-{uuid.uuid4().hex}.{file_extension}"
                    
                    # 上傳到 S3
                    s3.put_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=s3_key,
                        Body=content,
                        ContentType=content_type_file,
                        Metadata={
                            'original_filename': filename,
                            'team_id': team_id,
                            'upload_time': datetime.now().isoformat()
                        }
                    )
                    
                    uploaded_files.append({
                        'key': s3_key,
                        'filename': filename,
                        'size': len(content),
                        'content_type': content_type_file
                    })
                    
                    logger.info(f"? 檔案上傳成功: {filename} -> {s3_key}")
                    
                except Exception as e:
                    logger.error(f"? 檔案上傳失敗: {filename} - {str(e)}")
        
        # 構建回應訊息
        operations = []
        if team_data and any(key in team_data for key in ['company', 'company_code', 'department', 'dept_code', 'team_name', 'team_code', 'description']):
            operations.append("更新團隊資料")
        if files_to_delete:
            operations.append(f"刪除 {len(files_to_delete)} 個檔案")
        if uploaded_files:
            operations.append(f"上傳 {len(uploaded_files)} 個檔案")
        
        message = "團隊更新成功"
        if operations:
            message = f"團隊更新成功：{', '.join(operations)}"
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'team_id': team_id,
                'message': message,
                'uploaded_files': uploaded_files,
                'deleted_files': files_to_delete,
                'operations_performed': operations,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"? 檔案更新失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '團隊檔案更新失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

def parse_multipart_data(body, boundary):
    """解析 multipart 資料 - 支援多檔案"""
    try:
        # 確保 boundary 是 bytes
        if isinstance(boundary, str):
            boundary = boundary.encode('utf-8')
        if isinstance(body, str):
            body = body.encode('utf-8')
        
        # 清理 boundary（移除可能的引號）
        boundary = boundary.strip(b'"')
        
        parts = body.split(b'--' + boundary)
        parsed_data = {}
        file_list = []  # 儲存多個檔案
        
        for part in parts:
            if not part.strip() or part.strip() == b'--':
                continue
            
            # 分離 headers 和 content
            if b'\r\n\r\n' in part:
                header_section, content = part.split(b'\r\n\r\n', 1)
            elif b'\n\n' in part:
                header_section, content = part.split(b'\n\n', 1)
            else:
                continue
            
            # 解析 Content-Disposition 和其他 headers
            name = None
            filename = None
            content_type = 'text/plain'
            
            header_text = header_section.decode('utf-8', errors='ignore')
            for line in header_text.split('\n'):
                line = line.strip()
                if line.startswith('Content-Disposition:'):
                    # 更精確的解析
                    if 'name=' in line:
                        # 支援 name="value" 和 name=value 格式
                        if 'name="' in line:
                            name = line.split('name="')[1].split('"')[0]
                        else:
                            name_part = line.split('name=')[1].split(';')[0].strip()
                            name = name_part.strip('"')
                    
                    if 'filename=' in line:
                        # 支援 filename="value" 和 filename=value 格式
                        if 'filename="' in line:
                            filename = line.split('filename="')[1].split('"')[0]
                        else:
                            filename_part = line.split('filename=')[1].split(';')[0].strip()
                            filename = filename_part.strip('"')
                elif line.startswith('Content-Type:'):
                    content_type = line.split('Content-Type:')[1].strip()
            
            if name:
                # 清理 content（移除結尾的 boundary 標記和換行）
                content = content.rstrip(b'\r\n-')
                # 移除結尾的 boundary 殘留
                if content.endswith(b'--'):
                    content = content[:-2]
                
                if filename:
                    # 檔案內容 - 保持為 bytes
                    file_data = {
                        'filename': filename,
                        'content': content,
                        'content_type': content_type
                    }
                    
                    # 如果欄位名稱是 'files'，收集到列表中
                    if name == 'files':
                        file_list.append(file_data)
                    else:
                        parsed_data[name] = file_data
                    
                    logger.info(f"?? 解析到檔案: {filename} (大小: {len(content)} bytes)")
                else:
                    # 文字內容 - 轉換為字串
                    text_content = content.decode('utf-8', errors='ignore').strip()
                    parsed_data[name] = text_content
                    logger.info(f"?? 解析到文字欄位 '{name}': '{text_content[:50]}...' (前50字符)")
        
        # 如果有多個檔案，將它們加入到 parsed_data 中
        if file_list:
            parsed_data['files_list'] = file_list
            # 為了向後相容，如果只有一個檔案，也保留舊的格式
            if len(file_list) == 1:
                parsed_data['files'] = file_list[0]
        
        logger.info(f"?? 解析到的 multipart 資料: keys={list(parsed_data.keys())}, files_count={len(file_list)}")
        return parsed_data
        
    except Exception as e:
        logger.error(f"? multipart 解析失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

def delete_team(event, headers):
    """刪除團隊及其相關檔案"""
    try:
        # 從路徑參數獲取團隊 ID
        team_id = event.get('pathParameters', {}).get('team_id')
        
        if not team_id:
            logger.warning("?? 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'message': '請在路徑參數中提供 team_id'
                })
            }
        
        logger.info(f"??? 開始刪除團隊: {team_id}")
        
        # 檢查團隊是否存在
        team_response = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' not in team_response:
            logger.warning(f"?? 找不到團隊: {team_id}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到指定的團隊',
                    'team_id': team_id
                })
            }
        
        # 刪除 S3 中的團隊檔案
        try:
            # 列出團隊資料夾中的所有檔案
            s3_prefix = f'{S3_FOLDER_PREFIX}/{team_id}/'
            files_response = s3.list_objects_v2(
                Bucket=TEAM_INFO_BUCKET,
                Prefix=s3_prefix
            )
            
            # 刪除所有檔案
            if 'Contents' in files_response:
                for obj in files_response['Contents']:
                    s3.delete_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=obj['Key']
                    )
                    logger.info(f"? 已刪除檔案: {obj['Key']}")
            
            # 刪除團隊資料夾
            s3.delete_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=s3_prefix
            )
            logger.info(f"? 已刪除團隊資料夾: {s3_prefix}")
            
        except Exception as e:
            logger.warning(f"?? 刪除團隊檔案時發生錯誤: {str(e)}")
        
        # 從 DynamoDB 刪除團隊資料
        teams_table.delete_item(Key={'team_id': team_id})
        logger.info(f"? 已從 DynamoDB 刪除團隊: {team_id}")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '團隊刪除成功',
                'team_id': team_id,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"? 刪除團隊失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '刪除團隊失敗',
                'message': str(e),
                'team_id': team_id if 'team_id' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def handle_file_upload(event, headers):
    """處理團隊檔案上傳"""
    try:
        # 從路徑參數獲取團隊 ID
        team_id = event.get('pathParameters', {}).get('team_id')
        
        if not team_id:
            logger.warning("?? 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'message': '請在路徑參數中提供 team_id'
                })
            }
        
        # 檢查團隊是否存在
        team_response = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' not in team_response:
            logger.warning(f"?? 找不到團隊: {team_id}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到指定的團隊',
                    'team_id': team_id
                })
            }
        
        # 解析 multipart/form-data
        content_type = event.get('headers', {}).get('content-type', 
                      event.get('headers', {}).get('Content-Type', ''))
        
        if not content_type or 'multipart/form-data' not in content_type:
            logger.error("? 不支援的內容類型")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '不支援的內容類型',
                    'message': '請使用 multipart/form-data 格式上傳檔案'
                })
            }
        
        # 解析 multipart/form-data 內容
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
        else:
            body = body.encode('utf-8') if isinstance(body, str) else body
        
        # 使用 cgi.FieldStorage 解析表單資料
        fp = io.BytesIO(body)
        environ = {'REQUEST_METHOD': 'POST'}
        fs = cgi.FieldStorage(
            fp=fp, 
            environ=environ, 
            headers={'content-type': content_type}
        )
        
        uploaded_files = []
        
        # 處理每個上傳的檔案
        for field_name in fs:
            field = fs[field_name]
            if hasattr(field, 'filename') and field.filename:
                # 生成唯一的檔案名稱
                original_filename = field.filename
                file_extension = os.path.splitext(original_filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                
                # 構建 S3 key
                s3_key = f'{S3_FOLDER_PREFIX}/{team_id}/{unique_filename}'
                
                # 讀取檔案內容
                file_content = field.file.read()
                if hasattr(field.file, 'seek'):
                    field.file.seek(0)  # 重置檔案指針
                
                # 上傳檔案到 S3
                s3.put_object(
                    Bucket=TEAM_INFO_BUCKET,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=getattr(field, 'type', 'application/octet-stream'),
                    Metadata={
                        'original_filename': original_filename,
                        'team_id': team_id,
                        'upload_time': datetime.now().isoformat()
                    }
                )
                
                uploaded_files.append({
                    'original_filename': original_filename,
                    'key': s3_key,
                    'content_type': getattr(field, 'type', 'application/octet-stream'),
                    'size': len(file_content)
                })
                
                logger.info(f"? 檔案上傳成功: {original_filename} -> {s3_key}")
        
        if not uploaded_files:
            logger.warning("?? 沒有檔案被上傳")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '沒有檔案被上傳',
                    'message': '請選擇至少一個檔案上傳'
                })
            }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '檔案上傳成功',
                'team_id': team_id,
                'uploaded_files': uploaded_files,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"? 檔案上傳失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '檔案上傳失敗',
                'message': str(e),
                'team_id': team_id if 'team_id' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def handle_list_files(event, headers):
    """列出團隊檔案"""
    try:
        # 從路徑參數或查詢參數獲取團隊 ID
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        team_id = path_parameters.get('team_id') or query_parameters.get('team_id')
        
        if not team_id:
            logger.warning("?? 缺少 team_id 參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少團隊 ID',
                    'message': '請提供 team_id'
                })
            }
        
        # 檢查團隊是否存在
        team_response = teams_table.get_item(Key={'team_id': team_id})
        if 'Item' not in team_response:
            logger.warning(f"?? 找不到團隊: {team_id}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到指定的團隊',
                    'team_id': team_id
                })
            }
        
        # 列出團隊資料夾中的所有檔案
        s3_prefix = f'{S3_FOLDER_PREFIX}/{team_id}/'
        files_response = s3.list_objects_v2(
            Bucket=TEAM_INFO_BUCKET,
            Prefix=s3_prefix
        )
        
        files = []
        if 'Contents' in files_response:
            for obj in files_response['Contents']:
                # 跳過資料夾本身，但保留所有檔案（包括 team_info.json）
                key = obj['Key']
                if key == s3_prefix or key.endswith('/'):
                    continue
                
                # 獲取檔案的詳細資訊
                try:
                    head_response = s3.head_object(
                        Bucket=TEAM_INFO_BUCKET,
                        Key=key
                    )
                    
                    # 從 metadata 中獲取原始檔案名稱
                    original_filename = head_response.get('Metadata', {}).get('original-filename')
                    if not original_filename:
                        original_filename = key.split('/')[-1]
                    
                    file_info = {
                        'key': key,
                        'name': original_filename,  # 使用 name 欄位與前端一致
                        'size': obj['Size'],
                        'lastModified': obj['LastModified'].isoformat(),  # 使用駝峰命名與前端一致
                        'etag': obj['ETag'].strip('"'),
                        'content_type': head_response.get('ContentType', 'application/octet-stream')
                    }
                    files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"?? 獲取檔案資訊時發生錯誤 {key}: {str(e)}")
                    # 如果無法獲取詳細資訊，至少返回基本資訊
                    files.append({
                        'key': key,
                        'name': key.split('/')[-1],  # 使用 name 欄位與前端一致
                        'size': obj['Size'],
                        'lastModified': obj['LastModified'].isoformat(),  # 使用駝峰命名與前端一致
                        'etag': obj['ETag'].strip('"')
                    })
        
        # 根據最後修改時間排序，最新的在前面
        files.sort(key=lambda x: x['lastModified'], reverse=True)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'team_id': team_id,
                'files': files,
                'file_count': len(files),
                'timestamp': datetime.now().isoformat()
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"? 列出檔案失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '列出檔案失敗',
                'message': str(e),
                'team_id': team_id if 'team_id' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def handle_file_download(event, headers):
    """處理檔案下載 - 修正版本"""
    try:
        # 從路徑參數獲取檔案 key
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        file_key = path_parameters.get('file_key') or query_parameters.get('file_key')
        
        if not file_key:
            logger.warning("?? 缺少 file_key 參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少檔案 key',
                    'message': '請提供 file_key'
                })
            }
        
        # URL 解碼檔案 key
        file_key = urllib.parse.unquote(file_key)
        logger.info(f"?? 處理檔案下載請求: {file_key}")
        
        # 檢查檔案是否存在
        try:
            head_response = s3.head_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=file_key
            )
            logger.info(f"? 檔案存在: {file_key}")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"?? 找不到檔案: {file_key}")
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({
                        'error': '找不到指定的檔案',
                        'file_key': file_key
                    })
                }
            else:
                logger.error(f"? S3 錯誤: {str(e)}")
                raise
        
        # 生成預簽名 URL
        try:
            # 從 metadata 中獲取原始檔案名稱
            original_filename = head_response.get('Metadata', {}).get('original-filename') or head_response.get('Metadata', {}).get('original_filename')
            if not original_filename:
                original_filename = file_key.split('/')[-1]
            
            # 生成預簽名 URL，有效期 10 分鐘
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': TEAM_INFO_BUCKET,
                    'Key': file_key,
                    'ResponseContentDisposition': f'attachment; filename="{original_filename}"'
                },
                ExpiresIn=600  # 10 分鐘
            )
            
            logger.info(f"? 生成預簽名 URL 成功")
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'success': True,
                    'file_key': file_key,
                    'original_filename': original_filename,
                    'content_type': head_response.get('ContentType', 'application/octet-stream'),
                    'size': head_response['ContentLength'],
                    'download_url': presigned_url,
                    'expires_in': 600,
                    'timestamp': datetime.now().isoformat()
                })
            }
            
        except Exception as e:
            logger.error(f"? 生成下載 URL 失敗: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': '生成下載 URL 失敗',
                    'message': str(e),
                    'file_key': file_key
                })
            }
            
    except Exception as e:
        logger.error(f"? 檔案下載失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '檔案下載失敗',
                'message': str(e),
                'file_key': file_key if 'file_key' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

def handle_file_delete(event, headers):
    """處理檔案刪除"""
    try:
        logger.info("??? 開始處理檔案刪除請求")
        
        # 從查詢參數或請求體獲取要刪除的檔案 key
        query_parameters = event.get('queryStringParameters') or {}
        file_key = query_parameters.get('file_key')
        
        # 如果查詢參數沒有，嘗試從請求體獲取
        if not file_key:
            try:
                body = json.loads(event.get('body', '{}'))
                file_key = body.get('file_key')
            except json.JSONDecodeError:
                pass
        
        if not file_key:
            logger.warning("?? 缺少檔案 key")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '缺少檔案 key',
                    'message': '請提供要刪除的檔案 key'
                })
            }
        
        # URL 解碼檔案 key
        file_key = urllib.parse.unquote(file_key)
        logger.info(f"??? 準備刪除檔案: {file_key}")
        
        # 驗證檔案 key 格式（確保是團隊檔案）
        if not file_key.startswith(S3_FOLDER_PREFIX + '/') or '/../' in file_key:
            logger.warning(f"?? 無效的檔案 key: {file_key}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': '無效的檔案 key',
                    'message': '檔案 key 格式不正確'
                })
            }
        
        # 檢查檔案是否存在
        try:
            s3.head_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=file_key
            )
            logger.info(f"? 檔案確認存在: {file_key}")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"?? 找不到檔案: {file_key}")
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({
                        'error': '找不到指定的檔案',
                        'file_key': file_key
                    })
                }
            else:
                logger.error(f"? 檢查檔案時發生錯誤: {str(e)}")
                raise
        
        # 執行刪除
        try:
            s3.delete_object(
                Bucket=TEAM_INFO_BUCKET,
                Key=file_key
            )
            
            logger.info(f"? 檔案刪除成功: {file_key}")
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'success': True,
                    'message': '檔案刪除成功',
                    'deleted_file_key': file_key,
                    'timestamp': datetime.now().isoformat()
                })
            }
            
        except ClientError as e:
            logger.error(f"? 刪除檔案失敗: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': '刪除檔案失敗',
                    'message': str(e),
                    'file_key': file_key
                })
            }
            
    except Exception as e:
        logger.error(f"? 檔案刪除處理失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '檔案刪除處理失敗',
                'message': str(e),
                'file_key': file_key if 'file_key' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

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
        
        logger.info(f"? 團隊資料備份成功: s3://{TEAM_INFO_BUCKET}/{s3_key}")
        
    except Exception as e:
        logger.error(f"? 團隊資料備份失敗: {str(e)}")
        # 不拋出例外，因為備份失敗不應該影響主要功能

def create_team_folder(team_id):
    """創建團隊檔案資料夾"""
    try:
        s3.put_object(
            Bucket=TEAM_INFO_BUCKET,
            Key=f'{S3_FOLDER_PREFIX}/{team_id}/'
        )
        logger.info(f"? 團隊檔案資料夾創建成功: s3://{TEAM_INFO_BUCKET}/{S3_FOLDER_PREFIX}/{team_id}/")
    except Exception as e:
        logger.error(f"? 創建團隊檔案資料夾失敗: {str(e)}")
        # 不拋出例外，因為資料夾創建失敗不應該影響主要功能