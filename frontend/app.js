/**
 * CompService Monitor — анализ услуг ТО компьютерной техники
 */

// === State ===
const state = {
    currentTab: 'text',
    selectedImage: null,
    isLoading: false
};

// === DOM Elements ===
const elements = {
    // Navigation
    navButtons: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Text analysis
    competitorText: document.getElementById('competitor-text'),
    analyzeTextBtn: document.getElementById('analyze-text-btn'),
    
    // Image analysis
    uploadZone: document.getElementById('upload-zone'),
    imageInput: document.getElementById('image-input'),
    previewContainer: document.getElementById('preview-container'),
    imagePreview: document.getElementById('image-preview'),
    removeImageBtn: document.getElementById('remove-image'),
    analyzeImageBtn: document.getElementById('analyze-image-btn'),
    
    // Parse demo
    urlInput: document.getElementById('url-input'),
    parseBtn: document.getElementById('parse-btn'),
    savedSitesSelect: document.getElementById('saved-sites-select'),
    
    // Sites
    sitesList: document.getElementById('sites-list'),
    clearSitesBtn: document.getElementById('clear-sites-btn'),
    parseSelectedBtn: document.getElementById('parse-selected-btn'),
    
    // History
    historyList: document.getElementById('history-list'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    
    // Results
    resultsSection: document.getElementById('results-section'),
    resultsContent: document.getElementById('results-content'),
    closeResultsBtn: document.getElementById('close-results'),
    
    // Loading
    loadingOverlay: document.getElementById('loading-overlay')
};

// === API Functions ===
const api = {
    baseUrl: '',
    
    async analyzeText(text) {
        const response = await fetch(`${this.baseUrl}/analyze_text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        return response.json();
    },
    
    async analyzeImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/analyze_image`, {
            method: 'POST',
            body: formData
        });
        return response.json();
    },
    
    async parseDemo(url) {
        const response = await fetch(`${this.baseUrl}/parse_demo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        return response.json();
    },
    
    async getHistory() {
        const response = await fetch(`${this.baseUrl}/history`);
        return response.json();
    },
    
    async clearHistory() {
        const response = await fetch(`${this.baseUrl}/history`, {
            method: 'DELETE'
        });
        return response.json();
    },

    async getParsedSites() {
        const response = await fetch(`${this.baseUrl}/parsed_sites`);
        return response.json();
    },

    async deleteParsedSite(siteId) {
        const response = await fetch(`${this.baseUrl}/parsed_sites/${encodeURIComponent(siteId)}`, {
            method: 'DELETE'
        });
        return response.json();
    },

    async clearParsedSites() {
        const response = await fetch(`${this.baseUrl}/parsed_sites`, {
            method: 'DELETE'
        });
        return response.json();
    }
};

// === UI Functions ===
const ui = {
    showLoading() {
        state.isLoading = true;
        elements.loadingOverlay.style.display = 'flex';
    },
    
    hideLoading() {
        state.isLoading = false;
        elements.loadingOverlay.style.display = 'none';
    },
    
    showTab(tabId) {
        state.currentTab = tabId;
        
        // Update navigation
        elements.navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        
        // Update content
        elements.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabId}-tab`);
        });
        
        // Load history if needed
        if (tabId === 'history') {
            this.loadHistory();
        }
        if (tabId === 'sites' || tabId === 'parse') {
            this.loadSavedSites();
        }
    },
    
    showResults(html) {
        elements.resultsContent.innerHTML = html;
        elements.resultsSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
    },
    
    hideResults() {
        elements.resultsSection.hidden = true;
    },
    
    showError(message) {
        const html = `
            <div class="error-message">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>${message}</span>
            </div>
        `;
        this.showResults(html);
    },
    
    renderTextAnalysis(analysis) {
        const score = Number(analysis.overall_score || 0);
        const scorePercent = (score / 10) * 100;
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Оценка пакета услуг ТО
                </h3>
                <div class="score-display">
                    <span class="score-value">${score}/10</span>
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${scorePercent}%"></div>
                    </div>
                </div>
            </div>
            ${this.renderResultBlock('Виды услуг', analysis.service_types, 'unique')}
            ${this.renderResultBlock('Покрытие техники', analysis.equipment_coverage, 'insights')}
            ${this.renderResultBlock('SLA и процесс', analysis.sla_and_process, 'recommendations')}
            ${this.renderResultBlock('Цены и условия', analysis.pricing_notes, 'insights')}
            ${this.renderResultBlock('Сильные стороны', analysis.strengths, 'strengths')}
            ${this.renderResultBlock('Пробелы и риски', analysis.gaps, 'weaknesses')}
            ${this.renderResultBlock('Рекомендации', analysis.recommendations, 'recommendations')}
            ${analysis.summary ? `
                <div class="result-block result-summary">
                    <h3>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Резюме
                    </h3>
                    <p>${analysis.summary}</p>
                </div>
            ` : ''}
        `;
    },
    
    renderImageAnalysis(analysis) {
        const score = Number(analysis.visual_quality_score || 0);
        const scorePercent = (score / 10) * 100;
        
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    Описание изображения
                </h3>
                <p>${analysis.description || ''}</p>
            </div>
            
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Информативность визуала услуг
                </h3>
                <div class="score-display">
                    <span class="score-value">${score}/10</span>
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${scorePercent}%"></div>
                    </div>
                </div>
                <p>${analysis.visual_quality_analysis || ''}</p>
                ${analysis.communication_quality ? `<p>${analysis.communication_quality}</p>` : ''}
            </div>
            
            ${this.renderResultBlock('Услуги на изображении', analysis.detected_services, 'unique')}
            ${this.renderResultBlock('Техника / рабочее место', analysis.equipment_shown, 'insights')}
            ${this.renderResultBlock('Рекомендации', analysis.recommendations, 'recommendations')}
        `;
    },
    
    escapeAttr(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    },

    renderParsedContent(data) {
        const parsed = data;
        const links = parsed.links || [];
        
        return `
            <div class="parsed-content">
                <div class="label">URL:</div>
                <div class="value">${parsed.url}</div>
                
                <div class="label">Title:</div>
                <div class="value">${parsed.title || 'Не найден'}</div>
                
                <div class="label">H1:</div>
                <div class="value">${parsed.h1 || 'Не найден'}</div>
                
                <div class="label">Первый абзац:</div>
                <div class="value">${parsed.first_paragraph || 'Не найден'}</div>
            </div>
            ${this.renderDiscoveredLinks(links)}
            ${parsed.analysis ? this.renderTextAnalysis(parsed.analysis) : ''}
        `;
    },

    renderDiscoveredLinks(links) {
        if (!links || links.length === 0) {
            return '<div class="discovered-links"><p>Внутренние ссылки на этой странице не найдены</p></div>';
        }
        const rows = links.map((link) => {
            const url = this.escapeAttr(link.url);
            const title = this.escapeAttr(link.title || link.url);
            return `
                <label class="disc-link">
                    <input type="checkbox" class="disc-pick" data-url="${url}">
                    <div>
                        <span>${title}</span>
                        <small>${url}</small>
                    </div>
                </label>
            `;
        }).join('');
        return `
            <div class="discovered-links">
                <h3>Ссылки с текущей страницы (${links.length})</h3>
                <p>Отметьте страницы и разберите их вручную — автообход сайта не запускается</p>
                ${rows}
                <button type="button" class="btn btn-primary" id="parse-discovered-btn">Парсить выбранные ссылки</button>
            </div>
        `;
    },
    
    renderResultBlock(title, items, type) {
        if (!items || items.length === 0) return '';
        
        const icons = {
            strengths: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
            weaknesses: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
            unique: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
            recommendations: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
            insights: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
        };
        
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${icons[type] || icons.recommendations}
                    </svg>
                    ${title}
                </h3>
                <ul>
                    ${items.map(item => `<li>${item}</li>`).join('')}
                </ul>
            </div>
        `;
    },
    
    async loadHistory() {
        try {
            const data = await api.getHistory();
            this.renderHistory(data.items);
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    },
    
    renderHistory(items) {
        if (!items || items.length === 0) {
            elements.historyList.innerHTML = `
                <div class="history-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <p>История пуста</p>
                </div>
            `;
            return;
        }
        
        const icons = {
            text: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
            image: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
            parse: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
        };
        
        const typeLabels = {
            text: 'Анализ описания услуг',
            image: 'Анализ визуала ТО',
            parse: 'Парсинг сайта сервиса'
        };
        
        elements.historyList.innerHTML = items.map(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            return `
                <div class="history-item">
                    <div class="history-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${icons[item.request_type] || icons.text}
                        </svg>
                    </div>
                    <div class="history-content">
                        <div class="history-type">${typeLabels[item.request_type] || item.request_type}</div>
                        <div class="history-summary">${item.request_summary}</div>
                    </div>
                    <div class="history-time">${timeStr}</div>
                </div>
            `;
        }).join('');
    },

    displayUrlForInput(url) {
        return (url || '').replace(/^https?:\/\//i, '');
    },

    fillUrlInput(url) {
        if (!elements.urlInput) return;
        elements.urlInput.value = this.displayUrlForInput(url);
        if (elements.savedSitesSelect) {
            elements.savedSitesSelect.value = url;
        }
    },

    flattenTree(nodes, prefix = '') {
        const out = [];
        (nodes || []).forEach((node) => {
            out.push({ ...node, labelPrefix: prefix });
            out.push(...this.flattenTree(node.children || [], `${prefix}— `));
        });
        return out;
    },

    async loadSavedSites() {
        try {
            const data = await api.getParsedSites();
            const tree = data.tree || [];
            this.renderSavedSitesSelect(this.flattenTree(tree));
            this.renderSitesList(tree);
        } catch (error) {
            console.error('Failed to load saved sites:', error);
        }
    },

    renderSavedSitesSelect(items) {
        if (!elements.savedSitesSelect) return;
        const current = elements.savedSitesSelect.value;
        const options = ['<option value="">— выбрать из списка —</option>']
            .concat((items || []).map((item) => {
                const mark = item.analyzed ? '✓ ' : '';
                const prefix = item.labelPrefix || '';
                const label = `${mark}${prefix}${item.title || item.url}`;
                const selected = item.url === current ? ' selected' : '';
                return `<option value="${this.escapeAttr(item.url)}"${selected}>${this.escapeAttr(label)}</option>`;
            }));
        elements.savedSitesSelect.innerHTML = options.join('');
    },

    renderTreeNode(node) {
        const analyzed = Boolean(node.analyzed);
        const children = (node.children || []).map((child) => this.renderTreeNode(child)).join('');
        const date = node.last_parsed ? new Date(node.last_parsed) : null;
        const timeStr = date
            ? date.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            })
            : 'ещё не разбиралась';
        const safeUrl = this.escapeAttr(node.url);
        const safeId = this.escapeAttr(node.id);
        const title = this.escapeAttr(node.title || node.url);
        const hasChildren = (node.children || []).length > 0;
        return `
            <div class="tree-node ${analyzed ? 'analyzed' : 'pending'}">
                <div class="tree-row">
                    ${hasChildren
                        ? '<button type="button" class="tree-toggle" data-toggle>▾</button>'
                        : '<span class="tree-toggle-spacer"></span>'}
                    <input type="checkbox" class="tree-pick" data-url="${safeUrl}" title="Выбрать для парсинга">
                    <input type="checkbox" class="tree-done" disabled ${analyzed ? 'checked' : ''} title="${analyzed ? 'Уже проанализирована' : 'Ещё не проанализирована'}">
                    <div class="tree-meta">
                        <div class="tree-title">${title}</div>
                        <div class="tree-url">${safeUrl}</div>
                        <div class="tree-url">${analyzed ? `Разобрана ${timeStr}${node.parse_count ? ` · ${node.parse_count}×` : ''}` : timeStr}</div>
                    </div>
                    <div class="site-actions">
                        <button class="btn btn-secondary btn-small" data-select-url="${safeUrl}">Выбрать</button>
                        <button class="btn btn-primary btn-small" data-reparse-url="${safeUrl}">${analyzed ? 'Повторить' : 'Парсить'}</button>
                        <button class="btn btn-secondary btn-small" data-delete-site="${safeId}">Удалить</button>
                    </div>
                </div>
                ${hasChildren ? `<div class="tree-children">${children}</div>` : ''}
            </div>
        `;
    },

    renderSitesList(tree) {
        if (!elements.sitesList) return;
        if (!tree || tree.length === 0) {
            elements.sitesList.innerHTML = `
                <div class="history-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                    </svg>
                    <p>Пока нет сохранённых сайтов</p>
                </div>
            `;
            return;
        }
        elements.sitesList.innerHTML = tree.map((node) => this.renderTreeNode(node)).join('');
    }
};

// === Event Handlers ===
const handlers = {
    // Navigation
    handleNavClick(e) {
        const btn = e.target.closest('.nav-btn');
        if (btn) {
            ui.showTab(btn.dataset.tab);
        }
    },
    
    // Text analysis
    async handleAnalyzeText() {
        const text = elements.competitorText.value.trim();
        
        if (text.length < 10) {
            ui.showError('Введите описание услуг минимум 10 символов');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeText(text);
            
            if (result.success && result.analysis) {
                ui.showResults(ui.renderTextAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // Image upload
    handleUploadClick() {
        elements.imageInput.click();
    },
    
    handleImageSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processImage(file);
        }
    },
    
    handleDragOver(e) {
        e.preventDefault();
        elements.uploadZone.classList.add('dragover');
    },
    
    handleDragLeave(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
    },
    
    handleDrop(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            this.processImage(file);
        }
    },
    
    processImage(file) {
        state.selectedImage = file;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            elements.imagePreview.src = e.target.result;
            elements.previewContainer.hidden = false;
            elements.uploadZone.querySelector('.upload-content').hidden = true;
            elements.analyzeImageBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    },
    
    handleRemoveImage() {
        state.selectedImage = null;
        elements.imageInput.value = '';
        elements.imagePreview.src = '';
        elements.previewContainer.hidden = true;
        elements.uploadZone.querySelector('.upload-content').hidden = false;
        elements.analyzeImageBtn.disabled = true;
    },
    
    async handleAnalyzeImage() {
        if (!state.selectedImage) {
            ui.showError('Выберите изображение для анализа');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeImage(state.selectedImage);
            
            if (result.success && result.analysis) {
                ui.showResults(ui.renderImageAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе изображения');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    normalizeUrl(url) {
        let value = (url || '').trim();
        if (!value) return '';
        if (!value.startsWith('http://') && !value.startsWith('https://')) {
            value = 'https://' + value;
        }
        return value;
    },

    async runParse(url) {
        ui.showLoading();
        try {
            const result = await api.parseDemo(url);
            if (result.success && result.data) {
                ui.showResults(ui.renderParsedContent(result.data));
                await ui.loadSavedSites();
                return true;
            }
            ui.showError(result.error || 'Не удалось распарсить сайт');
            return false;
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
            return false;
        } finally {
            ui.hideLoading();
        }
    },

    async handleParse() {
        const url = this.normalizeUrl(elements.urlInput.value);
        if (!url) {
            ui.showError('Введите URL страницы услуг ТО');
            return;
        }
        await this.runParse(url);
    },

    selectedTreeUrls() {
        return Array.from(document.querySelectorAll('.tree-pick:checked'))
            .map((el) => el.dataset.url)
            .filter(Boolean);
    },

    async handleParseSelected() {
        const urls = this.selectedTreeUrls();
        if (!urls.length) {
            ui.showError('Отметьте ссылки в дереве для ручного разбора');
            return;
        }
        for (const url of urls) {
            ui.fillUrlInput(url);
            await this.runParse(url);
        }
    },

    async handleParseDiscovered() {
        const urls = Array.from(document.querySelectorAll('.disc-pick:checked'))
            .map((el) => el.dataset.url)
            .filter(Boolean);
        if (!urls.length) {
            ui.showError('Отметьте ссылки с текущей страницы');
            return;
        }
        for (const url of urls) {
            ui.fillUrlInput(url);
            await this.runParse(url);
        }
    },
    
    handleSavedSiteSelect() {
        const url = elements.savedSitesSelect.value;
        if (url) {
            ui.fillUrlInput(url);
        }
    },

    handleSitesListClick(e) {
        const toggle = e.target.closest('[data-toggle]');
        if (toggle) {
            const node = toggle.closest('.tree-node');
            node.classList.toggle('collapsed');
            toggle.textContent = node.classList.contains('collapsed') ? '▸' : '▾';
            return;
        }
        const selectBtn = e.target.closest('[data-select-url]');
        if (selectBtn) {
            ui.fillUrlInput(selectBtn.dataset.selectUrl);
            ui.showTab('parse');
            return;
        }
        const reparseBtn = e.target.closest('[data-reparse-url]');
        if (reparseBtn) {
            ui.fillUrlInput(reparseBtn.dataset.reparseUrl);
            ui.showTab('parse');
            handlers.handleParse.call(handlers);
            return;
        }
        const deleteBtn = e.target.closest('[data-delete-site]');
        if (deleteBtn) {
            handlers.handleDeleteSite(deleteBtn.dataset.deleteSite);
        }
    },

    async handleDeleteSite(siteId) {
        try {
            await api.deleteParsedSite(siteId);
            ui.loadSavedSites();
        } catch (error) {
            console.error('Failed to delete site:', error);
        }
    },

    async handleClearSites() {
        if (!confirm('Очистить список сохранённых сайтов?')) {
            return;
        }
        try {
            await api.clearParsedSites();
            ui.loadSavedSites();
        } catch (error) {
            console.error('Failed to clear sites:', error);
        }
    },
    
    async handleClearHistory() {
        if (!confirm('Вы уверены, что хотите очистить историю?')) {
            return;
        }
        
        try {
            await api.clearHistory();
            ui.renderHistory([]);
        } catch (error) {
            console.error('Failed to clear history:', error);
        }
    },
    
    // Results
    handleCloseResults() {
        ui.hideResults();
    }
};

// === Initialize ===
function init() {
    // Navigation
    elements.navButtons.forEach(btn => {
        btn.addEventListener('click', handlers.handleNavClick.bind(handlers));
    });
    
    // Text analysis
    elements.analyzeTextBtn.addEventListener('click', handlers.handleAnalyzeText.bind(handlers));
    
    // Image upload
    elements.uploadZone.addEventListener('click', handlers.handleUploadClick.bind(handlers));
    elements.imageInput.addEventListener('change', handlers.handleImageSelect.bind(handlers));
    elements.uploadZone.addEventListener('dragover', handlers.handleDragOver.bind(handlers));
    elements.uploadZone.addEventListener('dragleave', handlers.handleDragLeave.bind(handlers));
    elements.uploadZone.addEventListener('drop', handlers.handleDrop.bind(handlers));
    elements.removeImageBtn.addEventListener('click', handlers.handleRemoveImage.bind(handlers));
    elements.analyzeImageBtn.addEventListener('click', handlers.handleAnalyzeImage.bind(handlers));
    
    // Parse demo
    elements.parseBtn.addEventListener('click', handlers.handleParse.bind(handlers));
    elements.urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handlers.handleParse.call(handlers);
    });
    elements.savedSitesSelect.addEventListener('change', handlers.handleSavedSiteSelect.bind(handlers));
    elements.sitesList.addEventListener('click', handlers.handleSitesListClick.bind(handlers));
    elements.clearSitesBtn.addEventListener('click', handlers.handleClearSites.bind(handlers));
    if (elements.parseSelectedBtn) {
        elements.parseSelectedBtn.addEventListener('click', handlers.handleParseSelected.bind(handlers));
    }
    elements.resultsContent.addEventListener('click', (e) => {
        if (e.target.closest('#parse-discovered-btn')) {
            handlers.handleParseDiscovered.call(handlers);
        }
    });
    
    // History
    elements.clearHistoryBtn.addEventListener('click', handlers.handleClearHistory.bind(handlers));
    ui.loadSavedSites();
    
    // Results
    elements.closeResultsBtn.addEventListener('click', handlers.handleCloseResults.bind(handlers));
    
    // Show default tab
    ui.showTab('text');
}

// Start app
document.addEventListener('DOMContentLoaded', init);

