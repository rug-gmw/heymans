const app = Vue.createApp({
  data() {
    return {
      docList: [],
      docSelected: null,
      docName: '',
      docChunkCount: 0,
      docChunks: [],
      openChunks: new Set(),
      editingDocName: false,
      docNameDraft: "",  // temporary value while editing
      docPublic: false,  // for slider
    };
  },
  created() {
    this.fetchDocList();
  },

  methods: {
    // gets the document list. Also select the last one in the list.
    async fetchDocList() {
      // pull list from db, and parse json:
      // Here, never go for include_public (therefore: list/0);
      const response = await fetch('/api/documents/list/0');
      this.docList = await response.json();

      // Unlike quizzes, we do not select a document by default.
    },

    async showDoc(document_id, show_loading = false) {

      let overlayStart = null;

      if (show_loading) {
        overlayStart = Date.now();
        this.showSpinnerOverlay("Loading document...");
      }

      try {
        this.docSelected = document_id;

        const response = await fetch(`/api/documents/get/${document_id}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch document. Status: ${response.status}`);
        }

        const doc = await response.json();

        // Give metadata to vue
        this.docName = doc.name || "(Unnamed Document)";
        this.docPublic = !!doc.public;

        // Chunks
        this.docChunks = doc.chunks || [];
        this.docChunkCount = this.docChunks.length;

        // Collapse all initially
        this.openChunks = new Set();

        // Ensure spinner visible at least 500ms
        if (show_loading) {
          const elapsed = Date.now() - overlayStart;
          const remaining = Math.max(0, 500 - elapsed);
          setTimeout(() => this.closeOverlay(), remaining);
        }

      } catch (err) {
        console.error("Error loading document:", err);

        // Immediately replace spinner with error overlay
        this.showErrorOverlay("Failed to load document", err.message);
      }
    },

    // update set of open/closed chunk-views:
    toggleChunk(index) {
      if (this.openChunks.has(index)) {
        this.openChunks.delete(index);
      } else {
        this.openChunks.add(index);
      }

      // Force Vue reactivity because Set is not deeply reactive
      this.openChunks = new Set(this.openChunks);
    },



    // upload doc data:
    createNewDoc() {
      this.$refs.fileInput.click();
    },

    // Deleting a document
    async deleteDoc() {
      const doc_id = this.docSelected;

      try {
        const response = await fetch(`/api/documents/delete/${doc_id}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          console.log(`Document ${doc_id} successfully deleted.`);
        } else if (response.status === 404) {
          console.warn(`Document ${doc_id} not found.`);
        } else {
          throw new Error(`Unexpected status code: ${response.status}`);
        }

        // Refresh document list
        await this.fetchDocList();

        // Optionally reset selection
        this.docSelected = null;

      } catch (error) {
        console.error(`Error deleting document ${doc_id}:`, error);
        this.showErrorOverlay("Failed to delete document", error.message);
      }
    },

    async uploadDocument(event) {
      const file = event.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      // Optional: add extra JSON metadata
      const metadata = {
        public: false,         // Can always update this later
        name: file.name       // or some user input instead
      };
      // formData.append("json", new Blob([JSON.stringify(metadata)], { type: "application/json" }));
      formData.append("json", JSON.stringify(metadata));

      try {
        const response = await fetch("/api/documents/add", {
          method: "POST",
          body: formData
        });

        if (!response.ok) throw new Error(`Upload failed: ${response.statusText}`);

        const result = await response.json();
        console.log("Uploaded successfully:", result);
        // Optionally refresh list of documents here

      } catch (err) {
        console.error("Upload error:", err);
        this.showErrorOverlay("Document upload failed", err.message);
      }

      // update the List
      await this.fetchDocList();
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
          throw new Error(`Failed to rename. Status: ${response.status}`);
        }

        this.docName = trimmedName;

        // Update name in docList
        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) doc.name = trimmedName;

      } catch (err) {
        console.error("Error renaming document:", err);
        this.showErrorOverlay("Error renaming document", err.message);
      }
    },

    // change doc public/private:
    async updateDocPublic() {
      try {
        const response = await fetch(`/api/documents/update/${this.docSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ public: this.docPublic }),
        });

        if (!response.ok) {
          throw new Error(`Failed to update status. Status: ${response.status}`);
        }

        // Update local docList
        const doc = this.docList.find(d => d.document_id === this.docSelected);
        if (doc) doc.public = this.docPublic;

      } catch (err) {
        this.showErrorOverlay("Failed to update document", err.message);
        this.docPublic = !this.docPublic; // revert toggle
      }
    },

    // (user) Error notification:
    showErrorOverlay(primaryMessage, secondaryMessage = '') {
      // show the overlay:
      document.getElementById('overlay').style.display = 'flex';
      // show icon 
      document.getElementById('overlay-icon').style.display = 'block';
      // don't show spinner:
      document.getElementById('overlay-spinner').style.display = 'none';
      

      console.log(document.getElementById('overlay').innerHTML);
      // buttons
      const closeBtn = document.getElementById('overlay-close-btn');
      document.getElementById('overlay-confirm-btn').style.display = 'none';
      closeBtn.style.display = 'inline-block'
      closeBtn.onclick = this.closeOverlay;
      closeBtn.innerText = "Close"

      const msg = document.getElementById('overlay-msg');
      msg.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;
    },

    showSpinnerOverlay(loadingMessage = "Loading...") {
      // Show overlay
      document.getElementById('overlay').style.display = 'flex';

      // Hide icon, show spinner
      document.getElementById('overlay-icon').style.display = 'none';
      document.getElementById('overlay-spinner').style.display = 'block';

      // Set loading message
      const msg = document.getElementById('overlay-msg');
      msg.innerHTML = `<i>${loadingMessage}</i>`;

      // Hide all buttons
      document.getElementById('overlay-close-btn').style.display = 'none';
      document.getElementById('overlay-confirm-btn').style.display = 'none';
    },

    showConfirmationOverlay(primaryMessage, secondaryMessage = '', confirmCallback) {
      // Show overlay
      document.getElementById('overlay').style.display = 'flex';

      // Hide the ⚠️ icon and spinner
      document.getElementById('overlay-icon').style.display = 'none';
      document.getElementById('overlay-spinner').style.display = 'none';

      // Update the message
      const msg = document.getElementById('overlay-msg');
      msg.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;

      // Show Confirm button
      const confirmBtn = document.getElementById('overlay-confirm-btn');
      confirmBtn.style.display = 'inline-block';
      confirmBtn.innerText = "Confirm";
      confirmBtn.onclick = () => {
        this.closeOverlay();
        confirmCallback();  // Trigger user-passed callback
      };

      // Show Close button
      const closeBtn = document.getElementById('overlay-close-btn');
      closeBtn.style.display = 'inline-block';
      closeBtn.innerText = "Cancel";
      closeBtn.onclick = this.closeOverlay;
    },

    closeOverlay(){
      const overlay = document.getElementById('overlay');
      overlay.style.display = 'none';
    }, 

  },

  computed: {
    fallbackMessage() {
      if (!this.docList || this.docList.length === 0) {
        return "You currently have no documents. Click 'Create new' on the left to upload new materials.";
      }

      if (!this.docSelected) {
        return "Select a document to view its contents, or click 'Create new'  on the left to upload new materials.";
      }

      return "";
    }
  }

});

app.mount('#app');