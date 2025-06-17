import os
import json
import urllib.parse
import logging
from datetime import datetime
import io
import time

import boto3
from pdf2image import convert_from_bytes

logger = logging.getLogger()
logger.setLevel(logging.INFO)  # 或 DEBUG, WARNING, ERROR

bedrock_client = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
temperature = 0.0
maxTokens = 8192
inference_config = {"temperature": temperature, "maxTokens": maxTokens}
system_prompt = [{"text": """請依照下列步驟處理： 1. 讀取變數 Resume Raw Json Data 中的履歷原始資料。 2. 解析並重組成以下 **完整且相同欄位結構** 的 JSON。 3. **僅**輸出 JSON，本身不得夾帶任何說明、換行之外的文字，或多餘欄位。 ## 輸出格式範例 預期輸出格式如以下（鍵名與巢狀結構不得變動，只需依照實際資料填入對應值）： "profile": { "basics": { "first_name": <string>, "last_name": <string>, "gender": <"male" | "female" | "other" | "unknown">, "emails": [<string>, ...], "urls": [<string>, ...], "date_of_birth": { "year": <integer>, "month": <integer>, "day": <integer> }, "age": <integer>, // 若生日資訊不足以計算，填 null "total_experience_in_years": <integer>, // 四捨五入到整數；無法判斷填 null "current_title": <string>, "skills": [<string>, ...] }, "educations": [{ "start_year": <integer>, "is_current": <boolean>, "end_year": <integer>, // 若 is_current 為 true 可填 null "issuing_organization":<string>, "study_type": <string>, "department": <string>, "description": <string> }], "trainings_and_certifications": [{ "year": <integer>, "issuing_organization":<string>, "description": <string> }], "professional_experiences": [{ "start_year": <integer>, "start_month": <integer>, "is_current": <boolean>, "end_year": <integer>, "end_month": <integer>, "duration_in_months": <integer>, // 若未提供可自行計算；無法判斷填 null "company": <string>, "location": <string>, "title": <string>, "description": <string> }], "awards": [{ "year": <integer>, "title": <string>, "description": <string> }] } **切記：最終輸出僅能是以上 JSON，本行與其他說明文字皆不得包含。"""}]

s3 = boto3.client("s3")
parsed_output_s3_bucket = os.environ["PARSED_BUCKET"]
dynamodb_table_name = os.environ.get("DYNAMODB_TABLE", "benson-haire-parsed_resume")

def clean_for_dynamodb(data):
    """清理資料以符合 DynamoDB 要求"""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned_value = clean_for_dynamodb(value)
            # 只有非 None 的值才加入
            if cleaned_value is not None:
                cleaned[key] = cleaned_value
        return cleaned if cleaned else None
    elif isinstance(data, list):
        cleaned = [clean_for_dynamodb(item) for item in data if clean_for_dynamodb(item) is not None]
        return cleaned if cleaned else None
    elif isinstance(data, str):
        # 空字串轉為 None
        return data.strip() if data and data.strip() else None
    elif isinstance(data, (int, float)):
        # 0 值在某些情況下可以保留，但如果是 year 且為 0 則設為 None
        return data if data != 0 else None
    elif data is None:
        return None
    else:
        return data

