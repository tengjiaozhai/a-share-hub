// src/api/static/js/app.js

const routes = {
  '#/dashboard': { init: initDashboard, render: renderDashboard },
  '#/market':    { init: initMarket,    render: renderMarket },
  '#/alpha':     { init: initAlpha,     render: renderAlpha },
};

let initialized = {};

function navigateTo(hash) {
  const route = routes[hash] || routes['#/dashboard'];
  const viewId = hash.replace('#/', 'view-');

  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

  // Show target view
  const view = document.getElementById(viewId);
  if (view) view.classList.add('active');

  // Update nav buttons
  document.querySelectorAll('.nav-group button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });

  // Initialize if first time
  if (!initialized[hash]) {
    initialized[hash] = true;
    route.init();
  }

  // Render view
  route.render();

  // Update URL
  window.location.hash = hash;
}

function switchView(btn, viewId) {
  const hash = '#/' + viewId.replace('view-', '');
  navigateTo(hash);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash || '#/dashboard';
  navigateTo(hash);
});

// Listen for hash changes
window.addEventListener('hashchange', () => {
  navigateTo(window.location.hash);
});
