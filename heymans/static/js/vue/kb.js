const app = Vue.createApp({
  data() {
    return {
      docList: [],
      docSelected: null,

      docName: '',
      docNameDraft: '',     // temporary value while editing
      editingDocName: false,
      docPublic: false,     // default value, for slider

      docChunks: [],
      openChunks: new Set(),
    };
  },

  created() {
    this.fetchDocList();
  },

  methods: window.withCommonVueMethods({

    supportedDocumentExtensions() {
      return ['.docx', '.md', '.odt', '.pdf', '.txt'];
    },

    clearSelectedDoc() {
      this.docSelected = null;
      this.docName = '';
      this.docNameDraft = '';
      this.docPublic = false;
      this.docChunks = [];
      this.openChunks = new Set();
    },

    // pull list from db, and parse json:
    // Here, never go for include_public (therefore: list/0);
    async fetchDocList() {
      try {
        const response = await fetch('/api/documents/list/0');

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        this.docList = await response.json();
        // NOTE: Unlike quizzes, we do not select a document by default

      } catch (err) {
        console.error('Error loading document list:', err);
        this.showErrorOverlay(
          'Could not load list of documents',
          'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // Show some information about a selected document
    async showDoc(document_id, showLoading = false) {
      // assert that a doc id was passed
      if (!document_id) return;

      let overlayStart = null;
      if (showLoading) {
        overlayStart = Date.now();
        this.showSpinnerOverlay('Loading document...');
      }

      try {
        const response = await fetch(`/api/documents/get/${document_id}`);
        const docData = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            docData?.error || `Failed to load document. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        this.docSelected = document_id;
        this.docName = docData.name || '(Untitled document)';
        this.docNameDraft = this.docName;
        this.docPublic = !!docData.public;
        this.docChunks = Array.isArray(docData.chunks) ? docData.chunks : [];

        this.openChunks = new Set();

        // Keep spinner visible up to 300ms
        if (showLoading) {
          const elapsed = Date.now() - overlayStart;
          const remaining = Math.max(0, 300 - elapsed);
          setTimeout(() => this.closeOverlay(), remaining);
        }


      } catch (err) {
        console.error('Error loading document:', err);

        this.clearSelectedDoc();

        if (err.status === 404) {
          await this.fetchDocList();
          this.showErrorOverlay(
            'Document not found',
            'This document may have been deleted, or you may no longer have access to it.'
          );
          return;
        }

        this.showErrorOverlay('Error loading document', err.message);
      } 
      
    },

    // update set of open/closed chunk-views on chunks:
    toggleChunk(index) {
      const updated = new Set(this.openChunks);

      if (updated.has(index)) {
        updated.delete(index);
      } else {
        updated.add(index);
      }

      this.openChunks = updated;
    },

    // upload new doc data:
    createNewDoc() {
      this.triggerFileInput();
    },

    async uploadDocument(event) {
      const file = event.target.files[0];
      if (!file) return;

      const supportedExtensions = this.supportedDocumentExtensions();
      const filename = file.name || '';
      const extension = filename.includes('.')
        ? filename.slice(filename.lastIndexOf('.')).toLowerCase()
        : '';

      if (!supportedExtensions.includes(extension)) {
        this.showErrorOverlay(
          'Upload failed',
          'Please upload a .txt, .md, .docx, .odt, or .pdf file.'
        );
        event.target.value = '';
        return;
      }

      if (file.size === 0) {
        this.showErrorOverlay(
          'Upload failed',
          'The selected document appears to be empty.'
        );
        event.target.value = '';
        return;
      }

      const formData = new FormData();
      formData.append('file', file);

      // Optional: add extra JSON metadata
      const metadata = {
        public: false,         // Can always update this later
        name: file.name       // or some user input instead
      };
      // formData.append("json", new Blob([JSON.stringify(metadata)], { type: "application/json" }));
      formData.append("json", JSON.stringify(metadata));


      this.showSpinnerOverlay('Uploading document...');

      try {
        const response = await fetch('/api/documents/add', {
          method: 'POST',
          body: formData,
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to upload document. Status: ${response.status}`
          );
          error.status = response.status;
          error.data = data;
          throw error;
        }

        // get new database call, and highlight the new document
        try {
          await this.fetchDocList();
          if (data?.document_id) {
            await this.showDoc(data.document_id, false);
          }
        } catch (err) {
          console.error('Error refreshing uploaded document:', err);
          this.showErrorOverlay(
            'Document uploaded',
            'The document was uploaded, but could not be shown. Try refreshing the page.'
          );
          return;
        }
        this.closeOverlay();
      } catch (err) {
        console.error('Error uploading document:', err);
        this.showErrorOverlay(
          'Failed to upload document',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      } finally {
        if (this.$refs && this.$refs.fileInput) {
          this.$refs.fileInput.value = '';
        }
      }
    },

    startEditingDocName() {
      this.docNameDraft = this.docName;
      this.editingDocName = true;
      this.$nextTick(() => {
        this.$refs.titleInput?.focus();
        this.$refs.titleInput?.select();
      });
    },

    async saveDocName() {
      this.editingDocName = false;
      const trimmedName = this.docNameDraft.trim();

      if (!trimmedName || trimmedName === this.docName) {
        this.docNameDraft = this.docName;
        return;
      }

      if (!this.docSelected) {
        return;
      }

      try {
        const response = await fetch(`/api/documents/update/${this.docSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName }),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to rename document. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        const finalName = data?.name || trimmedName;
        this.docName = finalName;
        this.docNameDraft = finalName;

        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) {
          doc.name = finalName;
        }
      } catch (err) {
        console.error('Error renaming document:', err);
        this.docNameDraft = this.docName;

        if (err.status === 404) {
          this.clearSelectedDoc();

          this.showErrorOverlay(
            'Document not found',
            'This document may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchDocList();
          return;
        }

        this.showErrorOverlay(
          'Error renaming document',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    async updateDocPublic() {
      if (!this.docSelected) {
        return;
      }

      const requestedPublic = this.docPublic;

      try {
        const response = await fetch(`/api/documents/update/${this.docSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ public: requestedPublic }),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to update document status. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) {
          doc.public = requestedPublic;
        }
      } catch (err) {
        console.error('Error updating document public/private status:', err);
        this.docPublic = !requestedPublic;

        if (err.status === 404) {
          this.clearSelectedDoc();

          this.showErrorOverlay(
            'Document not found',
            'This document may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchDocList();
          return;
        }

        this.showErrorOverlay(
          'Failed to update document',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // Deleting a document
    deleteDoc() {
      if (!this.docSelected) return;

      this.showConfirmationOverlay(
        'Delete this document?',
        'This will permanently remove the document, but also any linked assignments!',
        async () => {
          const deletedId = this.docSelected;

          try {
            const response = await fetch(`/api/documents/delete/${deletedId}`, {
              method: 'DELETE',
            });

            if (response.ok) {
              console.log(`Document ${deletedId} successfully deleted.`);
            } else if (response.status === 404) {
              console.warn(`Document ${deletedId} was already deleted or is no longer accessible.`);
            } else {
              const data = await response.json().catch(() => null);
              throw new Error(data?.error || `Unexpected status code: ${response.status}`);
            }

            this.clearSelectedDoc();
            await this.fetchDocList();

          } catch (err) {
            console.error(`Error deleting document ${deletedId}:`, err);
            this.showErrorOverlay(
              'Failed to delete document',
              err.message || 'This might be a network issue. Try refreshing the page.'
            );
          }
        }
      );
    },
  }),

  computed: {
    docChunkCount() {
      return Array.isArray(this.docChunks) ? this.docChunks.length : 0;
    },
    fallbackMessage() {
      if (!this.docList || this.docList.length === 0) {
        return "You currently have no documents. Click 'Create new' on the left to upload new materials.";
      }

      if (!this.docSelected) {
        return "Select a document to view its contents, or click 'Create new'  on the left to upload new materials.";
      }

      return "";
    },
  },
});

window.registerCommonVueComponents(app);
app.mount('#app');