def validate_and_fix_profile(profile):
    """驗證並修正 profile 資料結構"""
    try:
        if not isinstance(profile, dict):
            return None
            
        # 清理 basics
        if 'basics' in profile:
            basics = profile['basics']
            
            # 處理 date_of_birth
            if 'date_of_birth' in basics and isinstance(basics['date_of_birth'], dict):
                dob = basics['date_of_birth']
                # 如果所有值都是 0 或 None，則移除整個 date_of_birth
                if (dob.get('year', 0) == 0 and 
                    dob.get('month', 0) == 0 and 
                    dob.get('day', 0) == 0):
                    del basics['date_of_birth']
                else:
                    # 清理個別欄位
                    for field in ['year', 'month', 'day']:
                        if dob.get(field, 0) == 0:
                            del dob[field]
            
            # 處理 age - 如果是 None 或 0，移除
            if basics.get('age') is None or basics.get('age') == 0:
                if 'age' in basics:
                    del basics['age']
            
            # 確保 emails 和 urls 是列表且非空
            for field in ['emails', 'urls', 'skills']:
                if field in basics:
                    if not isinstance(basics[field], list) or not basics[field]:
                        if field == 'skills':
                            basics[field] = []  # skills 可以是空陣列
                        else:
                            del basics[field]
        
        # 清理 educations
        if 'educations' in profile:
            cleaned_educations = []
            for edu in profile['educations']:
                if isinstance(edu, dict):
                    # 清理 end_year - 如果是 None 或 0，移除
                    if edu.get('end_year') is None or edu.get('end_year') == 0:
                        if 'end_year' in edu:
                            del edu['end_year']
                    
                    # 確保必要欄位存在
                    if edu.get('issuing_organization') and edu.get('start_year', 0) > 0:
                        cleaned_educations.append(edu)
            
            if cleaned_educations:
                profile['educations'] = cleaned_educations
            else:
                profile['educations'] = []
        
        # 清理 professional_experiences
        if 'professional_experiences' in profile:
            cleaned_experiences = []
            for exp in profile['professional_experiences']:
                if isinstance(exp, dict):
                    # 清理 null 值
                    if exp.get('end_year') is None:
                        if 'end_year' in exp:
                            del exp['end_year']
                    if exp.get('end_month') is None:
                        if 'end_month' in exp:
                            del exp['end_month']
                    
                    # 確保必要欄位存在
                    if exp.get('company') and exp.get('start_year', 0) > 0:
                        cleaned_experiences.append(exp)
            
            if cleaned_experiences:
                profile['professional_experiences'] = cleaned_experiences
            else:
                profile['professional_experiences'] = []
        
        # 清理 trainings_and_certifications
        if 'trainings_and_certifications' in profile:
            cleaned_certs = []
            for cert in profile['trainings_and_certifications']:
                if isinstance(cert, dict):
                    # 如果 year 是 0，移除
                    if cert.get('year', 0) == 0:
                        if 'year' in cert:
                            del cert['year']
                    
                    # 確保必要欄位存在
                    if cert.get('issuing_organization'):
                        cleaned_certs.append(cert)
            
            if cleaned_certs:
                profile['trainings_and_certifications'] = cleaned_certs
            else:
                profile['trainings_and_certifications'] = []
        
        # 清理 awards - 確保是陣列
        if 'awards' not in profile or not isinstance(profile['awards'], list):
            profile['awards'] = []
        
        return profile
        
    except Exception as e:
        logger.error(f"清理 profile 資料失敗: {str(e)}")
        return profile  # 返回原始資料

def extract_filename(key: str) -> str:
    """取得 key 中最後一段檔名，解碼後回傳"""
    filename = os.path.basename(key)
    filename = urllib.parse.unquote(filename) 
    return filename

def generate_output_key(key: str) -> str:
    """
    保留原始 key 的 prefix 路徑，將檔名改為 .json 副檔名
    範例:
      輸入: raw_resume/TECH-FE-DEV/TECH-FE-DEV-89c83426/zhang-xiaoming-resume.pdf
      輸出: parsed_resume/TECH-FE-DEV/TECH-FE-DEV-89c83426/zhang-xiaoming-resume.json
    """
    key = urllib.parse.unquote(key)  # decode URL encoding
    
    # 將 raw_resume 替換為 parsed_resume
    if key.startswith('raw_resume/'):
        # 替換前綴
        output_key = key.replace('raw_resume/', 'parsed_resume/')
        
        # 確保副檔名是 .json
        dir_name = os.path.dirname(output_key)
        base_name = os.path.basename(output_key)
        name_without_ext = os.path.splitext(base_name)[0]
        
        return f"{dir_name}/{name_without_ext}.json" if dir_name else f"{name_without_ext}.json"
    else:
        # 如果不是預期格式，加上 parsed- 前綴到檔名並確保是 .json 副檔名
        dir_name = os.path.dirname(key)
        base_name = os.path.basename(key)
        name_without_ext = os.path.splitext(base_name)[0]
        new_base = f"parsed-{name_without_ext}.json"
        return f"{dir_name}/{new_base}" if dir_name else new_base

