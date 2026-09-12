/*
 * StandupPilot's modified Google Meet CC Capturer bridge.
 *
 * The upstream project supplies the Meet caption observation foundation (kept
 * under vendor/ at the pinned revision). This focused controller retains the
 * upstream per-speaker DOM selectors while adding StandupPilot consent,
 * stabilization, contract event construction, and background delivery.
 */
(function exposeCaptionBridge(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(
      require('../lib/contracts.js'),
      require('../lib/caption-stabilizer.js')
    );
    return;
  }
  const api = factory(root.StandupPilotContracts, root.StandupPilotCaptionStabilizer);
  root.StandupPilotCaptionBridge = api;
  if (root.chrome?.runtime && root.document) {
    const controller = new api.CaptionBridgeController();
    controller.mount();
    root.standupPilotCaptionBridge = controller;
  }
})(typeof globalThis === 'object' ? globalThis : this, function createCaptionBridge(contracts, stabilizerModule) {
  'use strict';

  if (!contracts || !stabilizerModule) throw new Error('StandupPilot caption bridge dependencies are missing');

  const { CaptionStabilizer, extractCaptionItems } = stabilizerModule;
  const MESSAGE_TYPES = Object.freeze({
    SAVE_CONFIG: 'SP_SAVE_CONFIG',
    GET_CONFIG: 'SP_GET_CONFIG',
    GET_STATUS: 'SP_GET_STATUS',
    START_FORWARDING: 'SP_START_FORWARDING',
    STOP_FORWARDING: 'SP_STOP_FORWARDING',
    CAPTION_EVENT: 'SP_CAPTION_EVENT',
    GET_CAPTURE_STATUS: 'SP_GET_CAPTURE_STATUS',
    START_CAPTURE: 'SP_START_CAPTURE',
    STOP_CAPTURE: 'SP_STOP_CAPTURE',
    DELIVERY_STATUS: 'SP_DELIVERY_STATUS'
  });
  const DELIVERY_STATUSES = new Set(['connected', 'retrying', 'disconnected']);

  function runtimeApi(value) {
    return value || (typeof chrome === 'object' ? chrome : null);
  }

  class CaptionBridgeController {
    constructor({
      chromeApi = runtimeApi(),
      documentApi = typeof document === 'object' ? document : null,
      mutationObserver = typeof MutationObserver === 'function' ? MutationObserver : null,
      stabilizationMs = 900,
      render = true
    } = {}) {
      if (!chromeApi?.runtime?.sendMessage) throw new TypeError('Chrome runtime messaging is required');
      this.chromeApi = chromeApi;
      this.documentApi = documentApi;
      this.MutationObserver = mutationObserver;
      this.stabilizationMs = stabilizationMs;
      this.renderEnabled = render;
      this.capturing = false;
      this.forwarding = false;
      this.deliveryStatus = 'disconnected';
      this.pendingCount = 0;
      this.stabilizer = null;
      this.observer = null;
      this.panel = null;
      this.pendingSends = new Set();
      this.listenerInstalled = false;
    }

    async sendMessage(message) {
      return new Promise((resolve, reject) => {
        let settled = false;
        const complete = (response) => {
          if (settled) return;
          settled = true;
          resolve(response || {});
        };
        try {
          const result = this.chromeApi.runtime.sendMessage(message, complete);
          if (result && typeof result.then === 'function') result.then(complete, reject);
        } catch (error) {
          reject(error);
        }
      });
    }

    mount() {
      if (!this.listenerInstalled && this.chromeApi.runtime.onMessage?.addListener) {
        this.chromeApi.runtime.onMessage.addListener((message) => this.handleMessage(message));
        this.listenerInstalled = true;
      }
      if (this.renderEnabled) this.render();
      return this.sendMessage({ type: MESSAGE_TYPES.GET_STATUS })
        .then((response) => {
          if (response?.ok) {
            this.forwarding = Boolean(response.forwarding);
            this.deliveryStatus = response.deliveryStatus || this.deliveryStatus;
            this.pendingCount = Number(response.pendingCount || 0);
            this.updateUi();
          }
          return this.getStatus();
        })
        .catch(() => this.getStatus());
    }

    render() {
      const documentRef = this.documentApi;
      if (!documentRef?.body || typeof documentRef.createElement !== 'function') return;
      const existing = documentRef.getElementById?.('standup-pilot-caption-bridge');
      if (existing) {
        this.panel = existing;
        return;
      }
      const panel = documentRef.createElement('section');
      panel.id = 'standup-pilot-caption-bridge';
      panel.setAttribute('aria-label', 'StandupPilot caption bridge');
      panel.innerHTML = `
        <div class="sp-bridge-header"><strong>StandupPilot</strong><span id="sp-bridge-delivery-status">Disconnected</span></div>
        <p class="sp-bridge-notice">Native Meet captions will be shared with StandupPilot. Inform everyone before capture; displayed names are context, not verified identity.</p>
        <label class="sp-bridge-consent"><input id="sp-bridge-consent" type="checkbox"> I have informed meeting participants.</label>
        <div class="sp-bridge-controls"><button id="sp-bridge-start" type="button">Start caption forwarding</button><button id="sp-bridge-stop" type="button" disabled>Stop</button></div>
        <p id="sp-bridge-message" role="status"></p>
      `;
      documentRef.body.appendChild(panel);
      this.panel = panel;
      const consent = panel.querySelector('#sp-bridge-consent');
      const start = panel.querySelector('#sp-bridge-start');
      const stop = panel.querySelector('#sp-bridge-stop');
      if (consent && start) consent.addEventListener('change', () => { start.disabled = !consent.checked; });
      if (start) start.addEventListener('click', () => {
        this.start({ consentAcknowledged: Boolean(consent?.checked) }).catch((error) => this.showMessage(error.message));
      });
      if (stop) stop.addEventListener('click', () => {
        this.stop().catch((error) => this.showMessage(error.message));
      });
      this.updateUi();
    }

    showMessage(message) {
      const element = this.panel?.querySelector('#sp-bridge-message');
      if (element) element.textContent = message;
    }

    updateUi() {
      if (!this.panel) return;
      const status = this.panel.querySelector('#sp-bridge-delivery-status');
      const start = this.panel.querySelector('#sp-bridge-start');
      const stop = this.panel.querySelector('#sp-bridge-stop');
      if (status) status.textContent = this.deliveryStatus[0].toUpperCase() + this.deliveryStatus.slice(1);
      if (start) start.disabled = this.capturing || !this.panel.querySelector('#sp-bridge-consent')?.checked;
      if (stop) stop.disabled = !this.capturing;
      this.panel.dataset.deliveryStatus = this.deliveryStatus;
    }

    findCaptionRoot() {
      return this.documentApi?.body || null;
    }

    trackSend(promise) {
      this.pendingSends.add(promise);
      promise.then((response) => {
        if (response?.ok) {
          this.deliveryStatus = response.deliveryStatus || this.deliveryStatus;
          this.pendingCount = Number(response.pendingCount || 0);
        } else if (response) {
          this.deliveryStatus = 'disconnected';
          this.showMessage(response.error || 'Caption delivery failed');
        }
        this.updateUi();
      }).catch((error) => {
        this.deliveryStatus = 'disconnected';
        this.showMessage(error.message || 'Caption delivery failed');
        this.updateUi();
      }).finally(() => this.pendingSends.delete(promise));
      return promise;
    }

    onFinalized(event) {
      if (!this.capturing) return;
      this.trackSend(this.sendMessage({ type: MESSAGE_TYPES.CAPTION_EVENT, event }));
    }

    async start({ consentAcknowledged = false } = {}) {
      if (!consentAcknowledged) throw new Error('Inform participants before starting caption capture');
      if (this.capturing) return this.getStatus();
      const response = await this.sendMessage({ type: MESSAGE_TYPES.START_FORWARDING });
      if (!response?.ok) throw new Error(response?.error || 'Unable to start caption forwarding');
      const meetingSessionId = response.config?.meetingSessionId;
      if (!meetingSessionId) throw new Error('No meeting session is configured');
      this.stabilizer = new CaptionStabilizer({
        meetingSessionId,
        stabilizationMs: this.stabilizationMs,
        onFinalized: (event) => this.onFinalized(event)
      });
      this.capturing = true;
      this.forwarding = true;
      this.deliveryStatus = response.deliveryStatus || 'disconnected';
      const root = this.findCaptionRoot();
      if (root && this.MutationObserver) {
        this.observer = new this.MutationObserver(() => this.stabilizer.processDom(root));
        this.observer.observe(root, { childList: true, subtree: true, characterData: true });
        this.stabilizer.processDom(root);
      }
      this.showMessage('Capturing finalized native captions.');
      this.updateUi();
      return this.getStatus();
    }

    async stop() {
      if (!this.capturing) return this.getStatus();
      if (this.observer) {
        this.observer.disconnect();
        this.observer = null;
      }
      this.stabilizer?.stop();
      await Promise.allSettled([...this.pendingSends]);
      const response = await this.sendMessage({ type: MESSAGE_TYPES.STOP_FORWARDING });
      this.capturing = false;
      this.forwarding = false;
      if (response?.ok) {
        this.deliveryStatus = response.deliveryStatus || this.deliveryStatus;
        this.pendingCount = Number(response.pendingCount || 0);
      }
      this.updateUi();
      return this.getStatus();
    }

    getStatus() {
      return {
        capturing: this.capturing,
        forwarding: this.forwarding,
        deliveryStatus: this.deliveryStatus,
        pendingCount: this.pendingCount
      };
    }

    async handleMessage(message) {
      if (!message) return this.getStatus();
      switch (message.type) {
        case MESSAGE_TYPES.START_CAPTURE:
          return this.start(message);
        case MESSAGE_TYPES.STOP_CAPTURE:
          return this.stop();
        case MESSAGE_TYPES.GET_CAPTURE_STATUS:
          return this.getStatus();
        case MESSAGE_TYPES.DELIVERY_STATUS:
          if (DELIVERY_STATUSES.has(message.status)) this.deliveryStatus = message.status;
          this.pendingCount = Number(message.pendingCount || 0);
          this.updateUi();
          return this.getStatus();
        default:
          return this.getStatus();
      }
    }
  }

  return Object.freeze({ CaptionBridgeController, MESSAGE_TYPES, extractCaptionItems });
});
