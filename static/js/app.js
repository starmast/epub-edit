// ePub Editor - Main Application JavaScript

class EPubEditorApp {
    constructor() {
        this.currentProject = null;
        this.currentView = 'projects';
        this.websocket = null;
        this.projects = [];
        this.chapters = [];

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadProjects();
    }

    setupEventListeners() {
        // Upload area
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('epub-file-input');

        uploadArea.addEventListener('click', () => fileInput.click());

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].name.endsWith('.epub')) {
                this.uploadEpub(files[0]);
            } else {
                this.showToast('Please upload an ePub file', 'error');
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadEpub(e.target.files[0]);
            }
        });

        // Home button
        document.getElementById('home-btn').addEventListener('click', () => {
            this.showProjectsView();
        });

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.fixed').classList.add('hidden');
            });
        });

        // LLM Config Form
        document.getElementById('llm-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveLLMConfig();
        });

        // Test Connection
        document.getElementById('test-connection-btn').addEventListener('click', () => {
            this.testLLMConnection();
        });

        // Fetch Models
        document.getElementById('fetch-models-btn').addEventListener('click', () => {
            this.fetchAvailableModels();
        });

        // Processing Form
        document.getElementById('processing-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startProcessing();
        });

        // Worker count slider
        document.getElementById('worker-count').addEventListener('input', (e) => {
            document.getElementById('worker-count-display').textContent = e.target.value;
        });

        // Chapters per batch slider
        document.getElementById('chapters-per-batch').addEventListener('input', (e) => {
            document.getElementById('chapters-per-batch-display').textContent = e.target.value;
        });
    }

    // ========== API Methods ==========

    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            this.projects = await response.json();
            this.renderProjects();
        } catch (error) {
            console.error('Error loading projects:', error);
            this.showToast('Failed to load projects', 'error');
        }
    }

    async uploadEpub(file) {
        const formData = new FormData();
        formData.append('file', file);

        this.showToast('Uploading ePub...', 'info');

        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const project = await response.json();
                this.showToast('ePub uploaded successfully!', 'success');
                await this.loadProjects();
                this.openProject(project.id);
            } else {
                const error = await response.json();
                this.showToast(`Upload failed: ${error.detail}`, 'error');
            }
        } catch (error) {
            console.error('Error uploading ePub:', error);
            this.showToast('Upload failed', 'error');
        }
    }

    async deleteProject(projectId) {
        if (!confirm('Are you sure you want to delete this project?')) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showToast('Project deleted', 'success');
                await this.loadProjects();
            } else {
                this.showToast('Failed to delete project', 'error');
            }
        } catch (error) {
            console.error('Error deleting project:', error);
            this.showToast('Failed to delete project', 'error');
        }
    }

    async loadProject(projectId) {
        try {
            const [projectResponse, chaptersResponse] = await Promise.all([
                fetch(`/api/projects/${projectId}`),
                fetch(`/api/projects/${projectId}/chapters`)
            ]);

            this.currentProject = await projectResponse.json();
            this.chapters = await chaptersResponse.json();

            // Try to load LLM config
            const configResponse = await fetch(`/api/projects/${projectId}/llm-config`);
            this.currentProject.llmConfig = await configResponse.json();

            return true;
        } catch (error) {
            console.error('Error loading project:', error);
            this.showToast('Failed to load project', 'error');
            return false;
        }
    }

    async saveLLMConfig() {
        const config = {
            api_endpoint: document.getElementById('api-endpoint').value,
            api_key: document.getElementById('api-key').value,
            model: document.getElementById('model').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            max_tokens: parseInt(document.getElementById('max-tokens').value),
            system_prompt: null // Will use default based on editing style
        };

        try {
            const response = await fetch(`/api/projects/${this.currentProject.id}/llm-config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                this.showToast('LLM configuration saved', 'success');
                document.getElementById('llm-config-modal').classList.add('hidden');
                await this.loadProject(this.currentProject.id);
                this.renderDashboard();
            } else {
                this.showToast('Failed to save configuration', 'error');
            }
        } catch (error) {
            console.error('Error saving LLM config:', error);
            this.showToast('Failed to save configuration', 'error');
        }
    }

    async testLLMConnection() {
        const btn = document.getElementById('test-connection-btn');
        btn.textContent = 'Testing...';
        btn.disabled = true;

        const config = {
            api_endpoint: document.getElementById('api-endpoint').value,
            api_key: document.getElementById('api-key').value,
            model: document.getElementById('model').value
        };

        try {
            const response = await fetch('/api/test-llm-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('Connection successful!', 'success');
            } else {
                this.showToast(`Connection failed: ${result.message}`, 'error');
            }
        } catch (error) {
            this.showToast('Connection test failed', 'error');
        } finally {
            btn.textContent = 'Test Connection';
            btn.disabled = false;
        }
    }

    async fetchAvailableModels() {
        const btn = document.getElementById('fetch-models-btn');
        const statusEl = document.getElementById('model-fetch-status');
        const datalist = document.getElementById('model-suggestions');

        btn.textContent = 'Fetching...';
        btn.disabled = true;
        statusEl.textContent = 'Fetching available models...';
        statusEl.className = 'mt-1 text-sm text-blue-600';

        const apiEndpoint = document.getElementById('api-endpoint').value;
        const apiKey = document.getElementById('api-key').value;

        if (!apiEndpoint || !apiKey) {
            this.showToast('Please enter API endpoint and key first', 'error');
            btn.textContent = 'Fetch Models';
            btn.disabled = false;
            statusEl.textContent = 'Please enter API endpoint and key first';
            statusEl.className = 'mt-1 text-sm text-red-600';
            return;
        }

        try {
            // Remove trailing slash and add /models endpoint
            const baseUrl = apiEndpoint.replace(/\/+$/, '');
            const modelsUrl = baseUrl.endsWith('/v1') ? `${baseUrl}/models` : `${baseUrl}/v1/models`;

            const response = await fetch(modelsUrl, {
                headers: {
                    'Authorization': `Bearer ${apiKey}`,
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.error) {
                // Handle error response
                this.showToast(`Failed to fetch models: ${result.error.message || 'Unknown error'}`, 'error');
                statusEl.textContent = `Error: ${result.error.message || 'Failed to fetch models'}`;
                statusEl.className = 'mt-1 text-sm text-red-600';
                return;
            }

            // Clear existing options (except default ones)
            datalist.innerHTML = '';

            if (result.data && Array.isArray(result.data)) {
                // OpenAI-style response
                const models = result.data.map(m => m.id || m.model || m);

                if (models.length === 0) {
                    this.showToast('No models found', 'warning');
                    statusEl.textContent = 'No models found at this endpoint';
                    statusEl.className = 'mt-1 text-sm text-yellow-600';
                    return;
                }

                models.forEach(modelId => {
                    const option = document.createElement('option');
                    option.value = modelId;
                    datalist.appendChild(option);
                });

                this.showToast(`Found ${models.length} models`, 'success');
                statusEl.textContent = `Found ${models.length} available models - click to select from dropdown`;
                statusEl.className = 'mt-1 text-sm text-green-600';

                // Auto-select first model if current value is default
                const modelInput = document.getElementById('model');
                if (modelInput.value === 'gpt-4' && models.length > 0) {
                    modelInput.value = models[0];
                }
            } else {
                this.showToast('Unexpected response format from models endpoint', 'warning');
                statusEl.textContent = 'Unexpected response format - please enter model name manually';
                statusEl.className = 'mt-1 text-sm text-yellow-600';
            }
        } catch (error) {
            console.error('Error fetching models:', error);
            this.showToast('Failed to fetch models from endpoint', 'error');
            statusEl.textContent = 'Failed to fetch models - check endpoint and try again';
            statusEl.className = 'mt-1 text-sm text-red-600';
        } finally {
            btn.textContent = 'Fetch Models';
            btn.disabled = false;
        }
    }

    async startProcessing() {
        const config = {
            start_chapter: parseInt(document.getElementById('start-chapter').value),
            end_chapter: parseInt(document.getElementById('end-chapter').value) || null,
            worker_count: parseInt(document.getElementById('worker-count').value),
            chapters_per_batch: parseInt(document.getElementById('chapters-per-batch').value)
        };

        try {
            const response = await fetch(`/api/projects/${this.currentProject.id}/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                this.showToast('Processing started', 'success');
                document.getElementById('processing-modal').classList.add('hidden');
                this.connectWebSocket();
            } else {
                const error = await response.json();
                this.showToast(`Failed to start: ${error.detail}`, 'error');
            }
        } catch (error) {
            console.error('Error starting processing:', error);
            this.showToast('Failed to start processing', 'error');
        }
    }

    async pauseProcessing() {
        try {
            const response = await fetch(`/api/projects/${this.currentProject.id}/pause`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showToast('Processing paused', 'info');
            }
        } catch (error) {
            console.error('Error pausing:', error);
        }
    }

    async resumeProcessing() {
        try {
            const response = await fetch(`/api/projects/${this.currentProject.id}/resume`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showToast('Processing resumed', 'success');
            }
        } catch (error) {
            console.error('Error resuming:', error);
        }
    }

    async stopProcessing() {
        if (!confirm('Are you sure you want to stop processing?')) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${this.currentProject.id}/stop`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showToast('Processing stopped', 'info');
            }
        } catch (error) {
            console.error('Error stopping:', error);
        }
    }

    async exportProject() {
        try {
            window.location.href = `/api/projects/${this.currentProject.id}/export`;
            this.showToast('Exporting ePub...', 'info');
        } catch (error) {
            console.error('Error exporting:', error);
            this.showToast('Export failed', 'error');
        }
    }

    async viewChapterDiff(chapterId) {
        try {
            const response = await fetch(`/api/chapters/${chapterId}/diff`);
            if (response.ok) {
                const diff = await response.json();
                this.renderDiffView(diff);
            } else {
                this.showToast('Diff not available', 'error');
            }
        } catch (error) {
            console.error('Error loading diff:', error);
            this.showToast('Failed to load diff', 'error');
        }
    }

    // ========== WebSocket Methods ==========

    connectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/projects/${this.currentProject.id}`;

        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            // Start heartbeat
            this.startHeartbeat();
        };

        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket closed');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                if (this.currentView === 'dashboard') {
                    this.connectWebSocket();
                }
            }, 5000);
        };
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    action: 'ping',
                    timestamp: Date.now()
                }));
            }
        }, 30000); // Every 30 seconds
    }

    handleWebSocketMessage(message) {
        console.log('WebSocket message:', message);

        switch (message.type) {
            case 'connected':
                console.log('WebSocket connection confirmed');
                break;

            case 'chapter_started':
                this.updateChapterStatus(message.chapter_id, 'in_progress');
                this.showToast(`Processing chapter ${message.chapter_number}...`, 'info');
                break;

            case 'chapter_completed':
                this.updateChapterStatus(message.chapter_id, 'completed');
                this.showToast(`Chapter ${message.chapter_number} completed`, 'success');
                break;

            case 'chapter_failed':
                this.updateChapterStatus(message.chapter_id, 'failed');
                this.showToast(`Chapter ${message.chapter_number} failed: ${message.error}`, 'error');
                break;

            case 'processing_complete':
                this.showToast('All chapters processed!', 'success');
                this.loadProject(this.currentProject.id).then(() => {
                    this.renderDashboard();
                });
                break;

            case 'error':
                this.showToast(message.message, 'error');
                break;

            case 'pong':
                // Heartbeat response
                break;
        }
    }

    updateChapterStatus(chapterId, status) {
        const chapter = this.chapters.find(c => c.id === chapterId);
        if (chapter) {
            chapter.processing_status = status;
            // Update UI
            const row = document.querySelector(`[data-chapter-id="${chapterId}"]`);
            if (row) {
                const statusBadge = row.querySelector('.status-badge');
                if (statusBadge) {
                    statusBadge.className = `status-badge px-2 py-1 text-xs font-medium rounded-full status-${status}`;
                    statusBadge.textContent = status.replace('_', ' ').toUpperCase();
                }
            }
        }
    }

    // ========== View Rendering Methods ==========

    showProjectsView() {
        this.currentView = 'projects';
        document.getElementById('projects-view').classList.remove('hidden');
        document.getElementById('dashboard-view').classList.add('hidden');
        document.getElementById('diff-view').classList.add('hidden');
        document.getElementById('project-breadcrumb').classList.add('hidden');

        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        this.loadProjects();
    }

    renderProjects() {
        const grid = document.getElementById('projects-grid');
        const emptyState = document.getElementById('empty-state');

        if (this.projects.length === 0) {
            grid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');

        grid.innerHTML = this.projects.map(project => `
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow fade-in">
                <div class="flex justify-between items-start mb-4">
                    <div class="flex-1">
                        <h3 class="text-lg font-semibold text-gray-900 mb-1">${this.escapeHtml(project.name)}</h3>
                        <p class="text-sm text-gray-500">${project.chapter_count} chapters</p>
                    </div>
                    <span class="status-badge px-2 py-1 text-xs font-medium rounded-full status-${project.processing_status}">
                        ${project.processing_status.toUpperCase()}
                    </span>
                </div>

                ${project.metadata ? `
                    <div class="text-sm text-gray-600 space-y-1 mb-4">
                        ${project.metadata.author ? `<p><span class="font-medium">Author:</span> ${this.escapeHtml(project.metadata.author)}</p>` : ''}
                        ${project.metadata.language ? `<p><span class="font-medium">Language:</span> ${project.metadata.language}</p>` : ''}
                    </div>
                ` : ''}

                <div class="flex space-x-2">
                    <button onclick="app.openProject(${project.id})" class="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md">
                        Open
                    </button>
                    <button onclick="app.deleteProject(${project.id})" class="px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 border border-red-300 rounded-md">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');
    }

    async openProject(projectId) {
        const loaded = await this.loadProject(projectId);
        if (loaded) {
            this.currentView = 'dashboard';
            document.getElementById('projects-view').classList.add('hidden');
            document.getElementById('dashboard-view').classList.remove('hidden');
            document.getElementById('project-breadcrumb').classList.remove('hidden');
            document.getElementById('current-project-name').textContent = this.currentProject.name;

            this.renderDashboard();
            this.connectWebSocket();
        }
    }

    renderDashboard() {
        const dashboardView = document.getElementById('dashboard-view');

        const completedChapters = this.chapters.filter(c => c.processing_status === 'completed').length;
        const totalChapters = this.chapters.length;
        const progress = totalChapters > 0 ? (completedChapters / totalChapters * 100).toFixed(1) : 0;

        dashboardView.innerHTML = `
            <div class="fade-in">
                <!-- Project Header -->
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                    <div class="flex justify-between items-start">
                        <div>
                            <h2 class="text-2xl font-bold text-gray-900 mb-2">${this.escapeHtml(this.currentProject.name)}</h2>
                            ${this.currentProject.metadata ? `
                                <div class="text-sm text-gray-600 space-y-1">
                                    ${this.currentProject.metadata.author ? `<p><span class="font-medium">Author:</span> ${this.escapeHtml(this.currentProject.metadata.author)}</p>` : ''}
                                    ${this.currentProject.metadata.title ? `<p><span class="font-medium">Title:</span> ${this.escapeHtml(this.currentProject.metadata.title)}</p>` : ''}
                                    <p><span class="font-medium">Chapters:</span> ${totalChapters}</p>
                                </div>
                            ` : ''}
                        </div>
                        <span class="status-badge px-3 py-1 text-sm font-medium rounded-full status-${this.currentProject.processing_status}">
                            ${this.currentProject.processing_status.toUpperCase()}
                        </span>
                    </div>

                    <!-- Progress Bar -->
                    <div class="mt-4">
                        <div class="flex justify-between text-sm text-gray-600 mb-1">
                            <span>Progress</span>
                            <span>${completedChapters} / ${totalChapters} chapters (${progress}%)</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: ${progress}%"></div>
                        </div>
                    </div>
                </div>

                <!-- LLM Configuration -->
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-semibold text-gray-900">LLM Configuration</h3>
                        <button onclick="app.showLLMConfig()" class="px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 border border-blue-300 rounded-md">
                            ${this.currentProject.llmConfig && this.currentProject.llmConfig.configured ? 'Edit' : 'Configure'}
                        </button>
                    </div>

                    ${this.currentProject.llmConfig && this.currentProject.llmConfig.configured ? `
                        <div class="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span class="text-gray-500">Endpoint:</span>
                                <span class="ml-2 text-gray-900">${this.escapeHtml(this.currentProject.llmConfig.api_endpoint)}</span>
                            </div>
                            <div>
                                <span class="text-gray-500">Model:</span>
                                <span class="ml-2 text-gray-900">${this.currentProject.llmConfig.model}</span>
                            </div>
                            <div>
                                <span class="text-gray-500">API Key:</span>
                                <span class="ml-2 text-gray-900">${this.currentProject.llmConfig.masked_api_key || '****'}</span>
                            </div>
                            <div>
                                <span class="text-gray-500">Temperature:</span>
                                <span class="ml-2 text-gray-900">${this.currentProject.llmConfig.temperature}</span>
                            </div>
                        </div>
                    ` : `
                        <p class="text-sm text-gray-600">No LLM configuration set. Configure to start processing chapters.</p>
                    `}
                </div>

                <!-- Processing Controls -->
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Processing Controls</h3>
                    <div class="flex space-x-3">
                        ${this.currentProject.processing_status === 'idle' || this.currentProject.processing_status === 'completed' ? `
                            <button onclick="app.showProcessingModal()" class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md" ${!this.currentProject.llmConfig || !this.currentProject.llmConfig.configured ? 'disabled' : ''}>
                                Start Processing
                            </button>
                        ` : ''}
                        ${this.currentProject.processing_status === 'processing' ? `
                            <button onclick="app.pauseProcessing()" class="px-4 py-2 text-sm font-medium text-white bg-yellow-600 hover:bg-yellow-700 rounded-md">
                                Pause
                            </button>
                            <button onclick="app.stopProcessing()" class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md">
                                Stop
                            </button>
                        ` : ''}
                        ${this.currentProject.processing_status === 'paused' ? `
                            <button onclick="app.resumeProcessing()" class="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md">
                                Resume
                            </button>
                            <button onclick="app.stopProcessing()" class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md">
                                Stop
                            </button>
                        ` : ''}
                        ${completedChapters > 0 ? `
                            <button onclick="app.exportProject()" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md">
                                Export ePub
                            </button>
                        ` : ''}
                    </div>
                </div>

                <!-- Chapters Table -->
                <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h3 class="text-lg font-semibold text-gray-900">Chapters</h3>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Words</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tokens</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
                                ${this.chapters.map(chapter => `
                                    <tr data-chapter-id="${chapter.id}">
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${chapter.chapter_number}</td>
                                        <td class="px-6 py-4 text-sm text-gray-900">${this.escapeHtml(chapter.title || 'Untitled')}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chapter.word_count.toLocaleString()}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chapter.token_count.toLocaleString()}</td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <span class="status-badge px-2 py-1 text-xs font-medium rounded-full status-${chapter.processing_status}">
                                                ${chapter.processing_status.replace('_', ' ').toUpperCase()}
                                            </span>
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                                            ${chapter.processing_status === 'completed' ? `
                                                <button onclick="app.viewChapterDiff(${chapter.id})" class="text-blue-600 hover:text-blue-900">View Diff</button>
                                            ` : ''}
                                            ${chapter.processing_status === 'failed' ? `
                                                <button onclick="app.retryChapter(${chapter.id})" class="text-green-600 hover:text-green-900">Retry</button>
                                            ` : ''}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    }

    renderDiffView(diff) {
        const diffView = document.getElementById('diff-view');

        document.getElementById('dashboard-view').classList.add('hidden');
        diffView.classList.remove('hidden');

        diffView.innerHTML = `
            <div class="fade-in">
                <div class="mb-6 flex justify-between items-center">
                    <div>
                        <h2 class="text-2xl font-bold text-gray-900">Chapter ${diff.chapter_number}: ${this.escapeHtml(diff.title || 'Untitled')}</h2>
                        ${diff.stats ? `
                            <p class="text-sm text-gray-600 mt-1">
                                ${diff.stats.total_edits || 0} edits •
                                ${diff.stats.replacements || 0} replacements •
                                ${diff.stats.insertions || 0} insertions •
                                ${diff.stats.deletions || 0} deletions
                            </p>
                        ` : ''}
                    </div>
                    <button onclick="app.closeDiff()" class="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 border border-gray-300 rounded-md">
                        Back to Dashboard
                    </button>
                </div>

                <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                    <div class="grid grid-cols-2 divide-x divide-gray-200">
                        <div class="p-6">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">Original</h3>
                            <pre class="text-sm whitespace-pre-wrap font-mono">${this.escapeHtml(diff.original)}</pre>
                        </div>
                        <div class="p-6">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">Edited</h3>
                            <pre class="text-sm whitespace-pre-wrap font-mono">${this.escapeHtml(diff.edited)}</pre>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    closeDiff() {
        document.getElementById('diff-view').classList.add('hidden');
        document.getElementById('dashboard-view').classList.remove('hidden');
    }

    showLLMConfig() {
        const modal = document.getElementById('llm-config-modal');

        // Pre-fill if config exists
        if (this.currentProject.llmConfig && this.currentProject.llmConfig.configured) {
            document.getElementById('api-endpoint').value = this.currentProject.llmConfig.api_endpoint || '';
            document.getElementById('model').value = this.currentProject.llmConfig.model || 'gpt-4';
            document.getElementById('temperature').value = this.currentProject.llmConfig.temperature || 0.3;
            document.getElementById('max-tokens').value = this.currentProject.llmConfig.max_tokens || 4096;
        }

        modal.classList.remove('hidden');
    }

    showProcessingModal() {
        const modal = document.getElementById('processing-modal');
        document.getElementById('end-chapter').value = this.chapters.length;
        modal.classList.remove('hidden');
    }

    // ========== Utility Methods ==========

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');

        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500',
            warning: 'bg-yellow-500'
        };

        toast.className = `${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg mb-2 fade-in`;
        toast.textContent = message;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize app
const app = new EPubEditorApp();
