const State = {
  execMode: 'full',
  killSwitch: false,
  configHydrated: false,
  simRunning: false,
  pagination: {
    decisions: { page: 0, data: [] },
    orders:    { page: 0, data: [] },
    targets:   { page: 0, data: [] },
    errors:    { page: 0, data: [] },
  },
  PAGE_SIZE: 10,
};

function pagSlice(key) {
  const p = State.pagination[key];
  const start = p.page * State.PAGE_SIZE;
  return p.data.slice(start, start + State.PAGE_SIZE);
}

function pagTotal(key) {
  return Math.max(1, Math.ceil(State.pagination[key].data.length / State.PAGE_SIZE));
}

function pagPrev(key) {
  if (State.pagination[key].page > 0) {
    State.pagination[key].page--;
    renderPagTab(key);
  }
}

function pagNext(key) {
  if (State.pagination[key].page < pagTotal(key) - 1) {
    State.pagination[key].page++;
    renderPagTab(key);
  }
}

function renderPagControls(key) {
  const total = pagTotal(key);
  const cur = State.pagination[key].page + 1;
  return `<div class="pagination">
    <button onclick="pagPrev('${key}')" ${cur <= 1 ? 'disabled' : ''}>上一页</button>
    <span class="page-info">${cur} / ${total}</span>
    <button onclick="pagNext('${key}')" ${cur >= total ? 'disabled' : ''}>下一页</button>
  </div>`;
}

function renderPagTab(key) {
  const renderers = {
    decisions: renderDecisions,
    orders: renderOrders,
    targets: renderTargets,
    errors: renderErrorEvents,
  };
  if (renderers[key]) renderers[key](State.pagination[key].data);
}