def extract_path_info(s3_key: str) -> dict:
    """
    從 S3 key 中提取路徑資訊
    支援格式: raw_resume/{team_id}/{job_id}/{file_name}
    """
    try:
        # 解碼 URL encoding
        key = urllib.parse.unquote(s3_key)
        logger.info(f"解析 S3 key: {key}")
        
        # 移除前面的 raw_resume/ 如果存在
        if key.startswith('raw_resume/'):
            key = key[11:]  # 移除 'raw_resume/' 部分
        
        # 分割路徑
        path_parts = key.split('/')
        logger.info(f"路徑分割結果: {path_parts}")
        
        if len(path_parts) >= 3:
            team_id = path_parts[0]
            job_id = path_parts[1]
            file_name = path_parts[2]
            
            # 使用檔案名作為 resume_id，移除副檔名
            resume_id = os.path.splitext(file_name)[0]
            
            return {
                'team_id': team_id,
                'job_id': job_id,
                'resume_id': resume_id,
                'file_name': file_name
            }
        else:
            logger.error(f"S3 key 格式不正確，需要至少 3 個路徑段: {s3_key}")
            return None
            
    except Exception as e:
        logger.error(f"解析 S3 key 失敗: {str(e)}")
        return None

def extract_basic_info(profile_data: dict) -> dict:
    """從解析後的 profile 資料中提取基本資訊用於 DynamoDB"""
    try:
        basics = profile_data.get('basics', {})
        
        # 提取姓名
        first_name = basics.get('first_name', '') or ''
        last_name = basics.get('last_name', '') or ''
        candidate_name = f"{first_name} {last_name}".strip() if first_name or last_name else "Unknown"
        
        # 提取 email
        emails = basics.get('emails', [])
        candidate_email = emails[0] if emails and emails[0] else None
        
        # 提取現職
        current_title = basics.get('current_title') or ''
        
        return {
            'candidate_name': candidate_name,
            'candidate_email': candidate_email,
            'current_title': current_title
        }
        
    except Exception as e:
        logger.error(f"提取基本資訊失敗: {str(e)}")
        return {
            'candidate_name': "Unknown",
            'candidate_email': None,
            'current_title': ''
        }

def convert_pdf_to_image_bytes_list(pdf_bytes, 
                                    max_pages=5,
                                    image_format='png',
                                    dpi=300):
    """
    將 PDF bytes 轉換為多頁圖片，每頁一張，回傳圖片 bytes list。

    :param pdf_bytes: PDF 的 bytes 資料
    :param image_format: 圖片格式，如 'png', 'jpeg'
    :param dpi: 解析度（越高越清楚，但圖片也越大）
    :param max_pages: 最多保留幾頁（超過則只保留前 max_pages 頁）
    :return: List[bytes]，每張圖片為一筆 bytes
    """
    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi)

        if max_pages is not None:
            images = images[:max_pages]

        image_bytes_list = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format=image_format.upper())
            image_bytes_list.append(buf.getvalue())

        return image_bytes_list
    except Exception as e:
        logger.error(f"PDF 轉圖片失敗: {str(e)}")
        raise e

