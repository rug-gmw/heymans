(function () {
  // -----------------------------
  // Generic clipboard helper
  // -----------------------------
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

  // -----------------------------
  // Overlay DOM helper
  // -----------------------------
  function getOverlayEls() {
    return {
      overlay: document.getElementById('overlay'),
      icon: document.getElementById('overlay-icon'),
      spinner: document.getElementById('overlay-spinner'),
      msg: document.getElementById('overlay-msg'),
      confirmBtn: document.getElementById('overlay-confirm-btn'),
      closeBtn: document.getElementById('overlay-close-btn'),
    };
  }

  // -----------------------------
  // Shared overlay methods
  // To be mixed into Vue methods
  // -----------------------------
  window.commonVueMethods = {
    showErrorOverlay(primaryMessage, secondaryMessage = '') {
      const { overlay, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      icon.style.display = 'block';
      spinner.style.display = 'none';

      confirmBtn.style.display = 'none';
      closeBtn.style.display = 'inline-block';
      closeBtn.innerText = 'Close';
      closeBtn.onclick = () => this.closeOverlay();

      msg.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;
    },

    showSpinnerOverlay(loadingMessage = 'Loading...') {
      const { overlay, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
      icon.style.display = 'none';
      spinner.style.display = 'block';

      msg.innerHTML = `<i>${loadingMessage}</i>`;

      closeBtn.style.display = 'none';
      confirmBtn.style.display = 'none';
    },

    showConfirmationOverlay(primaryMessage, secondaryMessage = '', confirmCallback) {
      const { overlay, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
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
      const { overlay, icon, spinner, msg, confirmBtn, closeBtn } = getOverlayEls();
      if (!overlay) return;

      overlay.style.display = 'flex';
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
      const { overlay } = getOverlayEls();
      if (!overlay) return;
      overlay.style.display = 'none';
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

      if (typeof this.showTemporaryOverlayMessage === 'function') {
        this.showTemporaryOverlayMessage(successMessage);
      }

      return true;
    },
  };

  // -----------------------------
  // Shared Vue components
  // -----------------------------
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
        compact: {
          type: Boolean,
          default: false,
        }
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
            });
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
        <div
          class="md-report"
          :class="{ copyable: copyable, compact: compact }"
        >
          <template v-if="compact">
            <div class="md-report-compact-row">
              <div class="md-report-body" v-html="rendered"></div>

              <button
                v-if="copyable"
                class="md-copy-button compact"
                type="button"
                @click="copySource"
                :title="copied ? 'Copied!' : 'Copy to clipboard'"
              >
                <span v-if="!copied">Copy to clipboard</span>
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
              :title="copied ? 'Copied!' : 'Copy to clipboard'"
            >
              <span v-if="!copied">Copy to clipboard</span>
              <span v-else>✓ Copied</span>
            </button>

            <div class="md-report-body" v-html="rendered"></div>
          </template>
        </div>
      `,
    });
  };

  // -----------------------------
  // Helper to merge shared methods
  // into page-specific Vue methods
  // -----------------------------
  window.withCommonVueMethods = function (methods = {}) {
    return {
      ...window.commonVueMethods,
      ...methods,
    };
  };
})();