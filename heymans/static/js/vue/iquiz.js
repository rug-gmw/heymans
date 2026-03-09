const app = Vue.createApp({
  data() {
    return {

      quizList: [],
      quizSelected: null,
      fullQuizData: '',

      creatingNewQuiz: false,
      documentList: [],
      showCreatePanel: true,
      showStatsPanel: false,

      createForm: {
        document_id: null,
        public: false,
      },

      quizName: 'No quizzes available',
      quizNameDraft: 'New assignment',
      editingQuizName: false,

    };
  },
  created() {
    this.fetchQuizList();
  },

  beforeUnmount() {
  },

  methods: {
    // gets the quiz list; also poll result from last quiz:
    async fetchQuizList() {
      // pull list from db, and parse json:
      const response = await fetch('/api/interactive_quizzes/list');
      this.quizList = await response.json();

      // By default, select the bottom quiz:
      this.quizSelected = this.quizList.length ? this.quizList[this.quizList.length - 1].quiz_id : null;
      if (this.quizList.length) {
        this.getFullQuiz(this.quizSelected);
      } else {
        // Empty quizlist for this user:
        this.fullQuizData = ''
        this.quizName = 'No quizzes available'
        this.quizSelected = null 
      }

    },

    async fetchDocumentList() {
      const response = await fetch('/api/documents/list/0');
      if (!response.ok) {
        throw new Error(`Error loading document list: ${response.statusText}`);
      }

      this.documentList = await response.json();
    },

    async startNewQuiz() {
      this.creatingNewQuiz = true;
      this.quizSelected = null;
      this.fullQuizData = '';
      this.showCreatePanel = true;

      this.quizName = 'New assignment';
      this.quizNameDraft = 'New assignment';
      this.editingQuizName = false;

      this.createForm = {
        document_id: null,
        public: false,
      };

      if (!this.documentList.length) {
        await this.fetchDocumentList();
      }
    },

    cancelNewQuiz() {
      this.creatingNewQuiz = false;
      this.editingQuizName = false;

      this.quizName = this.quizList.length ? 'Select an assignment' : 'No quizzes available';
      this.quizNameDraft = this.quizName;

      this.createForm = {
        document_id: null,
        public: false,
      };
    },

    async getFullQuiz(quiz_id, setSelected = true) {
      if (setSelected) {
        this.quizSelected = quiz_id;
      }

      this.creatingNewQuiz = false;

      // later:
      // const response = await fetch(`/api/interactive_quizzes/get/${quiz_id}`);
      // this.fullQuizData = await response.json();
    },

    // creating a new quiz (empty with placeholder name..)
    async createNewQuiz() {
      const trimmedName = this.quizNameDraft.trim();
      if (!trimmedName || !this.createForm.document_id) {
        return;
      }

      const response = await fetch('/api/interactive_quizzes/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: trimmedName,
          document_id: this.createForm.document_id,
          public: this.createForm.public,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || `Error: ${response.statusText}`);
      }

      const data = await response.json();

      this.creatingNewQuiz = false;
      this.editingQuizName = false;
      this.quizName = trimmedName;

      await this.fetchQuizList();

      this.quizSelected = data.quiz_id;
      await this.getFullQuiz(data.quiz_id);
    },


    // deleting a quiz
    async deleteQuiz() {
      const quiz_id = this.quizSelected;

      try {
        const response = await fetch(`/api/interactive_quizzes/delete/${quiz_id}`, {
          method: 'DELETE'
        });

        if (response.status === 204) {
          console.log(`Quiz ${quiz_id} successfully deleted.`);
        } else if (response.status === 404) {
          console.warn(`Quiz ${quiz_id} not deleted: not found.`);
        } else {
          throw new Error(`Unexpected status code: ${response.status}`);
        }

        // Refresh quiz list and auto-select latest quiz if any
        await this.fetchQuizList();

      } catch (error) {
        console.error(`Error deleting Quiz ${quiz_id}`, error);
        this.showErrorOverlay("Error deleting quiz", `${error.message}`);
      }

      //select another quiz than the one that just got deleted:
      await this.fetchQuizList();

    },

    startEditingQuizName() {
      this.quizNameDraft = this.quizName;
      this.editingQuizName = true;
    },

    stopEditingQuizName() {
      this.editingQuizName = false;
      const trimmedName = this.quizNameDraft.trim();
      if (!trimmedName) {
        this.quizNameDraft = this.quizName;
        return;
      }
      this.quizName = trimmedName;
    },

    generateQuizReport(quiz) {

    },

    // export scores, to a format Brightspace likes
    async exportScores(){

    },
    

    // 'generic' Download function:
    async downloadFile({ endpoint, filename, mimeType, isBinary = false, method = "GET", body = null }) {
      try {
        const response = await fetch(endpoint, {
          method: method,
          headers: body ? { "Content-Type": "application/json" } : {},
          body: body ? JSON.stringify(body) : null
        });

        if (!response.ok) {
          throw new Error(`Download failed with status ${response.status}`);
        }

        const blob = isBinary
          ? await response.blob()
          : new Blob([(await response.json()).content], { type: mimeType });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", filename);

        document.body.appendChild(link);
        link.click();

        document.body.removeChild(link);
        URL.revokeObjectURL(url);

      } catch (err) {
        console.error(`Error downloading from ${endpoint}:`, err);
        throw err; // caller should handle overlay or UI errors
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

    triggerFileInput() {
      this.$refs.fileInput.click();
    },
  },
  computed: {
    quizStatusMessage() {
      if (this.creatingNewQuiz) {
        return 'Select a source document and create the assignment';
      }
      if (this.quizSelected) {
        return 'Interactive quiz selected';
      }
      return 'No quiz selected';
    },

    // state - based activation of cards:
    cardActiveCreate(){
      // always:
      return true
    }

  }
});

// markdown renderer:
app.component('markdown-renderer', {
  props: ['content'],
  data() {
    return {
      rendered: ''
    };
  },
  watch: {
    content: {
      immediate: true, // render on first mount too
      handler(newVal) {
        const md = window.markdownit();
        this.rendered = md.render(newVal || '');
      }
    }
  },
  template: `<div class="markdown-rendered" v-html="rendered"></div>`
});

// Spinner Placeholder Component
app.component('spinner-gap', {
  props: {
    active: { type: Boolean, default: false }
  },
  template: `
    <span class="spinner-gap">
      <span v-if="active" class="spinner"></span>
    </span>
  `
});


app.mount('#app');