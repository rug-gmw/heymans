const app = Vue.createApp({
  data() {
    return {
      quizList: [],
      quizSelected: null,
      fullQuizData: '',
      quizName: '',
      quizState: '',
      quizLen: 0,
      showCreatePanel: true,
      showGradePanel: false,
      showAnalyzePanel: false,

      pollValidationInterval: null,
      pollGradingInterval: null,

      validationStatus: '',
      validationReport: null,

      gradingStatus: '',
      gradingReport: null,
      analysisReport: null,

      spinValidate: false,
      spinGrade   : false,
      spinExportQuiz: false,
      spinExportScores: false,
      spinExportFeedback: false,
      spinExportItemAnalysis: false,
    };
  },
  created() {
    this.fetchQuizList();
  },

  beforeUnmount() {
    if (this.pollGradingInterval) clearInterval(this.pollGradingInterval);
    if (this.pollValidationInterval) clearInterval(this.pollValidationInterval);
  },

  methods: {
    // gets the quiz list; also poll result from last quiz:
    async fetchQuizList() {
      // pull list from db, and parse json:
      const response = await fetch('/api/quizzes/list');
      this.quizList = await response.json();

      // By default, select the bottom quiz:
      this.quizSelected = this.quizList.length ? this.quizList[this.quizList.length - 1].quiz_id : null;
      if (this.quizList.length) {
        this.getFullQuiz(this.quizSelected);
      } else {
        // Empty quizlist for this user:
        this.fullQuizData = ''
        this.quizName = 'No quizzes available'
        this.quizState = ''
        this.quizSelected = null 
      }
    },

    async getFullQuiz(quiz_id, show_loading = false) {
      let overlayStart = null;
      if (show_loading) {
        overlayStart = Date.now();
        this.showSpinnerOverlay("Loading quiz...");
      }

      try {
        // Clear polling
        if (this.pollValidationInterval) {
          clearInterval(this.pollValidationInterval);
          this.pollValidationInterval = null;
        }
        if (this.pollGradingInterval) {
          clearInterval(this.pollGradingInterval);
          this.pollGradingInterval = null;
        }

        this.quizSelected = quiz_id;
        await this.getQuizState(quiz_id);

        this.showCreatePanel = false;
        this.showGradePanel = false;
        this.showAnalyzePanel = false;
        this.gradingReport = null;

        switch (this.quizState) {
          case 'empty':
            this.showCreatePanel = true;
            break;
          case 'has_questions':
            this.showCreatePanel = true;
            this.showGradePanel = true;
            break;
          case 'has_attempts':
            this.showGradePanel = true;
            break;
          case 'has_scores':
            this.showGradePanel = true;
            this.showAnalyzePanel = true;
            break;
        }

        if (this.quizState !== 'empty') {
          this.validationStatus = '';
          this.gradingStatus = '';
          await this.pollValidationStatus();
          await this.pollGradingStatus();
          await this.getQuizState(quiz_id);
        } else {
          this.validationStatus = 'needs_validation';
        }

        const response = await fetch(`/api/quizzes/get/${quiz_id}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch quiz. Status: ${response.status}`);
        }

        const quizData = await response.json();
        this.fullQuizData = JSON.stringify(quizData, null, 2);
        this.quizName = quizData.name || '(Unnamed Quiz)';
        this.quizLen = Array.isArray(quizData.questions)
          ? quizData.questions.length
          : 0;

        this.validationReport = null;
        this.analysisReport = null;

        this.$nextTick(() => {
          setTimeout(() => {
            this.validationReport = quizData.validation || null;
            this.analysisReport = quizData.qualitative_error_analysis || null;
            this.generateGradingReport(quizData);
          }, 0);
        });

        // Ensure loading-spinner stays visible for at least 500ms
        if (show_loading) {
          const elapsed = Date.now() - overlayStart;
          const remaining = Math.max(0, 500 - elapsed);
          setTimeout(() => this.closeOverlay(), remaining);
        }

      } catch (err) {
        this.showErrorOverlay("Failed to load quiz", err.message);
      }
    },


    // Get the lifecycle state from the server:
    async getQuizState(quiz_id) {
      try {
        const response = await fetch(`/api/quizzes/state/${quiz_id}`);
        if (!response.ok) {
          throw new Error(`Failed to get quiz state; Status: ${response.status}`);
        }

        const data = await response.json();
        this.quizState = data.state;
      } catch (error) {
        console.error("Error polling state:", error);
        this.quizState = '(Error)';
      }
    },

    // creating a new quiz (empty with placeholder name..)
    async createNewQuiz() {
      // POST to make new quiz:
      const newQuizName = `New Quiz ${this.quizList.length + 1}`;
      const response = await fetch('/api/quizzes/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: newQuizName }),
      });

      // Check if the response is not ok
      ok = response.ok
      if (!ok) {
        // Throw an error with the response status text
        throw new Error(`Error: ${response.statusText}`);
      }      
      // // Otherwise: pull result, refresh the list
      const data = await response.json();
      await this.fetchQuizList();
      // fetchQuizList sets focus to the last (new) quiz
    },

    // deleting a quiz
    async deleteQuiz() {
      const quiz_id = this.quizSelected;

      try {
        const response = await fetch(`/api/quizzes/grading/delete/${quiz_id}`, {
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
    },

    // Upload quiz data:
    async uploadQuiz(event) {
      const file = event.target.files[0];
      if (!file) {
        console.warn("No file selected.");
        return;
      }

      const reader = new FileReader();
      reader.onload = async () => {
        const markdownContent = reader.result;

        // now handle the upload:
        try {
          const response = await fetch(`/api/quizzes/add/questions/${this.quizSelected}`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ questions: markdownContent }),
          });

          // handle different errors for add/questions?
          if (!response.ok) {
            throw new Error(`Upload failed with status ${response.status}`);
          }

          const result = await response.json();

          // update everything in view:
          // fetch quiz list then re-focus:
          const quiz_id = this.quizSelected;
          await this.fetchQuizList();
          this.quizSelected = quiz_id;
          await this.getFullQuiz(this.quizSelected);
          await this.getQuizState(this.quizSelected);
          // validation report cleared for this quiz:
          this.validationReport = null
          this.analysisReport = null
        } catch (err) {
          console.error("Error uploading quiz:", err);
          this.showErrorOverlay(`Upload failed`, `${err.message}`);
        }

      };

      // Actually read the file:
      reader.readAsText(file);
    },

    // kick off validation:
    async validateQuiz() {
      // clear old report from view:
      this.$nextTick(() => {
        setTimeout(() => {
          this.validationReport = null;
          this.analysisReport = null;
        }, 0);
      });

      try {
        const response = await fetch(`/api/quizzes/validation/start/${this.quizSelected}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ }),
        });

        if (!response.ok) {
          throw new Error(`Validation failed: ${response.status}`);
        }

        const result = await response.json();
        console.log("Validation started:", result);

        // Start polling immediately
        await this.pollValidationStatus();

      } catch (error) {
        console.error("Error during validation:", error);
      }
    },

    async pollValidationStatus(startInterval = true) {
      old_status = this.validationStatus
      try {
        const response = await fetch(`/api/quizzes/validation/poll/${this.quizSelected}`);
        if (!response.ok) throw new Error("Failed to fetch validation status");

        const data = await response.json();
        this.validationStatus = data["state"];
        if (startInterval && this.validationStatus === "validation_in_progress" && !this.pollValidationInterval) {
          this.pollValidationInterval = setInterval(() => {
            this.pollValidationStatus(false);
          }, 5000); // 5 seconds
        }

        if (this.validationStatus !== "validation_in_progress" && this.pollValidationInterval) {
          clearInterval(this.pollValidationInterval);
          this.pollValidationInterval = null;
        }
        // if the status has changed, (re)load the full quiz data
        if (old_status && (this.validationStatus != old_status)){
          this.getFullQuiz(this.quizSelected)
        } 

      } catch (err) {
        console.error("Validation polling error:", err);
        this.validationStatus = "error";
      }
    },

    // export quiz to a format Brightspace likes
    async exportQuiz() {
      const safeName = (this.quizName || "quiz").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/brightspace/${this.quizSelected}`,
          filename: `${safeName}.csv`,
          mimeType: "text/csv;charset=utf-8"
        });
      } catch (err) {
        this.showErrorOverlay("Export failed", err.message);
      }
    },

    // afer the exam, upload the events file:
    async uploadAttempts(event) {
      const file = event.target.files[0];
      if (!file) {
        console.warn("No file selected.");
        return;
      }

      const reader = new FileReader();

      reader.onload = async () => {
        const csvContent = reader.result;

        try {
          const response = await fetch(`/api/quizzes/add/attempts/${this.quizSelected}`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            
            body: JSON.stringify({ attempts: csvContent, format: "brightspace" }),
          });

          // TODO check for different statuses?
          if (!response.ok) {
            throw new Error(`Upload failed with status ${response.status}`);
          }

          const result = await response.json();
          console.log("Attempts upload successful:", result);

          // Refresh UI: quiz state likely changed
          await this.getQuizState(this.quizSelected);
          await this.getFullQuiz(this.quizSelected);

        } catch (err) {
          console.error("Error uploading attempts:", err);
          this.showErrorOverlay(`Upload failed`, `${err.message}`);
        }
      };

      reader.readAsText(file);
    },

    // Kick off grading
    async gradeQuiz() {
      // clear old report from view:
      this.$nextTick(() => {
        setTimeout(() => {
          this.analysisReport = null;
        }, 0);
      });
      try {
        const response = await fetch(`/api/quizzes/grading/start/${this.quizSelected}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });

        if (!response.ok) {
          throw new Error(`Grading failed: ${response.status}`);
        }

        const result = await response.json();
        console.log("Grading started:", result);

        await this.pollGradingStatus();

      } catch (error) {
        console.error("Error during grading:", error);
        this.showErrorOverlay("Grading error", error.message);
      }
    },

    async pollGradingStatus(startInterval = true) {
      old_status = this.gradingStatus
      try {
        const response = await fetch(`/api/quizzes/grading/poll/${this.quizSelected}`);
        if (!response.ok) throw new Error("Failed to fetch grading status");

        const data = await response.json();
        this.gradingStatus = data["state"];

        const isInProgress = ["grading_in_progress", "grading_needs_commit"].includes(this.gradingStatus);

        if (startInterval && isInProgress && !this.pollGradingInterval) {
          this.pollGradingInterval = setInterval(() => {
            this.pollGradingStatus(false);
          }, 5000); // 5 seconds
        }

        if (!isInProgress && this.pollGradingInterval) {
          clearInterval(this.pollGradingInterval);
          this.pollGradingInterval = null;
        }

        // if the status has changed, (re)load the full quiz data
        if (old_status && (this.validationStatus != old_status)){
          this.getFullQuiz(this.quizSelected)
        } 

      } catch (err) {
        console.error("Grading polling error:", err);
        this.gradingStatus = "error";
      }
    },

    generateGradingReport(quiz) {
      if (!quiz.questions) return;
      if(!(this.quizState=='has_scores')) return;

      let table = `| Question | Username | Score |\n`;
      table += `|----------|----------|-------|\n`;

      for (const question of quiz.questions) {
        for (const attempt of question.attempts || []) {
          table += `| ${question.name} | ${attempt.username} | ${attempt.score ?? '-'} |\n`;
        }
      }
      this.gradingReport = table;
    },

    // export scores, to a format Brightspace likes
    async exportScores(){
      this.spinExportScores = true;

      const safeName = (this.quizName || "scores").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/grades/${this.quizSelected}`,
          filename: `${this.quizName || "quiz"}_grades.csv`,
          mimeType: "text/csv;charset=utf-8",
          method: "POST",
          body: {
            normalize_scores: true,
            grading_formula: "ug_bss"
          }
        });
      } catch (err) {
        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportScores = false;
      }
    },
    
    async exportItemAnalysis(){
      this.spinExportItemAnalysis = true;

      const safeName = (this.quizName || "item_analysis").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/difficulty_and_discrimination/${this.quizSelected}`,
          filename: `${this.quizName || "quiz"}_item_analysis.csv`,
          mimeType: "text/csv;charset=utf-8",
          method: "GET",
        });
      } catch (err) {
        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportItemAnalysis = false;
      }
    },

    async exportAnalysis(){
      this.spinExportFeedback = true;

      const safeName = (this.quizName || "feedback").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/feedback/${this.quizSelected}`,
          filename: `${this.quizName || "quiz"}_feedback.zip`,
          mimeType: "application/zip",
          method: "POST",
          body: {
            normalize_scores: true,
            grading_formula: "ug_bss"
          },
          isBinary: true
        });
      } catch (err) {
        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportFeedback = false;
      }
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

    // upload event handling:
    checkBeforeQuizUpload() {
      if (this.quizState !== 'empty') {
        this.showConfirmationOverlay(
          "Are you sure?",
          "Uploading a new quiz will delete current questions and attempts. Continue?",
          () => this.triggerFileInput()
        );
      } else {
        this.triggerFileInput();
      }
    },

    triggerFileInput() {
      this.$refs.fileInput.click();
    },

    checkBeforeAttemptsUpload() {
      if (this.quizState === 'has_attempts' || this.quizState === 'has_scores') {
        this.showConfirmationOverlay(
          "Are you sure?",
          "Uploading new attempts will overwrite existing ones. Continue?",
          () => this.triggerAttemptsInput()
        );
      } else {
        this.triggerAttemptsInput();
      }
    },

    triggerAttemptsInput() {
      this.$refs.attemptsInput.click();
    },
  },

  computed: {
    quizStateLabel() {
      const labels = {
        empty: "This quiz is empty. Upload a quiz file to get started.",
        has_questions: "Questions have been uploaded. Validate (recommended) before administering quiz.",
        has_attempts: "Attempts have been uploaded. Ready to grade this quiz!",
        has_scores: "Grading is complete. Look at scores & analyses next."
      };
      return labels[this.quizState] || "You have no quizzes to show. Create one on the left to get started.";
    },

    validationMessage() {
      const label = {
        needs_validation: "Quiz has not yet been validated.",
        validation_in_progress: "Heymans is currently validating this quiz...",
        validation_done: "Validation done! Qualitative evaluation of questions and answer keys shown below.",
      };
      return label[this.validationStatus] || "Retrieving validation status, please wait ...";
    },

    gradingMessage() {
      const label = {
        needs_grading: "Grading has not started.",
        grading_in_progress: "Heymans is currently grading this quiz....",
        grading_error: "Heymans encountered some errors during grading! Results are probably incomplete. My suggestion is to restart grading.",
        grading_needs_commit: "Nearly done grading...",
        grading_done: "Grading done! Qualitative evaluation of incorrect responses shown below.",
      };
      return label[this.gradingStatus] || "Retrieving grading status...";
    },


    // state - based activation of cards:
    cardActiveCreate(){
      // always:
      return true
    },
    cardActiveGrade(){
      // after questions have been uploaded (quiz not empty)
      // it's active; validation not required, just recommended
      if (this.quizState == 'empty'){
        return false
      }
      return true
    },
    cardActiveAnalyze(){
      if (this.quizState == 'has_scores'){
        return true
      }
      return false
    },

    // state-based activation of buttons:
    //upload quiz:
    buttonActiveUpload(){
      // don't do anything if status is unknown
      if (!this.validationStatus){
        return false
      }
      // don't re-do upload if there are (ungraded) attempts.
      // if (this.quizState == 'has_attempts'){
      //   return false
      // }
      // don't do anything if validation is running
      if (this.validationStatus == 'validation_in_progress' ){
        return false
      }

      return true
    },

    // validate quiz:
    buttonActiveValidate(){
      // don't do anything new if status is unknown:
      if (!this.validationStatus){
        return false
      }

      // don't validate if there are no questions:
      if (this.quizState != 'has_questions'){
        return false
      }
      // don't do anything if validation is running
      if (this.validationStatus == 'validation_in_progress' ){
        return false
      }

      return true
    },

    // Upload attempts:
    buttonActiveAttempts(){
      // don't do anything new if status is unknown:
      if (!this.gradingStatus){
        return false
      } 
      // only if there is a quizState:
      if (this.quizState == 'empty'){
        return false
      }
      // and grading isn't  in progress (/needs_commit)
      if (this.gradingStatus == 'grading_in_progress'){
        return false
      }
      if (this.gradingStatus == 'grading_needs_commit'){
        return false
      }
      return true
    },

    // grade quiz:
    buttonActiveGrade(){
      // don't do anything new if status is unknown:
      if (!this.gradingStatus){
        return false
      } 

      // only 'has_attemps' (ungraded) allows for grading:
      if (this.quizState != 'has_attempts'){
        return false
      }
      // if currently grading, don't start a new process
      if (this.gradingStatus == 'grading_in_progress' ){
        return false
      }
      return true
    },
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