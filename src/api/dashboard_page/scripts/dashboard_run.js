const RUNS_API = '/api/v1/dashboard/runs';
const RUN_EVENTS_API = (runContextId) => `/api/v1/dashboard/runs/${encodeURIComponent(runContextId)}/events`;

let runEventSource = null;
let currentRunContextId = null;

function setStreamStatus(kind, message) {
  const el = document.getElementById('stream-status');
  if (!el) return;
  el.className = `stream-pill ${kind}`;
  el.textContent = message;
}

function applyRunStreamEvent(payload) {
  if (!payload || typeof payload !== 'object') return;
  if (payload.run_context_id) {
    document.getElementById('run-trace-id').textContent = payload.run_context_id;
  }
  if (Array.isArray(payload.steps)) {
    renderTimeline({
      run_context_id: payload.run_context_id,
      steps: payload.steps,
    });
  }
  if (payload.run_pnl_summary) {
    renderRunPnlSummary(payload.run_pnl_summary);
  }
  if (Array.isArray(payload.reconcile_items)) {
    renderReconcile(payload.reconcile_items);
  }
}

function connectRunStream(runContextId) {
  if (runEventSource) {
    runEventSource.close();
    runEventSource = null;
  }
  currentRunContextId = runContextId;
  document.getElementById('run-trace-id').textContent = runContextId;
  setStreamStatus('running', '运行中');
  runEventSource = new EventSource(RUN_EVENTS_API(runContextId));
  runEventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      applyRunStreamEvent(payload);
    } catch (err) {
      addAlert('err', `解析事件失败: ${err.message}`);
    }
  };
  runEventSource.addEventListener('run.completed', async (event) => {
    const payload = JSON.parse(event.data);
    await loadRunSnapshot(payload.run_context_id);
    setStreamStatus('success', '本轮完成');
    runEventSource.close();
    runEventSource = null;
    finishRun();
  });
  runEventSource.addEventListener('run.failed', async (event) => {
    const payload = JSON.parse(event.data);
    await loadRunSnapshot(payload.run_context_id);
    setStreamStatus('error', '运行失败');
    addAlert('err', payload.payload?.message || '运行失败');
    runEventSource.close();
    runEventSource = null;
    finishRun();
  });
}

async function loadRunSnapshot(runContextId) {
  const res = await fetch(`${WORKBENCH_API}?run_context_id=${encodeURIComponent(runContextId)}`);
  const body = await parseResponseBody(res);
  if (!res.ok) {
    throw new Error(extractErrorMessage(body, `加载运行快照失败 (${res.status})`));
  }
  renderWorkbench(body, { active: killSwitchActive });
}

async function triggerRun() {
  if (simRunning) return;
  simRunning = true;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, true, '运行中');
  setStreamStatus('pending', '请求中');
  renderTimeline({
    run_context_id: '--',
    steps: [
      {
        stage: 'decision',
        status: 'running',
        timestamp: new Date().toISOString(),
        message: '请求已提交，等待后台接受本轮任务。',
      },
    ],
  });

  try {
    const res = await fetch(RUNS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildRunPayload()),
    });
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, `启动失败 (${res.status})`));
    }
    connectRunStream(body.run_context_id);
  } catch (error) {
    setStreamStatus('error', '启动失败');
    addAlert('err', `运行失败: ${error.message}`);
    finishRun();
  }
}
