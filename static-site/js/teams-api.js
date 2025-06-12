// teams-api.js - API 呼叫邏輯

class TeamsAPI {
    constructor() {
        // ✅ 使用統一配置系統
        this.baseURL = this.getApiBaseUrl();
        this.endpoints = {
            teams: '/teams'
        };
        
        console.log('🔗 團隊 API 配置:', { baseURL: this.baseURL });
    }

    /**
     * 取得 API Base URL
     */
    getApiBaseUrl() {
        // 優先使用 Terraform 生成的配置
        if (window.CONFIG) {
            return window.CONFIG.API_BASE_URL;
        }
        
        // 後備配置 - 從 meta 標籤讀取
        const meta = document.querySelector('meta[name="api-base-url"]');
        return meta ? meta.getAttribute('content') : 'https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev';
    }

    /**
     * 取得所有團隊
     */
    async getAllTeams() {
        try {
            const response = await fetch(`${this.baseURL}${this.endpoints.teams}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                // 改進錯誤處理：先獲取響應文本，再嘗試解析 JSON
                const errorText = await response.text();
                let errorMessage = `HTTP error! status: ${response.status}`;
                
                try {
                    if (errorText.trim()) {
                        const errorData = JSON.parse(errorText);
                        errorMessage = errorData.error || errorData.message || errorMessage;
                    }
                } catch (parseError) {
                    // 如果無法解析為 JSON，使用原始文本
                    errorMessage = errorText || errorMessage;
                }
                
                throw new Error(errorMessage);
            }

            // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
            const responseText = await response.text();
            
            if (!responseText.trim()) {
                throw new Error('伺服器回傳空響應');
            }
            
            const data = JSON.parse(responseText);
            // 處理可能的資料結構差異
            return {
                success: true,
                data: {
                    teams: Array.isArray(data) ? data : (data.teams || [])
                }
            };
        } catch (error) {
            console.error('取得團隊列表失敗:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * 取得單一團隊
     */
    async getTeam(teamId) {
        try {
            const response = await fetch(`${this.baseURL}${this.endpoints.teams}/${teamId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                // 改進錯誤處理：先獲取響應文本，再嘗試解析 JSON
                const errorText = await response.text();
                let errorMessage = `HTTP error! status: ${response.status}`;
                
                try {
                    if (errorText.trim()) {
                        const errorData = JSON.parse(errorText);
                        errorMessage = errorData.error || errorData.message || errorMessage;
                    }
                } catch (parseError) {
                    // 如果無法解析為 JSON，使用原始文本
                    errorMessage = errorText || errorMessage;
                }
                
                throw new Error(errorMessage);
            }

            // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
            const responseText = await response.text();
            
            if (!responseText.trim()) {
                throw new Error('伺服器回傳空響應');
            }
            
            const data = JSON.parse(responseText);
            return {
                success: true,
                data: data
            };
        } catch (error) {
            console.error('取得團隊資料失敗:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * 建立新團隊
     */
    async createTeam(teamData) {
        try {
            const response = await fetch(`${this.baseURL}${this.endpoints.teams}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(teamData)
            });

            if (!response.ok) {
                // 改進錯誤處理：先獲取響應文本，再嘗試解析 JSON
                const errorText = await response.text();
                let errorMessage = `HTTP error! status: ${response.status}`;
                
                try {
                    if (errorText.trim()) {
                        const errorData = JSON.parse(errorText);
                        errorMessage = errorData.error || errorData.message || errorMessage;
                    }
                } catch (parseError) {
                    // 如果無法解析為 JSON，使用原始文本
                    errorMessage = errorText || errorMessage;
                }
                
                throw new Error(errorMessage);
            }

            // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
            const responseText = await response.text();
            
            if (!responseText.trim()) {
                throw new Error('伺服器回傳空響應');
            }
            
            const data = JSON.parse(responseText);
            return {
                success: true,
                data: data
            };
        } catch (error) {
            console.error('建立團隊失敗:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * 更新團隊資料 (支援檔案上傳和刪除) - 統一使用 Lambda update_team 方法
     */
    async updateTeam(teamId, teamData, newFiles = [], deletedFiles = []) {
        try {
            console.log('📤 TeamsAPI.updateTeam 調用 (統一版本):', {
                teamId,
                teamData,
                newFilesCount: newFiles.length,
                deletedFilesCount: deletedFiles.length
            });

            // 智能選擇請求格式：有實際檔案上傳時用 FormData，否則用 JSON
            let response;
            
            if (newFiles.length > 0) {
                // 有檔案上傳，使用 FormData
                console.log('📤 有檔案上傳，使用 multipart/form-data 格式');
                const formData = new FormData();
                
                // 添加基本團隊資料
                if (Object.keys(teamData).length > 0) {
                    formData.append('team_data', JSON.stringify(teamData));
                    console.log('📝 添加團隊基本資料:', JSON.stringify(teamData));
                }
                
                // 添加要刪除的檔案列表
                if (deletedFiles.length > 0) {
                    formData.append('files_to_delete', JSON.stringify(deletedFiles));
                    console.log('🗑️ 添加待刪除檔案列表:', deletedFiles);
                }
                
                // 添加新檔案
                newFiles.forEach((file, index) => {
                    formData.append('files', file);
                    console.log(`📎 添加檔案 ${index + 1}:`, file.name);
                });

                response = await fetch(`${this.baseURL}${this.endpoints.teams}/${teamId}`, {
                    method: 'PUT',
                    body: formData
                    // 不設置 Content-Type，讓瀏覽器自動設置 multipart/form-data boundary
                });
                
            } else {
                // 沒有檔案上傳，使用 JSON 格式
                console.log('📝 沒有檔案上傳，使用 application/json 格式');
                const requestBody = {
                    ...teamData
                };
                
                // 如果有檔案要刪除，加入到 JSON 中
                if (deletedFiles.length > 0) {
                    requestBody.files_to_delete = deletedFiles;
                    console.log('🗑️ 添加待刪除檔案列表到 JSON:', deletedFiles);
                }
                
                console.log('📋 JSON 請求體:', requestBody);
                
                response = await fetch(`${this.baseURL}${this.endpoints.teams}/${teamId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                });
            }

            console.log('🚀 發送統一更新請求完成');

            // 5. 處理響應
            const responseText = await response.text();
            console.log('📥 收到響應:', response.status, responseText);

            if (!response.ok) {
                let errorMessage = `團隊更新失敗 HTTP ${response.status}`;
                
                try {
                    if (responseText.trim()) {
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.error || errorData.message || errorMessage;
                    }
                } catch (parseError) {
                    errorMessage = responseText || errorMessage;
                }
                
                throw new Error(errorMessage);
            }

            // 6. 解析成功響應
            let result = null;
            if (responseText.trim()) {
                try {
                    result = JSON.parse(responseText);
                    console.log('✅ 團隊更新成功:', result);
                } catch (parseError) {
                    console.warn('⚠️ 響應解析失敗，但操作可能成功:', parseError);
                    result = {
                        success: true,
                        message: '團隊更新完成',
                        team_id: teamId,
                        raw_response: responseText
                    };
                }
            } else {
                result = {
                    success: true,
                    message: '團隊更新完成',
                    team_id: teamId
                };
            }

            // 7. 統一返回格式
            return {
                success: true,
                data: result,
                operations: {
                    basic_data_updated: Object.keys(teamData).length > 0,
                    files_deleted: deletedFiles.length,
                    files_uploaded: newFiles.length
                }
            };

        } catch (error) {
            console.error('❌ TeamsAPI.updateTeam 失敗:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * 刪除團隊
     */
    async deleteTeam(teamId) {
        try {
            const response = await fetch(`${this.baseURL}${this.endpoints.teams}/${teamId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                // 改進錯誤處理：先獲取響應文本，再嘗試解析 JSON
                const errorText = await response.text();
                let errorMessage = `HTTP error! status: ${response.status}`;
                
                try {
                    if (errorText.trim()) {
                        const errorData = JSON.parse(errorText);
                        errorMessage = errorData.error || errorData.message || errorMessage;
                    }
                } catch (parseError) {
                    // 如果無法解析為 JSON，使用原始文本
                    errorMessage = errorText || errorMessage;
                }
                
                throw new Error(errorMessage);
            }

            // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
            const responseText = await response.text();
            
            if (!responseText.trim()) {
                throw new Error('伺服器回傳空響應');
            }
            
            const data = JSON.parse(responseText);
            return {
                success: true,
                data: data
            };
        } catch (error) {
            console.error('刪除團隊失敗:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * 產生團隊 ID 預覽
     */
    generateTeamIdPreview(companyCode, deptCode, teamCode) {
        if (!companyCode || !deptCode || !teamCode) {
            return '';
        }
        return `${companyCode.toUpperCase()}-${deptCode.toUpperCase()}-${teamCode.toUpperCase()}`;
    }

    /**
     * 驗證表單資料
     */
    validateTeamData(formData) {
        const errors = [];
        const warnings = [];

        // 必填欄位檢查（嚴重錯誤）
        const requiredFields = ['company', 'department', 'team_name'];
        requiredFields.forEach(field => {
            if (!formData[field] || formData[field].trim() === '') {
                errors.push(`${this.getFieldLabel(field)} 為必填欄位`);
            }
        });

        // 代碼格式檢查（警告）
        if (formData.company_code && !/^[a-zA-Z0-9]{2,8}$/.test(formData.company_code)) {
            warnings.push('公司代碼建議為 2-8 個英文字母或數字');
        }

        if (formData.dept_code && !/^[a-zA-Z0-9]{2,10}$/.test(formData.dept_code)) {
            warnings.push('部門代碼建議為 2-10 個英文字母或數字');
        }

        if (formData.team_code && !/^[a-zA-Z0-9]{2,8}$/.test(formData.team_code)) {
            warnings.push('團隊代碼建議為 2-8 個英文字母或數字');
        }

        return {
            isValid: errors.length === 0,
            hasWarnings: warnings.length > 0,
            errors: errors,
            warnings: warnings
        };
    }

    /**
     * 取得欄位中文標籤
     */
    getFieldLabel(field) {
        const labels = {
            'company': '公司名稱',
            'company_code': '公司代碼',
            'department': '部門名稱',
            'dept_code': '部門代碼',
            'team_name': '團隊名稱',
            'team_code': '團隊代碼'
        };
        return labels[field] || field;
    }
}

// 建立全域 API 實例
window.teamsAPI = new TeamsAPI();
