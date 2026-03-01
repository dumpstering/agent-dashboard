(function () {
  const DashboardAgents = window.DashboardAgents || {};

  DashboardAgents.updateStats = function updateStats(stats) {
    if (!stats || typeof stats !== 'object') return;
    document.getElementById('statActive').textContent = String(stats.active ?? 0);
    document.getElementById('statCompleted').textContent = String(stats.completed_today ?? 0);
    document.getElementById('statQueued').textContent = String(stats.queued ?? 0);
    document.getElementById('statTotal').textContent = String(stats.total ?? 0);
  };

  DashboardAgents.updateAgentTable = function updateAgentTable(agents) {
    const tbody = document.getElementById('agentTableBody');
    tbody.replaceChildren();

    if (!Array.isArray(agents) || agents.length === 0) {
      tbody.appendChild(window.DashboardApp.createEmptyStateRow());
      return;
    }

    const byProject = {};
    agents.forEach((agent) => {
      if (!byProject[agent.project]) {
        byProject[agent.project] = [];
      }
      byProject[agent.project].push(agent);
    });

    const rows = [];
    Object.keys(byProject)
      .sort()
      .forEach((project) => {
        const projectRow = document.createElement('tr');
        projectRow.className = 'project-group-header';
        const projectCell = document.createElement('td');
        projectCell.colSpan = 4;
        projectCell.textContent = project;
        projectRow.appendChild(projectCell);
        rows.push(projectRow);

        byProject[project].forEach((agent) => {
          const row = document.createElement('tr');

          const idCell = document.createElement('td');
          idCell.textContent = String(agent.id ?? '');
          row.appendChild(idCell);

          const taskCell = document.createElement('td');
          taskCell.textContent = String(agent.task ?? '');
          row.appendChild(taskCell);

          const statusCell = document.createElement('td');
          statusCell.appendChild(window.DashboardApp.createStatusBadge(agent.status));
          row.appendChild(statusCell);

          const durationCell = document.createElement('td');
          durationCell.textContent = window.DashboardApp.formatDuration(agent.duration);
          row.appendChild(durationCell);

          rows.push(row);
        });
      });

    tbody.append(...rows);
  };

  window.DashboardAgents = DashboardAgents;
})();
