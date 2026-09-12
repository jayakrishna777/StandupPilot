/* StandupPilot popup controls; credentials stay inside chrome.storage and are never rendered. */
(function () {
  'use strict';

  const MESSAGE_TYPES = {
    SAVE_CONFIG: 'SP_SAVE_CONFIG',
    GET_CONFIG: 'SP_GET_CONFIG',
    GET_STATUS: 'SP_GET_STATUS',
    RETRY_PENDING: 'SP_RETRY_PENDING',
    START_CAPTURE: 'SP_START_CAPTURE',
    STOP_CAPTURE: 'SP_STOP_CAPTURE'
  };
  const form = document.getElementById('config-form');
  const sessionInput = document.getElementById('meeting-session');
  const tokenInput = document.getElementById('session-token');
  const tokenState = document.getElementById('token-state');
  const consent = document.getElementById('consent');
  const startButton = document.getElementById('start');
  const stopButton = document.getElementById('stop');
  const retryButton = document.getElementById('retry');
  const message = document.getElementById('message');
  const captureStatus = document.getElementById('capture-status');
  const deliveryStatus = document.getElementById('delivery-status');
  const queuedCount = document.getElementById('queued-count');

  function showMessage(value) {
    message.textContent = value || '';
  }

  function sendRuntime(messageValue) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const complete = (response) => {
        if (settled) return;
        settled = true;
        resolve(response || {});
      };
      try {
        const result = chrome.runtime.sendMessage(messageValue, complete);
        if (result && typeof result.then === 'function') result.then(complete, reject);
      } catch (error) {
        reject(error);
      }
    });
  }

  function sendTab(tabId, messageValue) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const complete = (response) => {
        if (settled) return;
        settled = true;
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(response || {});
      };
      try {
        const result = chrome.tabs.sendMessage(tabId, messageValue, complete);
        if (result && typeof result.then === 'function') result.then(complete, reject);
      } catch (error) {
        reject(error);
      }
    });
  }

  async function activeMeetTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs?.[0];
    if (!tab?.id || !/^https:\/\/meet\.google\.com\//.test(tab.url || '')) {
      throw new Error('Open a Google Meet tab before starting capture');
    }
    return tab;
  }

  function applyStatus(status) {
    captureStatus.textContent = status.capturing ? 'Capturing' : 'Stopped';
    deliveryStatus.textContent = (status.deliveryStatus || 'disconnected').replace(/^./, (letter) => letter.toUpperCase());
    queuedCount.textContent = String(status.pendingCount || 0);
    startButton.disabled = status.capturing || !consent.checked;
    stopButton.disabled = !status.capturing;
  }

  async function refreshStatus() {
    try {
      const response = await sendRuntime({ type: MESSAGE_TYPES.GET_STATUS });
      if (response.ok) applyStatus(response);
    } catch (error) {
      showMessage(error.message);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const response = await sendRuntime({
        type: MESSAGE_TYPES.SAVE_CONFIG,
        config: { meetingSessionId: sessionInput.value, sessionToken: tokenInput.value }
      });
      if (!response.ok) throw new Error(response.error || 'Unable to save configuration');
      tokenInput.value = '';
      tokenState.textContent = 'Token configured (value hidden)';
      showMessage('Configuration saved.');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message);
    }
  });

  consent.addEventListener('change', refreshStatus);
  startButton.addEventListener('click', async () => {
    if (!consent.checked) return showMessage('Inform participants before starting capture.');
    try {
      const tab = await activeMeetTab();
      const response = await sendTab(tab.id, { type: MESSAGE_TYPES.START_CAPTURE, consentAcknowledged: true });
      if (!response.ok && response.capturing !== true) throw new Error(response.error || 'Unable to start capture');
      showMessage('Capture started.');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message);
    }
  });

  stopButton.addEventListener('click', async () => {
    try {
      const tab = await activeMeetTab();
      await sendTab(tab.id, { type: MESSAGE_TYPES.STOP_CAPTURE });
      showMessage('Capture stopped.');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message);
    }
  });

  retryButton.addEventListener('click', async () => {
    try {
      const response = await sendRuntime({ type: MESSAGE_TYPES.RETRY_PENDING });
      if (!response.ok) throw new Error(response.error || 'Retry failed');
      showMessage('Queued events retried.');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message);
    }
  });

  (async () => {
    try {
      const response = await sendRuntime({ type: MESSAGE_TYPES.GET_CONFIG });
      if (response.ok) {
        sessionInput.value = response.config.meetingSessionId || '';
        tokenState.textContent = response.config.hasSessionToken ? 'Token configured (value hidden)' : 'No token configured';
      }
    } catch (error) {
      showMessage(error.message);
    }
    await refreshStatus();
  })();
  setInterval(refreshStatus, 1000);
})();
