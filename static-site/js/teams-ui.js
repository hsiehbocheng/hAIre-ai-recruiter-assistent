// teams-ui.js - 頁面互動邏輯

class TeamsUI {
    constructor() {
        this.currentEditingTeamId = null;
        this.allTeams = [];
        this.filteredTeams = [];
        this.init();
    }

    /**
     * 初始化頁面
     */
    init() {
        this.bindEvents();
        this.loadTeams();
    }

    /**
     * 綁定事件監聽器
     */
    bindEvents() {
        // 表單提交
        document.getElementById('teamForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit();
        });

        // 取消編輯
        document.getElementById('cancelBtn').addEventListener('click', () => {
            this.resetForm();
        });

        // 重新載入
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadTeams();
        });

        // 搜尋
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.performSearch();
        });

        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });

        // 即時搜尋
        document.getElementById('searchInput').addEventListener('input', () => {
            this.performSearch();
        });

        // 公司篩選
        document.getElementById('companyFilter').addEventListener('change', () => {
            this.performSearch();
        });

        // 即時預覽團隊 ID
        ['company_code', 'dept_code', 'team_code'].forEach(fieldId => {
            document.getElementById(fieldId).addEventListener('input', () => {
                this.updateTeamIdPreview();
            });
        });
    }

    /**
     * 載入團隊列表
     */
    async loadTeams() {
        this.showLoading();
        
        const result = await teamsAPI.getAllTeams();
        
        if (result.success) {
            this.allTeams = result.data.teams || [];
            this.filteredTeams = [...this.allTeams];
            this.renderTeams();
            this.updateCompanyFilter();
            this.hideLoading();
        } else {
            this.hideLoading();
            this.showToast('錯誤', result.error, 'error');
        }
    }

    /**
     * 顯示載入狀態
     */
    showLoading() {
        document.getElementById('loadingSpinner').style.display = 'block';
        document.getElementById('teamsContainer').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';
    }

    /**
     * 隱藏載入狀態
     */
    hideLoading() {
        document.getElementById('loadingSpinner').style.display = 'none';
        
        if (this.filteredTeams.length > 0) {
            document.getElementById('teamsContainer').style.display = 'block';
            document.getElementById('emptyState').style.display = 'none';
        } else {
            document.getElementById('teamsContainer').style.display = 'none';
            document.getElementById('emptyState').style.display = 'block';
        }
    }

    /**
     * 渲染團隊列表
     */
    renderTeams() {
        const container = document.getElementById('teamsGrid');
        container.innerHTML = '';

        this.filteredTeams.forEach(team => {
            const card = this.createTeamCard(team);
            container.appendChild(card);
        });
    }

    /**
     * 建立團隊卡片
     */
    createTeamCard(team) {
        const card = document.createElement('div');
        card.className = 'team-card';
        
        const description = team.team_description ? 
            `<div class="description">${team.team_description}</div>` : '';
        
        card.innerHTML = `
            <div class="team-card-header">
                <code class="team-id">${team.team_id}</code>
                <div class="team-actions">
                    <button type="button" class="btn-edit" onclick="teamsUI.editTeam('${team.team_id}')">
                        <i class="fas fa-edit"></i> 編輯
                    </button>
                    <button type="button" class="btn-delete" onclick="teamsUI.deleteTeam('${team.team_id}')">
                        <i class="fas fa-trash"></i> 刪除
                    </button>
                </div>
            </div>
            <div class="team-info">
                <h3>${team.team_name}</h3>
                <div class="company">${team.company}</div>
                <div class="department">${team.department}</div>
                <div class="codes">代碼：${team.company_code} - ${team.dept_code} - ${team.team_code}</div>
                ${description}
                <div class="created-at">建立於 ${this.formatDate(team.created_at)}</div>
            </div>
        `;
        
        return card;
    }

    /**
     * 處理表單提交
     */
    async handleFormSubmit() {
        const formData = this.getFormData();
        
        // 驗證資料
        const validation = teamsAPI.validateTeamData(formData);
        if (!validation.isValid) {
            this.showToast('驗證錯誤', validation.errors.join('<br>'), 'error');
            return;
        }

        // 設定按鈕載入狀態
        const submitBtn = document.getElementById('submitBtn');
        const originalHTML = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 處理中...';
        submitBtn.disabled = true;

        let result;
        if (this.currentEditingTeamId) {
            // 更新團隊
            result = await teamsAPI.updateTeam(this.currentEditingTeamId, formData);
        } else {
            // 建立新團隊
            result = await teamsAPI.createTeam(formData);
        }

        // 恢復按鈕狀態
        submitBtn.innerHTML = originalHTML;
        submitBtn.disabled = false;

        if (result.success) {
            const action = this.currentEditingTeamId ? '更新' : '建立';
            this.showToast('成功', `團隊${action}成功！`, 'success');
            this.resetForm();
            this.loadTeams();
        } else {
            this.showToast('錯誤', result.error, 'error');
        }
    }

    /**
     * 取得表單資料
     */
    getFormData() {
        const form = document.getElementById('teamForm');
        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            data[key] = value.trim();
        }
        
        return data;
    }

    /**
     * 編輯團隊
     */
    async editTeam(teamId) {
        const team = this.allTeams.find(t => t.team_id === teamId);
        if (!team) {
            this.showToast('錯誤', '找不到團隊資料', 'error');
            return;
        }

        // 填入表單
        document.getElementById('company').value = team.company;
        document.getElementById('company_code').value = team.company_code;
        document.getElementById('department').value = team.department;
        document.getElementById('dept_code').value = team.dept_code;
        document.getElementById('team_name').value = team.team_name;
        document.getElementById('team_code').value = team.team_code;
        document.getElementById('team_description').value = team.team_description || '';

        // 設定編輯模式
        this.currentEditingTeamId = teamId;
        document.getElementById('submitBtn').innerHTML = '<i class="fas fa-save"></i> 更新團隊';
        document.getElementById('cancelBtn').style.display = 'inline-flex';

        // 更新預覽
        this.updateTeamIdPreview();

        // 滾動到表單
        document.getElementById('teamForm').scrollIntoView({ behavior: 'smooth' });
    }

    /**
     * 刪除團隊
     */
    async deleteTeam(teamId) {
        const team = this.allTeams.find(t => t.team_id === teamId);
        if (!team) {
            this.showToast('錯誤', '找不到團隊資料', 'error');
            return;
        }

        if (!confirm(`確定要刪除團隊「${team.team_name}」嗎？\n\n此操作無法復原。`)) {
            return;
        }

        const result = await teamsAPI.deleteTeam(teamId);
        
        if (result.success) {
            this.showToast('成功', '團隊刪除成功！', 'success');
            this.loadTeams();
            
            // 如果正在編輯這個團隊，重設表單
            if (this.currentEditingTeamId === teamId) {
                this.resetForm();
            }
        } else {
            this.showToast('錯誤', result.error, 'error');
        }
    }

    /**
     * 重設表單
     */
    resetForm() {
        document.getElementById('teamForm').reset();
        this.currentEditingTeamId = null;
        document.getElementById('submitBtn').innerHTML = '<i class="fas fa-save"></i> 建立團隊';
        document.getElementById('cancelBtn').style.display = 'none';
        this.updateTeamIdPreview();
    }

    /**
     * 更新團隊 ID 預覽
     */
    updateTeamIdPreview() {
        const companyCode = document.getElementById('company_code').value.trim();
        const deptCode = document.getElementById('dept_code').value.trim();
        const teamCode = document.getElementById('team_code').value.trim();
        
        const previewSection = document.getElementById('previewSection');
        const previewId = document.getElementById('previewId');
        
        if (companyCode && deptCode && teamCode) {
            const preview = teamsAPI.generateTeamIdPreview(companyCode, deptCode, teamCode);
            previewId.textContent = preview;
            previewSection.style.display = 'block';
        } else {
            previewSection.style.display = 'none';
        }
    }

    /**
     * 執行搜尋
     */
    performSearch() {
        const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
        const selectedCompany = document.getElementById('companyFilter').value;

        this.filteredTeams = this.allTeams.filter(team => {
            const matchesSearch = !searchTerm || 
                team.team_name.toLowerCase().includes(searchTerm) ||
                team.company.toLowerCase().includes(searchTerm) ||
                team.department.toLowerCase().includes(searchTerm) ||
                team.team_id.toLowerCase().includes(searchTerm) ||
                (team.team_description && team.team_description.toLowerCase().includes(searchTerm));

            const matchesCompany = !selectedCompany || team.company === selectedCompany;

            return matchesSearch && matchesCompany;
        });

        this.renderTeams();
        this.hideLoading();
    }

    /**
     * 更新公司篩選器
     */
    updateCompanyFilter() {
        const companies = [...new Set(this.allTeams.map(team => team.company))];
        const select = document.getElementById('companyFilter');
        
        // 保存當前選擇
        const currentValue = select.value;
        
        // 清空現有選項（保留「所有公司」）
        select.innerHTML = '<option value="">所有公司</option>';
        
        companies.forEach(company => {
            const option = document.createElement('option');
            option.value = company;
            option.textContent = company;
            select.appendChild(option);
        });
        
        // 恢復選擇
        select.value = currentValue;
    }

    /**
     * 格式化日期
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * 顯示 Toast 訊息
     */
    showToast(title, message, type = 'info') {
        const toast = document.getElementById('messageToast');
        const toastIcon = document.getElementById('toastIcon');
        const toastTitle = document.getElementById('toastTitle');
        const toastMessage = document.getElementById('toastMessage');

        // 設定圖示和樣式
        const configs = {
            success: { icon: 'fas fa-check-circle', class: 'success' },
            error: { icon: 'fas fa-exclamation-circle', class: 'error' },
            info: { icon: 'fas fa-info-circle', class: 'info' }
        };

        const config = configs[type] || configs.info;
        
        // 移除舊的類別
        toast.classList.remove('success', 'error', 'info');
        // 添加新的類別
        toast.classList.add(config.class);
        
        toastIcon.innerHTML = `<i class="${config.icon}"></i>`;
        toastTitle.textContent = title;
        toastMessage.innerHTML = message;

        // 顯示 Toast
        toast.style.display = 'flex';
        
        // 3秒後自動隱藏
        setTimeout(() => {
            this.hideToast();
        }, 3000);
    }

    /**
     * 隱藏 Toast
     */
    hideToast() {
        const toast = document.getElementById('messageToast');
        toast.style.display = 'none';
    }
}

// 全域函數
function hideToast() {
    if (window.teamsUI) {
        window.teamsUI.hideToast();
    }
}

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', () => {
    window.teamsUI = new TeamsUI();
});
