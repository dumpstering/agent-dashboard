(function () {
  const DashboardSystem = window.DashboardSystem || {};

  DashboardSystem.fetchSystemStats = async function fetchSystemStats() {
    try {
      const response = await fetch('/api/system');
      const data = await response.json();

      document.getElementById('sysUptime').textContent = data.uptime;

      document.getElementById('sysRam').textContent = `${data.memory.used_gb} / ${data.memory.total_gb} GB`;
      document.getElementById('sysRamPercent').textContent = `${data.memory.percent.toFixed(1)}%`;

      const ramBar = document.getElementById('sysRamBar');
      ramBar.style.width = `${data.memory.percent}%`;
      ramBar.className = 'progress-fill';
      if (data.memory.percent > 90) ramBar.className += ' error';
      else if (data.memory.percent > 75) ramBar.className += ' warning';

      document.getElementById('sysCpu').textContent = `${data.cpu.percent.toFixed(1)}%`;

      const maxLoad = 4.0;
      document.getElementById('cpuLoad1m').style.height = `${Math.min(100, (data.cpu.load_1m / maxLoad) * 100)}%`;
      document.getElementById('cpuLoad5m').style.height = `${Math.min(100, (data.cpu.load_5m / maxLoad) * 100)}%`;
      document.getElementById('cpuLoad15m').style.height = `${Math.min(100, (data.cpu.load_15m / maxLoad) * 100)}%`;

      document.getElementById('cpuLoad1mLabel').textContent = `${data.cpu.load_1m}`;
      document.getElementById('cpuLoad5mLabel').textContent = `${data.cpu.load_5m}`;
      document.getElementById('cpuLoad15mLabel').textContent = `${data.cpu.load_15m}`;

      const allTime = window.DashboardApp.getNetworkWindow(data.network, 'all_time');
      const last24h = window.DashboardApp.getNetworkWindow(data.network, 'last_24h');
      const last1h = window.DashboardApp.getNetworkWindow(data.network, 'last_1h');

      document.getElementById('sysNetAllTimeSent').textContent = allTime.bytes_sent_str;
      document.getElementById('sysNetAllTimeRecv').textContent = allTime.bytes_recv_str;
      document.getElementById('sysNet24hSent').textContent = last24h.bytes_sent_str;
      document.getElementById('sysNet24hRecv').textContent = last24h.bytes_recv_str;
      document.getElementById('sysNet1hSent').textContent = last1h.bytes_sent_str;
      document.getElementById('sysNet1hRecv').textContent = last1h.bytes_recv_str;
    } catch (error) {
      console.error('Error fetching system stats:', error);
    }
  };

  window.DashboardSystem = DashboardSystem;
})();
