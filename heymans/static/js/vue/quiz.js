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

      validationStatus: '',
      validationReport: null,

      gradingStatus: '',
      gradingReport: null,

    };
  },
  created() {
    this.fetchQuizList();
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

    // sets local variables, to see which quiz is selected
    async getFullQuiz(quiz_id) {
      // We get here when selection changes
      this.quizSelected = quiz_id

      try {
        const response = await fetch(`/api/quizzes/get/${quiz_id}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch quiz. Status: ${response.status}`);
        }

        const quizData = await response.json();
        // For now, to display:
        this.fullQuizData = JSON.stringify(quizData, null, 2);
        // Set quiz name and length from full data
        this.quizName = quizData.name || '(Unnamed Quiz)';
        this.quizLen = Array.isArray(quizData.questions)
          ? quizData.questions.length
          : 0;

        this.gradingReport = null
        this.validationReport = quizData.validation ? quizData.validation : null;

      } catch (error) {
        console.error("Error fetching quiz:", error);
        this.fullQuizData = `Error: ${error.message}`;
        this.quizName = `Error loading name.`;
      }

      // Setting the state may change the open/close/activate state of certain cards:
      await this.getQuizState(quiz_id);

      // Reset all panels first
      this.showCreatePanel = false;
      this.showGradePanel = false;
      this.showAnalyzePanel = false;

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
          this.generateGradingReport();
          break;
      }

      // poll status for grading + validation:
      if (this.quizState != 'empty'){
        this.validationStatus = '';
        this.gradingStatus = '';
        await this.pollValidationStatus()
        await this.pollGradingStatus()
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

    // creating a new quiz (by default, it's empty)
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
        this.showOverlay("Error deleting quiz", `${error.message}`);
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
        } catch (err) {
          console.error("Error uploading quiz:", err);
          this.showOverlay(`Upload failed`, `${err.message}`);
        }

      };

      // Actually read the file:
      reader.readAsText(file);
    },

    // kick off validation:
    async validateQuiz() {
      try {
        const response = await fetch(`/api/quizzes/validation/start/${this.quizSelected}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ model: "gpt-4.1" }),
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
        // this.showOverlay("Validation error", error.message);
      }
    },

    async pollValidationStatus() {
      try {
        const response = await fetch(`/api/quizzes/validation/poll/${this.quizSelected}`);
        if (!response.ok) throw new Error("Failed to fetch validation status");

        const data = await response.json();
        this.validationStatus = data.message; // "needs_validation", etc.
      } catch (err) {
        console.error("Validation polling error:", err);
        this.validationStatus = "error";
      }
    },

    // export quiz to a format Brightspace likes
    async exportQuiz(){
      this.showOverlay("Not implemented yet","sorry");
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
            body: JSON.stringify({ attempts: csvContent }),
          });

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
          this.showOverlay(`Upload failed`, `${err.message}`);
        }
      };

      reader.readAsText(file);
    },

    // Kick off grading
    async gradeQuiz() {
      try {
        const response = await fetch(`/api/quizzes/grading/start/${this.quizSelected}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ model: "gpt-4.1" }),
        });

        if (!response.ok) {
          throw new Error(`Grading failed: ${response.status}`);
        }

        const result = await response.json();
        console.log("Grading started:", result);

        await this.pollGradingStatus();

      } catch (error) {
        console.error("Error during grading:", error);
        this.showOverlay("Grading error", error.message);
      }
    },

    async pollGradingStatus() {
      try {
        const response = await fetch(`/api/quizzes/grading/poll/${this.quizSelected}`);
        if (!response.ok) throw new Error("Failed to fetch grading status");

        const data = await response.json();
        this.gradingStatus = data.message;  // "needs_grading", "in_progress", etc.
      } catch (err) {
        console.error("Grading polling error:", err);
        this.gradingStatus = "error";
      }
    },

    // export scored quiz to a format Brightspace likes
    async exportScores(){
      this.showOverlay("Not implemented yet","sorry");
    },

    generateGradingReport() {
      const quiz = JSON.parse(this.fullQuizData || '{}');
      if (!quiz.questions) return;

      let table = `| Question | Username | Score |\n`;
      table += `|----------|----------|-------|\n`;

      for (const question of quiz.questions) {
        for (const attempt of question.attempts || []) {
          table += `| ${question.name} | ${attempt.username} | ${attempt.score ?? '-'} |\n`;
        }
      }

      this.gradingReport = table;
    },

    // Whenever there's a user error:
    showOverlay(primaryMessage, secondaryMessage = '') {
      const overlay = document.getElementById('overlay');
      const overlayMessage = document.getElementById('overlay-message');
      overlayMessage.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;
      overlay.style.display = 'flex';
    },

    closeOverlay(){
      const overlay = document.getElementById('overlay');
      overlay.style.display = 'none';
    }, 

    // file input event handling:
    triggerFileInput() {
      this.$refs.fileInput.click();
    },

    triggerAttemptsInput() {
      this.$refs.attemptsInput.click();
    },

  },
  computed: {
    quizStateLabel() {
      const labels = {
        empty: "This quiz is empty. Upload a quiz file to add (new) questions.",
        has_questions: "Questions have been uploaded. Validate (recommended!) before administering quiz.",
        has_attempts: "Attempts have been uploaded. Ready to grade this quiz!",
        has_scores: "Grading complete! Look at scores & analyses next."
      };
      return labels[this.quizState] || "You have no quizzes to show. Create one on the left to get started.";
    },

    validationMessage() {
      const label = {
        needs_validation: "Quiz has not been validated",
        validation_in_progress: "Validation is currently running.",
        validation_done: "Validation report has been generated.",
      };
      return label[this.validationStatus] || "Validation status unknown.";
    },

    gradingMessage() {
      const label = {
        needs_grading: "Grading has not started.",
        grading_in_progress: "Heymans is grading this quiz ...",
        grading_aborted: "Grading aborted so results are incomplete. Try restarting?",
        grading_done: "Grading is done",
      };
      return label[this.gradingStatus] || "Grading status unknown.";
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

    //upload quiz:
    buttonActiveUpload(){
      if (this.quizState == 'has_attempts'){
        return false
      }
      if (this.quizState == 'has_scores'){
        return false
      }
      return true
    },

    // state-based activation of buttons:
    buttonActiveValidate(){
      if (this.quizState != 'has_questions'){
        return false
      }
      if (this.validationStatus == 'validation_in_progress' ){
        return false
      }

      return true
    },

    buttonActiveGrade(){
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
  computed: {
    renderedHtml() {
      const md = window.markdownit();
      return md.render(this.content || '');
    }
  },
  template: `<div class="markdown-rendered" v-html="renderedHtml"></div>`
});

app.mount('#app');