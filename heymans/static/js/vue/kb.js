const app = Vue.createApp({
  data() {
    return {
      docList: [],
      docSelected: null,

      docName: '',
      docNameDraft: '',
      editingDocName: false,
      docPublic: false,

      docChunks: [],
      openChunks: new Set(),

      fallbackMessage: 'No document selected.',
    };
  },

  created() {
    this.fetchDocList();
  },

  methods: window.withCommonVueMethods({
    async fetchDocList() {
      const response = await fetch('/api/documents/list/0');
      if (!response.ok) {
        throw new Error(`Failed to load documents. Status: ${response.status}`);
      }

      this.docList = await response.json();

      if (this.docList.length) {
        this.docSelected = this.docList[this.docList.length - 1].document_id;
        await this.showDoc(this.docSelected, false);
      } else {
        this.docSelected = null;
        this.docName = '';
        this.docNameDraft = '';
        this.docPublic = false;
        this.docChunks = [];
        this.openChunks = new Set();
        this.fallbackMessage = 'No documents available yet. Create one to get started.';
      }
    },

    async showDoc(document_id, showLoading = false) {
      if (!document_id) return;

      let overlayStart = null;
      if (showLoading) {
        overlayStart = Date.now();
        this.showSpinnerOverlay('Loading document...');
      }

      try {
        this.docSelected = document_id;

        const response = await fetch(`/api/documents/get/${document_id}`);
        if (!response.ok) {
          throw new Error(`Failed to load document. Status: ${response.status}`);
        }

        const docData = await response.json();

        this.docName = docData.name || '(Untitled document)';
        this.docNameDraft = this.docName;
        this.docPublic = !!docData.public;
        this.docChunks = Array.isArray(docData.chunks) ? docData.chunks : [];

        this.openChunks = new Set();
        if (this.docChunks.length > 0) {
          this.openChunks.add(0);
        }
      } catch (err) {
        console.error('Error loading document:', err);
        this.showErrorOverlay('Error loading document', err.message);
      } finally {
        if (showLoading && overlayStart) {
          const elapsed = Date.now() - overlayStart;
          const minVisible = 300;
          const remaining = Math.max(0, minVisible - elapsed);

          setTimeout(() => {
            this.closeOverlay();
          }, remaining);
        }
      }
    },

    createNewDoc() {
      this.triggerFileInput();
    },

    async uploadDocument(event) {
      const file = event.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      this.showSpinnerOverlay('Uploading document...');

      try {
        const response = await fetch('/api/documents/new', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`Failed to upload document. Status: ${response.status}`);
        }

        const data = await response.json();

        await this.fetchDocList();

        if (data.document_id) {
          await this.showDoc(data.document_id, false);
        }
      } catch (err) {
        console.error('Error uploading document:', err);
        this.showErrorOverlay('Failed to upload document', err.message);
      } finally {
        this.closeOverlay();
        if (this.$refs && this.$refs.fileInput) {
          this.$refs.fileInput.value = '';
        }
      }
    },

    startEditingDocName() {
      this.docNameDraft = this.docName;
      this.editingDocName = true;
    },

    async saveDocName() {
      this.editingDocName = false;
      const trimmedName = this.docNameDraft.trim();

      if (!trimmedName || trimmedName === this.docName) return;

      try {
        const response = await fetch(`/api/documents/update/${this.docSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName }),
        });

        if (!response.ok) {
          throw new Error(`Failed to rename document. Status: ${response.status}`);
        }

        this.docName = trimmedName;

        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) {
          doc.name = trimmedName;
        }
      } catch (err) {
        console.error('Error renaming document:', err);
        this.showErrorOverlay('Error renaming document', err.message);
      }
    },

    async updateDocPublic() {
      try {
        const response = await fetch(`/api/documents/update/${this.docSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ public: this.docPublic }),
        });

        if (!response.ok) {
          throw new Error(`Failed to update document status. Status: ${response.status}`);
        }

        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) {
          doc.public = this.docPublic;
        }
      } catch (err) {
        console.error('Error updating document public/private status:', err);
        this.showErrorOverlay('Failed to update document', err.message);
        this.docPublic = !this.docPublic;
      }
    },

    toggleChunk(index) {
      const updated = new Set(this.openChunks);

      if (updated.has(index)) {
        updated.delete(index);
      } else {
        updated.add(index);
      }

      this.openChunks = updated;
    },

    deleteDoc() {
      if (!this.docSelected) return;

      this.showConfirmationOverlay(
        'Delete this document?',
        'This will permanently remove the document, but also any linked assignments!',
        async () => {
          try {
            const deletedId = this.docSelected;

            const response = await fetch(`/api/documents/delete/${deletedId}`, {
              method: 'DELETE',
            });

            if (!response.ok) {
              throw new Error(`Failed to delete document. Status: ${response.status}`);
            }

            this.docSelected = null;
            this.docName = '';
            this.docNameDraft = '';
            this.docPublic = false;
            this.docChunks = [];
            this.openChunks = new Set();

            await this.fetchDocList();

            if (this.docList.length) {
              const fallbackDoc =
                this.docList.find(d => d.document_id !== deletedId) ||
                this.docList[this.docList.length - 1];

              if (fallbackDoc) {
                await this.showDoc(fallbackDoc.document_id, false);
              }
            }
          } catch (err) {
            console.error('Error deleting document:', err);
            this.showErrorOverlay('Failed to delete document', err.message);
          }
        }
      );
    },
  }),

  computed: {
    docChunkCount() {
      return Array.isArray(this.docChunks) ? this.docChunks.length : 0;
    },
  },
});

window.registerCommonVueComponents(app);
app.mount('#app');