/**
 * 職缺管理 UI 控制模組
 * 處理所有使用者介面交互和資料展示
 */

// 全域變數
let currentPage = 1;
let currentFilters = {};
let currentEditingJobId = null;
let availableTeams = [];
let requiredSkills = [];

/**
 * 頁面初始化
 */
document.addEventListener('DOMContentLoaded', async () => {
    await initializePage();
    setupEventListeners();
    await loadInitialData();
});

/**
 * 初始化頁面
 */
async function initializePage() {
    showLoading(true);
    try {
        // 載入團隊列表（用於表單選項）
        await loadTeams();
        
        // 設定篩選器預設值
        setupFilters();
        
        console.log('職缺管理頁面初始化完成');
    } catch (error) {
        console.error('頁面初始化失敗:', error);
        JobsErrorHandler.showError('頁面初始化失敗');
    } finally {
        showLoading(false);
    }
}

/**
 * 設定事件監聽器
 */
function setupEventListeners() {
    // 新增職缺按鈕
    document.getElementById('addJobBtn').addEventListener('click', openAddJobModal);
    
    // 模態框控制
    document.getElementById('closeModal').addEventListener('click', closeJobModal);
    document.getElementById('cancelBtn').addEventListener('click', closeJobModal);
    document.getElementById('closeDeleteModal').addEventListener('click', closeDeleteModal);
    document.getElementById('cancelDeleteBtn').addEventListener('click', closeDeleteModal);
    
    // 表單提交
    document.getElementById('jobForm').addEventListener('submit', handleJobFormSubmit);
    document.getElementById('confirmDeleteBtn').addEventListener('click', handleJobDelete);
    
    // 篩選器
    document.getElementById('searchInput').addEventListener('input', debounce(handleSearch, 300));
    document.getElementById('teamFilter').addEventListener('change', handleFilterChange);
    document.getElementById('statusFilter').addEventListener('change', handleFilterChange);
    document.getElementById('employmentTypeFilter').addEventListener('change', handleFilterChange);
    document.getElementById('experienceFilter').addEventListener('change', handleFilterChange);
    document.getElementById('remoteFilter').addEventListener('change', handleFilterChange);
    document.getElementById('limitFilter').addEventListener('change', handleFilterChange);
    document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);
    
    // 重新整理按鈕
    document.getElementById('refreshBtn').addEventListener('click', refreshJobsList);
    
    // 模態框外點擊關閉
    window.addEventListener('click', (event) => {
        const jobModal = document.getElementById('jobModal');
        const deleteModal = document.getElementById('deleteModal');
        
        if (event.target === jobModal) {
            closeJobModal();
        }
        if (event.target === deleteModal) {
            closeDeleteModal();
        }
    });
}

/**
 * 載入初始資料
 */
async function loadInitialData() {
    await Promise.all([
        loadJobStats(),
        loadJobsList()
    ]);
}

/**
 * 載入團隊列表
 */
async function loadTeams() {
    try {
        const response = await jobsApi.getTeams();
        availableTeams = response.data || [];
        
        // 更新表單中的團隊選項
        updateTeamSelects();
        
        console.log(`載入了 ${availableTeams.length} 個團隊`);
    } catch (error) {
        console.error('載入團隊列表失敗:', error);
        availableTeams = [];
    }
}

/**
 * 更新團隊選擇器
 */
function updateTeamSelects() {
    const teamSelect = document.getElementById('teamSelect');
    const teamFilter = document.getElementById('teamFilter');
    
    // 清空現有選項（保留預設選項）
    teamSelect.innerHTML = '<option value="">請選擇團隊</option>';
    teamFilter.innerHTML = '<option value="">所有團隊</option>';
    
    // 添加團隊選項
    availableTeams.forEach(team => {
        const option1 = new Option(`${team.company} - ${team.team_name}`, team.team_id);
        const option2 = new Option(`${team.company} - ${team.team_name}`, team.team_id);
        
        teamSelect.appendChild(option1);
        teamFilter.appendChild(option2);
    });
}

/**
 * 載入職缺統計
 */
async function loadJobStats() {
    try {
        const stats = await jobsApi.getJobStats();
        
        document.getElementById('totalJobs').textContent = stats.totalJobs;
        document.getElementById('activeJobs').textContent = stats.activeJobs;
        document.getElementById('pausedJobs').textContent = stats.pausedJobs;
        document.getElementById('totalViews').textContent = stats.totalViews;
        
    } catch (error) {
        console.error('載入統計資料失敗:', error);
        // 顯示預設值
        document.getElementById('totalJobs').textContent = '0';
        document.getElementById('activeJobs').textContent = '0';
        document.getElementById('pausedJobs').textContent = '0';
        document.getElementById('totalViews').textContent = '0';
    }
}

