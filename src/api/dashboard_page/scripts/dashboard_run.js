const RUNS_API = '/api/v1/dashboard/runs';
const RUN_EVENTS_API = (runContextId) => `/api/v1/dashboard/runs/${encodeURIComponent(runContextId)}/events`;

let runEventSource = null;
let currentRunContextId = null;
let runStreamHeartbeatTimer = null;
let runStreamHardTimeoutTimer = null;
let runStreamReconnectAttempts = 0;
const RUN_STREAM_HEARTBEAT_MS = 90_000;
const RUN_STREAM_HARD_TIMEOUT_MS = 180_000;
const RUN_STREAM_RECONNECT_MAX = 5;

function clearRunStreamTimers() {
  if (runStreamHeartbeatTimer) {
    clearTimeout(runStreamHeartbeatTimer);
    runStreamHeartbeatTimer = null;
  }
  if (runStreamHardTimeoutTimer) {
    clearTimeout(runStreamHardTimeoutTimer);
    runStreamHardTimeoutTimer = null;
  }
}

function endRunStream(reason, kind) {
  clearRunStreamTimers();
  if (!runEventSource) return;
  try { runEventSource.close(); } catch (_) { /* 关闭失败也不影响后续清理 */ }
  runEventSource = null;
  setStreamStatus(kind || 'error', reason || '运行超时');
  if (kind === 'error' && reason) {
    addAlert('err', reason);
  }
  finishRun();
}

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

  const resetHeartbeat = () => {
    if (runStreamHeartbeatTimer) clearTimeout(runStreamHeartbeatTimer);
    runStreamHeartbeatTimer = setTimeout(() => {
      endRunStream('运行超时，90 秒内未收到任何事件，连接已断开', 'error');
    }, RUN_STREAM_HEARTBEAT_MS);
  };
  resetHeartbeat();

  runStreamHardTimeoutTimer = setTimeout(() => {
    endRunStream('运行超时，已达到 180 秒硬性上限，强制关闭', 'error');
  }, RUN_STREAM_HARD_TIMEOUT_MS);

  runStreamReconnectAttempts = 0;

  runEventSource.onmessage = (event) => {
    runStreamReconnectAttempts = 0;
    try {
      const payload = JSON.parse(event.data);
      applyRunStreamEvent(payload);
      resetHeartbeat();
    } catch (err) {
      addAlert('err', `解析事件失败: ${err.message}`);
    }
  };
  runEventSource.addEventListener('run.completed', async (event) => {
    const payload = JSON.parse(event.data);
    try { await loadRunSnapshot(payload.run_context_id); } catch (_) { /* 快照加载失败也不影响结束 */ }
    endRunStream('本轮完成', 'success');
  });
  runEventSource.addEventListener('run.failed', async (event) => {
    const payload = JSON.parse(event.data);
    try { await loadRunSnapshot(payload.run_context_id); } catch (_) { /* 快照加载失败也不影响结束 */ }
    endRunStream(payload.payload?.message || '运行失败', 'error');
  });
  runEventSource.onerror = () => {
    if (runStreamHeartbeatTimer) {
      clearTimeout(runStreamHeartbeatTimer);
      runStreamHeartbeatTimer = null;
    }
    runStreamReconnectAttempts += 1;
    if (runStreamReconnectAttempts > RUN_STREAM_RECONNECT_MAX) {
      endRunStream(`重连失败 ${runStreamReconnectAttempts} 次`, 'error');
      return;
    }
    setStreamStatus('pending', `连接中断，重试中 (${runStreamReconnectAttempts}/${RUN_STREAM_RECONNECT_MAX})…`);
  };
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
