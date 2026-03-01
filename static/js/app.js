(function () {
  const DashboardApp = window.DashboardApp || {};

  DashboardApp.state = {
    eventSource: null,
    sseReconnectTimer: null,
    systemStatsInterval: null,
    chatSocket: null,
    chatReconnectTimer: null,
    chatReconnectDelayMs: 1000,
    streamingBubble: null,
    typingIndicator: null,
  };

  DashboardApp.formatDuration = function formatDuration(seconds) {
    if (!seconds) return '—';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hours}h ${remainMins}m`;
  };

  DashboardApp.createStatusBadge = function createStatusBadge(status) {
    const safeStatus = typeof status === 'string' ? status : 'unknown';
    const badge = document.createElement('span');
    badge.className = `status-badge status-${safeStatus}`;
    badge.textContent = safeStatus;
    return badge;
  };

  DashboardApp.createEmptyStateRow = function createEmptyStateRow() {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;

    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';

    const icon = document.createElement('div');
    icon.className = 'empty-state-icon';
    icon.textContent = '⚡';

    const text = document.createElement('div');
    text.textContent = 'No agents active';

    emptyState.appendChild(icon);
    emptyState.appendChild(text);
    cell.appendChild(emptyState);
    row.appendChild(cell);
    return row;
  };

  DashboardApp.parseEventData = function parseEventData(event, eventName) {
    try {
      return JSON.parse(event.data);
    } catch (error) {
      console.error(`Invalid SSE payload for ${eventName}:`, error);
      return null;
    }
  };

  DashboardApp.updateConnectionStatus = function updateConnectionStatus(connected, label) {
    const status = document.getElementById('connStatus');
    const text = document.getElementById('connText');

    if (connected) {
      status.className = 'connection-status connected';
      text.textContent = label || 'Connected';
      return;
    }

    status.className = 'connection-status disconnected';
    text.textContent = label || 'Disconnected';
  };

  DashboardApp.getNetworkWindow = function getNetworkWindow(network, key) {
    if (!network || typeof network !== 'object') {
      return { bytes_sent_str: '—', bytes_recv_str: '—' };
    }
    const windowData = network[key];
    if (!windowData || typeof windowData !== 'object') {
      return { bytes_sent_str: '—', bytes_recv_str: '—' };
    }
    return {
      bytes_sent_str: windowData.bytes_sent_str ?? '—',
      bytes_recv_str: windowData.bytes_recv_str ?? '—',
    };
  };

  DashboardApp.bindChatInput = function bindChatInput() {
    const input = document.getElementById('chatInput');
    if (!input || input.dataset.boundEnter === '1') return;

    input.addEventListener('keypress', (event) => {
      if (event.key === 'Enter') {
        window.DashboardChat.sendMessage();
      }
    });
    input.dataset.boundEnter = '1';
  };

  DashboardApp.init = async function init() {
    await window.DashboardSystem.fetchSystemStats();
    window.DashboardWebSocket.connectSSE();
    window.DashboardWebSocket.connectChatWebSocket();

    DashboardApp.state.systemStatsInterval = setInterval(
      window.DashboardSystem.fetchSystemStats,
      90000
    );
  };

  window.DashboardApp = DashboardApp;

  document.addEventListener('DOMContentLoaded', () => {
    DashboardApp.bindChatInput();
    DashboardApp.init();
  });
})();