/**
 * 載入職缺列表
 */
async function loadJobsList() {
    showLoading(true);
    
    try {
        const params = {
            page: currentPage,
            limit: document.getElementById('limitFilter').value,
            ...currentFilters
        };
        
        const response = await jobsApi.getJobs(params);
        displayJobsList(response.data, response.pagination);
        
    } catch (error) {
        console.error('載入職缺列表失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
        displayJobsList([], null);
    } finally {
        showLoading(false);
    }
}

/**
 * 顯示職缺列表
 */
function displayJobsList(jobs, pagination) {
    const jobsList = document.getElementById('jobsList');
    const jobCount = document.getElementById('jobCount');
    
    if (!jobs || jobs.length === 0) {
        jobsList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-briefcase fa-3x"></i>
                <h3>沒有找到職缺</h3>
                <p>請嘗試調整篩選條件或新增職缺</p>
            </div>
        `;
        jobCount.textContent = '(0)';
        updatePagination(null);
        return;
    }
    
    // 更新計數
    jobCount.textContent = `(${pagination ? pagination.total_items : jobs.length})`;
    
    // 渲染職缺卡片
    jobsList.innerHTML = jobs.map(job => createJobCard(job)).join('');
    
    // 更新分頁
    if (pagination) {
        updatePagination(pagination);
    }
}

/**
 * 建立職缺卡片 HTML
 */
function createJobCard(job) {
    const salaryRange = JobsFormatter.formatSalaryRange(job.salary_min, job.salary_max);
    const employmentType = JobsFormatter.formatEmploymentType(job.employment_type);
    const experienceLevel = JobsFormatter.formatExperienceLevel(job.experience_level);
    const remoteOption = JobsFormatter.formatRemoteOption(job.remote_option);
    const createdDate = JobsFormatter.formatRelativeTime(job.created_at);
    const description = JobsFormatter.truncateText(job.job_description, 150);
    
    const skills = Array.isArray(job.required_skills) 
        ? job.required_skills.slice(0, 5) 
        : (job.required_skills ? [job.required_skills] : []);
    
    return `
        <div class="job-card" data-job-id="${job.job_id}">
            <div class="job-header">
                <div>
                    <div class="job-title">${job.job_title}</div>
                    <div class="job-company">${job.company} - ${job.team_name}</div>
                </div>
                <div class="job-status ${job.status}">${getStatusText(job.status)}</div>
            </div>
            
            <div class="job-meta">
                <div class="job-meta-item">
                    <i class="fas fa-briefcase"></i>
                    <span>${employmentType}</span>
                </div>
                <div class="job-meta-item">
                    <i class="fas fa-chart-line"></i>
                    <span>${experienceLevel}</span>
                </div>
                <div class="job-meta-item">
                    <i class="fas fa-dollar-sign"></i>
                    <span>${salaryRange}</span>
                </div>
                <div class="job-meta-item">
                    <i class="fas fa-laptop"></i>
                    <span>${remoteOption}</span>
                </div>
                ${job.location ? `
                <div class="job-meta-item">
                    <i class="fas fa-map-marker-alt"></i>
                    <span>${job.location}</span>
                </div>
                ` : ''}
                <div class="job-meta-item">
                    <i class="fas fa-clock"></i>
                    <span>${createdDate}</span>
                </div>
                <div class="job-meta-item">
                    <i class="fas fa-eye"></i>
                    <span>${job.view_count || 0} 次瀏覽</span>
                </div>
            </div>
            
            <div class="job-description">${description}</div>
            
            <div class="job-skills">
                ${skills.map(skill => `<span class="skill-tag">${skill}</span>`).join('')}
                ${skills.length < job.required_skills?.length ? `<span class="skill-tag">+${job.required_skills.length - skills.length}</span>` : ''}
            </div>
            
            <div class="job-actions">
                <button class="btn btn-sm btn-outline-primary" onclick="viewJob('${job.job_id}')">
                    <i class="fas fa-eye"></i> 檢視
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="editJob('${job.job_id}')">
                    <i class="fas fa-edit"></i> 編輯
                </button>
                <button class="btn btn-sm btn-outline-info" onclick="duplicateJob('${job.job_id}')">
                    <i class="fas fa-copy"></i> 複製
                </button>
                <button class="btn btn-sm btn-outline-warning" onclick="toggleJobStatus('${job.job_id}', '${job.status}')">
                    <i class="fas fa-${job.status === 'active' ? 'pause' : 'play'}"></i> 
                    ${job.status === 'active' ? '暫停' : '啟用'}
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteJob('${job.job_id}')">
                    <i class="fas fa-trash"></i> 刪除
                </button>
            </div>
        </div>
    `;
}

/**
 * 取得狀態文字
 */
function getStatusText(status) {
    const statusMap = {
        'active': '活躍中',
        'paused': '暫停',
        'closed': '關閉',
        'deleted': '已刪除'
    };
    return statusMap[status] || status;
}

/**
 * 更新分頁
 */
function updatePagination(pagination) {
    const paginationContainer = document.getElementById('pagination');
    
    if (!pagination || pagination.total_pages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    const { current_page, total_pages } = pagination;
    let paginationHTML = '<div class="pagination-controls">';
    
    // 上一頁
    if (current_page > 1) {
        paginationHTML += `<button class="btn btn-sm btn-outline-secondary" onclick="changePage(${current_page - 1})">
            <i class="fas fa-chevron-left"></i> 上一頁
        </button>`;
    }
    
    // 頁碼
    const startPage = Math.max(1, current_page - 2);
    const endPage = Math.min(total_pages, current_page + 2);
    
    if (startPage > 1) {
        paginationHTML += `<button class="btn btn-sm btn-outline-secondary" onclick="changePage(1)">1</button>`;
        if (startPage > 2) {
            paginationHTML += `<span class="pagination-ellipsis">...</span>`;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === current_page ? 'btn-primary' : 'btn-outline-secondary';
        paginationHTML += `<button class="btn btn-sm ${isActive}" onclick="changePage(${i})">${i}</button>`;
    }
    
    if (endPage < total_pages) {
        if (endPage < total_pages - 1) {
            paginationHTML += `<span class="pagination-ellipsis">...</span>`;
        }
        paginationHTML += `<button class="btn btn-sm btn-outline-secondary" onclick="changePage(${total_pages})">${total_pages}</button>`;
    }
    
    // 下一頁
    if (current_page < total_pages) {
        paginationHTML += `<button class="btn btn-sm btn-outline-secondary" onclick="changePage(${current_page + 1})">
            下一頁 <i class="fas fa-chevron-right"></i>
        </button>`;
    }
    
    paginationHTML += '</div>';
    paginationContainer.innerHTML = paginationHTML;
}

/**
 * 切換頁面
 */
function changePage(page) {
    currentPage = page;
    loadJobsList();
}

/**
 * 處理搜尋
 */
function handleSearch(event) {
    const searchTerm = event.target.value.trim();
    if (searchTerm) {
        currentFilters.search = searchTerm;
    } else {
        delete currentFilters.search;
    }
    currentPage = 1;
    loadJobsList();
}

/**
 * 處理篩選變更
 */
function handleFilterChange() {
    currentFilters = {
        team_id: document.getElementById('teamFilter').value,
        status: document.getElementById('statusFilter').value,
        employment_type: document.getElementById('employmentTypeFilter').value,
        experience_level: document.getElementById('experienceFilter').value,
        remote_option: document.getElementById('remoteFilter').value,
    };
    
    // 移除空值
    Object.keys(currentFilters).forEach(key => {
        if (!currentFilters[key]) {
            delete currentFilters[key];
        }
    });
    
    currentPage = 1;
    loadJobsList();
}

/**
 * 清除篩選
 */
function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('teamFilter').value = '';
    document.getElementById('statusFilter').value = 'active';
    document.getElementById('employmentTypeFilter').value = '';
    document.getElementById('experienceFilter').value = '';
    document.getElementById('remoteFilter').value = '';
    
    currentFilters = {};
    currentPage = 1;
    loadJobsList();
}

/**
 * 重新整理職缺列表
 */
async function refreshJobsList() {
    await Promise.all([
        loadJobStats(),
        loadJobsList()
    ]);
}

/**
 * 開啟新增職缺模態框
 */
function openAddJobModal() {
    currentEditingJobId = null;
    document.getElementById('modalTitle').textContent = '新增職缺';
    resetJobForm();
    document.getElementById('jobModal').style.display = 'block';
}

/**
 * 開啟編輯職缺模態框
 */
async function editJob(jobId) {
    try {
        showLoading(true);
        const response = await jobsApi.getJob(jobId);
        const job = response.data;
        
        currentEditingJobId = jobId;
        document.getElementById('modalTitle').textContent = '編輯職缺';
        populateJobForm(job);
        document.getElementById('jobModal').style.display = 'block';
        
    } catch (error) {
        console.error('載入職缺資料失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 檢視職缺詳情
 */
async function viewJob(jobId) {
    try {
        const response = await jobsApi.getJob(jobId);
        const job = response.data;
        
        // 簡單的彈窗顯示，未來可以改為專用的檢視模態框
        const details = `
職缺標題：${job.job_title}
所屬公司：${job.company}
所屬團隊：${job.team_name}
就業類型：${JobsFormatter.formatEmploymentType(job.employment_type)}
經驗等級：${JobsFormatter.formatExperienceLevel(job.experience_level)}
薪資範圍：${JobsFormatter.formatSalaryRange(job.salary_min, job.salary_max)}
工作地點：${job.location || '未指定'}
工作模式：${JobsFormatter.formatRemoteOption(job.remote_option)}
必備技能：${Array.isArray(job.required_skills) ? job.required_skills.join(', ') : job.required_skills}
學歷要求：${job.education_requirement || '無特殊要求'}
申請截止：${job.application_deadline ? JobsFormatter.formatDate(job.application_deadline) : '無限制'}
瀏覽次數：${job.view_count || 0}
申請人數：${job.application_count || 0}
建立時間：${JobsFormatter.formatDate(job.created_at)}

職缺描述：
${job.job_description}
        `;
        
        alert(details);
        
    } catch (error) {
        console.error('載入職缺詳情失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    }
}

/**
 * 複製職缺
 */
async function duplicateJob(jobId) {
    if (!confirm('確定要複製這個職缺嗎？複製的職缺將以暫停狀態建立。')) {
        return;
    }
    
    try {
        showLoading(true);
        await jobsApi.duplicateJob(jobId);
        JobsErrorHandler.showSuccess('職缺複製成功');
        await refreshJobsList();
        
    } catch (error) {
        console.error('複製職缺失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 切換職缺狀態
 */
async function toggleJobStatus(jobId, currentStatus) {
    const newStatus = currentStatus === 'active' ? 'paused' : 'active';
    const action = newStatus === 'active' ? '啟用' : '暫停';
    
    if (!confirm(`確定要${action}這個職缺嗎？`)) {
        return;
    }
    
    try {
        showLoading(true);
        await jobsApi.updateJob(jobId, { status: newStatus });
        JobsErrorHandler.showSuccess(`職缺${action}成功`);
        await refreshJobsList();
        
    } catch (error) {
        console.error('更新職缺狀態失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 確認刪除職缺
 */
function confirmDeleteJob(jobId) {
    currentEditingJobId = jobId;
    document.getElementById('deleteModal').style.display = 'block';
}

/**
 * 執行刪除職缺
 */
async function handleJobDelete() {
    if (!currentEditingJobId) return;
    
    try {
        showLoading(true);
        await jobsApi.deleteJob(currentEditingJobId);
        JobsErrorHandler.showSuccess('職缺刪除成功');
        closeDeleteModal();
        await refreshJobsList();
        
    } catch (error) {
        console.error('刪除職缺失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 關閉職缺模態框
 */
function closeJobModal() {
    document.getElementById('jobModal').style.display = 'none';
    resetJobForm();
    currentEditingJobId = null;
}

/**
 * 關閉刪除確認模態框
 */
function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    currentEditingJobId = null;
}

/**
 * 重置職缺表單
 */
function resetJobForm() {
    document.getElementById('jobForm').reset();
    requiredSkills = [];
    updateRequiredSkillsDisplay();
}

/**
 * 填充職缺表單
 */
function populateJobForm(job) {
    document.getElementById('teamSelect').value = job.team_id || '';
    document.getElementById('jobTitle').value = job.job_title || '';
    document.getElementById('jobDescription').value = job.job_description || '';
    document.getElementById('employmentType').value = job.employment_type || '';
    document.getElementById('experienceLevel').value = job.experience_level || '';
    document.getElementById('salaryMin').value = job.salary_min || '';
    document.getElementById('salaryMax').value = job.salary_max || '';
    document.getElementById('location').value = job.location || '';
    document.getElementById('remoteOption').value = job.remote_option || 'onsite';
    document.getElementById('educationRequirement').value = job.education_requirement || '';
    document.getElementById('applicationDeadline').value = job.application_deadline || '';
    
    // 設定必備技能
    requiredSkills = Array.isArray(job.required_skills) ? [...job.required_skills] : (job.required_skills ? [job.required_skills] : []);
    updateRequiredSkillsDisplay();
}

/**
 * 處理職缺表單提交
 */
async function handleJobFormSubmit(event) {
    event.preventDefault();
    
    if (requiredSkills.length === 0) {
        alert('請至少添加一個必備技能');
        return;
    }
    
    const formData = new FormData(event.target);
    const jobData = Object.fromEntries(formData);
    
    // 設定必備技能
    jobData.required_skills = requiredSkills;
    
    // 轉換數字類型
    if (jobData.salary_min) jobData.salary_min = parseFloat(jobData.salary_min);
    if (jobData.salary_max) jobData.salary_max = parseFloat(jobData.salary_max);
    
    // 移除空值
    Object.keys(jobData).forEach(key => {
        if (jobData[key] === '' || jobData[key] === null) {
            delete jobData[key];
        }
    });
    
    try {
        showLoading(true);
        
        if (currentEditingJobId) {
            // 更新職缺
            await jobsApi.updateJob(currentEditingJobId, jobData);
            JobsErrorHandler.showSuccess('職缺更新成功');
        } else {
            // 建立新職缺
            await jobsApi.createJob(jobData);
            JobsErrorHandler.showSuccess('職缺建立成功');
        }
        
        closeJobModal();
        await refreshJobsList();
        
    } catch (error) {
        console.error('儲存職缺失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 添加必備技能
 */
function addSkill(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        
        const input = event.target;
        const skill = input.value.trim();
        
        if (skill && !requiredSkills.includes(skill)) {
            requiredSkills.push(skill);
            input.value = '';
            updateRequiredSkillsDisplay();
        }
    }
}

/**
 * 移除必備技能
 */
function removeSkill(skill) {
    requiredSkills = requiredSkills.filter(s => s !== skill);
    updateRequiredSkillsDisplay();
}

/**
 * 更新必備技能顯示
 */
function updateRequiredSkillsDisplay() {
    const container = document.getElementById('requiredSkillsList');
    const hiddenInput = document.getElementById('requiredSkills');
    
    container.innerHTML = requiredSkills.map(skill => `
        <div class="skill-input-tag">
            <span>${skill}</span>
            <span class="remove-skill" onclick="removeSkill('${skill}')">×</span>
        </div>
    `).join('');
    
    hiddenInput.value = JSON.stringify(requiredSkills);
}

/**
 * 設定篩選器
 */
function setupFilters() {
    // 設定預設狀態為活躍
    document.getElementById('statusFilter').value = 'active';
    currentFilters = { status: 'active' };
}

/**
 * 顯示載入指示器
 */
function showLoading(show) {
    const loadingIndicator = document.getElementById('loadingIndicator');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (show) {
        loadingIndicator.style.display = 'block';
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 載入中...';
    } else {
        loadingIndicator.style.display = 'none';
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 重新整理';
    }
}

/**
 * 防抖函數
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 匯出職缺資料 (未來功能)
 */
async function exportJobs() {
    try {
        showLoading(true);
        const jobs = await jobsApi.exportJobs();
        
        // 轉換為 CSV 格式
        const csvContent = convertJobsToCSV(jobs);
        
        // 下載檔案
        downloadCSV(csvContent, '職缺資料.csv');
        
        JobsErrorHandler.showSuccess('職缺資料匯出成功');
        
    } catch (error) {
        console.error('匯出失敗:', error);
        JobsErrorHandler.showError(JobsErrorHandler.handleApiError(error));
    } finally {
        showLoading(false);
    }
}

/**
 * 轉換職缺資料為 CSV 格式
 */
function convertJobsToCSV(jobs) {
    const headers = [
        '職缺ID', '職缺標題', '公司', '團隊', '就業類型', '經驗等級', 
        '最低薪資', '最高薪資', '工作地點', '工作模式', '必備技能', 
        '學歷要求', '狀態', '瀏覽次數', '申請人數', '建立時間'
    ];
    
    const rows = jobs.map(job => [
        job.job_id,
        job.job_title,
        job.company,
        job.team_name,
        JobsFormatter.formatEmploymentType(job.employment_type),
        JobsFormatter.formatExperienceLevel(job.experience_level),
        job.salary_min || '',
        job.salary_max || '',
        job.location || '',
        JobsFormatter.formatRemoteOption(job.remote_option),
        Array.isArray(job.required_skills) ? job.required_skills.join('; ') : job.required_skills,
        job.education_requirement || '',
        getStatusText(job.status),
        job.view_count || 0,
        job.application_count || 0,
        JobsFormatter.formatDate(job.created_at)
    ]);
    
    return [headers, ...rows].map(row => 
        row.map(field => `"${field}"`).join(',')
    ).join('\n');
}

/**
 * 下載 CSV 檔案
 */
function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
} 