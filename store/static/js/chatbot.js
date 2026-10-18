document.addEventListener('DOMContentLoaded', function() {
    const chatbotContainer = document.getElementById('chatbot-container');
    const chatToggle = document.getElementById('chatbot-toggle');
    const minimizeBtn = document.getElementById('minimize-chat');
    const closeBtn = document.getElementById('close-chat');
    const chatMessages = document.querySelector('.chat-messages');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-message');
    const header = document.querySelector('.chatbot-header');
    
    let isFirstOpen = true;
    let isDragging = false;
    let offsetX, offsetY;

    // Toggle chat window
    chatToggle.addEventListener('click', function() {
        if (chatbotContainer.style.opacity === '1') {
            // Close chat
            chatbotContainer.style.opacity = '0';
            chatbotContainer.style.visibility = 'hidden';
            setTimeout(() => {
                chatbotContainer.style.display = 'none';
            }, 300);
        } else {
            // Open chat
            chatbotContainer.style.display = 'block';
            // Small delay to allow display:block to take effect
            setTimeout(() => {
                chatbotContainer.style.opacity = '1';
                chatbotContainer.style.visibility = 'visible';
                // Show welcome message on first open
                if (isFirstOpen) {
                    isFirstOpen = false;
                    // Small delay to allow chat to appear before showing welcome message
                    setTimeout(showWelcomeMessage, 300);
                }
                // Focus input field
                userInput.focus();
            }, 10);
        }
    });

    // Minimize chat
    minimizeBtn.addEventListener('click', function() {
        chatbotContainer.style.opacity = '0';
        chatbotContainer.style.visibility = 'hidden';
        setTimeout(() => {
            chatbotContainer.style.display = 'none';
        }, 300);
    });

    // Close chat completely
    closeBtn.addEventListener('click', function() {
        closeChatbot();
    });
    
    // Also handle the new close button
    const newCloseBtn = document.getElementById('chatbot-close');
    if (newCloseBtn) {
        newCloseBtn.addEventListener('click', function() {
            closeChatbot();
        });
    }
    
    // Function to handle closing the chat
    function closeChatbot() {
        chatbotContainer.style.opacity = '0';
        chatbotContainer.style.visibility = 'hidden';
        // Hide after transition
        setTimeout(() => {
            chatbotContainer.style.display = 'none';
        }, 300);
    }

    // Send message function
    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        // Add user message to chat
        addMessage(message, 'user');
        userInput.value = '';
        
        // Disable input while waiting for response
        userInput.disabled = true;
        sendBtn.disabled = true;
        
        try {
            // Show typing indicator
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'chat-message bot-message typing-indicator';
            typingIndicator.innerHTML = `
                <div class="typing">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
            chatMessages.appendChild(typingIndicator);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Call the chatbot API
            const response = await fetch('/api/chatbot/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ message: message })
            });
            
            // Remove typing indicator
            chatMessages.removeChild(typingIndicator);
            
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success') {
                    // Add bot response
                    addMessage(data.message, 'bot');
                    
                    // Add suggested responses if available
                    if (data.suggestions && data.suggestions.length > 0) {
                        const suggestionsDiv = document.createElement('div');
                        suggestionsDiv.className = 'suggested-responses';
                        data.suggestions.forEach(suggestion => {
                            const suggestionBtn = document.createElement('button');
                            suggestionBtn.className = 'suggestion-btn';
                            suggestionBtn.textContent = suggestion;
                            suggestionBtn.onclick = () => {
                                userInput.value = suggestion;
                                sendMessage();
                            };
                            suggestionsDiv.appendChild(suggestionBtn);
                        });
                        
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'chat-message bot-message';
                        messageDiv.appendChild(suggestionsDiv);
                        chatMessages.appendChild(messageDiv);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                } else {
                    throw new Error(data.message || 'Unknown error');
                }
            } else {
                throw new Error('Network response was not ok');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage("I'm having trouble connecting to the server. Please try again later.", 'bot');
        } finally {
            // Re-enable input
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    }
    
    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Add message to chat
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${sender}-message`;
        
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageDiv.innerHTML = `
            <div class="message-content">${text}</div>
            <div class="message-time">${timeString}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Initial welcome message when chat opens
    function showWelcomeMessage() {
        const welcomeMessage = "Hello! I'm your GourmetGrove assistant. How can I help you today?";
        const suggestions = [
            "What products do you have?",
            "How can I track my order?",
            "What are your shipping policies?"
        ];
        
        addMessage(welcomeMessage, 'bot');
        
        const suggestionsDiv = document.createElement('div');
        suggestionsDiv.className = 'suggested-responses';
        suggestions.forEach(suggestion => {
            const suggestionBtn = document.createElement('button');
            suggestionBtn.className = 'suggestion-btn';
            suggestionBtn.textContent = suggestion;
            suggestionBtn.onclick = () => {
                userInput.value = suggestion;
                sendMessage();
            };
            suggestionsDiv.appendChild(suggestionBtn);
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot-message';
        messageDiv.appendChild(suggestionsDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Make chat window draggable
    header.addEventListener('mousedown', function(e) {
        if (e.target.tagName === 'BUTTON') return;
        
        isDragging = true;
        const rect = chatbotContainer.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        
        chatbotContainer.style.cursor = 'grabbing';
        chatbotContainer.style.userSelect = 'none';
        
        e.preventDefault();
    });
    
    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        
        chatbotContainer.style.left = (e.clientX - offsetX) + 'px';
        chatbotContainer.style.top = (e.clientY - offsetY) + 'px';
        chatbotContainer.style.right = 'auto';
        chatbotContainer.style.bottom = 'auto';
    });
    
    document.addEventListener('mouseup', function() {
        isDragging = false;
        chatbotContainer.style.cursor = '';
        chatbotContainer.style.userSelect = '';
    });
    
    // Prevent text selection while dragging
    header.addEventListener('selectstart', function(e) {
        if (isDragging) e.preventDefault();
    });
});
