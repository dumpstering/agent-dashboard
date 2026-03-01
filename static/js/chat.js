(function () {
  const DashboardChat = window.DashboardChat || {};

  DashboardChat.createChatMessageElement = function createChatMessageElement(
    text,
    role,
    timestampSeconds,
    isTyping
  ) {
    const resolvedRole = role || 'op';
    const resolvedTimestamp = timestampSeconds || Math.floor(Date.now() / 1000);
    const typing = Boolean(isTyping);

    const msg = document.createElement('div');
    msg.className = `chat-message chat-${resolvedRole}`;
    if (typing) {
      msg.classList.add('typing');
    }

    if (resolvedRole === 'system') {
      const body = document.createElement('span');
      body.className = 'chat-text system';
      body.textContent = typeof text === 'string' ? text : String(text ?? '');
      msg.appendChild(body);
      return msg;
    }

    const meta = document.createElement('div');
    meta.className = 'chat-meta';

    const author = document.createElement('span');
    author.className = 'chat-author';
    author.textContent = resolvedRole === 'user' ? 'You' : 'Op';

    const timestamp = document.createElement('span');
    timestamp.className = 'chat-timestamp';
    const date = new Date(resolvedTimestamp * 1000);
    timestamp.textContent = date.toTimeString().split(' ')[0];

    const body = document.createElement('div');
    body.className = 'chat-bubble';
    body.textContent = typeof text === 'string' ? text : String(text ?? '');

    meta.appendChild(author);
    meta.appendChild(timestamp);
    msg.appendChild(meta);
    msg.appendChild(body);
    return msg;
  };

  DashboardChat.appendChatMessage = function appendChatMessage(text, role, timestampSeconds, isTyping) {
    const messages = document.getElementById('chatMessages');
    const message = DashboardChat.createChatMessageElement(
      text,
      role || 'op',
      timestampSeconds || Math.floor(Date.now() / 1000),
      Boolean(isTyping)
    );
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
    return message;
  };

  DashboardChat.showTypingIndicator = function showTypingIndicator(show) {
    const messages = document.getElementById('chatMessages');
    const state = window.DashboardApp.state;

    if (show) {
      if (state.typingIndicator) return;
      state.typingIndicator = DashboardChat.createChatMessageElement(
        'Op is typing...',
        'op',
        Math.floor(Date.now() / 1000),
        true
      );
      messages.appendChild(state.typingIndicator);
      messages.scrollTop = messages.scrollHeight;
      return;
    }

    if (state.typingIndicator && state.typingIndicator.parentNode) {
      state.typingIndicator.parentNode.removeChild(state.typingIndicator);
    }
    state.typingIndicator = null;
  };

  DashboardChat.beginStreamIfNeeded = function beginStreamIfNeeded() {
    const state = window.DashboardApp.state;
    if (state.streamingBubble) return;
    const message = DashboardChat.appendChatMessage('', 'op');
    state.streamingBubble = message.querySelector('.chat-bubble');
  };

  DashboardChat.finalizeStream = function finalizeStream() {
    const state = window.DashboardApp.state;
    if (!state.streamingBubble) return;

    const text = state.streamingBubble.textContent.trim();
    if (!text) {
      const parent = state.streamingBubble.closest('.chat-message');
      if (parent && parent.parentNode) {
        parent.parentNode.removeChild(parent);
      }
    }

    state.streamingBubble = null;
    DashboardChat.showTypingIndicator(false);
  };

  DashboardChat.handleChatWsMessage = function handleChatWsMessage(data) {
    if (!data || typeof data !== 'object') return;

    if (data.type === 'connected') {
      window.DashboardApp.updateConnectionStatus(true, 'Connected');
      return;
    }

    if (data.type === 'history' && Array.isArray(data.messages)) {
      const chat = document.getElementById('chatMessages');
      chat.replaceChildren();
      data.messages.forEach((msg) => {
        const text = typeof msg?.text === 'string' ? msg.text : '';
        const timestamp = Number(msg?.timestamp) || Math.floor(Date.now() / 1000);
        const role = msg?.is_system
          ? 'system'
          : msg?.role === 'user' || msg?.from === 'user'
            ? 'user'
            : 'op';
        DashboardChat.appendChatMessage(text, role, timestamp);
      });
      return;
    }

    if (data.type === 'stream') {
      DashboardChat.beginStreamIfNeeded();
      DashboardChat.showTypingIndicator(true);
      const delta = typeof data.delta === 'string' ? data.delta : '';
      window.DashboardApp.state.streamingBubble.textContent += delta;
      const messages = document.getElementById('chatMessages');
      messages.scrollTop = messages.scrollHeight;
      return;
    }

    if (data.type === 'stream_end') {
      DashboardChat.finalizeStream();
      return;
    }

    if (data.type === 'reply') {
      DashboardChat.finalizeStream();
      DashboardChat.appendChatMessage(data.text ?? '', 'op');
      return;
    }

    if (data.type === 'error') {
      DashboardChat.finalizeStream();
      DashboardChat.appendChatMessage(data.text ?? 'Chat error', 'system');
    }
  };

  DashboardChat.sendMessage = function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();

    if (!text) {
      return;
    }

    const socket = window.DashboardApp.state.chatSocket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      DashboardChat.appendChatMessage('Chat is disconnected. Reconnecting...', 'system');
      return;
    }

    DashboardChat.appendChatMessage(text, 'user');
    input.value = '';
    socket.send(JSON.stringify({ message: text }));
  };

  window.DashboardChat = DashboardChat;
  window.sendMessage = DashboardChat.sendMessage;
})();
