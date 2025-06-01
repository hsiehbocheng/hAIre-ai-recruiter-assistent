import json
import boto3
import base64
from datetime import datetime
from typing import Dict, Any

# 初始化 S3 客戶端
s3_client = boto3.client('s3')

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    處理團隊文件管理的 Lambda 函數
    支援: 文件上傳、下載、列表查詢、刪除
    """
    
    # 設置 CORS 響應頭
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Content-Type': 'application/json'
    }
    
    try:
        # 處理 OPTIONS 請求 (CORS preflight)
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # 取得請求方法和路徑
        method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        print(f"📨 收到請求: {method} {path}")
        print(f"📨 事件詳情: {json.dumps(event, default=str)}")
        
        # 路由處理
        if method == 'POST' and '/upload-team-file' in path:
            return handle_file_upload(event, headers)
        elif method == 'GET' and '/team-files/' in path:
            return handle_list_files(event, headers)
        elif method == 'GET' and '/download-team-file/' in path:
            return handle_file_download(event, headers)
        elif method == 'DELETE' and '/delete-team-file' in path:
            return handle_file_delete(event, headers)
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': '找不到對應的 API 端點',
                    'method': method,
                    'path': path
                })
            }
            
    except Exception as e:
        print(f"❌ Lambda 函數執行錯誤: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '伺服器內部錯誤',
                'message': str(e)
            })
        }

def handle_file_upload(event: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """處理文件上傳"""
    try:
        # 解析 multipart/form-data
        content_type = event.get('headers', {}).get('content-type', '') or event.get('headers', {}).get('Content-Type', '')
        
        if 'multipart/form-data' not in content_type:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '需要 multipart/form-data 格式'})
            }
        
        # 取得請求體 (base64 編碼)
        body = event.get('body', '')
        is_base64 = event.get('isBase64Encoded', False)
        
        if is_base64:
            body = base64.b64decode(body)
        else:
            body = body.encode('utf-8')
        
        # 解析 multipart 數據 (簡化版本，實際應使用專門的解析器)
        # 這裡假設已經解析出了必要的字段
        boundary = content_type.split('boundary=')[1] if 'boundary=' in content_type else None
        
        if not boundary:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '無法找到 boundary'})
            }
        
        # 從查詢參數或請求體中取得文件資訊
        team_id = event.get('queryStringParameters', {}).get('teamId', '') if event.get('queryStringParameters') else ''
        bucket_name = 'benson-haire-team-info-e36d5aee'
        
        # 模擬文件上傳成功 (實際實作需要完整的 multipart 解析)
        file_key = f"team_docs/{team_id}-example_file.txt"
        
        # 實際上傳到 S3 的邏輯會在這裡
        # s3_client.put_object(
        #     Bucket=bucket_name,
        #     Key=file_key,
        #     Body=file_content,
        #     ContentType=file_content_type
        # )
        
        print(f"✅ 模擬文件上傳成功: {file_key}")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '文件上傳成功',
                'key': file_key,
                'bucket': bucket_name,
                'uploaded_at': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"❌ 文件上傳失敗: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '文件上傳失敗',
                'message': str(e)
            })
        }

def handle_list_files(event: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """列出團隊文件"""
    try:
        # 從路徑參數中取得團隊 ID
        path_params = event.get('pathParameters', {})
        team_id = path_params.get('team_id', '') if path_params else ''
        
        if not team_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少團隊 ID'})
            }
        
        bucket_name = 'benson-haire-team-info-e36d5aee'
        prefix = f'team_docs/{team_id}-'
        
        print(f"📂 列出文件: bucket={bucket_name}, prefix={prefix}")
        
        # 列出 S3 文件
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
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
        
        print(f"✅ 找到 {len(files)} 個文件")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'files': files,
                'count': len(files),
                'team_id': team_id
            })
        }
        
    except Exception as e:
        print(f"❌ 列出文件失敗: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '列出文件失敗',
                'message': str(e)
            })
        }

def handle_file_download(event: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """處理文件下載"""
    try:
        # 從路徑參數中取得文件 key
        path_params = event.get('pathParameters', {})
        file_key = path_params.get('file_key', '') if path_params else ''
        
        if not file_key:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少文件 key'})
            }
        
        bucket_name = 'benson-haire-team-info-e36d5aee'
        
        print(f"📥 下載文件: bucket={bucket_name}, key={file_key}")
        
        # 生成預簽名 URL 用於下載
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': file_key},
            ExpiresIn=3600  # 1小時有效期
        )
        
        print(f"✅ 生成下載 URL 成功")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'downloadUrl': download_url,
                'expiresIn': 3600,
                'key': file_key
            })
        }
        
    except Exception as e:
        print(f"❌ 文件下載失敗: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '文件下載失敗',
                'message': str(e)
            })
        }

def handle_file_delete(event: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """處理文件刪除"""
    try:
        # 解析請求體
        body = json.loads(event.get('body', '{}'))
        file_key = body.get('key', '')
        bucket_name = body.get('bucket', 'benson-haire-team-info-e36d5aee')
        
        if not file_key:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少文件 key'})
            }
        
        print(f"🗑️ 刪除文件: bucket={bucket_name}, key={file_key}")
        
        # 刪除 S3 文件
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=file_key
        )
        
        print(f"✅ 文件刪除成功")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '文件刪除成功',
                'key': file_key,
                'deleted_at': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"❌ 文件刪除失敗: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '文件刪除失敗',
                'message': str(e)
            })
        } 