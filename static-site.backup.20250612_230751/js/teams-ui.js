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
     * 綁定事件
     */
    bindEvents() {
        // 搜尋功能
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                this.performSearch();
            });
        }

        // 公司篩選
        const companyFilter = document.getElementById('companyFilter');
        if (companyFilter) {
            companyFilter.addEventListener('change', () => {
                this.performSearch();
            });
        }

        // 表單提交 - 支援多種可能的按鈕 ID
        const submitButtons = ['submitBtn', 'createTeam', 'updateTeam'];
        submitButtons.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.handleFormSubmit();
                });
            }
        });

        // 取消按鈕
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.resetForm();
            });
        }

        // 即時預覽團隊 ID - 支援多種可能的欄位 ID
        const previewFields = [
            ['company_code', 'companyCode'],
            ['dept_code', 'deptCode'], 
            ['team_code', 'teamCode']
        ];
        
        previewFields.forEach(fieldIds => {
            fieldIds.forEach(fieldId => {
                const element = document.getElementById(fieldId);
                if (element) {
                    element.addEventListener('input', () => {
                        this.updateTeamIdPreview();
                    });
                }
            });
        });

        // 編輯表單的即時預覽
        const editPreviewFields = ['editCompanyCode', 'editDeptCode', 'editTeamCode'];
        editPreviewFields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element) {
                element.addEventListener('input', () => {
                    this.updateTeamIdPreview();
                });
            }
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
        card.className = 'col-md-6 col-lg-4 mb-3';
        
        // 處理不同的欄位名稱
        const teamName = team.team_name || '';
        const company = team.company || '';
        const department = team.department || '';
        const description = team.description || team.team_description || '';
        const companyCode = team.company_code || '';
        const deptCode = team.dept_code || '';
        const teamCode = team.team_code || '';
        const createdAt = team.created_at || '';
        
        card.innerHTML = `
            <div class="team-card">
                <div class="team-card-header">
                    <code class="team-id">${team.team_id}</code>
                    <div class="team-actions">
                        <button type="button" class="btn-view" onclick="teamsUI.viewTeam('${team.team_id}')" title="查看詳情">
                            <i class="fas fa-eye"></i> 查看
                        </button>
                        <button type="button" class="btn-edit" onclick="teamsUI.editTeam('${team.team_id}')" title="編輯團隊">
                            <i class="fas fa-edit"></i> 編輯
                        </button>
                        <button type="button" class="btn-delete" onclick="teamsUI.deleteTeam('${team.team_id}')" title="刪除團隊">
                            <i class="fas fa-trash"></i> 刪除
                        </button>
                    </div>
                </div>
                <div class="team-info">
                    <h3>${teamName}</h3>
                    <div class="company">${company}</div>
                    <div class="department">${department}</div>
                    <div class="codes">代碼：${companyCode} - ${deptCode} - ${teamCode}</div>
                    ${description ? `<div class="description">${description}</div>` : ''}
                    <div class="created-at">建立於 ${this.formatDate(createdAt)}</div>
                </div>
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
        // 嘗試兩種可能的表單 ID
        const form = document.getElementById('teamForm') || document.getElementById('addTeamForm');
        if (!form) {
            console.error('找不到團隊表單');
            return {};
        }
        
        // 手動收集表單資料，因為表單結構可能不同
        const data = {
            company: (document.getElementById('company') || document.getElementById('editCompany'))?.value?.trim() || '',
            company_code: (document.getElementById('company_code') || document.getElementById('companyCode') || document.getElementById('editCompanyCode'))?.value?.trim() || '',
            department: (document.getElementById('department') || document.getElementById('editDepartment'))?.value?.trim() || '',
            dept_code: (document.getElementById('dept_code') || document.getElementById('deptCode') || document.getElementById('editDeptCode'))?.value?.trim() || '',
            team_name: (document.getElementById('team_name') || document.getElementById('teamName') || document.getElementById('editTeamName'))?.value?.trim() || '',
            team_code: (document.getElementById('team_code') || document.getElementById('teamCode') || document.getElementById('editTeamCode'))?.value?.trim() || '',
            team_description: (document.getElementById('team_description') || document.getElementById('teamDescription') || document.getElementById('editTeamDescription'))?.value?.trim() || ''
        };
        
        return data;
    }

    /**
     * 編輯團隊
     */
    async editTeam(teamId) {
        console.log('🔧 TeamsUI: 開始編輯團隊:', teamId);
        
        const team = this.allTeams.find(t => t.team_id === teamId);
        if (!team) {
            console.error('❌ TeamsUI: 找不到團隊資料:', teamId);
            this.showToast('錯誤', '找不到團隊資料', 'error');
            return;
        }

        console.log('📋 TeamsUI: 載入團隊資料進行編輯:', team);

        // 填入表單 - 支援多種可能的 ID
        const setFieldValue = (ids, value) => {
            let success = false;
            for (const id of ids) {
                const element = document.getElementById(id);
                if (element) {
                    element.value = value || '';
                    console.log(`✅ 設定 ${id} = "${value}"`);
                    success = true;
                    break;
                }
            }
            if (!success) {
                console.warn(`⚠️  找不到欄位: ${ids.join(', ')}`);
            }
        };

        // 處理不同的欄位名稱
        setFieldValue(['company', 'editCompany'], team.company);
        setFieldValue(['company_code', 'companyCode', 'editCompanyCode'], team.company_code);
        setFieldValue(['department', 'editDepartment'], team.department);
        setFieldValue(['dept_code', 'deptCode', 'editDeptCode'], team.dept_code);
        setFieldValue(['team_name', 'teamName', 'editTeamName'], team.team_name);
        setFieldValue(['team_code', 'teamCode', 'editTeamCode'], team.team_code);
        setFieldValue(['team_description', 'teamDescription', 'editTeamDescription'], team.description || team.team_description);

        console.log('✅ TeamsUI: 編輯表單填入完成');

        // 設定編輯模式
        this.currentEditingTeamId = teamId;
        
        // 更新按鈕文字（如果存在的話）
        const submitBtn = document.getElementById('submitBtn') || document.getElementById('createTeam') || document.getElementById('updateTeam');
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-save"></i> 更新團隊';
        }
        
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            cancelBtn.style.display = 'inline-flex';
        }

        // 更新預覽
        this.updateTeamIdPreview();

        // 顯示編輯模態框或滾動到表單
        const editModal = document.getElementById('editTeamModal');
        if (editModal) {
            console.log('📝 顯示編輯模態框');
            new bootstrap.Modal(editModal).show();
        } else {
            console.log('📝 滾動到表單位置');
            const form = document.getElementById('teamForm') || document.getElementById('addTeamForm');
            if (form) {
                form.scrollIntoView({ behavior: 'smooth' });
            }
        }
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
        const form = document.getElementById('teamForm') || document.getElementById('addTeamForm');
        if (form) {
            form.reset();
        }
        
        this.currentEditingTeamId = null;
        
        const submitBtn = document.getElementById('submitBtn') || document.getElementById('createTeam') || document.getElementById('updateTeam');
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-save"></i> 建立團隊';
        }
        
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            cancelBtn.style.display = 'none';
        }
        
        this.updateTeamIdPreview();
    }

    /**
     * 更新團隊 ID 預覽
     */
    updateTeamIdPreview() {
        const getFieldValue = (ids) => {
            for (const id of ids) {
                const element = document.getElementById(id);
                if (element) {
                    return element.value.trim();
                }
            }
            return '';
        };

        const companyCode = getFieldValue(['company_code', 'companyCode', 'editCompanyCode']);
        const deptCode = getFieldValue(['dept_code', 'deptCode', 'editDeptCode']);
        const teamCode = getFieldValue(['team_code', 'teamCode', 'editTeamCode']);
        
        // 更新預覽（如果元素存在）
        const previewSection = document.getElementById('previewSection');
        const previewId = document.getElementById('previewId');
        const teamIdPreview = document.getElementById('teamIdPreview');
        
        if (companyCode && deptCode && teamCode) {
            const preview = teamsAPI.generateTeamIdPreview(companyCode, deptCode, teamCode);
            
            if (previewId) {
                previewId.textContent = preview;
            }
            if (teamIdPreview) {
                teamIdPreview.innerHTML = `<code>${preview}</code>`;
                teamIdPreview.className = 'fw-bold text-primary';
            }
            if (previewSection) {
                previewSection.style.display = 'block';
            }
        } else {
            if (teamIdPreview) {
                teamIdPreview.textContent = '請填寫必要欄位';
                teamIdPreview.className = 'fw-bold text-muted';
            }
            if (previewSection) {
                previewSection.style.display = 'none';
            }
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

    /**
     * 查看團隊詳情
     */
    async viewTeam(teamId) {
        const team = this.allTeams.find(t => t.team_id === teamId);
        if (!team) {
            this.showToast('錯誤', '找不到團隊資料', 'error');
            return;
        }

        // 處理不同的欄位名稱
        const teamName = team.team_name || '';
        const company = team.company || '';
        const department = team.department || '';
        const description = team.description || team.team_description || '';
        const companyCode = team.company_code || '';
        const deptCode = team.dept_code || '';
        const teamCode = team.team_code || '';
        const createdAt = team.created_at || '';
        const updatedAt = team.updated_at || '';

        // 顯示團隊詳情
        const content = document.getElementById('teamDetailContent');
        content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-building me-2"></i>公司</h6>
                    <p class="border-bottom pb-2">${company || '未設定'}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-building me-2"></i>部門</h6>
                    <p class="border-bottom pb-2">${department || '未設定'}</p>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-users me-2"></i>團隊名稱</h6>
                    <p class="border-bottom pb-2">${teamName || '未設定'}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-code me-2"></i>團隊代碼</h6>
                    <p class="border-bottom pb-2">${companyCode}-${deptCode}-${teamCode}</p>
                </div>
            </div>
            <div class="mb-3">
                <h6><i class="fas fa-info-circle me-2"></i>團隊描述</h6>
                <p class="border-bottom pb-2">${description || '未設定'}</p>
            </div>
            <div class="mb-3">
                <h6><i class="fas fa-file me-2"></i>團隊文件</h6>
                <div id="teamFiles" class="border rounded p-3 bg-light">
                    <div class="text-center">
                        <i class="fas fa-spinner fa-spin"></i> 載入文件列表中...
                    </div>
                </div>
            </div>
            <div class="text-muted small">
                <p><strong>團隊 ID:</strong> ${team.team_id}</p>
                <p><strong>建立時間:</strong> ${createdAt || '未知'}</p>
                <p><strong>最後更新:</strong> ${updatedAt || '未知'}</p>
            </div>
        `;

        // 設置編輯按鈕的 team_id
        document.getElementById('editFromDetail').setAttribute('data-team-id', teamId);

        // 顯示模態框
        const modal = new bootstrap.Modal(document.getElementById('teamDetailModal'));
        modal.show();

        // 載入文件列表
        await this.loadTeamFiles(teamId);
    }

    /**
     * 載入團隊文件
     */
    async loadTeamFiles(teamId) {
        const container = document.getElementById('teamFiles');
        if (!container) return;

        try {
            console.log('📂 載入團隊文件:', teamId);
            
            const apiUrl = window.CONFIG ? window.CONFIG.API_BASE_URL : 'https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev';
            const response = await fetch(`${apiUrl}/teams/${encodeURIComponent(teamId)}?action=files`);

            if (!response.ok) {
                container.innerHTML = '<p class="text-danger">載入文件失敗</p>';
                return;
            }

            const result = await response.json();
            const files = result.files || [];

            if (files.length === 0) {
                container.innerHTML = '<p class="text-muted">目前沒有任何文件</p>';
                return;
            }

            const fileList = files.map(file => {
                // 從 S3 key 中提取文件名稱 (移除 team_info_docs/{teamId}/ 前綴)
                const fileName = file.key ? file.key.replace(`team_info_docs/${teamId}/`, '') : file.name || '未知文件';
                const uploadDate = file.lastModified ? new Date(file.lastModified).toLocaleDateString('zh-TW') : '未知';
                const fileSize = file.size ? this.formatFileSize(file.size) : '未知';
                const fileExt = fileName.split('.').pop()?.toLowerCase() || '';
                const fileIcon = this.getFileIcon(fileExt);
                
                return `
                    <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                        <div class="d-flex align-items-center">
                            <div class="file-icon me-3">
                                <i class="${fileIcon}" style="font-size: 1.2rem; color: #0047AB;"></i>
                            </div>
                            <div>
                                <div class="fw-bold">${fileName}</div>
                                <div class="small text-muted">
                                    <i class="fas fa-weight-hanging me-1"></i>大小: ${fileSize}
                                    <i class="fas fa-clock ms-2 me-1"></i>上傳: ${uploadDate}
                                </div>
                            </div>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-primary" onclick="teamsUI.downloadTeamFile('${file.key}', '${fileName}')" title="下載文件">
                                <i class="fas fa-download"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="teamsUI.deleteTeamFile('${file.key}', '${fileName}', '${teamId}')" title="刪除文件">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
            
            container.innerHTML = fileList;
        } catch (error) {
            console.error('❌ 載入團隊文件失敗:', error);
            container.innerHTML = '<p class="text-danger">載入文件失敗</p>';
        }
    }

    /**
     * 下載團隊文件
     */
    async downloadTeamFile(fileKey, fileName) {
        try {
            console.log('📥 下載文件:', fileName);
            
            const apiUrl = window.CONFIG ? window.CONFIG.API_BASE_URL : 'https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev';
            
            // 使用完整的 fileKey 進行下載
            const encodedFileKey = encodeURIComponent(fileKey);
            const response = await fetch(`${apiUrl}/download-team-file/${encodedFileKey}`);
            
            if (!response.ok) {
                throw new Error(`下載失敗 HTTP ${response.status}`);
            }

            const result = await response.json();
            
            // 開啟下載 URL
            window.open(result.downloadUrl, '_blank');
            this.showToast('成功', '文件下載開始', 'success');
        } catch (error) {
            console.error('❌ 文件下載失敗:', error);
            this.showToast('錯誤', '文件下載失敗：' + error.message, 'error');
        }
    }

    /**
     * 刪除團隊文件
     */
    async deleteTeamFile(fileKey, fileName, teamId) {
        if (!confirm(`確定要刪除文件「${fileName}」嗎？此操作無法復原。`)) {
            return;
        }

        try {
            console.log('🗑️ 刪除文件:', fileName);
            
            const apiUrl = window.CONFIG ? window.CONFIG.API_BASE_URL : 'https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev';
            
            const response = await fetch(`${apiUrl}/delete-team-file`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ key: fileKey })
            });
            
            if (!response.ok) {
                throw new Error(`刪除失敗 HTTP ${response.status}`);
            }

            this.showToast('成功', '文件刪除成功', 'success');
            // 重新載入文件列表
            await this.loadTeamFiles(teamId);
        } catch (error) {
            console.error('❌ 文件刪除失敗:', error);
            this.showToast('錯誤', '文件刪除失敗：' + error.message, 'error');
        }
    }

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 獲取文件圖示
     */
    getFileIcon(fileExt) {
        const icons = {
            'pdf': 'fas fa-file-pdf',
            'doc': 'fas fa-file-word',
            'docx': 'fas fa-file-word',
            'xls': 'fas fa-file-excel',
            'xlsx': 'fas fa-file-excel',
            'ppt': 'fas fa-file-powerpoint',
            'pptx': 'fas fa-file-powerpoint',
            'txt': 'fas fa-file-alt',
            'md': 'fas fa-file-code',
            'json': 'fas fa-file-code',
            'csv': 'fas fa-file-csv',
            'zip': 'fas fa-file-archive',
            'rar': 'fas fa-file-archive',
            'jpg': 'fas fa-file-image',
            'jpeg': 'fas fa-file-image',
            'png': 'fas fa-file-image',
            'gif': 'fas fa-file-image'
        };
        return icons[fileExt] || 'fas fa-file';
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
