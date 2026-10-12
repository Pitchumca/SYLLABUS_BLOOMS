// Base URL detection with robust normalization
function getNormalizedApiBase() {
  let base = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');
  if (!base) {
    return '/api';
  }
  if (!base.endsWith('/api')) {
    return `${base}/api`;
  }
  return base;
}

const API_BASE = getNormalizedApiBase();
const DIRECT_BACKEND = 'http://127.0.0.1:8000/api';

/**
 * Universal fetch wrapper with automatic fallback between relative proxy (/api)
 * and direct backend (http://127.0.0.1:8000/api), plus informative error messages,
 * safe response parsing, automatic Bearer token refresh, and connection error classification.
 */
async function apiRequest(endpoint, options = {}) {
  let path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (path.startsWith('/api/')) {
    path = path.slice(4);
  } else if (path === '/api') {
    path = '';
  }

  const targets = [
    `${API_BASE}${path}`,
    `${DIRECT_BACKEND}${path}`
  ];

  // Inject Authorization header if token is stored in localStorage
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  options.headers = headers;

  let lastError = null;

  for (let i = 0; i < targets.length; i++) {
    const url = targets[i];
    try {
      const res = await fetch(url, options);

      // Automatic token refresh on 401 Unauthorized
      if (res.status === 401 && !options._isRetry && token && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
        try {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });
          if (refreshRes.ok) {
            const refreshData = await refreshRes.json();
            if (refreshData?.access_token) {
              localStorage.setItem('auth_token', refreshData.access_token);
              localStorage.setItem('access_token', refreshData.access_token);
              const retryHeaders = new Headers(options.headers || {});
              retryHeaders.set('Authorization', `Bearer ${refreshData.access_token}`);
              return await apiRequest(endpoint, {
                ...options,
                headers: retryHeaders,
                _isRetry: true
              });
            }
          }
        } catch {
          // Token refresh failed, continue to standard error processing
        }
      }

      if (!res.ok) {
        if (i === 0 && res.status >= 500 && targets.length > 1) {
          continue;
        }

        // Safe response reading: text first, then JSON if valid
        const contentType = res.headers.get('content-type') || '';
        const rawText = await res.text();
        let errData = null;
        if (contentType.includes('application/json')) {
          try {
            errData = JSON.parse(rawText);
          } catch {
            errData = null;
          }
        }

        let stage = 'UNKNOWN_STAGE';
        let stageExplanation = '';

        if (res.status === 401) {
          stage = 'AUTHENTICATION_REQUIRED';
          stageExplanation = 'Your session has expired or authentication credentials are required.';
        } else if (res.status === 403) {
          stage = 'ACCESS_FORBIDDEN';
          stageExplanation = 'You do not have administrative or faculty permissions for this resource.';
        } else if (res.status === 404) {
          stage = 'ENDPOINT_NOT_FOUND';
          stageExplanation = `The requested endpoint was not found on the backend: ${path}`;
        } else if (res.status === 429) {
          stage = 'RATE_LIMIT_EXCEEDED';
          stageExplanation = 'Rate limit exceeded on external repository providers. Please wait 30 seconds.';
        } else if (res.status >= 500) {
          stage = 'BACKEND_SERVICE_ERROR';
          stageExplanation = `Backend server error (${res.status}). External provider or database issue.`;
        }

        let detailMsg = '';
        if (typeof errData?.detail === 'string') {
          detailMsg = errData.detail;
        } else if (Array.isArray(errData?.detail)) {
          detailMsg = errData.detail.map(d => d.msg || JSON.stringify(d)).join(', ');
        } else if (errData?.message) {
          detailMsg = errData.message;
        } else if (rawText && rawText.length < 300 && !rawText.includes('<!DOCTYPE')) {
          detailMsg = rawText;
        }

        const fullMessage = detailMsg 
          ? `${stageExplanation ? stageExplanation + ' ' : ''}${detailMsg}` 
          : (stageExplanation || `Server returned ${res.status}: ${res.statusText}`);

        const error = new Error(fullMessage);
        error.status = res.status;
        error.stage = stage;
        error.data = errData;
        error.rawBody = rawText;
        throw error;
      }

      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const text = await res.text();
        try {
          return JSON.parse(text);
        } catch {
          return text;
        }
      }
      return res;

    } catch (err) {
      lastError = err;
      if (err.status && err.status < 500) {
        throw err;
      }
      if (i < targets.length - 1) {
        continue;
      }
    }
  }

  const networkErr = new Error(
    `Unable to connect to backend server (${path}). Please ensure FastAPI is running on port 8000 and CORS is allowed.`
  );
  networkErr.stage = 'NETWORK_CONNECTIVITY_FAILURE';
  networkErr.originalError = lastError;
  throw lastError && lastError.status ? lastError : networkErr;
}

