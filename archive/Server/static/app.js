// Label Printer Web App - JavaScript
// Modern ES6+ JavaScript for the label printer interface

class LabelPrinterApp {
    constructor() {
        this.currentSection = 'quick-print';
        this.apiBase = '';  // Use relative URLs
        this.templates = {};
        this.config = null;
        
        this.init();
    }

    async init() {
        console.log('Initializing Label Printer Web App...');
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Show initial section
        this.showSection('quick-print');
        
        // Load initial data
        await this.loadServerStatus();
        await this.loadConfiguration();
        
        console.log('App initialized successfully');
    }

    setupEventListeners() {
        // Form submission
        const quickPrintForm = document.getElementById('quick-print-form');
        if (quickPrintForm) {
            quickPrintForm.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Preview button
        const previewBtn = document.getElementById('preview-btn');
        if (previewBtn) {
            previewBtn.addEventListener('click', (e) => this.handlePreview(e));
        }

        // Retry buttons
        const errorRetryBtn = document.getElementById('error-retry-btn');
        if (errorRetryBtn) {
            errorRetryBtn.addEventListener('click', () => this.hideError());
        }

        // Refresh logs button
        const refreshLogsBtn = document.getElementById('refresh-logs');
        if (refreshLogsBtn) {
            refreshLogsBtn.addEventListener('click', () => this.loadLogs());
        }

        // Navigation setup
        this.setupNavigation();
        
        console.log('Event listeners set up');
    }

    setupNavigation() {
        // Add click handlers to navigation links
        const navLinks = document.querySelectorAll('.main-nav a');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.getAttribute('href').replace('#', '');
                this.showSection(section);
            });
        });
    }

    showSection(sectionName) {
        console.log(`Showing section: ${sectionName}`);
        
        // Hide all sections
        const sections = document.querySelectorAll('.content-section');
        sections.forEach(section => section.classList.add('hidden'));
        
        // Hide states
        this.hideLoading();
        this.hideError();
        this.hideSuccess();
        
        // Show requested section
        const targetSection = document.getElementById(`${sectionName}-section`);
        if (targetSection) {
            targetSection.classList.remove('hidden');
            this.currentSection = sectionName;
        }
        
        // Update navigation
        const navLinks = document.querySelectorAll('.main-nav a');
        navLinks.forEach(link => link.classList.remove('active'));
        const activeLink = document.getElementById(`nav-${sectionName}`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
        
        // Load section-specific data
        this.loadSectionData(sectionName);
    }

    async loadSectionData(sectionName) {
        switch (sectionName) {
            case 'templates':
                await this.loadTemplates();
                break;
            case 'logs':
                await this.loadLogs();
                break;
            case 'settings':
                await this.loadConfiguration();
                break;
        }
    }

    async handleFormSubmit(event) {
        event.preventDefault();
        console.log('Form submitted');
        
        const formData = new FormData(event.target);
        const data = Object.fromEntries(formData.entries());
        
        // Convert checkboxes to booleans
        data.message_only = formData.has('message_only');
        data.preview_only = formData.has('preview_only');
        
        // Convert count to number
        data.count = parseInt(data.count) || 1;
        
        console.log('Form data:', data);
        
        await this.createLabel(data);
    }

    async handlePreview(event) {
        event.preventDefault();
        console.log('Preview requested');
        
        const form = document.getElementById('quick-print-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Force preview only
        data.message_only = formData.has('message_only');
        data.preview_only = true;
        data.count = 1;  // Preview only needs 1
        
        await this.createLabel(data);
    }

    async createLabel(data) {
        try {
            this.showLoading('Creating your label...');
            
            console.log('Sending label request:', data);
            
            const response = await fetch('/api/print', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            console.log('Label creation result:', result);
            
            if (result.success) {
                this.showSuccess('Label created successfully!', result);
            } else {
                this.showError('Failed to create label', result.error);
            }
            
        } catch (error) {
            console.error('Error creating label:', error);
            this.showError('Network error', 'Could not connect to the label printer server. Please check if the server is running.');
        } finally {
            this.hideLoading();
        }
    }

    async loadTemplates() {
        try {
            document.getElementById('templates-loading').classList.remove('hidden');
            document.getElementById('templates-content').classList.add('hidden');
            
            const response = await fetch('/api/templates');
            const templates = await response.json();
            
            console.log('Loaded templates:', templates);
            this.templates = templates;
            this.renderTemplates(templates);
            
        } catch (error) {
            console.error('Error loading templates:', error);
            this.showError('Failed to load templates', error.message);
        } finally {
            document.getElementById('templates-loading').classList.add('hidden');
            document.getElementById('templates-content').classList.remove('hidden');
        }
    }

    renderTemplates(templates) {
        const container = document.getElementById('templates-content');
        if (!container) return;
        
        if (Object.keys(templates).length === 0) {
            container.innerHTML = `
                <div class="card">
                    <p>No templates found. Create templates in the <code>label-images</code> directory.</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        Object.entries(templates).forEach(([category, templateList]) => {
            html += `
                <div class="template-category">
                    <div class="template-category-header">
                        📁 ${category.charAt(0).toUpperCase() + category.slice(1)}
                    </div>
                    <div class="template-list">
            `;
            
            templateList.forEach(template => {
                html += `
                    <div class="template-item">
                        <div class="template-name">${template.name}</div>
                        <button class="template-use-btn" onclick="app.useTemplate('${category}', '${template.filename}')">
                            Use Template
                        </button>
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }

    async useTemplate(category, filename) {
        try {
            console.log(`Using template: ${category}/${filename}`);
            
            const template = this.templates[category]?.find(t => t.filename === filename);
            if (!template) {
                this.showError('Template not found', `Could not find template ${filename} in ${category}`);
                return;
            }
            
            // Parse template content and populate form
            // This is a simplified version - you might want to implement more sophisticated template parsing
            this.showSection('quick-print');
            
            // You could implement template parsing here to extract variables
            // For now, just show a message
            this.showSuccess('Template loaded!', { 
                message: `Template "${template.name}" from ${category} category is ready to use.`,
                template_content: template.content 
            });
            
        } catch (error) {
            console.error('Error using template:', error);
            this.showError('Failed to use template', error.message);
        }
    }

    async loadLogs() {
        try {
            const logsContent = document.getElementById('logs-content');
            if (logsContent) {
                logsContent.innerHTML = `
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading logs...</p>
                    </div>
                `;
            }
            
            const response = await fetch('/api/logs');
            const result = await response.json();
            
            console.log('Loaded logs:', result);
            this.renderLogs(result.logs || []);
            
        } catch (error) {
            console.error('Error loading logs:', error);
            const logsContent = document.getElementById('logs-content');
            if (logsContent) {
                logsContent.innerHTML = `
                    <div class="error-state">
                        <p>Failed to load logs: ${error.message}</p>
                    </div>
                `;
            }
        }
    }

    renderLogs(logs) {
        const container = document.getElementById('logs-content');
        if (!container) return;
        
        if (logs.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <p>No recent logs found.</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        logs.forEach(log => {
            html += `
                <div class="log-entry">
                    <div class="log-timestamp">
                        📅 ${log.date} - ${log.timestamp}
                    </div>
                    <div class="log-content">${this.escapeHtml(log.content)}</div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }

    async loadConfiguration() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            
            console.log('Loaded configuration:', config);
            this.config = config;
            this.renderConfiguration(config);
            
        } catch (error) {
            console.error('Error loading configuration:', error);
            this.config = null;
        }
    }

    renderConfiguration(config) {
        const container = document.getElementById('config-content');
        if (!container) return;
        
        container.classList.remove('hidden');
        document.getElementById('config-loading').classList.add('hidden');
        
        if (config.error) {
            container.innerHTML = `
                <div class="error-state">
                    <p>Failed to load configuration: ${config.error}</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="config-group">
                <h4>Printer Settings</h4>
                <div class="config-item">
                    <span class="config-label">Default Printer:</span>
                    <span class="config-value">${config.default_printer || 'Not set'}</span>
                </div>
                <div class="config-item">
                    <span class="config-label">Date Format:</span>
                    <span class="config-value">${config.date_format || 'Not set'}</span>
                </div>
            </div>
            <div class="config-group">
                <h4>Available Printers</h4>
                ${config.printers && config.printers.length > 0 ? 
                    config.printers.map(printer => `
                        <div class="config-item">
                            <span class="config-label">📖</span>
                            <span class="config-value">${printer}</span>
                        </div>
                    `).join('') : 
                    '<p>No printers configured</p>'
                }
            </div>
        `;
    }

    async loadServerStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            console.log('Server status:', status);
            
            const statusText = document.getElementById('server-status-text');
            const lastUpdated = document.getElementById('last-updated');
            
            if (statusText) {
                statusText.textContent = status.status === 'running' ? '🟢 Online' : '🔴 Offline';
            }
            
            if (lastUpdated) {
                lastUpdated.textContent = new Date().toLocaleString();
            }
            
        } catch (error) {
            console.error('Error loading server status:', error);
            const statusText = document.getElementById('server-status-text');
            if (statusText) {
                statusText.textContent = '🔴 Offline';
            }
        }
    }

    setExample(message, borderMessage = '', messageOnly = false) {
        console.log(`Setting example: ${message}`);
        
        // Fill the form with example data
        const messageInput = document.getElementById('message');
        const borderMessageInput = document.getElementById('border-message');
        const messageOnlyCheckbox = document.getElementById('message-only');
        
        if (messageInput) messageInput.value = message;
        if (borderMessageInput) borderMessageInput.value = borderMessage;
        if (messageOnlyCheckbox) messageOnlyCheckbox.checked = messageOnly;
        
        // Focus the message input
        if (messageInput) messageInput.focus();
    }

    showLoading(message = 'Loading...') {
        const loadingState = document.getElementById('loading-state');
        if (loadingState) {
            const loadingText = loadingState.querySelector('p');
            if (loadingText) loadingText.textContent = message;
            loadingState.classList.remove('hidden');
        }
    }

    hideLoading() {
        const loadingState = document.getElementById('loading-state');
        if (loadingState) {
            loadingState.classList.add('hidden');
        }
    }

    showError(title, message) {
        const errorState = document.getElementById('error-state');
        const errorMessage = document.getElementById('error-message');
        
        if (errorState && errorMessage) {
            errorMessage.textContent = message;
            errorState.classList.remove('hidden');
        }
        
        console.error('Error shown:', title, message);
    }

    hideError() {
        const errorState = document.getElementById('error-state');
        if (errorState) {
            errorState.classList.add('hidden');
        }
    }

    showSuccess(title, result = {}) {
        const successState = document.getElementById('success-state');
        const successMessage = document.getElementById('success-message');
        const previewContainer = document.getElementById('preview-container');
        const labelPreview = document.getElementById('label-preview');
        
        if (successState && successMessage) {
            successMessage.textContent = result.message || title;
            successState.classList.remove('hidden');
            
            // Show preview if available
            if (result.preview_available && result.preview_url && previewContainer && labelPreview) {
                labelPreview.src = result.preview_url + '?t=' + Date.now(); // Cache busting
                previewContainer.classList.remove('hidden');
            }
        }
        
        console.log('Success shown:', title, result);
    }

    hideSuccess() {
        const successState = document.getElementById('success-state');
        if (successState) {
            successState.classList.add('hidden');
        }
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
}

// Global functions for HTML onclick handlers
window.showSection = function(section) {
    if (window.app) {
        window.app.showSection(section);
    }
};

window.setExample = function(message, borderMessage, messageOnly) {
    if (window.app) {
        window.app.setExample(message, borderMessage, messageOnly);
    }
};

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing app...');
    window.app = new LabelPrinterApp();
});

// Error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    if (window.app) {
        window.app.showError('Application Error', 'An unexpected error occurred. Please refresh the page.');
    }
});

// Unhandled promise rejection handling
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    if (window.app) {
        window.app.showError('Network Error', 'A network error occurred. Please check your connection.');
    }
});