// teams-ui.js - 頁面互動邏輯

class TeamsUI {
  constructor() {
    // 確保 teamsAPI 已經初始化
    if (!window.teamsAPI) {
      throw new Error("TeamsAPI 尚未初始化");
    }

    this.currentEditingTeamId = null;
    this.allTeams = [];
    this.filteredTeams = [];
    this.editSelectedFiles = []; // 編輯時選擇的新文件
    this.deletedFiles = []; // 編輯時標記刪除的文件
    
    // 快取機制，避免重複載入相同團隊的文件
    this.fileCache = new Map();
    this.lastCacheTime = new Map();
    this.CACHE_TTL = 30000; // 30秒快取
    
    this.init();
  }

  /**
   * 初始化頁面
   */
  async init() {
    // 優化載入順序，先綁定事件和設置UI，再載入資料
    this.bindEvents();
    this.setupFileUpload();
    
    // 非阻塞式載入團隊資料
    this.loadTeamsAsync();
    
    console.log('✅ TeamsUI 初始化完成');
  }
  
  // 非阻塞式載入團隊資料
  async loadTeamsAsync() {
    try {
      await this.loadTeams();
    } catch (error) {
      console.error('❌ 異步載入團隊失敗:', error);
    }
  }

  /**
   * 綁定事件
   */
  bindEvents() {
    // 搜尋功能
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
      searchInput.addEventListener("input", () => {
        this.performSearch();
      });
    }

    // 公司篩選
    const companyFilter = document.getElementById("companyFilter");
    if (companyFilter) {
      companyFilter.addEventListener("change", () => {
        this.performSearch();
      });
    }

    // 表單提交 - 使用表單的 submit 事件而不是按鈕的 click 事件
    const forms = ["addTeamForm", "editTeamForm"];
    forms.forEach((formId) => {
      const form = document.getElementById(formId);
      if (form) {
        form.addEventListener("submit", (e) => {
          e.preventDefault();
          this.handleFormSubmit();
        });
      }
    });

