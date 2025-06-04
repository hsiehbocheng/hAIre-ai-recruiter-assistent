#!/usr/bin/env python3
"""
清理 DynamoDB 中的舊欄位名稱
移除 department_code 和 section_code，只保留新的統一欄位 dept_code 和 team_code
"""

import boto3
import json
from botocore.exceptions import ClientError

def cleanup_old_fields():
    """清理舊欄位名稱"""
    dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
    teams_table = dynamodb.Table('benson-haire-teams')
    
    print("🔄 開始清理舊欄位...")
    
    try:
        # 掃描所有團隊資料
        response = teams_table.scan()
        teams = response['Items']
        
        updated_count = 0
        
        for team in teams:
            team_id = team['team_id']
            needs_update = False
            
            # 檢查是否有舊欄位需要移除
            old_fields_to_remove = []
            
            if 'department_code' in team:
                old_fields_to_remove.append('department_code')
                needs_update = True
                print(f"  - 團隊 {team_id}: 將移除 department_code = {team.get('department_code')}")
            
            if 'section_code' in team:
                old_fields_to_remove.append('section_code')
                needs_update = True
                print(f"  - 團隊 {team_id}: 將移除 section_code = {team.get('section_code')}")
            
            # 如果需要更新
            if needs_update:
                try:
                    # 使用 REMOVE 更新表達式移除舊欄位
                    update_expression = 'REMOVE ' + ', '.join(old_fields_to_remove)
                    
                    teams_table.update_item(
                        Key={'team_id': team_id},
                        UpdateExpression=update_expression
                    )
                    
                    updated_count += 1
                    print(f"✅ 團隊 {team_id} 舊欄位清理完成")
                    
                except ClientError as e:
                    print(f"❌ 團隊 {team_id} 更新失敗: {str(e)}")
            else:
                print(f"✓ 團隊 {team_id} 無需清理")
        
        print(f"\n🎉 清理完成！共處理了 {updated_count} 個團隊")
        
        # 驗證結果
        print("\n🔍 驗證清理結果...")
        response = teams_table.scan()
        teams = response['Items']
        
        remaining_old_fields = 0
        for team in teams:
            if 'department_code' in team or 'section_code' in team:
                remaining_old_fields += 1
                print(f"⚠️  團隊 {team['team_id']} 仍有舊欄位")
        
        if remaining_old_fields == 0:
            print("✅ 所有舊欄位已清理完成！")
        else:
            print(f"❌ 仍有 {remaining_old_fields} 個團隊包含舊欄位")
            
    except Exception as e:
        print(f"❌ 清理過程發生錯誤: {str(e)}")
        raise

if __name__ == "__main__":
    cleanup_old_fields() 