def bedrock_converse_convert_images_to_text_batch(bedrock_client, model_id, images_bytes_list, batch_size=3, sleep_sec=1):
    """
    分批將多張圖片丟給 Claude 模型，避免一次丟太多造成 timeout。

    :param bedrock_client: boto3 的 bedrock client
    :param model_id: Claude 模型 ID（例如 Claude 3.5）
    :param images_bytes_list: List of image bytes（每張為一頁）
    :param batch_size: 每批最多幾張圖片（預設 3）
    :param sleep_sec: 每批間隔幾秒（預設 1 秒，避免觸發限速）
    :return: 完整的履歷文字內容｀
    """
    try:
        all_text_content = []
        total_batches = (len(images_bytes_list) + batch_size - 1) // batch_size

        for i in range(0, len(images_bytes_list), batch_size):
            batch = images_bytes_list[i:i + batch_size]

            content_list = [{"text": f"""
                             我會傳給你求職者的履歷資訊，當中的內容都非常重要，請你擷取圖片中的所有履歷文字內容
                             不要省略任何欄位，也不要自行生成額外資訊，這非常重要
                             """}]
            for img_bytes in batch:
                content_list.append({
                    "image": {
                        "format": "png",
                        "source": {"bytes": img_bytes}
                    }
                })

            messages = [{
                "role": "user",
                "content": content_list
            }]

            logger.info(f"發送 batch {i//batch_size + 1} / {total_batches} ...")
            response = bedrock_client.converse(
                modelId=model_id,
                messages=messages
            )
            
            text = response["output"]["message"]["content"][0]["text"]
            all_text_content.append(text)

            if sleep_sec > 0 and i + batch_size < len(images_bytes_list):
                time.sleep(sleep_sec)

        # 串接所有批次回覆成一段完整文字
        full_resume_content = "\n".join(all_text_content)
        logger.info(f"Claude 解析完成，解析結果{full_resume_content}")
        return full_resume_content
        
    except Exception as e:
        logger.error(f"批次處理圖片失敗: {str(e)}")
        raise e

def is_pdf_file(file_content_bytes):
    """檢查檔案是否為 PDF 格式"""
    return file_content_bytes.startswith(b'%PDF')

