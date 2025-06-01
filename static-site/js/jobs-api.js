/**
 * 職缺管理 API 模組
 * 處理與後端 Lambda 函數的所有通訊
 */

// ✅ 簡化配置系統 - 直接使用全域CONFIG
const getApiConfig = () => {
    // 優先使用 Terraform 生成的配置
    if (window.CONFIG) {
        return {
            jobsUrl: `${window.CONFIG.API_BASE_URL}/jobs`,
            teamsUrl: `${window.CONFIG.API_BASE_URL}/teams`
        };
    }
    
    // 後備配置 - 從 meta 標籤讀取
    const meta = document.querySelector('meta[name="api-base-url"]');
    const baseUrl = meta ? meta.getAttribute('content') : 'https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev';
    
    return {
        jobsUrl: `${baseUrl}/jobs`,
        teamsUrl: `${baseUrl}/teams`
    };
};

const apiConfig = getApiConfig();
const JOBS_API_BASE_URL = apiConfig.jobsUrl;
const TEAMS_API_BASE_URL = apiConfig.teamsUrl;

console.log('🔗 職缺 API 配置:', { JOBS_API_BASE_URL, TEAMS_API_BASE_URL });

/**
 * HTTP 請求處理器
 */
class JobsApiClient {
    constructor() {
        this.baseUrl = JOBS_API_BASE_URL;
        this.teamsBaseUrl = TEAMS_API_BASE_URL;
    }

