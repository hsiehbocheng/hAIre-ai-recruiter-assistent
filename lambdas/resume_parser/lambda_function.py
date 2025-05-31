import os, json, urllib.parse
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)  # 或 DEBUG, WARNING, ERROR

bedrock_client = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
temperature = 0.0
maxTokens = 8192
inference_config = {"temperature": temperature, "maxTokens": maxTokens}
system_prompt = [{"text": """請依照下列步驟處理： 1. 讀取變數 Resume Raw Json Data 中的履歷原始資料。 2. 解析並重組成以下 **完整且相同欄位結構** 的 JSON。 3. **僅**輸出 JSON，本身不得夾帶任何說明、換行之外的文字，或多餘欄位。 ## 輸出格式範例 預期輸出格式如以下（鍵名與巢狀結構不得變動，只需依照實際資料填入對應值）： "profile": { "basics": { "first_name": <string>, "last_name": <string>, "gender": <"male" | "female" | "other" | "unknown">, "emails": [<string>, ...], "urls": [<string>, ...], "date_of_birth": { "year": <integer>, "month": <integer>, "day": <integer> }, "age": <integer>, // 若生日資訊不足以計算，填 null "total_experience_in_years": <integer>, // 四捨五入到整數；無法判斷填 null "current_title": <string>, "skills": [<string>, ...] }, "educations": [{ "start_year": <integer>, "is_current": <boolean>, "end_year": <integer>, // 若 is_current 為 true 可填 null "issuing_organization":<string>, "study_type": <string>, "department": <string>, "description": <string> }], "trainings_and_certifications": [{ "year": <integer>, "issuing_organization":<string>, "description": <string> }], "professional_experiences": [{ "start_year": <integer>, "start_month": <integer>, "is_current": <boolean>, "end_year": <integer>, "end_month": <integer>, "duration_in_months": <integer>, // 若未提供可自行計算；無法判斷填 null "company": <string>, "location": <string>, "title": <string>, "description": <string> }], "awards": [{ "year": <integer>, "title": <string>, "description": <string> }] } **切記：最終輸出僅能是以上 JSON，本行與其他說明文字皆不得包含。"""}]

s3 = boto3.client("s3")
parsed_output_s3_bucket = os.environ["PARSED_BUCKET"]

def extract_filename(key: str) -> str:
    """取得 key 中最後一段檔名，解碼後回傳"""
    filename = os.path.basename(key)
    filename = urllib.parse.unquote(filename) 
    return filename

def generate_output_key(key: str) -> str:
    """
    保留原始 key 的 prefix 路徑，只在檔名前加上 parsed-
    範例:
      輸入: 20250522/resume#job#cxidataci#dsa001#104-resume-benson003.json
      輸出: 20250522/parsed-resume#job#cxidataci#dsa001#104-resume-benson003.json
    """
    key = urllib.parse.unquote(key)  # decode URL encoding (%23 ➝ #)
    dir_name = os.path.dirname(key)  # 20250522
    base_name = os.path.basename(key)  # resume#job#...
    new_base = f"parsed-{base_name}"
    return f"{dir_name}/{new_base}"

def lambda_handler(event, context):
    logger.info(event)
    for rec in event["Records"]:

        bucket = rec["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(rec["s3"]["object"]["key"])
        logger.info(f"Received S3 event - bucket: {bucket}, key: {key}")

        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        logger.info(body)

        user_message = {
            "role": "user",
            "content": [{"text": f"Resume Raw Json Data 為: {body}"}]
        }

        response = bedrock_client.converse(
            modelId = model_id,
            messages=[user_message],
            system=system_prompt,
            inferenceConfig = inference_config
        )
        result = json.loads(response['output']['message']["content"][0]["text"])
        logger.info(result)

        output_s3_key = generate_output_key(key)
        s3.put_object(
            Bucket=parsed_output_s3_bucket,
            Key=output_s3_key,
            Body=json.dumps(result, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json; charset=utf-8"
        )

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
