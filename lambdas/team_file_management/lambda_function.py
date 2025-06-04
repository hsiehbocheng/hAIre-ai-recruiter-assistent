import json
import boto3
import base64
from datetime import datetime
from typing import Dict, Any
import cgi # 用於解析 multipart/form-data
import io # 用於處理字節流
import os # 用於讀取環境變數

# 初始化 S3 客戶端
s3_client = boto3.client('s3')

# S3 儲存桶設定 - 從環境變數讀取
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'benson-haire-team-info-e36d5aee')
S3_FOLDER_PREFIX = 'team_info_docs/'

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    處理團隊文件管理的 Lambda 函數
    支援: 文件上傳、下載、列表查詢、刪除
    """
    
    # 設置 CORS 響應頭
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token', # 確保 Content-Type 被允許
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
        # print(f"📨 事件詳情: {json.dumps(event, default=str)}") # 包含文件內容，可能會很長
        
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
        import traceback
        print(traceback.format_exc())
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
        content_type_header = event.get('headers', {}).get('content-type', event.get('headers', {}).get('Content-Type', ''))
        
        if not content_type_header or 'multipart/form-data' not in content_type_header:
            print(f"⚠️ 錯誤的 Content-Type: {content_type_header}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '需要 multipart/form-data 格式'})
            }

        team_id = event.get('queryStringParameters', {}).get('teamId', '')
        if not team_id:
            print("⚠️ 缺少 teamId 查詢參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少 teamId 查詢參數'})
            }

        # 解碼 base64 主體
        body_bytes = base64.b64decode(event['body']) if event.get('isBase64Encoded', False) else event['body'].encode('utf-8')
        
        # 使用 cgi.FieldStorage 解析 multipart/form-data
        # FieldStorage 需要 file-like object 和 headers
        fp = io.BytesIO(body_bytes)
        
        # 準備 cgi.FieldStorage 所需的環境變數
        environ = {'REQUEST_METHOD': 'POST'}
        
        # 確保 content_type_header 是字串
        if isinstance(content_type_header, bytes):
            content_type_header = content_type_header.decode('utf-8')

        # cgi.FieldStorage 解析需要 boundary，它在 content_type_header 中
        # Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW
        
        form = cgi.FieldStorage(fp=fp, environ=environ, headers={'content-type': content_type_header})

        uploaded_files_info = []

        if 'file' in form:
            file_item = form['file']
            if isinstance(file_item, list): # 如果上傳多個同名文件
                file_items = file_item
            else:
                file_items = [file_item]

            for item in file_items:
                if item.filename:
                    original_filename = item.filename
                    file_content = item.file.read() # 讀取文件內容 (bytes)
                    
                    # 建構 S3 物件金鑰
                    # 使用原始檔案名稱，但進行一些清理以避免 S3 金鑰問題
                    safe_original_filename = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in original_filename)
                    file_key = f"{S3_FOLDER_PREFIX}{team_id}/{safe_original_filename}"
                    
                    # 上傳到 S3
                    s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=file_key,
                        Body=file_content,
                        # ContentType 可以從 item.type 獲取，但前端可能未正確設定
                        # 如果需要，可以根據文件擴展名推斷，或讓瀏覽器/S3自行處理
                    )
                    
                    print(f"✅ 文件上傳成功: s3://{S3_BUCKET_NAME}/{file_key}")
                    uploaded_files_info.append({
                        'key': file_key,
                        'filename': original_filename,
                        'size': len(file_content)
                    })
                else:
                    print("⚠️ 收到一個沒有檔案名稱的 file item")
        else:
            print("⚠️ multipart/form-data 中沒有找到 'file' 欄位")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': "multipart/form-data 中沒有找到 'file' 欄位"})
            }

        if not uploaded_files_info:
             print("⚠️ 沒有成功上傳任何文件")
             return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '沒有成功上傳任何文件'})
            }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': f'{len(uploaded_files_info)} 個文件上傳成功',
                'uploaded_files': uploaded_files_info
            })
        }
        
    except Exception as e:
        print(f"❌ 文件上傳失敗: {str(e)}")
        import traceback
        print(traceback.format_exc())
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
        path_params = event.get('pathParameters', {})
        team_id = path_params.get('team_id', '') if path_params else ''
        
        if not team_id:
            print("⚠️ 缺少 team_id 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少團隊 ID'})
            }
        
        # 更新 S3 前綴以符合新的資料夾結構和命名規則
        s3_prefix_for_team = f'{S3_FOLDER_PREFIX}{team_id}_'
        
        print(f"📂 列出文件: bucket={S3_BUCKET_NAME}, prefix={s3_prefix_for_team}")
        
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=s3_prefix_for_team
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # 從完整的 S3 Key 中提取原始檔案名稱
                # Key 格式: team_info_docs/TEAM_ID_原始檔案名稱.pdf
                # 我們需要移除 team_info_docs/TEAM_ID_ 這部分
                original_filename = obj['Key'].replace(s3_prefix_for_team, '', 1)
                
                files.append({
                    'key': obj['Key'], # 完整的 S3 Object Key
                    'name': original_filename, # 原始檔案名稱
                    'size': obj['Size'],
                    'lastModified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag'].strip('"')
                })
        
        print(f"✅ 找到 {len(files)} 個文件，team_id: {team_id}")
        
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
        import traceback
        print(traceback.format_exc())
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
        path_params = event.get('pathParameters', {})
        # 前端傳送的 file_key 應該是 URL 編碼過的，API Gateway 會自動解碼
        file_key_from_path = path_params.get('file_key', '') if path_params else ''

        if not file_key_from_path:
            print("⚠️ 缺少 file_key 路徑參數")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '缺少文件 key'})
            }
        
        # 確保 file_key 是我們期望的格式，例如 team_info_docs/some_team_id_file.pdf
        # 前端傳來的應該已經是完整的 S3 key
        s3_object_key = file_key_from_path
        
        print(f"📥 下載文件: bucket={S3_BUCKET_NAME}, key={s3_object_key}")
        
        # 生成預簽名 URL 用於下載
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_object_key},
            ExpiresIn=3600  # 1小時有效期
        )
        
        print(f"✅ 生成下載 URL 成功: {download_url}")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'downloadUrl': download_url,
                'key': s3_object_key # 回傳原始的 key
            })
        }
        
    except Exception as e:
        print(f"❌ 文件下載失敗: {str(e)}")
        import traceback
        print(traceback.format_exc())
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
        # 前端應該在請求體中傳送 {'key': '完整S3物件金鑰'}
        body = json.loads(event.get('body', '{}'))
        s3_object_key = body.get('key')

        if not s3_object_key:
            print("⚠️ 請求體中缺少 'key'")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': "請求體中缺少 'key'"})
            }

        print(f"🗑️ 刪除文件: bucket={S3_BUCKET_NAME}, key={s3_object_key}")

        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_object_key)

        print(f"✅ 文件刪除成功: {s3_object_key}")

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': '文件刪除成功',
                'key': s3_object_key
            })
        }

    except Exception as e:
        print(f"❌ 文件刪除失敗: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '文件刪除失敗',
                'message': str(e)
            })
        } 