    // 取消按鈕
    const cancelBtn = document.getElementById("cancelBtn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        this.resetForm();
      });
    }

    // 即時預覽團隊 ID - 支援多種可能的欄位 ID
    const previewFields = [
      ["company_code", "companyCode"],
      ["dept_code", "deptCode"],
      ["team_code", "teamCode"],
    ];

    previewFields.forEach((fieldIds) => {
      fieldIds.forEach((fieldId) => {
        const element = document.getElementById(fieldId);
        if (element) {
          element.addEventListener("input", () => {
            this.updateTeamIdPreview();
          });
        }
      });
    });

    // 編輯表單的即時預覽
    const editPreviewFields = [
      "editCompanyCode",
      "editDeptCode",
      "editTeamCode",
    ];
    editPreviewFields.forEach((fieldId) => {
      const element = document.getElementById(fieldId);
      if (element) {
        element.addEventListener("input", () => {
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
      this.showToast("錯誤", result.error, "error");
    }
  }

  /**
   * 顯示載入狀態
   */
  showLoading() {
    document.getElementById("loadingSpinner").style.display = "block";
    document.getElementById("teamsContainer").style.display = "none";
    document.getElementById("emptyState").style.display = "none";
  }

  /**
   * 隱藏載入狀態
   */
  hideLoading() {
    document.getElementById("loadingSpinner").style.display = "none";

    if (this.filteredTeams.length > 0) {
      document.getElementById("teamsContainer").style.display = "block";
      document.getElementById("emptyState").style.display = "none";
    } else {
      document.getElementById("teamsContainer").style.display = "none";
      document.getElementById("emptyState").style.display = "block";
    }
  }

  /**
   * 渲染團隊列表
   */
  renderTeams() {
    const container = document.getElementById("teamsGrid");
    container.innerHTML = "";

    this.filteredTeams.forEach((team) => {
      const card = this.createTeamCard(team);
      container.appendChild(card);
    });
  }

  /**
   * 建立團隊卡片
   */
  createTeamCard(team) {
    const card = document.createElement("div");
    card.className = "col-md-6 col-lg-4 mb-3";

    // 處理不同的欄位名稱
    const teamName = team.team_name || "";
    const company = team.company || "";
    const department = team.department || "";
    const description = team.description || team.team_description || "";
    const companyCode = team.company_code || "";
    const deptCode = team.dept_code || "";
    const teamCode = team.team_code || "";
    const createdAt = team.created_at || "";

    card.innerHTML = `
            <div class="team-card">
                <div class="team-card-header">
                    <code class="team-id">${team.team_id}</code>
                    <div class="team-actions">
                        <button type="button" class="btn-view" onclick="teamsUI.viewTeam('${
                          team.team_id
                        }')" title="查看詳情">
                            <i class="fas fa-eye"></i> 查看
                        </button>
                        <button type="button" class="btn-edit" onclick="teamsUI.editTeam('${
                          team.team_id
                        }')" title="編輯團隊">
                            <i class="fas fa-edit"></i> 編輯
                        </button>
                        <button type="button" class="btn-delete" onclick="teamsUI.deleteTeam('${
                          team.team_id
                        }')" title="刪除團隊">
                            <i class="fas fa-trash"></i> 刪除
                        </button>
                    </div>
                </div>
                <div class="team-info">
                    <h3>${teamName}</h3>
                    <div class="company">${company}</div>
                    <div class="department">${department}</div>
                    <div class="codes">代碼：${companyCode} - ${deptCode} - ${teamCode}</div>
                    ${
                      description
                        ? `<div class="description">${description}</div>`
                        : ""
                    }
                    <div class="created-at">建立於 ${this.formatDate(
                      createdAt
                    )}</div>
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

    // 如果有嚴重錯誤，阻止提交
    if (!validation.isValid) {
      this.showToast("驗證錯誤", validation.errors.join("<br>"), "error");
      return;
    }

    // 如果有警告，顯示確認對話框
    if (validation.hasWarnings) {
      const warningMessage = validation.warnings.join("\n");
      if (!confirm(`請注意以下警告：\n${warningMessage}\n\n是否確定要繼續？`)) {
        return;
      }
    }

    // 根據當前模式取得正確的按鈕
    let submitBtn;
    if (this.currentEditingTeamId) {
      submitBtn =
        document.getElementById("updateTeam") ||
        document.querySelector('#editTeamForm button[type="submit"]');
    } else {
      submitBtn =
        document.getElementById("createTeam") ||
        document.querySelector('#addTeamForm button[type="submit"]');
    }

    if (!submitBtn) {
      console.error("找不到提交按鈕");
      return;
    }

    // 設定按鈕載入狀態
    const originalHTML = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 處理中...';
    submitBtn.disabled = true;

    try {
      let result;

      if (this.currentEditingTeamId) {
        // 確保更新時包含團隊 ID
        formData.team_id = this.currentEditingTeamId;
        
        // 收集待刪除的文件
        const deleteButtons = document.querySelectorAll('#existingFiles .delete-file-btn[data-deleted="true"]');
        const deletedFiles = Array.from(deleteButtons).map(btn => btn.dataset.fileKey);
        
        console.log('📁 檢查文件操作狀態:', {
          newFiles: this.editSelectedFiles.length,
          deletedFiles: deletedFiles.length,
          selectedFiles: this.editSelectedFiles.map(f => f.name)
        });
        
        // 使用 teamsAPI 來處理更新，不再直接調用 fetch
        console.log('📤 準備呼叫 teamsAPI.updateTeam:', {
          teamId: this.currentEditingTeamId,
          formData: formData,
          newFilesCount: this.editSelectedFiles.length,
          deletedFilesCount: deletedFiles.length,
          newFilesDetails: this.editSelectedFiles.map(f => ({ name: f.name, size: f.size, type: f.type })),
          deletedFilesDetails: deletedFiles,
          editSelectedFilesIsArray: Array.isArray(this.editSelectedFiles),
          editSelectedFilesType: typeof this.editSelectedFiles
        });
        
        result = await teamsAPI.updateTeam(
          this.currentEditingTeamId,
          formData,
          this.editSelectedFiles,
          deletedFiles
        );
        
        console.log('📨 teamsAPI.updateTeam 回應:', result);
      } else {
        // 建立新團隊 - 檢查是否有文件需要上傳
        const newTeamFiles = window.selectedFiles || [];
        
        console.log('📁 檢查新團隊文件狀態:', {
          newFiles: newTeamFiles.length,
          filesDetails: newTeamFiles.map(f => ({ name: f.name, size: f.size, type: f.type }))
        });
        
        if (newTeamFiles.length > 0) {
          // 有文件需要上傳，使用帶文件的創建方法
          result = await teamsAPI.createTeamWithFiles(formData, newTeamFiles);
        } else {
          // 沒有文件，使用標準創建方法
          result = await teamsAPI.createTeam(formData);
        }
      }

      if (result.success) {
        const action = this.currentEditingTeamId ? "更新" : "建立";
        this.showToast("成功", `團隊${action}成功！`, "success");

        // 如果是編輯模式，關閉編輯模態框並重整畫面
        if (this.currentEditingTeamId) {
          // 儲存當前團隊 ID
          const currentTeamId = this.currentEditingTeamId;
          
          // 清理編輯狀態
          this.resetForm();
          
          // 關閉編輯模態框
          const editModal = document.getElementById("editTeamModal");
          if (editModal) {
            const modalInstance = bootstrap.Modal.getInstance(editModal);
            if (modalInstance) {
              modalInstance.hide();
            }
          }
          
          // 完全重新載入頁面資料
          setTimeout(async () => {
            console.log('🔄 開始完整刷新頁面資料...');
            
            // 清除文件快取
            this.fileCache.clear();
            this.lastCacheTime.clear();
            
            // 重新載入所有團隊資料
            await this.loadTeams();
            
            console.log('✅ 頁面資料刷新完成');
          }, 300);
        } else {
          // 新增模式：清理狀態並關閉模態框
          
          // 清理全局 selectedFiles
          if (window.selectedFiles) {
            window.selectedFiles.length = 0;
          }
          
          // 清理文件列表顯示
          const fileList = document.getElementById('fileList');
          if (fileList) {
            fileList.innerHTML = '';
          }
          
          // 清理文件輸入
          const fileInput = document.getElementById('fileInput');
          if (fileInput) {
            fileInput.value = '';
          }
          
          this.resetForm();
          
          // 關閉新增模態框
          const addModal = document.getElementById("addTeamModal");
          if (addModal) {
            const modalInstance = bootstrap.Modal.getInstance(addModal);
            if (modalInstance) {
              modalInstance.hide();
            }
          }
          
          // 重新載入團隊列表
          await this.loadTeams();
        }
      } else {
        this.showToast("錯誤", result.error || "操作失敗", "error");
      }
    } catch (error) {
      console.error("操作失敗:", error);
      this.showToast("錯誤", error.message || "操作失敗", "error");
    } finally {
      // 恢復按鈕狀態
      submitBtn.innerHTML = originalHTML;
      submitBtn.disabled = false;
    }
  }

  /**
   * 取得表單資料
   */
  getFormData() {
    // 根據當前模式決定要使用哪個表單
    const formId = this.currentEditingTeamId ? "editTeamForm" : "addTeamForm";
    const form = document.getElementById(formId);

    if (!form) {
      console.error("找不到團隊表單:", formId);
      return {};
    }

    // 手動收集表單資料
    const data = {};

    // 定義所有可能的欄位 ID
    const fieldMappings = {
      company: this.currentEditingTeamId ? ["editCompany"] : ["company"],
      company_code: this.currentEditingTeamId
        ? ["editCompanyCode"]
        : ["companyCode", "company_code"],
      department: this.currentEditingTeamId
        ? ["editDepartment"]
        : ["department"],
      dept_code: this.currentEditingTeamId
        ? ["editDeptCode"]
        : ["deptCode", "dept_code"],
      team_name: this.currentEditingTeamId
        ? ["editTeamName"]
        : ["teamName", "team_name"],
      team_code: this.currentEditingTeamId
        ? ["editTeamCode"]
        : ["teamCode", "team_code"],
      description: this.currentEditingTeamId
        ? ["editTeamDescription"]
        : ["teamDescription", "team_description"],
    };

    // 遍歷每個欄位，找到第一個存在的 ID 並獲取其值
    for (const [key, ids] of Object.entries(fieldMappings)) {
      for (const id of ids) {
        const element = document.getElementById(id);
        if (element) {
          data[key] = element.value.trim();
          console.log(`✅ 獲取 ${key} 值從 ${id}: "${data[key]}"`);
          break;
        }
      }

      // 如果沒有找到任何對應的元素，設置為空字串
      if (!data[key]) {
        data[key] = "";
        console.warn(`⚠️ 找不到 ${key} 的任何欄位`);
      }
    }

    console.log("📝 收集到的表單資料:", data);
    return data;
  }

  /**
   * 編輯團隊
   */
  async editTeam(teamId) {
    console.log("🔧 TeamsUI: 開始編輯團隊:", teamId);

    const team = this.allTeams.find((t) => t.team_id === teamId);
    if (!team) {
      console.error("❌ TeamsUI: 找不到團隊資料:", teamId);
      this.showToast("錯誤", "找不到團隊資料", "error");
      return;
    }

    console.log("📋 TeamsUI: 載入團隊資料進行編輯:", team);

    // 填入表單 - 支援多種可能的 ID
    const setFieldValue = (id, value) => {
      const element = document.getElementById(id);
      if (element) {
        element.value = value || "";
        console.log(`✅ 設定 ${id} = "${value}"`);
      } else {
        console.warn(`⚠️  找不到欄位: ${id}`);
      }
    };

    // 設定編輯表單欄位值
    setFieldValue("editTeamId", team.team_id);
    setFieldValue("editCompany", team.company);
    setFieldValue("editCompanyCode", team.company_code || team.companyCode);
    setFieldValue("editDepartment", team.department);
    setFieldValue(
      "editDeptCode",
      team.dept_code || team.department_code || team.deptCode
    );
    setFieldValue("editTeamName", team.team_name || team.teamName);
    setFieldValue(
      "editTeamCode",
      team.team_code || team.section_code || team.teamCode
    );
    setFieldValue(
      "editTeamDescription",
      team.description || team.team_description
    );

    console.log("✅ TeamsUI: 編輯表單填入完成");

    // 設定編輯模式並完全清理文件狀態
    this.currentEditingTeamId = teamId;
    this.editSelectedFiles.length = 0; // 清空但保持引用
    this.deletedFiles.length = 0; // 清空但保持引用
    console.log('📁 TeamsUI: 清空編輯文件列表，當前文件數:', this.editSelectedFiles.length);
    
    // 清理所有文件相關的 UI 元素
    const editFileList = document.getElementById('editFileList');
    if (editFileList) {
      editFileList.innerHTML = '';
      console.log('✅ 已清空 editFileList');
    }
    
    const existingFiles = document.getElementById('existingFiles');
    if (existingFiles) {
      existingFiles.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">載入文件中...</div></div>';
      console.log('✅ 已重置 existingFiles 顯示');
    }
    
    const editFileInput = document.getElementById('editFileInput');
    if (editFileInput) {
      editFileInput.value = '';
      console.log('✅ 已清空文件輸入框');
    }

    // 顯示編輯模態框
    const editModal = document.getElementById("editTeamModal");
    if (editModal) {
      console.log("📝 顯示編輯模態框");
      const modalInstance = new bootstrap.Modal(editModal);
      
      // 監聽模態框顯示完成事件，然後初始化上傳功能和載入文件
      editModal.addEventListener('shown.bs.modal', () => {
        console.log("📝 編輯模態框顯示完成，開始初始化文件功能");
        
        // 等待一小段時間確保DOM完全渲染
        setTimeout(() => {
          // 初始化編輯文件上傳功能
          this.setupEditFileUpload();
          console.log("📁 編輯文件上傳功能初始化完成");
          
          // 載入現有文件
          this.loadExistingFiles(teamId);
          console.log("📂 開始載入現有文件");
        }, 100);
      }, { once: true });
      
      modalInstance.show();
    } else {
      console.error("❌ 找不到編輯模態框");
      this.showToast("錯誤", "無法開啟編輯視窗", "error");
    }
  }

  /**
   * 刪除團隊
   */
  async deleteTeam(teamId) {
    const team = this.allTeams.find((t) => t.team_id === teamId);
    if (!team) {
      this.showToast("錯誤", "找不到團隊資料", "error");
      return;
    }

    if (
      !confirm(`確定要刪除團隊「${team.team_name}」嗎？\n\n此操作無法復原。`)
    ) {
      return;
    }

    const result = await teamsAPI.deleteTeam(teamId);

    if (result.success) {
      this.showToast("成功", "團隊刪除成功！", "success");
      this.loadTeams();

      // 如果正在編輯這個團隊，重設表單
      if (this.currentEditingTeamId === teamId) {
        this.resetForm();
      }
    } else {
      this.showToast("錯誤", result.error, "error");
    }
  }

  /**
   * 重設表單
   */
  resetForm() {
    // 重設新增團隊表單
    const addForm = document.getElementById("addTeamForm");
    if (addForm) {
      addForm.reset();
    }
    
    // 重設編輯團隊表單
    const editForm = document.getElementById("editTeamForm");
    if (editForm) {
      editForm.reset();
    }

    this.currentEditingTeamId = null;
    
    // 完全清理文件相關狀態 - 使用splice確保數組完全清空
    this.editSelectedFiles.splice(0, this.editSelectedFiles.length);
    this.deletedFiles.splice(0, this.deletedFiles.length);
    
    // 清理編輯文件列表顯示
    const editFileList = document.getElementById('editFileList');
    if (editFileList) {
      editFileList.innerHTML = '';
    }
    
    // 清理編輯文件輸入
    const editFileInput = document.getElementById('editFileInput');
    if (editFileInput) {
      editFileInput.value = '';
    }
    
    // 清理新增文件列表顯示
    const addFileList = document.getElementById('fileList');
    if (addFileList) {
      addFileList.innerHTML = '';
    }
    
    // 清理新增文件輸入
    const addFileInput = document.getElementById('fileInput');
    if (addFileInput) {
      addFileInput.value = '';
    }
    
    // 移除編輯文件上傳的事件監聽器
    this.removeEditFileUploadListeners();
    
    // 重設所有刪除按鈕狀態
    const existingFiles = document.getElementById('existingFiles');
    if (existingFiles) {
      const deleteButtons = existingFiles.querySelectorAll('.delete-file-btn');
      deleteButtons.forEach(btn => {
        btn.dataset.deleted = 'false';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-outline-danger');
        btn.innerHTML = '<i class="fas fa-trash"></i>';
      });
      
      // 移除刪除標記
      const fileNames = existingFiles.querySelectorAll('.file-name');
      fileNames.forEach(fileName => {
        fileName.style.textDecoration = 'none';
        fileName.style.color = '';
      });
      
      // 清空現有文件容器
      existingFiles.innerHTML = '';
    }

    const submitBtn =
      document.getElementById("submitBtn") ||
      document.getElementById("createTeam") ||
      document.getElementById("updateTeam");
    if (submitBtn) {
      submitBtn.innerHTML = '<i class="fas fa-save"></i> 建立團隊';
    }

    const cancelBtn = document.getElementById("cancelBtn");
    if (cancelBtn) {
      cancelBtn.style.display = "none";
    }

    this.updateTeamIdPreview();
    
    console.log('✅ 表單重設完成，文件狀態已清理');
    console.log('📊 清理後狀態:', {
      editSelectedFiles: this.editSelectedFiles.length,
      deletedFiles: this.deletedFiles.length
    });
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
      return "";
    };

    const companyCode = getFieldValue([
      "company_code",
      "companyCode",
      "editCompanyCode",
    ]);
    const deptCode = getFieldValue(["dept_code", "deptCode", "editDeptCode"]);
    const teamCode = getFieldValue(["team_code", "teamCode", "editTeamCode"]);

    // 更新預覽（如果元素存在）
    const previewSection = document.getElementById("previewSection");
    const previewId = document.getElementById("previewId");
    const teamIdPreview = document.getElementById("teamIdPreview");

    if (companyCode && deptCode && teamCode) {
      const preview = teamsAPI.generateTeamIdPreview(
        companyCode,
        deptCode,
        teamCode
      );

      if (previewId) {
        previewId.textContent = preview;
      }
      if (teamIdPreview) {
        teamIdPreview.innerHTML = `<code>${preview}</code>`;
        teamIdPreview.className = "fw-bold text-primary";
      }
      if (previewSection) {
        previewSection.style.display = "block";
      }
    } else {
      if (teamIdPreview) {
        teamIdPreview.textContent = "請填寫必要欄位";
        teamIdPreview.className = "fw-bold text-muted";
      }
      if (previewSection) {
        previewSection.style.display = "none";
      }
    }
  }

  /**
   * 執行搜尋
   */
  performSearch() {
    const searchTerm = document
      .getElementById("searchInput")
      .value.toLowerCase()
      .trim();
    const selectedCompany = document.getElementById("companyFilter").value;

    this.filteredTeams = this.allTeams.filter((team) => {
      const matchesSearch =
        !searchTerm ||
        team.team_name.toLowerCase().includes(searchTerm) ||
        team.company.toLowerCase().includes(searchTerm) ||
        team.department.toLowerCase().includes(searchTerm) ||
        team.team_id.toLowerCase().includes(searchTerm) ||
        (team.team_description &&
          team.team_description.toLowerCase().includes(searchTerm));

      const matchesCompany =
        !selectedCompany || team.company === selectedCompany;

      return matchesSearch && matchesCompany;
    });

    this.renderTeams();
    this.hideLoading();
  }

  /**
   * 更新公司篩選器
   */
  updateCompanyFilter() {
    const companies = [...new Set(this.allTeams.map((team) => team.company))];
    const select = document.getElementById("companyFilter");

    // 保存當前選擇
    const currentValue = select.value;

    // 清空現有選項（保留「所有公司」）
    select.innerHTML = '<option value="">所有公司</option>';

    companies.forEach((company) => {
      const option = document.createElement("option");
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
    return date.toLocaleString("zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /**
   * 顯示 Toast 訊息
   */
  showToast(title, message, type = "info") {
    const toast = document.getElementById("messageToast");
    const toastIcon = document.getElementById("toastIcon");
    const toastTitle = document.getElementById("toastTitle");
    const toastMessage = document.getElementById("toastMessage");

    // 設定圖示和樣式
    const configs = {
      success: { icon: "fas fa-check-circle", class: "success" },
      error: { icon: "fas fa-exclamation-circle", class: "error" },
      info: { icon: "fas fa-info-circle", class: "info" },
    };

    const config = configs[type] || configs.info;

    // 移除舊的類別
    toast.classList.remove("success", "error", "info");
    // 添加新的類別
    toast.classList.add(config.class);

    toastIcon.innerHTML = `<i class="${config.icon}"></i>`;
    toastTitle.textContent = title;
    toastMessage.innerHTML = message;

    // 顯示 Toast
    toast.style.display = "flex";

    // 3秒後自動隱藏
    setTimeout(() => {
      this.hideToast();
    }, 3000);
  }

  /**
   * 隱藏 Toast
   */
  hideToast() {
    const toast = document.getElementById("messageToast");
    toast.style.display = "none";
  }

  /**
   * 查看團隊詳情
   */
  async viewTeam(teamId) {
    const team = this.allTeams.find((t) => t.team_id === teamId);
    if (!team) {
      this.showToast("錯誤", "找不到團隊資料", "error");
      return;
    }

    // 處理不同的欄位名稱
    const teamName = team.team_name || "";
    const company = team.company || "";
    const department = team.department || "";
    const description = team.description || team.team_description || "";
    const companyCode = team.company_code || "";
    const deptCode = team.dept_code || "";
    const teamCode = team.team_code || "";
    const createdAt = team.created_at || "";
    const updatedAt = team.updated_at || "";

    // 顯示團隊詳情
    const content = document.getElementById("teamDetailContent");
    content.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-building me-2"></i>公司</h6>
                    <p class="border-bottom pb-2">${company || "未設定"}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-building me-2"></i>部門</h6>
                    <p class="border-bottom pb-2">${department || "未設定"}</p>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-users me-2"></i>團隊名稱</h6>
                    <p class="border-bottom pb-2">${teamName || "未設定"}</p>
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-code me-2"></i>團隊代碼</h6>
                    <p class="border-bottom pb-2">${companyCode}-${deptCode}-${teamCode}</p>
                </div>
            </div>
            <div class="mb-3">
                <h6><i class="fas fa-info-circle me-2"></i>團隊描述</h6>
                <p class="border-bottom pb-2">${description || "未設定"}</p>
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
                <p><strong>建立時間:</strong> ${createdAt || "未知"}</p>
                <p><strong>最後更新:</strong> ${updatedAt || "未知"}</p>
            </div>
        `;

    // 設置編輯按鈕的 team_id
    document
      .getElementById("editFromDetail")
      .setAttribute("data-team-id", teamId);

    // 顯示模態框
    const modal = new bootstrap.Modal(
      document.getElementById("teamDetailModal")
    );
    modal.show();

    // 載入文件列表
    await this.loadTeamFiles(teamId);
  }

  /**
   * 載入團隊文件
   */
  async loadTeamFiles(teamId) {
    // 支援兩種容器：詳情視窗的 teamFiles 和編輯視窗的 existingFiles
    const containers = [
      document.getElementById("teamFiles"),
      document.getElementById("existingFiles"),
    ].filter(Boolean); // 過濾掉不存在的容器

    if (containers.length === 0) {
      console.warn("⚠️ 找不到文件容器");
      return;
    }

    // 檢查快取
    const now = Date.now();
    const lastCache = this.lastCacheTime.get(teamId);
    if (lastCache && (now - lastCache) < this.CACHE_TTL && this.fileCache.has(teamId)) {
      console.log(`📋 使用快取的文件列表: ${teamId}`);
      this.renderTeamFileList(containers, this.fileCache.get(teamId), teamId);
      return;
    }

    try {
      console.log("📂 載入團隊文件:", teamId);

      // 顯示載入狀態
      containers.forEach((container) => {
        container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">載入文件中...</div></div>';
      });

      const apiUrl = window.CONFIG
        ? window.CONFIG.API_BASE_URL
        : "https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev";
      const response = await fetch(
        `${apiUrl}/teams/${encodeURIComponent(teamId)}?action=files`
      );

      if (!response.ok) {
        containers.forEach((container) => {
          container.innerHTML = '<p class="text-danger">載入文件失敗</p>';
        });
        return;
      }

      // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
      const responseText = await response.text();
      
      if (!responseText.trim()) {
        containers.forEach((container) => {
          container.innerHTML = '<p class="text-danger">伺服器回傳空響應</p>';
        });
        return;
      }
      
      let result;
      try {
        result = JSON.parse(responseText);
        console.log('📦 文件 API 回應:', result);
      } catch (parseError) {
        console.error('❌ JSON 解析錯誤:', parseError);
        console.error('❌ 回應內容:', responseText);
        containers.forEach((container) => {
          container.innerHTML = '<p class="text-danger">伺服器回應格式錯誤</p>';
        });
        return;
      }
      
      // 處理多種可能的回應格式
      let files = [];
      if (Array.isArray(result)) {
        files = result;
      } else if (result.files && Array.isArray(result.files)) {
        files = result.files;
      } else if (result.data && Array.isArray(result.data)) {
        files = result.data;
      }
      
      // 確保每個文件都有必要的屬性
      files = files.map(file => ({
        key: file.key || file.Key || '',
        name: file.name || file.filename || file.original_filename || '',
        size: file.size || file.Size || 0,
        lastModified: file.lastModified || file.LastModified || file.last_modified || null
      }));
      
      console.log('📁 處理後的文件列表:', files);

      // 更新快取
      this.fileCache.set(teamId, files);
      this.lastCacheTime.set(teamId, now);

      this.renderTeamFileList(containers, files, teamId);
    } catch (error) {
      console.error("❌ 載入團隊文件失敗:", error);
      containers.forEach((container) => {
        container.innerHTML = '<p class="text-danger">載入文件失敗</p>';
      });
    }
  }

  /**
   * 渲染團隊文件列表
   */
  renderTeamFileList(containers, files, teamId) {
    if (files.length === 0) {
      containers.forEach((container) => {
        container.innerHTML = '<p class="text-muted">目前沒有任何文件</p>';
      });
      return;
    }

    const fileList = files
      .map((file) => {
        // 從 S3 key 中提取文件名稱 (移除 team_info_docs/{teamId}/ 前綴)
        const fileName = file.key
          ? file.key.replace(`team_info_docs/${teamId}/`, "")
          : file.name || "未知文件";
        const uploadDate = file.lastModified
          ? new Date(file.lastModified).toLocaleDateString("zh-TW")
          : "未知";
        const fileSize = file.size ? this.formatFileSize(file.size) : "未知";
        const fileExt = fileName.split(".").pop()?.toLowerCase() || "";
        const fileIcon = this.getFileIcon(fileExt);
        
        // 確保 fileKey 有效
        const fileKey = file.key || fileName;
        
        console.log("📁 渲染文件:", {
          fileName,
          fileKey,
          originalKey: file.key,
          teamId
        });

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
                          <button class="btn btn-sm btn-outline-primary" onclick="teamsUI.downloadTeamFile('${fileKey}', '${fileName}', '${teamId}')" title="下載文件">
                              <i class="fas fa-download"></i>
                          </button>
                          <button class="btn btn-sm btn-outline-danger" onclick="teamsUI.deleteTeamFile('${fileKey}', '${fileName}', '${teamId}')" title="刪除文件">
                              <i class="fas fa-trash"></i>
                          </button>
                      </div>
                  </div>
              `;
      })
      .join("");

    // 更新所有容器的內容
    containers.forEach((container) => {
      container.innerHTML = fileList;
    });
  }

  /**
   * 下載團隊文件
   */
  async downloadTeamFile(fileKey, fileName, teamId) {
    try {
      console.log("📥 下載文件:", fileName, "FileKey:", fileKey);

      const apiUrl = window.CONFIG
        ? window.CONFIG.API_BASE_URL
        : "https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev";

      // 確保 fileKey 不是 undefined
      if (!fileKey) {
        throw new Error("文件鍵值不存在");
      }

      // 使用正確的 API 路徑和 GET 方法
      const downloadUrl = `${apiUrl}/download-team-file/${encodeURIComponent(fileKey)}`;
      console.log("🔗 下載 API URL:", downloadUrl);
      
      const response = await fetch(downloadUrl, {
        method: "GET",
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ API 回應錯誤:", errorText);
        throw new Error(`下載失敗 HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      console.log("📦 下載 API 回應:", result);

      // 檢查回應是否包含下載 URL
      if (!result.download_url) {
        console.error("❌ API 回應缺少 downloadUrl:", result);
        throw new Error("伺服器未返回有效的下載連結");
      }

      console.log("🔗 準備下載:", result.download_url);

      // 開啟下載 URL
      const link = document.createElement("a");
      link.href = result.download_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      this.showToast("成功", "文件下載開始", "success");
    } catch (error) {
      console.error("❌ 文件下載失敗:", error);
      this.showToast("錯誤", "文件下載失敗：" + error.message, "error");
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
      console.log("🗑️ 刪除文件:", fileName);

      const apiUrl = window.CONFIG
        ? window.CONFIG.API_BASE_URL
        : "https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev";

      const response = await fetch(
        `${apiUrl}/delete-team-file/${encodeURIComponent(fileKey)}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(`刪除失敗 HTTP ${response.status}`);
      }

      this.showToast("成功", "文件刪除成功", "success");
      // 重新載入文件列表
      await this.loadTeamFiles(teamId);
    } catch (error) {
      console.error("❌ 文件刪除失敗:", error);
      this.showToast("錯誤", "文件刪除失敗：" + error.message, "error");
    }
  }

  /**
   * 格式化文件大小
   */
  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  /**
   * 獲取文件圖示
   */
  getFileIcon(fileExt) {
    const icons = {
      pdf: "fas fa-file-pdf",
      doc: "fas fa-file-word",
      docx: "fas fa-file-word",
      xls: "fas fa-file-excel",
      xlsx: "fas fa-file-excel",
      ppt: "fas fa-file-powerpoint",
      pptx: "fas fa-file-powerpoint",
      txt: "fas fa-file-alt",
      md: "fas fa-file-code",
      json: "fas fa-file-code",
      csv: "fas fa-file-csv",
      zip: "fas fa-file-archive",
      rar: "fas fa-file-archive",
      jpg: "fas fa-file-image",
      jpeg: "fas fa-file-image",
      png: "fas fa-file-image",
      gif: "fas fa-file-image",
    };
    return icons[fileExt] || "fas fa-file";
  }

  /**
   * 設置文件上傳功能
   */
  setupFileUpload() {
    // 設置編輯模式的文件上傳
    this.setupEditFileUpload();
  }

  /**
   * 設置編輯模式的文件上傳
   */
  setupEditFileUpload() {
    console.log('🔧 開始設置編輯文件上傳功能');
    
    const uploadArea = document.getElementById('editUploadArea');
    const fileInput = document.getElementById('editFileInput');
    
    console.log('📍 檢查元素:', {
      uploadArea: !!uploadArea,
      fileInput: !!fileInput,
      uploadAreaId: uploadArea?.id,
      fileInputId: fileInput?.id
    });
    
    if (!uploadArea || !fileInput) {
      console.error('❌ 找不到編輯文件上傳元素:', {
        uploadArea: !!uploadArea,
        fileInput: !!fileInput
      });
      return;
    }

    // 移除所有現有的事件監聽器（如果有的話）
    const newUploadArea = uploadArea.cloneNode(true);
    const newFileInput = fileInput.cloneNode(true);
    
    // 替換元素以移除事件監聽器
    uploadArea.parentNode.replaceChild(newUploadArea, uploadArea);
    fileInput.parentNode.replaceChild(newFileInput, fileInput);
    
    // 重新獲取元素引用
    const finalUploadArea = document.getElementById('editUploadArea');
    const finalFileInput = document.getElementById('editFileInput');
    
    console.log('📍 重新獲取元素:', {
      finalUploadArea: !!finalUploadArea,
      finalFileInput: !!finalFileInput
    });

    if (!finalUploadArea || !finalFileInput) {
      console.error('❌ 重新獲取元素失敗');
      return;
    }

    // 點擊上傳區域觸發文件選擇
    finalUploadArea.addEventListener('click', (e) => {
      console.log('🖱️ 點擊編輯上傳區域');
      e.preventDefault();
      e.stopPropagation();
      finalFileInput.click();
    });

    // 文件選擇事件
    finalFileInput.addEventListener('change', (e) => {
      console.log('📁 編輯文件輸入改變事件觸發');
      e.preventDefault();
      this.handleEditFiles(e.target.files);
      e.target.value = ''; // 清空輸入框
    });

    // 拖拽事件
    finalUploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      finalUploadArea.classList.add('dragover');
    });

    finalUploadArea.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      finalUploadArea.classList.remove('dragover');
    });

    finalUploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      finalUploadArea.classList.remove('dragover');
      
      if (e.dataTransfer && e.dataTransfer.files) {
        this.handleEditFiles(e.dataTransfer.files);
      }
    });
    
    // 標記為已初始化
    finalUploadArea.setAttribute('data-teams-ui-initialized', 'true');
    console.log('✅ 編輯文件上傳功能重新初始化完成');
    
    // 驗證功能是否正常
    console.log('🔍 驗證上傳區域:', {
      hasClickListener: finalUploadArea.onclick !== null,
      classList: Array.from(finalUploadArea.classList),
      style: finalUploadArea.style.cssText
    });
  }

  /**
   * 移除編輯文件上傳的事件監聽器
   */
  removeEditFileUploadListeners() {
    const uploadArea = document.getElementById('editUploadArea');
    if (uploadArea) {
      uploadArea.removeAttribute('data-teams-ui-initialized');
    }
  }

  /**
   * 處理編輯模式的文件選擇
   */
  handleEditFiles(files) {
    console.log(`📁 處理編輯文件選擇: ${files.length} 個文件`);
    
    if (files.length === 0) {
      console.warn('⚠️ 沒有選擇文件');
      return;
    }
    
    // 限制每次只能選擇一個文件
    if (files.length > 1) {
      this.showToast('提示', '每次只能選擇一個文件', 'info');
      return;
    }
    
    const file = files[0];
    console.log(`📁 處理文件: ${file.name} (${file.size} bytes, ${file.type})`);
    
    if (this.isValidFileType(file)) {
      this.editSelectedFiles.push(file);
      console.log(`✅ 文件添加成功，當前選擇的文件數: ${this.editSelectedFiles.length}`);
      this.renderEditFileList();
      this.showToast('成功', `文件 "${file.name}" 已添加`, 'success');
    } else {
      this.showToast('錯誤', `檔案 ${file.name} 格式不支援，僅支援 TXT, JSON, CSV, PDF 格式。`, 'error');
    }
  }

  /**
   * 驗證文件類型
   */
  isValidFileType(file) {
    const allowedTypes = ['.txt', '.json', '.csv', '.pdf'];
    const fileName = file.name.toLowerCase();
    return allowedTypes.some(type => fileName.endsWith(type));
  }

  /**
   * 渲染編輯文件列表
   */
  renderEditFileList() {
    const fileListElement = document.getElementById('editFileList');
    if (!fileListElement) return;

    fileListElement.innerHTML = '';
    this.editSelectedFiles.forEach((file, index) => {
      const fileItem = document.createElement('div');
      fileItem.className = 'alert alert-info alert-dismissible fade show';
      fileItem.innerHTML = `
        <i class="fas fa-file me-2"></i>${file.name}
        <button type="button" class="btn-close" onclick="teamsUI.removeEditFile(${index})"></button>
      `;
      fileListElement.appendChild(fileItem);
    });
  }

  /**
   * 移除編輯文件
   */
  removeEditFile(index) {
    this.editSelectedFiles.splice(index, 1);
    this.renderEditFileList();
  }

  /**
   * 刷新特定團隊的文件列表
   */
  async refreshFileListsForTeam(teamId) {
    console.log(`🔄 開始刷新團隊 ${teamId} 的文件列表`);
    
    // 刷新所有可能顯示這個團隊文件的容器
    const containerIds = [
      `files-${teamId}`,
      'teamFiles',
      'existingFiles'
    ];
    
    for (const containerId of containerIds) {
      const container = document.getElementById(containerId);
      if (container) {
        console.log(`🔄 發現容器 ${containerId}，開始刷新`);
        
        if (containerId === 'existingFiles') {
          // 特別處理編輯模式的文件列表
          await this.loadExistingFiles(teamId);
        } else {
          // 處理其他文件列表容器
          await this.loadTeamFiles(teamId);
        }
      }
    }
    
    console.log(`✅ 完成刷新團隊 ${teamId} 的文件列表`);
  }

  /**
   * 載入編輯模式下的現有文件
   */
  async loadExistingFiles(teamId) {
    const container = document.getElementById('existingFiles');
    if (!container) {
      console.warn('⚠️ 找不到 existingFiles 容器');
      return;
    }

    try {
      container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">載入文件中...</div></div>';

      const apiUrl = window.CONFIG
        ? window.CONFIG.API_BASE_URL
        : "https://44wy0r4r16.execute-api.ap-southeast-1.amazonaws.com/dev";
        
      const response = await fetch(`${apiUrl}/teams/${encodeURIComponent(teamId)}?action=files`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      // 改進響應處理：先獲取響應文本，再嘗試解析 JSON
      const responseText = await response.text();
      
      if (!responseText.trim()) {
        throw new Error('伺服器回傳空響應');
      }
      
      let result;
      try {
        result = JSON.parse(responseText);
      } catch (parseError) {
        console.error('❌ JSON 解析錯誤:', parseError);
        console.error('❌ 回應內容:', responseText);
        throw new Error(`伺服器回應格式錯誤: ${parseError.message}`);
      }
      const files = Array.isArray(result) ? result : (result.files || []);
      
      if (files.length === 0) {
        container.innerHTML = '<p class="text-muted">目前沒有任何文件</p>';
        return;
      }
      
      let html = '';
      files.forEach(file => {
        // 從 S3 key 中提取文件名稱
        const fileName = file.key ? file.key.split('/').pop() : (file.name || '未知文件');
        const fileKey = file.key || fileName;
        const fileSize = file.size ? this.formatFileSize(file.size) : '未知大小';
        
        console.log('📁 載入現有文件:', {
          fileName,
          fileKey,
          originalKey: file.key,
          teamId
        });
        
        html += `
          <div class="file-item d-flex justify-content-between align-items-center mb-2">
            <div class="file-info">
              <i class="fas fa-file me-2"></i>
              <span class="file-name">${fileName}</span>
              <small class="text-muted ms-2">${fileSize}</small>
            </div>
            <div class="file-actions">
              <button class="btn btn-sm btn-outline-primary me-2" 
                      onclick="window.teamsUI && window.teamsUI.downloadTeamFile('${fileKey}', '${fileName}', '${teamId}')"
                      title="下載文件">
                <i class="fas fa-download"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger delete-file-btn" 
                      data-file-key="${fileKey}" 
                      data-deleted="false"
                      onclick="window.teamsUI && window.teamsUI.toggleFileDelete(this)"
                      title="刪除文件">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </div>
        `;
      });
      
      container.innerHTML = html;
      console.log(`✅ 載入了 ${files.length} 個現有文件`);
      
    } catch (error) {
      console.error('❌ 載入現有文件失敗:', error);
      container.innerHTML = '<p class="text-danger"><i class="fas fa-exclamation-circle me-2"></i>載入文件失敗</p>';
    }
  }

  /**
   * 切換文件刪除狀態
   */
  toggleFileDelete(button) {
    if (!button) {
      console.error('❌ toggleFileDelete: 按鈕元素不存在');
      return;
    }
    
    const isDeleted = button.dataset.deleted === 'true';
    const newDeletedState = !isDeleted;
    button.dataset.deleted = newDeletedState.toString();
    
    const fileItem = button.closest('.file-item');
    if (!fileItem) {
      console.error('❌ toggleFileDelete: 找不到文件項目容器');
      return;
    }
    
    const fileName = fileItem.querySelector('.file-name');
    if (!fileName) {
      console.error('❌ toggleFileDelete: 找不到文件名元素');
      return;
    }
    
    if (newDeletedState) {
      // 標記為刪除
      button.classList.remove('btn-outline-danger');
      button.classList.add('btn-danger');
      button.innerHTML = '<i class="fas fa-undo"></i>';
      button.title = '取消刪除';
      
      fileName.style.textDecoration = 'line-through';
      fileName.style.color = '#dc3545';
      
      console.log(`🗑️ 文件標記為刪除: ${button.dataset.fileKey}`);
    } else {
      // 取消刪除標記
      button.classList.remove('btn-danger');
      button.classList.add('btn-outline-danger');
      button.innerHTML = '<i class="fas fa-trash"></i>';
      button.title = '刪除文件';
      
      fileName.style.textDecoration = 'none';
      fileName.style.color = '';
      
      console.log(`↩️ 取消刪除標記: ${button.dataset.fileKey}`);
    }
  }

  /**
   * 刷新當前團隊資料
   */
  async refreshCurrentTeamData(teamId) {
    try {
      console.log(`🔄 刷新團隊資料: ${teamId}`);
      
      const result = await teamsAPI.getTeam(teamId);
      if (result.success) {
        // 更新 allTeams 中對應的團隊資料
        const index = this.allTeams.findIndex(team => team.team_id === teamId);
        if (index !== -1) {
          this.allTeams[index] = result.data.team;
          console.log(`✅ 已更新團隊 ${teamId} 的資料`);
          
          // 重新渲染團隊列表以反映最新資料
          this.renderTeams();
        }
      }
    } catch (error) {
      console.error(`❌ 刷新團隊 ${teamId} 資料失敗:`, error);
    }
  }
}

// 全域函數
function hideToast() {
  if (window.teamsUI) {
    window.teamsUI.hideToast();
  }
}

// 頁面載入完成後初始化
document.addEventListener("DOMContentLoaded", () => {
  window.teamsUI = new TeamsUI();
});
