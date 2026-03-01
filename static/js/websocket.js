(function () {
  const DashboardWebSocket = window.DashboardWebSocket || {};

  DashboardWebSocket.scheduleChatReconnect = function scheduleChatReconnect() {
    const state = window.DashboardApp.state;
    if (state.chatReconnectTimer) return;

    const delay = state.chatReconnectDelayMs;
    window.DashboardApp.updateConnectionStatus(false, `Reconnecting in ${(delay / 1000).toFixed(1)}s`);
    state.chatReconnectTimer = setTimeout(() => {
      state.chatReconnectTimer = null;
      DashboardWebSocket.connectChatWebSocket();
    }, delay);
    state.chatReconnectDelayMs = Math.min(state.chatReconnectDelayMs * 2, 10000);
  };

  DashboardWebSocket.connectChatWebSocket = function connectChatWebSocket() {
    const state = window.DashboardApp.state;

    if (state.chatSocket) {
      state.chatSocket.close();
      state.chatSocket = null;
    }

    const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
    state.chatSocket = new WebSocket(`${wsProtocol}://${location.host}/ws/chat`);
    window.DashboardApp.updateConnectionStatus(false, 'Connecting...');

    state.chatSocket.onopen = () => {
      state.chatReconnectDelayMs = 1000;
      if (state.chatReconnectTimer) {
        clearTimeout(state.chatReconnectTimer);
        state.chatReconnectTimer = null;
      }
    };

    state.chatSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        window.DashboardChat.handleChatWsMessage(data);
      } catch (error) {
        console.error('Invalid chat WS payload:', error);
      }
    };

    state.chatSocket.onerror = (error) => {
      console.error('Chat WS error:', error);
    };

    state.chatSocket.onclose = () => {
      window.DashboardChat.finalizeStream();
      window.DashboardChat.showTypingIndicator(false);
      DashboardWebSocket.scheduleChatReconnect();
    };
  };

  DashboardWebSocket.connectSSE = function connectSSE() {
    const state = window.DashboardApp.state;

    if (state.eventSource) {
      state.eventSource.close();
    }

    state.eventSource = new EventSource('/api/sse');

    state.eventSource.onopen = () => {
      if (state.sseReconnectTimer) {
        clearTimeout(state.sseReconnectTimer);
        state.sseReconnectTimer = null;
      }
    };

    state.eventSource.addEventListener('agents', (event) => {
      const data = window.DashboardApp.parseEventData(event, 'agents');
      if (!data) return;
      if (Array.isArray(data)) {
        window.DashboardAgents.updateAgentTable(data);
        return;
      }
      if (typeof data === 'object') {
        if (data.stats) window.DashboardAgents.updateStats(data.stats);
        if (Array.isArray(data.agents)) window.DashboardAgents.updateAgentTable(data.agents);
      }
    });

    state.eventSource.addEventListener('system', (event) => {
      const data = window.DashboardApp.parseEventData(event, 'system');
      if (!data || typeof data !== 'object') return;

      if ('active' in data || 'completed_today' in data || 'queued' in data || 'total' in data) {
        window.DashboardAgents.updateStats(data);
      }
    });

    state.eventSource.addEventListener('message', (event) => {
      const data = window.DashboardApp.parseEventData(event, 'message');
      if (!data) return;

      if (data.stats || data.agents) {
        window.DashboardAgents.updateStats(data.stats);
        window.DashboardAgents.updateAgentTable(data.agents);
      }
    });

    state.eventSource.onerror = () => {
      state.eventSource.close();
      if (!state.sseReconnectTimer) {
        state.sseReconnectTimer = setTimeout(() => {
          DashboardWebSocket.connectSSE();
        }, 2000);
      }
    };
  };

  window.DashboardWebSocket = DashboardWebSocket;
})();