export const api = {
  // Health
  async checkHealth() {
    return apiRequest('/health');
  },

  // Auth
  async login(email, password) {
    return apiRequest('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
  },

  async getMe() {
    return apiRequest('/auth/me');
  },

  // Faculty Management (Admin)
  async getFacultyList(params = {}) {
    const query = new URLSearchParams();
    if (params.department) query.append('department', params.department);
    if (params.designation) query.append('designation', params.designation);
    if (params.search) query.append('search', params.search);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return apiRequest(`/faculty${queryString}`);
  },

  async getFacultyStats() {
    return apiRequest('/faculty/stats');
  },

  async createFaculty(facultyData) {
    return apiRequest('/faculty', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(facultyData)
    });
  },

  async updateFaculty(id, facultyData) {
    return apiRequest(`/faculty/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(facultyData)
    });
  },

  async deleteFaculty(id) {
    return apiRequest(`/faculty/${id}`, {
      method: 'DELETE'
    });
  },

  // Syllabus Upload & Extraction
  async uploadSyllabus(file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest('/upload', {
      method: 'POST',
      body: formData,
    });
  },

  async loadSampleSyllabus() {
    return apiRequest('/upload/sample', {
      method: 'POST',
    });
  },

  async triggerOCR(syllabusId) {
    return apiRequest(`/upload/ocr/${syllabusId}`, {
      method: 'POST',
    });
  },

  async getSyllabus(syllabusId) {
    return apiRequest(`/upload/syllabus/${syllabusId}`);
  },

  async updateSyllabus(syllabusId, text) {
    return apiRequest(`/upload/syllabus/${syllabusId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extracted_text: text }),
    });
  },

  async updateSyllabusText(syllabusId, text) {
    return this.updateSyllabus(syllabusId, text);
  },

  async listRecentSyllabuses(limit = 10) {
    return apiRequest(`/upload/syllabuses?limit=${limit}`);
  },

  // Course Content Upload (PPT/PPTX, PDF) & Outcomes
  async uploadContentFile(file, syllabusId = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (syllabusId) {
      formData.append('syllabus_id', syllabusId);
    }
    return apiRequest('/content/upload', {
      method: 'POST',
      body: formData
    });
  },

  async getContentFiles(syllabusId) {
    return apiRequest(`/content/syllabus/${syllabusId}`);
  },

  async getContentFilePreview(fileId) {
    return apiRequest(`/content/file/${fileId}/preview`);
  },

  async deleteContentFile(fileId) {
    return apiRequest(`/content/file/${fileId}`, {
      method: 'DELETE'
    });
  },

  async getContentAlignments(syllabusId) {
    return apiRequest(`/content/syllabus/${syllabusId}/alignments`);
  },

  async getCourseOutcomes(syllabusId) {
    return apiRequest(`/content/syllabus/${syllabusId}/outcomes`);
  },

  async getSyllabusUnits(syllabusId) {
    return apiRequest(`/content/syllabus/${syllabusId}/units`);
  },

  // Question Paper Blueprint & Generation
  async getCourseMetadata(syllabusId) {
    return apiRequest(`/question-paper/course-metadata?syllabus_id=${syllabusId}`);
  },

  async getCoverageMatrix(coveragePayload) {
    return apiRequest('/question-paper/coverage-matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(coveragePayload)
    });
  },

  async getBlueprintPresets() {
    return apiRequest('/question-paper/blueprint/presets');
  },

  async generateQuestionPaper(blueprintPayload) {
    return apiRequest('/question-paper/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(blueprintPayload)
    });
  },

  async getQuestionPaper(paperId) {
    return apiRequest(`/question-paper/${paperId}`);
  },

  async listFacultyQuestionPapers() {
    return apiRequest('/question-paper');
  },

  async updateQuestion(paperId, questionId, updateData) {
    return apiRequest(`/question-paper/${paperId}/question/${questionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData)
    });
  },

  async reviewQuestion(paperId, questionId, reviewData) {
    return apiRequest(`/question-paper/${paperId}/question/${questionId}/review`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reviewData)
    });
  },

  async getQuestionProvenance(paperId, questionId) {
    return apiRequest(`/question-paper/${paperId}/question/${questionId}/source`);
  },

  async validateAllQuestions(paperId) {
    return apiRequest(`/question-paper/${paperId}/validate-all`, {
      method: 'POST'
    });
  },

  async regenerateQuestion(paperId, questionId, directiveData = {}) {
    return apiRequest(`/question-paper/${paperId}/question/${questionId}/regenerate`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(directiveData)
    });
  },

  async addCustomQuestion(paperId, questionData, params = {}) {
    const query = new URLSearchParams(params).toString();
    const queryString = query ? `?${query}` : '';
    return apiRequest(`/question-paper/${paperId}/question${queryString}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(questionData)
    });
  },

  async deleteQuestion(paperId, questionId) {
    return apiRequest(`/question-paper/${paperId}/question/${questionId}`, {
      method: 'DELETE'
    });
  },

  async uploadWordTemplate(paperId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest(`/question-paper/${paperId}/upload-template`, {
      method: 'POST',
      body: formData
    });
  },

  // Module B & E: Institution Question Paper Template Extraction & Library
  async uploadAndExtractTemplate(file, syllabusId = null) {
    const formData = new FormData();
    formData.append('file', file);
    const query = syllabusId ? `?syllabus_id=${syllabusId}` : '';
    return apiRequest(`/template/upload${query}`, {
      method: 'POST',
      body: formData
    });
  },

  async validateExtractedBlueprint(blueprint, syllabusId = null) {
    const query = syllabusId ? `?syllabus_id=${syllabusId}` : '';
    return apiRequest(`/template/validate${query}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(blueprint)
    });
  },

  async saveTemplateToLibrary(templateData) {
    return apiRequest('/template/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(templateData)
    });
  },

  async getTemplateLibrary(params = {}) {
    const query = new URLSearchParams();
    if (params.course_code) query.append('course_code', params.course_code);
    if (params.exam_type) query.append('exam_type', params.exam_type);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return apiRequest(`/template/library${queryString}`);
  },

  async listTemplates(params = {}) {
    return this.getTemplateLibrary(params);
  },

  async getTemplateDetail(templateId) {
    return apiRequest(`/template/${templateId}`);
  },

  async getTemplate(templateId) {
    return this.getTemplateDetail(templateId);
  },

  async updateTemplate(templateId, updateData) {
    return apiRequest(`/template/${templateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData)
    });
  },

  async deleteTemplate(templateId) {
    return apiRequest(`/template/${templateId}`, {
      method: 'DELETE'
    });
  },

  getTemplateOriginalDownloadUrl(templateId) {
    return `${DIRECT_BACKEND}/template/${templateId}/download-original`;
  },

  getTemplateBlueprintJsonDownloadUrl(templateId) {
    return `${DIRECT_BACKEND}/template/${templateId}/export-blueprint-json`;
  },

  async getExportValidation(paperId) {
    return apiRequest(`/question-paper/${paperId}/export-validation/`);
  },

  async downloadQuestionPaperDocx(paperId, exportType = 'question_paper', exportApprovedOnly = true) {
    const query = `?export_type=${encodeURIComponent(exportType)}&export_approved_only=${exportApprovedOnly}`;
    const path = `/question-paper/${paperId}/download-docx${query}`;
    const targets = [
      `${API_BASE}${path}`,
      `${DIRECT_BACKEND}${path}`
    ];

    const token = localStorage.getItem('auth_token');
    const headers = new Headers();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    let lastError = null;
    for (let i = 0; i < targets.length; i++) {
      const url = targets[i];
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers
        });

        if (!response.ok) {
          if (i === 0 && response.status >= 500) {
            continue;
          }

          let errorMsg = `Server returned ${response.status}: ${response.statusText}`;
          try {
            const errData = await response.json();
            errorMsg = errData.detail || errData.message || errorMsg;
          } catch {
            // response was not JSON
          }

          const error = new Error(errorMsg);
          error.status = response.status;
          error.response = { status: response.status, data: { detail: errorMsg } };
          throw error;
        }

        const contentType = response.headers.get('content-type') || '';
        if (
          contentType.includes('application/json') ||
          !contentType.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        ) {
          const errorText = await response.text();
          let message = 'Unable to generate the Word document.';
          try {
            const errorData = JSON.parse(errorText);
            message = errorData.detail || errorData.message || message;
          } catch {
            // retain default message
          }
          throw new Error(message);
        }

        const disposition = response.headers.get('content-disposition');
        let filename = `Question_Paper_${paperId}.docx`;
        const filenameMatch = disposition?.match(/filename\*?=(?:UTF-8''|")?([^";]+)/);
        if (filenameMatch?.[1]) {
          filename = decodeURIComponent(filenameMatch[1].replace(/"/g, ''));
        }

        const blob = await response.blob();
        if (blob.size === 0) {
          throw new Error('The generated Word document is empty.');
        }

        return { blob, filename };
      } catch (err) {
        lastError = err;
        if (i < targets.length - 1) {
          continue;
        }
        throw lastError;
      }
    }
  },

  async downloadQuestionPaperPdf(paperId, exportType = 'question_paper', exportApprovedOnly = true) {
    const query = `?export_type=${encodeURIComponent(exportType)}&export_approved_only=${exportApprovedOnly}`;
    const path = `/question-paper/${paperId}/download-pdf${query}`;
    const targets = [
      `${API_BASE}${path}`,
      `${DIRECT_BACKEND}${path}`
    ];

    const token = localStorage.getItem('auth_token');
    const headers = new Headers();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    let lastError = null;
    for (let i = 0; i < targets.length; i++) {
      const url = targets[i];
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers
        });

        if (!response.ok) {
          if (i === 0 && response.status >= 500) {
            continue;
          }
          let errorMsg = `Server returned ${response.status}: ${response.statusText}`;
          try {
            const errData = await response.json();
            errorMsg = errData.detail || errData.message || errorMsg;
          } catch {}
          const error = new Error(errorMsg);
          error.status = response.status;
          error.response = { status: response.status, data: { detail: errorMsg } };
          throw error;
        }

        const disposition = response.headers.get('content-disposition');
        let filename = `Question_Paper_${paperId}.pdf`;
        const filenameMatch = disposition?.match(/filename\*?=(?:UTF-8''|")?([^";]+)/);
        if (filenameMatch?.[1]) {
          filename = decodeURIComponent(filenameMatch[1].replace(/"/g, ''));
        }

        const blob = await response.blob();
        if (blob.size === 0) {
          throw new Error('The generated PDF document is empty.');
        }

        return { blob, filename };
      } catch (err) {
        lastError = err;
        if (i < targets.length - 1) {
          continue;
        }
        throw lastError;
      }
    }
  },

  async getQuestionPaperProvenanceReport(paperId) {
    return apiRequest(`/question-paper/${paperId}/provenance-report`);
  },

  async getQuestionPaperValidationReport(paperId) {
    return apiRequest(`/question-paper/${paperId}/validation-report`);
  },

  getDefaultTemplateUrl() {
    return `${DIRECT_BACKEND}/question-paper/default-template/download`;
  },

  // Book Parsing & Review
  async parseBooks(syllabusId, customText = null) {
    const body = customText ? JSON.stringify({ syllabus_id: syllabusId, custom_text: customText }) : undefined;
    const headers = customText ? { 'Content-Type': 'application/json' } : {};
    return apiRequest(`/books/parse/${syllabusId}`, {
      method: 'POST',
      headers,
      body,
    });
  },

  async getBooks(syllabusId, category = null, search = null) {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (search) params.append('search', search);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return apiRequest(`/books/syllabus/${syllabusId}${queryString}`);
  },

  async createBook(syllabusId, bookData) {
    return apiRequest(`/books/syllabus/${syllabusId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookData),
    });
  },

  async updateBook(bookId, bookData) {
    return apiRequest(`/books/${bookId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookData),
    });
  },

  async deleteBook(bookId) {
    return apiRequest(`/books/${bookId}`, {
      method: 'DELETE',
    });
  },

  async mergeBooks(primaryBookId, secondaryBookIds, overrideData = {}) {
    return apiRequest(`/books/merge/${primaryBookId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_book_id: primaryBookId,
        source_book_ids: secondaryBookIds,
        merged_data: overrideData,
        secondary_book_ids: secondaryBookIds,
        override_data: overrideData,
      }),
    });
  },

  async confirmAllBooks(syllabusId) {
    return apiRequest(`/books/confirm-all/${syllabusId}`, {
      method: 'POST',
    });
  },

  // Lawful Search & Prioritization
  async searchSingleBook(bookId) {
    return apiRequest(`/search/book/${bookId}`, {
      method: 'POST',
    });
  },

  async searchSyllabusBooks(syllabusId) {
    return apiRequest(`/search/syllabus/${syllabusId}`, {
      method: 'POST',
    });
  },

  // Asynchronous Multi-Repository Book Search & RAG Indexing Pipeline
  async startCourseBookSearchAndIndex(courseOrSyllabusId, payload = {}) {
    return apiRequest(`/courses/${courseOrSyllabusId}/books/search-and-index/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_ids: payload.book_ids,
        search_sources: payload.search_sources || [
          'local_database', 'open_library', 'google_books', 'internet_archive',
          'oer_commons', 'crossref', 'semantic_scholar', 'doab'
        ],
        find_accessible_files: payload.find_accessible_files !== false,
        download_verified_files: payload.download_verified_files !== false,
        start_rag_indexing: payload.start_rag_indexing !== false
      })
    });
  },

  async getBookSearchJob(jobId) {
    return apiRequest(`/book-search-jobs/${jobId}/`);
  },

  async retryBookSearchInJob(jobId, bookId) {
    return apiRequest(`/book-search-jobs/${jobId}/retry-book/${bookId}/`, {
      method: 'POST'
    });
  },

  async getSearchResults(syllabusId, filters = {}) {
    const params = new URLSearchParams();
    params.append('syllabus_id', syllabusId);
    if (filters.category && filters.category !== 'All') params.append('category', filters.category);
    if (filters.access_status && filters.access_status !== 'All') params.append('access_status', filters.access_status);
    if (filters.access_type && filters.access_type !== 'All') params.append('access_type', filters.access_type);
    if (filters.accessTier && filters.accessTier !== 'All') params.append('access_tier', filters.accessTier);
    if (filters.source && filters.source !== 'All') params.append('source', filters.source);
    if (filters.min_confidence !== undefined && filters.min_confidence !== null && filters.min_confidence > 0) {
      params.append('min_confidence', filters.min_confidence);
    }
    if (filters.minConfidence !== undefined && filters.minConfidence !== null && filters.minConfidence > 0) {
      params.append('min_confidence', filters.minConfidence);
    }
    if (filters.query_text) params.append('query_text', filters.query_text);
    if (filters.search) params.append('search', filters.search);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return apiRequest(`/search/syllabus/${syllabusId}${queryString}`);
  },

  async triggerAutoDownloadJobs(syllabusId) {
    return apiRequest(`/search/auto-download-jobs/${syllabusId}`, {
      method: 'POST'
    });
  },

  async verifyAndDownloadResult(searchResultId) {
    return apiRequest(`/search/verify-and-download/${searchResultId}`, {
      method: 'POST'
    });
  },

  async retryVerification(searchResultId) {
    return apiRequest(`/search/retry-verification/${searchResultId}`, {
      method: 'POST'
    });
  },

  async getJobStatus(jobId) {
    return apiRequest(`/search/jobs/${jobId}`);
  },

  async getJobForBook(bookId) {
    return apiRequest(`/search/jobs/by-book/${bookId}`);
  },

  async getFacultySettings() {
    return apiRequest('/faculty/settings');
  },

  async updateFacultySettings(settingsData) {
    return apiRequest('/faculty/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settingsData)
    });
  },


  // Analytics
  async getAnalytics(syllabusId) {
    return apiRequest(`/analytics/syllabus/${syllabusId}`);
  },

  // Export
  async exportReport(syllabusId, format, options = {}) {
    const res = await apiRequest('/export/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        syllabus_id: syllabusId,
        format: format,
        include_unmatched: options.includeUnmatched ?? true,
        department: options.department || 'Computer Science & Engineering',
        course_name: options.courseName || 'Advanced Data Structures & Algorithms',
      }),
    });
    return res;
  },

  async getExportHistory(syllabusId = null) {
    const endpoint = syllabusId ? `/export/history/${syllabusId}` : '/export/history';
    return apiRequest(endpoint);
  },

  getDownloadUrl(filename) {
    return `${DIRECT_BACKEND}/export/download/${filename}`;
  },

  // Student Adaptive Learning Module
  async getStudentProfile() {
    return apiRequest('/student/profile');
  },

  async getStudentCourses() {
    return apiRequest('/student/courses');
  },

  async getStudentCourseDetails(courseId) {
    return apiRequest(`/student/courses/${courseId}`);
  },

  async getStudentDashboard() {
    return apiRequest('/student/dashboard');
  },

  async getStudentNotifications() {
    return apiRequest('/student/notifications');
  },

  async markNotificationRead(notificationId) {
    return apiRequest(`/student/notifications/${notificationId}/read`, {
      method: 'PUT'
    });
  },

  // Module A: Lawful Online PDF Acquisition & Indexing
  async verifyResourceRights(url, metadata = {}) {
    return apiRequest('/resources/verify-rights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_url: url, ...metadata })
    });
  },

  async acquireLawfulResource(data) {
    return apiRequest('/resources/acquire', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  },

  async getSyllabusResources(syllabusId) {
    return apiRequest(`/resources/syllabus/${syllabusId}`);
  },

  async getResourceDetails(resourceId) {
    return apiRequest(`/resources/${resourceId}`);
  },

  async getResourceChunks(resourceId, unitNumber = null) {
    const query = unitNumber ? `?unit_number=${unitNumber}` : '';
    return apiRequest(`/resources/${resourceId}/chunks${query}`);
  },

  async approveResourceForRag(resourceId, approved = true, units = null) {
    return apiRequest(`/resources/${resourceId}/approve`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved, units })
    });
  },

  async deleteResource(resourceId) {
    return apiRequest(`/resources/${resourceId}`, {
      method: 'DELETE'
    });
  },

  async getDownloadAuditLogs(limit = 50) {
    return apiRequest(`/resources/audit/logs?limit=${limit}`);
  },

  // Faculty Settings & Auto-download Workflow
  async getFacultySettings() {
    return apiRequest('/faculty/settings');
  },

  async updateFacultySettings(settings) {
    return apiRequest('/faculty/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
  },

  async triggerAutoDownloadJobs(syllabusId) {
    return apiRequest(`/search/auto-download-jobs/${syllabusId}`, {
      method: 'POST'
    });
  },

  async verifyAndDownloadResult(searchResultId) {
    return apiRequest(`/search/verify-and-download/${searchResultId}`, {
      method: 'POST'
    });
  },

  async retryVerification(searchResultId) {
    return apiRequest(`/search/retry-verification/${searchResultId}`, {
      method: 'POST'
    });
  },

  async getJobStatus(jobId) {
    return apiRequest(`/search/jobs/${jobId}`);
  },

  async getJobForBook(bookId) {
    return apiRequest(`/search/jobs/by-book/${bookId}`);
  },

  // Multi-Source Discovery & RAG API (Sections 1-14)
  async parseDiscoveryBooks(syllabusId, customText) {
    return apiRequest('/discovery/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ syllabus_id: syllabusId, custom_text: customText })
    });
  },

  async getDiscoveryBooks(syllabusId, resourceType) {
    let url = '/discovery/books';
    const params = [];
    if (syllabusId) params.push(`syllabus_id=${syllabusId}`);
    if (resourceType) params.push(`resource_type=${resourceType}`);
    if (params.length) url += `?${params.join('&')}`;
    return apiRequest(url);
  },

  async searchDiscoveryBook(payload) {
    return apiRequest('/discovery/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  async preValidateDiscoveryLink(url, bookSourceId, bookFileId) {
    return apiRequest('/discovery/verify-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, book_source_id: bookSourceId, book_file_id: bookFileId })
    });
  },

  async triggerDiscoveryDownloadAndIndex(bookId, syllabusId, courseId) {
    return apiRequest('/discovery/download-and-index', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_id: bookId, syllabus_id: syllabusId, course_id: courseId })
    });
  },

  async batchDownloadVerifiedDiscovery(syllabusId, courseId) {
    return apiRequest('/discovery/download-all-verified', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ syllabus_id: syllabusId, course_id: courseId })
    });
  },

  async getDiscoveryJobStatus(jobId) {
    return apiRequest(`/discovery/jobs/${jobId}`);
  },

  async cancelDiscoveryJob(jobId) {
    return apiRequest(`/discovery/jobs/${jobId}/cancel`, {
      method: 'POST'
    });
  },

  async retryDiscoveryJob(jobId) {
    return apiRequest(`/discovery/jobs/${jobId}/retry`, {
      method: 'POST'
    });
  },

  async getDiscoveryCoverageMatrix(syllabusId, courseId) {
    let url = `/discovery/coverage-matrix?syllabus_id=${syllabusId}`;
    if (courseId) url += `&course_id=${courseId}`;
    return apiRequest(url);
  },

  async reindexDiscoveryBook(bookId) {
    return apiRequest('/discovery/reindex', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_id: bookId })
    });
  },

  async removeDiscoveryBookIndex(bookId) {
    return apiRequest(`/discovery/index/${bookId}`, {
      method: 'DELETE'
    });
  },

  async mergeDiscoveryBooks(primaryBookId, secondaryBookIds) {
    return apiRequest('/discovery/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ primary_book_id: primaryBookId, secondary_book_ids: secondaryBookIds })
    });
  },

  async updateDiscoveryBookMetadata(bookId, payload) {
    return apiRequest(`/discovery/metadata/${bookId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  }
};

