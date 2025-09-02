/**
 * Embeddable Chat Widget
 * Usage: <script src="widget.js" data-tenant-id="xxx"></script>
 */

(function() {
    'use strict';
    
    // Configuration
    const API_URL = window.CHAT_API_URL || 'http://localhost:8000';
    const WIDGET_VERSION = '1.0.0';
    
    class ChatWidget {
        constructor(tenantId) {
            this.tenantId = tenantId;
            this.sessionId = this.getSessionFromCookie();
            this.isOpen = false;
            this.messages = [];
            this.container = null;
            this.init();
        }
        
        init() {
            this.createStyles();
            this.createWidget();
            this.attachEventListeners();
            this.initializeSession();
        }
        
        createStyles() {
            const style = document.createElement('style');
            style.textContent = `
                .chat-widget-container {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    z-index: 9999;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }
                
                .chat-widget-button {
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border: none;
                    cursor: pointer;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: transform 0.3s ease;
                }
                
                .chat-widget-button:hover {
                    transform: scale(1.1);
                }
                
                .chat-widget-button svg {
                    width: 30px;
                    height: 30px;
                    fill: white;
                }
                
                .chat-widget-window {
                    position: absolute;
                    bottom: 80px;
                    right: 0;
                    width: 380px;
                    height: 600px;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                    display: flex;
                    flex-direction: column;
                    transition: opacity 0.3s ease, transform 0.3s ease;
                    transform-origin: bottom right;
                }
                
                .chat-widget-window.hidden {
                    opacity: 0;
                    transform: scale(0);
                    pointer-events: none;
                }
                
                .chat-widget-header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .chat-widget-title {
                    font-size: 18px;
                    font-weight: 600;
                }
                
                .chat-widget-close {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    font-size: 24px;
                    line-height: 1;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                }
                
                .chat-widget-messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    background: #f7f8fa;
                }
                
                .chat-widget-message {
                    margin-bottom: 16px;
                    animation: fadeIn 0.3s ease;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .chat-widget-message.user {
                    text-align: right;
                }
                
                .chat-widget-message-bubble {
                    display: inline-block;
                    max-width: 70%;
                    padding: 12px 16px;
                    border-radius: 18px;
                    word-wrap: break-word;
                }
                
                .chat-widget-message.user .chat-widget-message-bubble {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                
                .chat-widget-message.assistant .chat-widget-message-bubble {
                    background: white;
                    color: #333;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
                }
                
                .chat-widget-products {
                    display: flex;
                    gap: 12px;
                    overflow-x: auto;
                    padding: 16px 0;
                    margin-bottom: 12px;
                    scroll-behavior: smooth;
                }
                
                .chat-widget-products::-webkit-scrollbar {
                    height: 6px;
                }
                
                .chat-widget-products::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 3px;
                }
                
                .chat-widget-products::-webkit-scrollbar-thumb {
                    background: #888;
                    border-radius: 3px;
                }
                
                .chat-widget-products::-webkit-scrollbar-thumb:hover {
                    background: #555;
                }
                
                .chat-widget-product-card {
                    flex: 0 0 150px;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                    cursor: pointer;
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                }
                
                .chat-widget-product-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                }
                
                .chat-widget-product-image {
                    width: 100%;
                    height: 150px;
                    object-fit: cover;
                    background: #f5f5f5;
                }
                
                .chat-widget-product-info {
                    padding: 8px;
                }
                
                .chat-widget-product-name {
                    font-size: 13px;
                    font-weight: 500;
                    color: #333;
                    margin-bottom: 4px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                }
                
                .chat-widget-product-price {
                    font-size: 12px;
                    color: #667eea;
                    font-weight: 600;
                }
                
                .chat-widget-input-container {
                    padding: 20px;
                    background: white;
                    border-top: 1px solid #e0e0e0;
                    border-radius: 0 0 12px 12px;
                }
                
                .chat-widget-input-wrapper {
                    display: flex;
                    gap: 10px;
                }
                
                .chat-widget-input {
                    flex: 1;
                    padding: 12px 16px;
                    border: 1px solid #e0e0e0;
                    border-radius: 24px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.3s ease;
                }
                
                .chat-widget-input:focus {
                    border-color: #667eea;
                }
                
                .chat-widget-send {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border: none;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: transform 0.3s ease;
                }
                
                .chat-widget-send:hover {
                    transform: scale(1.1);
                }
                
                .chat-widget-send svg {
                    width: 20px;
                    height: 20px;
                    fill: white;
                }
                
                .chat-widget-typing {
                    padding: 20px;
                    display: none;
                }
                
                .chat-widget-typing.active {
                    display: block;
                }
                
                .chat-widget-typing-dots {
                    display: inline-flex;
                    gap: 4px;
                }
                
                .chat-widget-typing-dot {
                    width: 8px;
                    height: 8px;
                    background: #999;
                    border-radius: 50%;
                    animation: typingDot 1.4s infinite;
                }
                
                .chat-widget-typing-dot:nth-child(2) {
                    animation-delay: 0.2s;
                }
                
                .chat-widget-typing-dot:nth-child(3) {
                    animation-delay: 0.4s;
                }
                
                @keyframes typingDot {
                    0%, 60%, 100% { opacity: 0.3; }
                    30% { opacity: 1; }
                }
                
                @media (max-width: 480px) {
                    .chat-widget-window {
                        width: 100vw;
                        height: 100vh;
                        bottom: 0;
                        right: 0;
                        border-radius: 0;
                    }
                    
                    .chat-widget-header {
                        border-radius: 0;
                    }
                    
                    .chat-widget-input-container {
                        border-radius: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        createWidget() {
            // Container
            this.container = document.createElement('div');
            this.container.className = 'chat-widget-container';
            
            // Chat button
            const button = document.createElement('button');
            button.className = 'chat-widget-button';
            button.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
            `;
            
            // Chat window
            const window = document.createElement('div');
            window.className = 'chat-widget-window hidden';
            window.innerHTML = `
                <div class="chat-widget-header">
                    <div class="chat-widget-title">Product Assistant</div>
                    <button class="chat-widget-close">×</button>
                </div>
                <div class="chat-widget-messages" id="chat-messages">
                    <div class="chat-widget-message assistant">
                        <div class="chat-widget-message-bubble">
                            👋 Hello! I'm here to help you find the perfect products. What are you looking for today?
                        </div>
                    </div>
                </div>
                <div class="chat-widget-typing" id="chat-typing">
                    <div class="chat-widget-typing-dots">
                        <div class="chat-widget-typing-dot"></div>
                        <div class="chat-widget-typing-dot"></div>
                        <div class="chat-widget-typing-dot"></div>
                    </div>
                </div>
                <div class="chat-widget-input-container">
                    <div class="chat-widget-input-wrapper">
                        <input 
                            type="text" 
                            class="chat-widget-input" 
                            id="chat-input"
                            placeholder="Type your message..."
                            maxlength="1000"
                        />
                        <button class="chat-widget-send" id="chat-send">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
            
            this.container.appendChild(button);
            this.container.appendChild(window);
            document.body.appendChild(this.container);
            
            // Store references
            this.button = button;
            this.window = window;
            this.messagesContainer = document.getElementById('chat-messages');
            this.input = document.getElementById('chat-input');
            this.sendButton = document.getElementById('chat-send');
            this.typingIndicator = document.getElementById('chat-typing');
        }
        
        attachEventListeners() {
            // Toggle chat window
            this.button.addEventListener('click', () => this.toggleChat());
            this.window.querySelector('.chat-widget-close').addEventListener('click', () => this.toggleChat());
            
            // Send message
            this.sendButton.addEventListener('click', () => this.sendMessage());
            this.input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
        }
        
        toggleChat() {
            this.isOpen = !this.isOpen;
            if (this.isOpen) {
                this.window.classList.remove('hidden');
                this.input.focus();
            } else {
                this.window.classList.add('hidden');
            }
        }
        
        async initializeSession() {
            try {
                const response = await fetch(`${API_URL}/api/session`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        tenant_id: this.tenantId,
                        session_id: this.sessionId
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.sessionId = data.session_id;
                    this.saveSessionToCookie(this.sessionId);
                }
            } catch (error) {
                console.error('Failed to initialize session:', error);
            }
        }
        
        async sendMessage() {
            const message = this.input.value.trim();
            if (!message) return;
            
            // Add user message to UI
            this.addMessage(message, 'user');
            this.input.value = '';
            
            // Show typing indicator
            this.showTyping();
            
            try {
                // Use streaming endpoint
                const response = await fetch(`${API_URL}/api/chat/stream`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        message: message,
                        tenant_id: this.tenantId,
                        session_id: this.sessionId
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                // Get session ID from header
                const sessionId = response.headers.get('X-Session-Id');
                if (sessionId) {
                    this.sessionId = sessionId;
                    this.saveSessionToCookie(sessionId);
                }
                
                // Read stream
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let assistantMessage = '';
                let messageDiv = null;
                let hasProductCards = false;
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                
                                if (data.error) {
                                    this.hideTyping();
                                    this.addMessage('Sorry, an error occurred. Please try again.', 'assistant');
                                    return;
                                }
                                
                                // Handle product cards response
                                if (data.type === 'product_cards' && data.data) {
                                    this.hideTyping();
                                    hasProductCards = true;
                                    
                                    // Display product cards
                                    if (data.data.products && data.data.products.length > 0) {
                                        this.addProductCards(data.data.products);
                                    }
                                    
                                    // Display the message text
                                    if (data.data.message) {
                                        this.addMessage(data.data.message, 'assistant');
                                    }
                                }
                                
                                // Handle regular text chunks (only if we haven't shown product cards)
                                if (data.chunk && !hasProductCards) {
                                    assistantMessage += data.chunk;
                                    
                                    // Create or update message
                                    if (!messageDiv) {
                                        this.hideTyping();
                                        messageDiv = this.addMessage(assistantMessage, 'assistant', true);
                                    } else {
                                        messageDiv.querySelector('.chat-widget-message-bubble').textContent = assistantMessage;
                                    }
                                }
                                
                                if (data.done) {
                                    this.hideTyping();
                                }
                            } catch (e) {
                                console.error('Failed to parse SSE data:', e);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to send message:', error);
                this.hideTyping();
                this.addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
            }
        }
        
        addMessage(text, role, returnElement = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-widget-message ${role}`;
            
            const bubble = document.createElement('div');
            bubble.className = 'chat-widget-message-bubble';
            bubble.textContent = text;
            
            messageDiv.appendChild(bubble);
            this.messagesContainer.appendChild(messageDiv);
            
            // Scroll to bottom
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
            
            if (returnElement) {
                return messageDiv;
            }
        }
        
        showTyping() {
            this.typingIndicator.classList.add('active');
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
        
        hideTyping() {
            this.typingIndicator.classList.remove('active');
        }
        
        addProductCards(products) {
            // Create container for products
            const container = document.createElement('div');
            container.className = 'chat-widget-message assistant';
            
            const productsGrid = document.createElement('div');
            productsGrid.className = 'chat-widget-products';
            
            // Add each product card
            products.forEach(product => {
                const card = this.createProductCard(product);
                productsGrid.appendChild(card);
            });
            
            container.appendChild(productsGrid);
            this.messagesContainer.appendChild(container);
            
            // Scroll to bottom
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
        
        createProductCard(product) {
            const card = document.createElement('div');
            card.className = 'chat-widget-product-card';
            
            // Product image with fallback
            const img = document.createElement('img');
            img.className = 'chat-widget-product-image';
            img.src = product.image_url || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="150" height="150" viewBox="0 0 150 150"%3E%3Crect width="150" height="150" fill="%23f5f5f5"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14" fill="%23999"%3ENo Image%3C/text%3E%3C/svg%3E';
            img.alt = product.name || 'Product';
            img.onerror = function() {
                this.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="150" height="150" viewBox="0 0 150 150"%3E%3Crect width="150" height="150" fill="%23f5f5f5"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14" fill="%23999"%3ENo Image%3C/text%3E%3C/svg%3E';
            };
            
            // Product info
            const info = document.createElement('div');
            info.className = 'chat-widget-product-info';
            
            const name = document.createElement('div');
            name.className = 'chat-widget-product-name';
            name.textContent = product.name || 'Unnamed Product';
            
            const price = document.createElement('div');
            price.className = 'chat-widget-product-price';
            if (product.price_min !== undefined) {
                if (product.price_max && product.price_max !== product.price_min) {
                    price.textContent = `$${product.price_min.toFixed(2)} - $${product.price_max.toFixed(2)}`;
                } else {
                    price.textContent = `$${product.price_min.toFixed(2)}`;
                }
            }
            
            info.appendChild(name);
            info.appendChild(price);
            
            card.appendChild(img);
            card.appendChild(info);
            
            return card;
        }
        
        getSessionFromCookie() {
            const name = 'chat_session_id=';
            const decodedCookie = decodeURIComponent(document.cookie);
            const ca = decodedCookie.split(';');
            for (let i = 0; i < ca.length; i++) {
                let c = ca[i];
                while (c.charAt(0) === ' ') {
                    c = c.substring(1);
                }
                if (c.indexOf(name) === 0) {
                    return c.substring(name.length, c.length);
                }
            }
            return null;
        }
        
        saveSessionToCookie(sessionId) {
            const expires = new Date();
            expires.setTime(expires.getTime() + (60 * 60 * 1000)); // 1 hour
            document.cookie = `chat_session_id=${sessionId};expires=${expires.toUTCString()};path=/`;
        }
    }
    
    // Initialize widget when script loads
    document.addEventListener('DOMContentLoaded', function() {
        const script = document.currentScript || document.querySelector('script[data-tenant-id]');
        const tenantId = script?.getAttribute('data-tenant-id');
        
        if (!tenantId) {
            console.error('Chat Widget: tenant-id is required');
            return;
        }
        
        window.chatWidget = new ChatWidget(tenantId);
    });
    
    // Also try to initialize immediately if DOM is already loaded
    if (document.readyState !== 'loading') {
        const script = document.currentScript || document.querySelector('script[data-tenant-id]');
        const tenantId = script?.getAttribute('data-tenant-id');
        
        if (tenantId && !window.chatWidget) {
            window.chatWidget = new ChatWidget(tenantId);
        }
    }
})();