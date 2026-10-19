(function () {
  // =========================================================
  // Plain shared helpers
  // =========================================================

  function getOverlayEls() {
    return {
      overlay: document.getElementById('overlay'),
      content: document.querySelector('#overlay .overlay-content'),
      icon: document.getElementById('overlay-icon'),
      spinner: document.getElementById('overlay-spinner'),
      msg: document.getElementById('overlay-msg'),
      confirmBtn: document.getElementById('overlay-confirm-btn'),
      closeBtn: document.getElementById('overlay-close-btn'),
    };
  }

  window.copyTextToClipboard = async function (text) {
    if (!text) return false;

    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.error('Failed to copy text:', err);
      return false;
    }
  };

  window.downloadFile = async function ({
    endpoint,
    filename,
    mimeType,
    isBinary = false,
    method = 'GET',
    body = null,
  }) {
    try {
      const response = await fetch(endpoint, {
        method: method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : null,
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const error = new Error(data?.error || `Download failed with status ${response.status}`);
        error.status = response.status;
        throw error;
      }

      const blob = isBinary
        ? await response.blob()
        : new Blob([(await response.json()).content], { type: mimeType });

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(`Error downloading from ${endpoint}:`, err);
      throw err;
    }
  };

  // =========================================================
  // Shared Vue methods
  // These become available as this.someMethod(...)
  // inside page scripts that use withCommonVueMethods(...)
  // =========================================================

  window.commonVueMethods = {
    showErrorOverlay(primaryMessage, secondaryMessage = '') {
      const { overlay, content, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      content?.classList.remove('detailed');
      icon.style.display = 'block';
      spinner.style.display = 'none';

      confirmBtn.style.display = 'none';
      closeBtn.style.display = 'inline-block';
      closeBtn.innerText = 'Close';
      closeBtn.onclick = () => this.closeOverlay();

      msg.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;
    },

    showDetailedErrorOverlay(primaryMessage, {
      message = '',
      hint = '',
      contextLabel = 'Context',
      context = '',
    } = {}) {
      const { overlay, content, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      content?.classList.add('detailed');
      icon.style.display = 'block';
      spinner.style.display = 'none';

      confirmBtn.style.display = 'none';
      closeBtn.style.display = 'inline-block';
      closeBtn.innerText = 'Close';
      closeBtn.onclick = () => this.closeOverlay();

      msg.innerHTML = '';

      const title = document.createElement('div');
      title.className = 'overlay-msg-title';
      title.textContent = primaryMessage;
      msg.appendChild(title);

      if (message) {
        const body = document.createElement('div');
        body.className = 'overlay-msg-body';
        body.textContent = message;
        msg.appendChild(body);
      }

      if (hint) {
        const hintEl = document.createElement('div');
        hintEl.className = 'overlay-msg-hint';
        hintEl.textContent = hint;
        msg.appendChild(hintEl);
      }

      if (context) {
        const contextWrapper = document.createElement('div');
        contextWrapper.className = 'overlay-context';

        const label = document.createElement('div');
        label.className = 'overlay-context-label';
        label.textContent = contextLabel;
        contextWrapper.appendChild(label);

        const pre = document.createElement('pre');
        pre.textContent = context;
        contextWrapper.appendChild(pre);

        msg.appendChild(contextWrapper);
      }
    },

    showSpinnerOverlay(loadingMessage = 'Loading...') {
      const { overlay, content, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      content?.classList.remove('detailed');
      icon.style.display = 'none';
      spinner.style.display = 'block';

      msg.innerHTML = `<i>${loadingMessage}</i>`;

      closeBtn.style.display = 'none';
      confirmBtn.style.display = 'none';
    },

    showConfirmationOverlay(primaryMessage, secondaryMessage = '', confirmCallback) {
      const { overlay, content, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      content?.classList.remove('detailed');
      icon.style.display = 'none';
      spinner.style.display = 'none';

      msg.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;

      confirmBtn.style.display = 'inline-block';
      confirmBtn.innerText = 'Confirm';
      confirmBtn.onclick = () => {
        this.closeOverlay();
        if (typeof confirmCallback === 'function') {
          confirmCallback();
        }
      };

      closeBtn.style.display = 'inline-block';
      closeBtn.innerText = 'Cancel';
      closeBtn.onclick = () => this.closeOverlay();
    },

    showTemporaryOverlayMessage(message, timeout = 900) {
      const { overlay, content, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      content?.classList.remove('detailed');
      icon.style.display = 'none';
      spinner.style.display = 'none';
      confirmBtn.style.display = 'none';
      closeBtn.style.display = 'none';

      msg.innerHTML = `<i>${message}</i>`;

      setTimeout(() => {
        this.closeOverlay();
      }, timeout);
    },

    closeOverlay() {
      const { overlay, content } = getOverlayEls();
      if (!overlay) return;
      overlay.style.display = 'none';
      content?.classList.remove('detailed');
    },

    triggerFileInput() {
      if (this.$refs && this.$refs.fileInput) {
        this.$refs.fileInput.click();
      }
    },

    async copyToClipboard(text, successMessage = 'Copied to clipboard') {
      const ok = await window.copyTextToClipboard(text);
      if (!ok) {
        this.showErrorOverlay('Copy failed', 'Could not copy text to clipboard.');
        return false;
      }

      this.showTemporaryOverlayMessage(successMessage);
      return true;
    },

    async downloadFile(options) {
      return window.downloadFile(options);
    },
  };

  // =========================================================
  // Shared Vue components
  // =========================================================

  window.registerCommonVueComponents = function (app) {
    app.component('md-report', {
      props: {
        content: {
          type: String,
          default: '',
        },
        copyable: {
          type: Boolean,
          default: false,
        },
        copyLabel: {
          type: String,
          default: 'Copy to clipboard',
        },
        compact: {
          type: Boolean,
          default: false,
        },
      },

      data() {
        return {
          rendered: '',
          copied: false,
        };
      },

      watch: {
        content: {
          immediate: true,
          handler(newVal) {
            const md = window.markdownit({
              breaks: true,
              linkify: true,
              html: false,
            });

            md.renderer.rules.image = function (tokens, idx) {
              const alt = tokens[idx].content || 'image';
              return `<span class="md-image-placeholder">[${alt}]</span>`;
            };

            this.rendered = md.render(newVal || '');
          },
        },
      },
      methods: {
        async copySource() {
          const ok = await window.copyTextToClipboard(this.content || '');
          if (!ok) return;

          this.copied = true;
          setTimeout(() => {
            this.copied = false;
          }, 1000);
        },
      },

      template: `
        <div class="md-report" :class="{ copyable: copyable, compact: compact }">
          <template v-if="compact">
            <div class="md-report-compact-row">
              <div class="md-report-body" v-html="rendered"></div>

              <button
                v-if="copyable"
                class="md-copy-button compact"
                type="button"
                @click="copySource"
                :title="copied ? 'Copied!' : copyLabel"
              >
                <span v-if="!copied">{{ copyLabel }}</span>
                <span v-else>✓ Copied</span>
              </button>
            </div>
          </template>

          <template v-else>
            <button
              v-if="copyable"
              class="md-copy-button"
              type="button"
              @click="copySource"
              :title="copied ? 'Copied!' : copyLabel"
            >
              <span v-if="!copied">{{ copyLabel }}</span>
              <span v-else>✓ Copied</span>
            </button>

            <div class="md-report-body" v-html="rendered"></div>
          </template>
        </div>
      `,
    });

    app.component('spinner-gap', {
      props: {
        active: {
          type: Boolean,
          default: false,
        },
      },
      template: `
        <span class="spinner-gap">
          <span v-if="active" class="spinner"></span>
        </span>
      `,
    });
  };

  // =========================================================
  // Helper to merge shared Vue methods into page methods
  // Page-specific methods override shared ones if names collide
  // =========================================================

  window.withCommonVueMethods = function (methods = {}) {
    return {
      ...window.commonVueMethods,
      ...methods,
    };
  };
})();
