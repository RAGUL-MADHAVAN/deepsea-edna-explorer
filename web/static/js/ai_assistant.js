// Ocean-themed AI Assistant JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const contextProjectSelect = document.getElementById('context-project');
    const contextSampleSelect = document.getElementById('context-sample');
    const contextAnalysisSelect = document.getElementById('context-analysis');
    const expertiseLevelSelect = document.getElementById('expertise-level');
    const responseLengthSelect = document.getElementById('response-length');
    const citationsToggle = document.getElementById('citations-toggle');
    const dataAccessToggle = document.getElementById('data-access-toggle');
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Add welcome message
    addAssistantMessage("Welcome to OceanGenome AI Assistant! I can help with species identification, literature searches, data analysis, and method suggestions. How can I assist your research today?");
    
    // Send message when button is clicked
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    // Send message when Enter key is pressed
    if (userInput) {
        userInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Function to send message
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;
        
        // Add user message to chat
        addUserMessage(message);
        
        // Clear input
        userInput.value = '';
        
        // Show typing indicator
        showTypingIndicator();
        
        // Get context from selectors
        const context = {
            project: contextProjectSelect ? contextProjectSelect.value : null,
            sample: contextSampleSelect ? contextSampleSelect.value : null,
            analysis: contextAnalysisSelect ? contextAnalysisSelect.value : null,
            expertiseLevel: expertiseLevelSelect ? expertiseLevelSelect.value : 'intermediate',
            responseLength: responseLengthSelect ? responseLengthSelect.value : 'medium',
            citations: citationsToggle ? citationsToggle.checked : false,
            dataAccess: dataAccessToggle ? dataAccessToggle.checked : false
        };
        
        // Send to API
        fetch('/api/ai-assistant/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: message,
                context: context
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            removeTypingIndicator();
            
            if (data.success) {
                // Add assistant response
                addAssistantMessage(data.response);
            } else {
                // Show error
                addAssistantMessage("I'm sorry, I encountered an error processing your request. Please try again.");
            }
        })
        .catch(error => {
            console.error('Error:', error);
            removeTypingIndicator();
            addAssistantMessage("I'm sorry, I encountered an error processing your request. Please try again.");
        });
    }
    
    // Function to add user message to chat
    function addUserMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <p>${escapeHtml(message)}</p>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
        `;
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // Function to add assistant message to chat
    function addAssistantMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message assistant-message';
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <p>${formatMessage(message)}</p>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
        `;
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
        
        // Add wave animation to assistant message
        const waveAnimation = document.createElement('div');
        waveAnimation.className = 'message-wave';
        messageDiv.appendChild(waveAnimation);
    }
    
    // Function to show typing indicator
    function showTypingIndicator() {
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'chat-message assistant-message typing-indicator';
        indicatorDiv.id = 'typing-indicator';
        indicatorDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        chatContainer.appendChild(indicatorDiv);
        scrollToBottom();
    }
    
    // Function to remove typing indicator
    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    // Function to format message with markdown-like syntax
    function formatMessage(message) {
        // Replace URLs with links
        message = message.replace(/https?:\/\/[^\s]+/g, function(url) {
            return `<a href="${url}" target="_blank">${url}</a>`;
        });
        
        // Format citations
        message = message.replace(/\[(\d+)\]/g, '<sup class="citation">[$1]</sup>');
        
        // Add paragraph breaks
        message = message.replace(/\n\n/g, '</p><p>');
        
        return message;
    }
    
    // Function to get current time
    function getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    // Function to scroll chat to bottom
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Function to escape HTML
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    // Tool selection
    const toolButtons = document.querySelectorAll('.tool-button');
    toolButtons.forEach(button => {
        button.addEventListener('click', function() {
            const toolType = this.getAttribute('data-tool');
            let promptText = '';
            
            switch(toolType) {
                case 'species':
                    promptText = 'Can you help identify the species in this DNA sequence?';
                    break;
                case 'literature':
                    promptText = 'Can you find recent research papers about deep-sea corals?';
                    break;
                case 'analysis':
                    promptText = 'What analysis methods would you recommend for this marine sample data?';
                    break;
                case 'methods':
                    promptText = 'What sequencing method would be best for identifying novel marine bacteria?';
                    break;
            }
            
            userInput.value = promptText;
            userInput.focus();
        });
    });
    
    // Context dependency handling
    if (contextProjectSelect && contextSampleSelect) {
        contextProjectSelect.addEventListener('change', function() {
            // In a real implementation, this would fetch samples for the selected project
            // For demonstration, we'll just enable the sample select
            contextSampleSelect.disabled = false;
        });
    }
    
    if (contextSampleSelect && contextAnalysisSelect) {
        contextSampleSelect.addEventListener('change', function() {
            // In a real implementation, this would fetch analyses for the selected sample
            // For demonstration, we'll just enable the analysis select
            contextAnalysisSelect.disabled = false;
        });
    }
});