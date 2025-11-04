/**
 * Knockout.js ViewModel for Custom UI Chat Interface
 */
function CustomUIChatViewModel(config) {
    var self = this;
    
    // Configuration
    self.appId = config.appId;
    self.domain = config.domain;
    self.generateUrl = config.generateUrl;
    self.statusUrl = config.statusUrl;
    self.disableUrl = config.disableUrl;
    
    // Observable properties
    self.messages = ko.observableArray([]);
    self.currentMessage = ko.observable('');
    self.isGenerating = ko.observable(false);
    self.customUIEnabled = ko.observable(false);
    self.lastUpdateTime = ko.observable('');
    
    // Computed properties
    self.conversationLength = ko.computed(function() {
        return self.messages().length;
    });
    
    self.canSend = ko.computed(function() {
        return self.currentMessage().trim().length > 0 && !self.isGenerating();
    });
    
    /**
     * Initialize - load current status
     */
    self.init = function() {
        self.loadStatus();
    };
    
    /**
     * Load current custom UI status
     */
    self.loadStatus = function() {
        $.ajax({
            url: self.statusUrl,
            method: 'GET',
        }).done(function(response) {
            if (response.success) {
                self.customUIEnabled(response.enabled);
                if (response.enabled) {
                    self.lastUpdateTime(new Date().toLocaleString());
                }
            }
        }).fail(function(xhr) {
            console.error('Error loading status:', xhr);
        });
    };
    
    /**
     * Send message to Claude
     */
    self.sendMessage = function() {
        if (!self.canSend()) return;
        
        var userMessage = self.currentMessage().trim();
        
        // Add user message to conversation
        self.messages.push({
            role: 'user',
            content: userMessage,
            timestamp: new Date().toLocaleTimeString(),
            formattedContent: self.formatMessage(userMessage)
        });
        
        // Clear input
        self.currentMessage('');
        
        // Set generating state
        self.isGenerating(true);
        
        // Scroll to bottom
        self.scrollToBottom();
        
        // Build conversation history for API
        var conversationHistory = self.messages()
            .filter(function(msg) { return msg.role !== 'system'; })
            .map(function(msg) {
                return {
                    role: msg.role,
                    content: msg.content
                };
            });
        
        // Call API
        $.ajax({
            url: self.generateUrl,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                message: userMessage,
                conversation_history: conversationHistory.slice(0, -1), // Exclude current message
            }),
        }).done(function(response) {
            if (response.success) {
                // Add Claude's response
                self.messages.push({
                    role: 'assistant',
                    content: response.full_response,
                    timestamp: new Date().toLocaleTimeString(),
                    formattedContent: self.formatMessage(response.full_response)
                });
                
                // Update status
                if (response.saved) {
                    self.customUIEnabled(true);
                    self.lastUpdateTime(new Date().toLocaleString());
                    
                    // Refresh preview
                    self.refreshPreview();
                    
                    // Show success notification
                    self.showNotification('Custom UI updated successfully!', 'success');
                }
            } else {
                self.showNotification('Error: ' + response.message, 'danger');
            }
        }).fail(function(xhr) {
            console.error('API Error:', xhr);
            var errorMsg = 'Failed to generate UI. Please try again.';
            if (xhr.responseJSON && xhr.responseJSON.message) {
                errorMsg = xhr.responseJSON.message;
            }
            self.showNotification(errorMsg, 'danger');
        }).always(function() {
            self.isGenerating(false);
            self.scrollToBottom();
        });
    };
    
    /**
     * Format message content (markdown-like)
     */
    self.formatMessage = function(text) {
        // Basic markdown formatting
        var formatted = text;
        
        // Code blocks
        formatted = formatted.replace(
            /```(\w+)?\n([\s\S]*?)```/g,
            '<pre><code class="language-$1">$2</code></pre>'
        );
        
        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    };
    
    /**
     * Handle keyboard shortcuts
     */
    self.handleKeyPress = function(data, event) {
        // Ctrl/Cmd + Enter to send
        if ((event.ctrlKey || event.metaKey) && event.keyCode === 13) {
            self.sendMessage();
            return false;
        }
        return true;
    };
    
    /**
     * Quick start templates
     */
    self.quickStart = function(template) {
        var templates = {
            'patient-form': 'Create a patient intake form with fields for: full name, date of birth, gender, contact phone, and a text area for medical history. Use a modern, mobile-friendly design with clear labels and a submit button that uses CommCareAPI.submitForm().',
            
            'case-list': 'Create a case list dashboard that displays patient cases using CommCareAPI.getCases(). Show the patient name, case ID, date opened, and status. Include a search bar and the ability to click on a case to view details. Use cards for each case with a modern design.',
            
            'survey': 'Create a survey interface with multiple choice questions. Include: question text, radio buttons for answers, a progress indicator, and next/previous navigation. Submit results using CommCareAPI.submitForm(). Make it visually appealing with good spacing.'
        };
        
        if (templates[template]) {
            self.currentMessage(templates[template]);
            // Auto-send after short delay
            setTimeout(function() {
                self.sendMessage();
            }, 500);
        }
    };
    
    /**
     * Clear conversation and start fresh
     */
    self.clearConversation = function() {
        if (self.messages().length === 0) return;
        
        if (confirm('Clear conversation history? This will not delete your custom UI.')) {
            self.messages([]);
            self.currentMessage('');
        }
    };
    
    /**
     * Refresh preview iframe
     */
    self.refreshPreview = function() {
        var previewIframe = document.querySelector('.preview-wrapper iframe');
        if (previewIframe) {
            previewIframe.contentWindow.location.reload();
        }
    };
    
    /**
     * Disable custom UI
     */
    self.disableCustomUI = function() {
        if (!confirm('Disable custom UI? You can re-enable it by generating a new UI.')) {
            return;
        }
        
        $.ajax({
            url: self.disableUrl,
            method: 'POST',
        }).done(function(response) {
            if (response.success) {
                self.customUIEnabled(false);
                self.refreshPreview();
                self.showNotification('Custom UI disabled', 'info');
            }
        }).fail(function(xhr) {
            self.showNotification('Error disabling custom UI', 'danger');
        });
    };
    
    /**
     * Scroll conversation to bottom
     */
    self.scrollToBottom = function() {
        setTimeout(function() {
            var container = document.getElementById('conversation-display');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }, 100);
    };
    
    /**
     * Show notification
     */
    self.showNotification = function(message, type) {
        // Use HQ's notification system if available
        if (window.hqImport && window.hqImport('hqwebapp/js/alert_user')) {
            var alertUser = window.hqImport('hqwebapp/js/alert_user');
            if (type === 'success') {
                alertUser.alert_user(message, 'success');
            } else if (type === 'danger' || type === 'error') {
                alertUser.alert_user(message, 'danger');
            } else {
                alertUser.alert_user(message, 'info');
            }
        } else {
            // Fallback to alert
            alert(message);
        }
    };
    
    // Initialize on creation
    self.init();
}