def lambda_handler(event, context):
    logger.info(f"收到事件: {event}")
    
    # 初始化 DynamoDB 表格
    table = dynamodb.Table(dynamodb_table_name)
    
    for rec in event["Records"]:
        bucket = rec["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(rec["s3"]["object"]["key"])
        logger.info(f"處理 S3 事件 - bucket: {bucket}, key: {key}")

        # 從 S3 路徑中提取資訊
        path_info = extract_path_info(key)
        if not path_info:
            logger.error(f"無法解析 S3 路徑，跳過處理: {key}")
            continue
            
        team_id = path_info['team_id']
        job_id = path_info['job_id']
        resume_id = path_info['resume_id']
        
        logger.info(f"提取到路徑資訊 - team_id: {team_id}, job_id: {job_id}, resume_id: {resume_id}")

        # 從 S3 讀取原始履歷檔案
        try:
            file_content_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            logger.info(f"成功讀取原始履歷檔案，大小: {len(file_content_bytes)} bytes")
        except Exception as e:
            logger.error(f"讀取 S3 檔案失敗: {str(e)}")
            continue

        # 判斷檔案格式並處理
        try:
            if is_pdf_file(file_content_bytes):
                logger.info("偵測到 PDF 檔案，進行 PDF 轉圖片處理...")
                
                # 將 PDF 轉換為圖片
                images_bytes_list = convert_pdf_to_image_bytes_list(
                    file_content_bytes, 
                    max_pages=10, 
                    dpi=300
                )
                logger.info(f"PDF 轉換完成，共 {len(images_bytes_list)} 頁")
                
                # 使用批次處理將圖片轉換為文字
                resume_text_content = bedrock_converse_convert_images_to_text_batch(
                    bedrock_client=bedrock_client,
                    model_id=model_id,
                    images_bytes_list=images_bytes_list,
                    batch_size=2,
                    sleep_sec=1
                )
                
                # 使用 Claude 解析履歷文字
                user_message = {
                    "role": "user",
                    "content": [{"text": f"Resume Raw Json Data 為: {resume_text_content}"}]
                }
                
            else:
                # 處理 JSON 格式（原來的邏輯）
                logger.info("偵測到 JSON 檔案，進行 JSON 解析...")
                body = file_content_bytes.decode("utf-8")
                
                user_message = {
                    "role": "user",
                    "content": [{"text": f"Resume Raw Json Data 為: {body}"}]
                }

            # 使用 Claude 解析履歷
            response = bedrock_client.converse(
                modelId=model_id,
                messages=[user_message],
                system=system_prompt,
                inferenceConfig=inference_config
            )
            
            result = json.loads(response['output']['message']["content"][0]["text"])
            logger.info(f"Claude 解析成功，解析結果大小: {len(str(result))} 字元")
            
            logger.info(f"Claude 解析完成，解析結果{result}")
            
        except Exception as e:
            logger.error(f"檔案處理或 Claude 解析失敗: {str(e)}")
            continue

        # 寫入解析後的履歷到 S3 parsed bucket
        try:
            output_s3_key = generate_output_key(key)
            s3.put_object(
                Bucket=parsed_output_s3_bucket,
                Key=output_s3_key,
                Body=json.dumps(result, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json; charset=utf-8"
            )
            logger.info(f"成功寫入解析結果到 S3: {output_s3_key}")
        except Exception as e:
            logger.error(f"寫入 S3 parsed bucket 失敗: {str(e)}")
            continue

        # 提取基本資訊用於 DynamoDB
        basic_info = extract_basic_info(result.get('profile', {}))
        
        # 準備寫入 DynamoDB 的資料 - 按照 dataflow.md 的完整 profile 結構
        try:
            # 確保 profile 包含完整結構
            profile = result.get('profile', {})
            
            # 驗證並補充必要的結構
            if 'basics' not in profile:
                profile['basics'] = {}
            if 'educations' not in profile:
                profile['educations'] = []
            if 'trainings_and_certifications' not in profile:
                profile['trainings_and_certifications'] = []
            if 'professional_experiences' not in profile:
                profile['professional_experiences'] = []
            if 'awards' not in profile:
                profile['awards'] = []
            
            # 清理資料
            cleaned_profile = clean_for_dynamodb(profile)
            if cleaned_profile is None:
                logger.error(f"清理後的 profile 為空，跳過寫入: {profile}")
                continue
            
            # 驗證並修正 profile 資料結構
            validated_profile = validate_and_fix_profile(cleaned_profile)
            if validated_profile is None:
                logger.error(f"驗證後的 profile 為空，跳過寫入: {cleaned_profile}")
                continue
            
            dynamodb_item = {
                # 主鍵和基本識別資訊
                'resume_id': resume_id,
                'team_id': team_id,
                'job_id': job_id,
                's3_key': key,
                'parsed_s3_key': output_s3_key,
                'has_applied': True,
                
                # 候選人基本資訊（從解析資料中提取，用於快速查詢）
                'candidate_name': basic_info['candidate_name'],
                'candidate_email': basic_info['candidate_email'],
                'current_title': basic_info['current_title'],
                
                # 完整的 profile 結構（包含所有 dataflow.md 定義的欄位）
                'profile': validated_profile,
                
                # 時間戳記
                'processed_at': datetime.utcnow().isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # 寫入 DynamoDB
            table.put_item(Item=dynamodb_item)
            logger.info(f"成功寫入 DynamoDB: resume_id={resume_id}, team_id={team_id}, job_id={job_id}")
            logger.info(f"候選人資訊: {basic_info['candidate_name']}, 信箱: {basic_info['candidate_email']}")
            logger.info(f"Profile 結構包含: basics, educations({len(validated_profile.get('educations', []))})項, trainings_and_certifications({len(validated_profile.get('trainings_and_certifications', []))})項, professional_experiences({len(validated_profile.get('professional_experiences', []))})項, awards({len(validated_profile.get('awards', []))})項")
            
        except Exception as e:
            logger.error(f"寫入 DynamoDB 失敗: {str(e)}")
            continue

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': '履歷解析完成',
            'processed_files': len(event["Records"])
        })
    }