    /**
     * 發送 HTTP 請求的通用方法
     */
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const config = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API 請求失敗:', error);
            throw error;
        }
    }

    /**
     * 建立新職缺
     * @param {Object} jobData - 職缺資料
     * @returns {Promise<Object>} 建立結果
     */
    async createJob(jobData) {
        return await this.request(this.baseUrl, {
            method: 'POST',
            body: JSON.stringify(jobData),
        });
    }

    /**
     * 取得職缺列表
     * @param {Object} params - 查詢參數
     * @returns {Promise<Object>} 職缺列表和分頁資訊
     */
    async getJobs(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${this.baseUrl}?${queryString}` : this.baseUrl;
        return await this.request(url);
    }

    /**
     * 取得單一職缺
     * @param {string} jobId - 職缺 ID
     * @returns {Promise<Object>} 職缺詳細資料
     */
    async getJob(jobId) {
        return await this.request(`${this.baseUrl}/${jobId}`);
    }

    /**
     * 更新職缺
     * @param {string} jobId - 職缺 ID
     * @param {Object} jobData - 更新的職缺資料
     * @returns {Promise<Object>} 更新結果
     */
    async updateJob(jobId, jobData) {
        return await this.request(`${this.baseUrl}/${jobId}`, {
            method: 'PUT',
            body: JSON.stringify(jobData),
        });
    }

    /**
     * 刪除職缺（軟刪除）
     * @param {string} jobId - 職缺 ID
     * @returns {Promise<Object>} 刪除結果
     */
    async deleteJob(jobId) {
        return await this.request(`${this.baseUrl}/${jobId}`, {
            method: 'DELETE',
        });
    }

    /**
     * 取得團隊列表（用於職缺表單）
     * @returns {Promise<Object>} 團隊列表
     */
    async getTeams() {
        return await this.request(this.teamsBaseUrl);
    }

    /**
     * 取得職缺統計資料
     * @returns {Promise<Object>} 統計資料
     */
    async getJobStats() {
        try {
            // 取得所有狀態的職缺進行統計
            const [activeJobs, pausedJobs, closedJobs] = await Promise.all([
                this.getJobs({ status: 'active', limit: 1000 }),
                this.getJobs({ status: 'paused', limit: 1000 }),
                this.getJobs({ status: 'closed', limit: 1000 })
            ]);

            const totalViews = [
                ...activeJobs.data,
                ...pausedJobs.data,
                ...closedJobs.data
            ].reduce((sum, job) => sum + (job.view_count || 0), 0);

            return {
                totalJobs: activeJobs.pagination.total_items + pausedJobs.pagination.total_items + closedJobs.pagination.total_items,
                activeJobs: activeJobs.pagination.total_items,
                pausedJobs: pausedJobs.pagination.total_items,
                closedJobs: closedJobs.pagination.total_items,
                totalViews: totalViews
            };
        } catch (error) {
            console.error('取得職缺統計失敗:', error);
            return {
                totalJobs: 0,
                activeJobs: 0,
                pausedJobs: 0,
                closedJobs: 0,
                totalViews: 0
            };
        }
    }

    /**
     * 批次操作職缺狀態
     * @param {Array} jobIds - 職缺 ID 陣列
     * @param {string} status - 新狀態
     * @returns {Promise<Array>} 批次操作結果
     */
    async batchUpdateJobStatus(jobIds, status) {
        const promises = jobIds.map(jobId => 
            this.updateJob(jobId, { status })
        );

        try {
            const results = await Promise.allSettled(promises);
            return results.map((result, index) => ({
                jobId: jobIds[index],
                success: result.status === 'fulfilled',
                error: result.status === 'rejected' ? result.reason.message : null
            }));
        } catch (error) {
            console.error('批次更新職缺狀態失敗:', error);
            throw error;
        }
    }

    /**
     * 搜尋職缺
     * @param {string} searchTerm - 搜尋關鍵字
     * @param {Object} filters - 篩選條件
     * @returns {Promise<Object>} 搜尋結果
     */
    async searchJobs(searchTerm, filters = {}) {
        const params = {
            search: searchTerm,
            ...filters
        };

        // 移除空值
        Object.keys(params).forEach(key => {
            if (params[key] === '' || params[key] === null || params[key] === undefined) {
                delete params[key];
            }
        });

        return await this.getJobs(params);
    }

    /**
     * 取得職缺的相關統計（瀏覽數、申請數等）
     * @param {string} jobId - 職缺 ID
     * @returns {Promise<Object>} 職缺統計
     */
    async getJobAnalytics(jobId) {
        try {
            const job = await this.getJob(jobId);
            return {
                viewCount: job.data.view_count || 0,
                applicationCount: job.data.application_count || 0,
                // 未來可以加入更多分析資料
            };
        } catch (error) {
            console.error('取得職缺分析資料失敗:', error);
            return {
                viewCount: 0,
                applicationCount: 0
            };
        }
    }

    /**
     * 複製職缺
     * @param {string} jobId - 要複製的職缺 ID
     * @returns {Promise<Object>} 新建職缺結果
     */
    async duplicateJob(jobId) {
        try {
            const originalJob = await this.getJob(jobId);
            const jobData = originalJob.data;

            // 移除不需要複製的欄位
            const {
                job_id,
                created_at,
                updated_at,
                view_count,
                application_count,
                ai_parsed,
                ...duplicateData
            } = jobData;

            // 修改標題以表示這是複製的職缺
            duplicateData.job_title = `${duplicateData.job_title} (複製)`;
            duplicateData.status = 'paused'; // 複製的職缺預設為暫停狀態

            return await this.createJob(duplicateData);
        } catch (error) {
            console.error('複製職缺失敗:', error);
            throw error;
        }
    }

    /**
     * 匯出職缺資料
     * @param {Array} jobIds - 要匯出的職缺 ID 陣列（可選，不提供則匯出所有）
     * @returns {Promise<Array>} 職缺資料陣列
     */
    async exportJobs(jobIds = null) {
        try {
            if (jobIds && jobIds.length > 0) {
                // 匯出指定職缺
                const promises = jobIds.map(jobId => this.getJob(jobId));
                const results = await Promise.all(promises);
                return results.map(result => result.data);
            } else {
                // 匯出所有職缺
                const allJobs = await this.getJobs({ limit: 1000 });
                return allJobs.data;
            }
        } catch (error) {
            console.error('匯出職缺資料失敗:', error);
            throw error;
        }
    }
}

// 建立全域 API 客戶端實例
const jobsApi = new JobsApiClient();

/**
 * 格式化職缺資料的輔助函數
 */
const JobsFormatter = {
    /**
     * 格式化薪資範圍
     * @param {number} minSalary - 最低薪資
     * @param {number} maxSalary - 最高薪資
     * @returns {string} 格式化的薪資範圍
     */
    formatSalaryRange(minSalary, maxSalary) {
        if (!minSalary && !maxSalary) return '面議';
        if (!minSalary) return `最高 ${maxSalary.toLocaleString()} 元`;
        if (!maxSalary) return `${minSalary.toLocaleString()} 元起`;
        if (minSalary === maxSalary) return `${minSalary.toLocaleString()} 元`;
        return `${minSalary.toLocaleString()} - ${maxSalary.toLocaleString()} 元`;
    },

    /**
     * 格式化就業類型
     * @param {string} employmentType - 就業類型
     * @returns {string} 中文就業類型
     */
    formatEmploymentType(employmentType) {
        const types = {
            'full-time': '全職',
            'part-time': '兼職',
            'contract': '約聘',
            'internship': '實習',
            'freelance': '自由接案'
        };
        return types[employmentType] || employmentType;
    },

    /**
     * 格式化經驗等級
     * @param {string} experienceLevel - 經驗等級
     * @returns {string} 中文經驗等級
     */
    formatExperienceLevel(experienceLevel) {
        const levels = {
            'entry': '新手',
            'junior': '初級',
            'mid': '中級',
            'senior': '資深',
            'lead': '主管',
            'executive': '高階主管'
        };
        return levels[experienceLevel] || experienceLevel;
    },

    /**
     * 格式化工作模式
     * @param {string} remoteOption - 遠端選項
     * @returns {string} 中文工作模式
     */
    formatRemoteOption(remoteOption) {
        const options = {
            'onsite': '現場辦公',
            'remote': '完全遠端',
            'hybrid': '混合辦公'
        };
        return options[remoteOption] || remoteOption;
    },

    /**
     * 格式化日期
     * @param {string} dateString - ISO 日期字串
     * @returns {string} 格式化的日期
     */
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    },

    /**
     * 格式化相對時間
     * @param {string} dateString - ISO 日期字串
     * @returns {string} 相對時間描述
     */
    formatRelativeTime(dateString) {
        if (!dateString) return '';
        
        const now = new Date();
        const date = new Date(dateString);
        const diffInMs = now - date;
        const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
        const diffInDays = Math.floor(diffInHours / 24);

        if (diffInHours < 1) return '剛剛';
        if (diffInHours < 24) return `${diffInHours} 小時前`;
        if (diffInDays < 7) return `${diffInDays} 天前`;
        if (diffInDays < 30) return `${Math.floor(diffInDays / 7)} 週前`;
        if (diffInDays < 365) return `${Math.floor(diffInDays / 30)} 個月前`;
        return `${Math.floor(diffInDays / 365)} 年前`;
    },

    /**
     * 截斷文字
     * @param {string} text - 原始文字
     * @param {number} maxLength - 最大長度
     * @returns {string} 截斷後的文字
     */
    truncateText(text, maxLength = 100) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
};

/**
 * 錯誤處理輔助函數
 */
const JobsErrorHandler = {
    /**
     * 處理 API 錯誤
     * @param {Error} error - 錯誤物件
     * @returns {string} 使用者友善的錯誤訊息
     */
    handleApiError(error) {
        console.error('API 錯誤:', error);

        if (error.message.includes('404')) {
            return '找不到指定的資源';
        }
        if (error.message.includes('400')) {
            return '請求資料格式錯誤';
        }
        if (error.message.includes('401')) {
            return '身份驗證失敗';
        }
        if (error.message.includes('403')) {
            return '沒有權限執行此操作';
        }
        if (error.message.includes('500')) {
            return '伺服器內部錯誤，請稍後再試';
        }
        if (error.message.includes('Failed to fetch')) {
            return '網路連線失敗，請檢查網路連線';
        }

        return '操作失敗，請稍後再試';
    },

    /**
     * 顯示錯誤訊息
     * @param {string} message - 錯誤訊息
     */
    showError(message) {
        // 可以整合通知系統，目前使用 alert
        alert(`錯誤：${message}`);
    },

    /**
     * 顯示成功訊息
     * @param {string} message - 成功訊息
     */
    showSuccess(message) {
        // 可以整合通知系統，目前使用 alert
        alert(`成功：${message}`);
    }
}; 