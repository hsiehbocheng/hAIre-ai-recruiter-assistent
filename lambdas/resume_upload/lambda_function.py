import os
import json
import logging
import base64
import cgi
import io
import uuid
from datetime import datetime
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS 服務初始化
s3 = boto3.client('s3', region_name='ap-southeast-1')
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')

# 環境變數
RAW_RESUME_BUCKET = os.environ.get('RAW_RESUME_BUCKET', 'benson-haire-raw-resume-e36d5aee')
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME', 'benson-haire-job-posting')

# DynamoDB 表格
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)

def get_job_info(job_id: str) -> Dict[str, Any]:
    """從 DynamoDB 獲取職缺資訊"""
    try:
        response = jobs_table.get_item(Key={'job_id': job_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"獲取職缺資訊失敗: {str(e)}")
        return {}

def lambda_handler(event, context):
    """履歷上傳處理函式"""
    logger.info(f"🔥 履歷上傳 Lambda 被調用! Event: {json.dumps(event, default=str)}")
    
    # 設置 CORS 響應頭
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
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
        
        # 只處理 POST 請求
        if event.get('httpMethod') != 'POST':
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({'error': '只支援 POST 方法'})
            }
        
        # 檢查 Content-Type
        content_type = event.get('headers', {}).get('content-type', 
                      event.get('headers', {}).get('Content-Type', ''))
        
        if not content_type or 'multipart/form-data' not in content_type:
            logger.warning(f"⚠️ 錯誤的 Content-Type: {content_type}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '需要 multipart/form-data 格式'})
            }

        # 解碼 base64 主體
        body_bytes = base64.b64decode(event['body']) if event.get('isBase64Encoded', False) else event['body'].encode('utf-8')
        
        # 使用 cgi.FieldStorage 解析 multipart/form-data
        fp = io.BytesIO(body_bytes)
        environ = {'REQUEST_METHOD': 'POST'}
        
        if isinstance(content_type, bytes):
            content_type = content_type.decode('utf-8')

        form = cgi.FieldStorage(fp=fp, environ=environ, headers={'content-type': content_type})

        # 提取職缺資訊
        job_id = form.getvalue('job_id', '')
        job_title = form.getvalue('job_title', '')
        company = form.getvalue('company', '')

        logger.info(f"📋 職缺資訊: job_id={job_id}, job_title={job_title}, company={company}")

        # 從 DynamoDB 獲取完整的職缺資訊，包括 team_id
        job_info = get_job_info(job_id)
        if not job_info:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': '找不到指定的職缺'})
            }
        
        team_id = job_info.get('team_id', '')
        if not team_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '職缺缺少 team_id 資訊'})
            }

        # 處理檔案上傳
        if 'file' not in form:
            logger.warning("⚠️ multipart/form-data 中沒有找到 'file' 欄位")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': "multipart/form-data 中沒有找到 'file' 欄位"})
            }

        file_item = form['file']
        if not file_item.filename:
            logger.warning("⚠️ 收到一個沒有檔案名稱的 file item")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '請選擇要上傳的檔案'})
            }

        original_filename = file_item.filename
        file_content = file_item.file.read()
        
        # 驗證檔案格式
        allowed_extensions = ['.pdf', '.json']
        file_extension = os.path.splitext(original_filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '只支援 PDF 和 JSON 格式的檔案'})
            }
        
        # 驗證檔案大小 (10MB)
        max_size = 10 * 1024 * 1024
        if len(file_content) > max_size:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': '檔案大小不能超過 10MB'})
            }

        # 生成唯一的 resume_id 和當前日期
        resume_id = str(uuid.uuid4())[:8]  # 短 UUID
        current_date = datetime.now().strftime('%Y%m%d')
        
        # 清理原始檔名（移除副檔名）
        file_name_without_ext = os.path.splitext(original_filename)[0]
        safe_file_name = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in file_name_without_ext)
        
        # 建構新的檔名：{file_name}-{resume_id}-{current_date}.pdf/.json
        new_filename = f"{safe_file_name}-{resume_id}-{current_date}{file_extension}"
        
        # 建構 S3 金鑰：raw_resume/{team_id}/{job_id}/{new_filename}
        s3_key = f"raw_resume/{team_id}/{job_id}/{new_filename}"
        
        # 準備檔案元數據（只使用 ASCII 字符）
        metadata = {
            'job_id': job_id,
            'team_id': team_id,
            'resume_id': resume_id,
            'original_filename': base64.b64encode(original_filename.encode('utf-8')).decode('ascii'),  # Base64 編碼中文檔名
            'upload_timestamp': datetime.now().isoformat(),
            'file_type': file_extension.replace('.', ''),
            'file_size': str(len(file_content)),
            'current_date': current_date
        }
        
        # 如果有中文資訊，進行 Base64 編碼
        if job_title:
            metadata['job_title_b64'] = base64.b64encode(job_title.encode('utf-8')).decode('ascii')
        if company:
            metadata['company_b64'] = base64.b64encode(company.encode('utf-8')).decode('ascii')

        # 上傳到 S3
        try:
            s3.put_object(
                Bucket=RAW_RESUME_BUCKET,
                Key=s3_key,
                Body=file_content,
                ContentType=file_item.type or 'application/octet-stream',
                Metadata=metadata
            )
            
            logger.info(f"✅ 履歷上傳成功: s3://{RAW_RESUME_BUCKET}/{s3_key}")
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'success': True,
                    'message': '履歷上傳成功',
                    'file_info': {
                        'key': s3_key,
                        'original_filename': original_filename,
                        'new_filename': new_filename,
                        'size': len(file_content),
                        'job_id': job_id,
                        'team_id': team_id,
                        'resume_id': resume_id,
                        'job_title': job_title,
                        'company': company
                    },
                    'timestamp': datetime.now().isoformat()
                })
            }
            
        except ClientError as e:
            logger.error(f"❌ S3 上傳失敗: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': 'S3 上傳失敗',
                    'message': str(e)
                })
            }
        
    except Exception as e:
        logger.error(f"❌ 履歷上傳失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': '履歷上傳失敗',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        } 