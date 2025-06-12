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
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return {
                success: true,
                data: data
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
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
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
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
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
     * 更新團隊資料
     */
    async updateTeam(teamId, teamData) {
        try {
            const response = await fetch(`${this.baseURL}${this.endpoints.teams}/${teamId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(teamData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return {
                success: true,
                data: data
            };
        } catch (error) {
            console.error('更新團隊失敗:', error);
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
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
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

        // 必填欄位檢查
        const requiredFields = ['company', 'company_code', 'department', 'dept_code', 'team_name', 'team_code'];
        requiredFields.forEach(field => {
            if (!formData[field] || formData[field].trim() === '') {
                errors.push(`${this.getFieldLabel(field)} 為必填欄位`);
            }
        });

        // 代碼格式檢查
        if (formData.company_code && !/^[a-zA-Z0-9]{2,8}$/.test(formData.company_code)) {
            errors.push('公司代碼必須為 2-8 個英文字母或數字');
        }

        if (formData.dept_code && !/^[a-zA-Z0-9]{2,10}$/.test(formData.dept_code)) {
            errors.push('部門代碼必須為 2-10 個英文字母或數字');
        }

        if (formData.team_code && !/^[a-zA-Z0-9]{2,8}$/.test(formData.team_code)) {
            errors.push('團隊代碼必須為 2-8 個英文字母或數字');
        }

        return {
            isValid: errors.length === 0,
            errors: errors
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
