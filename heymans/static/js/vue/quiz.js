const app = Vue.createApp({
  data() {
    return {
      quizList: [],
      quizSelected: null,
      fullQuizData: '',

      editingQuizName: false,
      quizNameDraft: '',

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

  methods: window.withCommonVueMethods({

    // gets the quiz list; also poll result from last quiz:
    async fetchQuizList() {
      try {
        const response = await fetch('/api/quizzes/list');

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        this.quizList = await response.json();

        this.quizSelected = this.quizList.length
          ? this.quizList[this.quizList.length - 1].quiz_id
          : null;

        if (this.quizSelected) {
          await this.getFullQuiz(this.quizSelected);
        } else {
          this.fullQuizData = '';
          this.quizName = 'No quizzes available';
          this.quizState = '';
          this.quizSelected = null;
        }
      } catch (err) {
        console.error('Error loading quiz list:', err);
        this.showErrorOverlay(
          'Could not load list of quizzes',
          'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // load content of the selected quiz from the database..
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

        // set other ui params to sensible defaults:
        this.quizSelected = quiz_id;
        this.quizState = '';
        this.validationStatus = '';
        this.gradingStatus = '';
        this.showCreatePanel = false;
        this.showGradePanel = false;
        this.showAnalyzePanel = false;

        // now let's assess what state the quiz is in, and 
        // (re)set parameters accordingly:
        await this.getQuizState(quiz_id); // may throw 404

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

        // if not empty, set grading/validation status:
        if (this.quizState !== 'empty') {
          await this.pollValidationStatus();
          await this.pollGradingStatus();
          await this.getQuizState(quiz_id);
        } else {
          this.validationStatus = 'needs_validation';
        }

        // we now know the statuses -- now fetch relevant quiz content:
        const response = await fetch(`/api/quizzes/get/${quiz_id}`);
        const quizData = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            quizData?.error || `Failed to fetch quiz. Status: ${response.status}`
          );
          error.status = response.status;
          throw error; // may throw 404
        }

        // set relevant content in the UI:
        this.fullQuizData = JSON.stringify(quizData, null, 2);
        this.quizName = quizData.name || '(Unnamed Quiz)';
        this.quizNameDraft = this.quizName;
        this.quizLen = Array.isArray(quizData.questions)
          ? quizData.questions.length
          : 0;

        this.validationReport = null;
        this.analysisReport = null;

        this.$nextTick(() => {
          setTimeout(() => {
            this.validationReport = quizData.validation || null;
            this.analysisReport = quizData.qualitative_error_analysis || null;
          }, 0);
        });

        // Ensure loading-spinner stays visible for at least 500ms
        if (show_loading) {
          const elapsed = Date.now() - overlayStart;
          const remaining = Math.max(0, 500 - elapsed);
          setTimeout(() => this.closeOverlay(), remaining);
        }

      } catch (err) {
        // sensible default behavior if the quiz somehow fails to load.
        console.error('Failed to load quiz:', err);
        this.quizState = 'error';
        this.validationStatus = '';
        this.gradingStatus = '';
        this.showCreatePanel = false;
        this.showGradePanel = false;
        this.showAnalyzePanel = false;

        if (err.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Failed to load quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // Get the lifecycle state from the server:
    async getQuizState(quiz_id) {
      const response = await fetch(`/api/quizzes/state/${quiz_id}`);
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const error = new Error(
          data?.error || `Failed to get quiz state. Status: ${response.status}`
        );
        error.status = response.status;
        throw error;
      }

      this.quizState = data.state;
    },

    // start creating a new quiz (empty entry with placeholder name)
    async createNewQuiz() {
      const newQuizName = `New Quiz ${this.quizList.length + 1}`;

      try {
        const response = await fetch('/api/quizzes/new', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ name: newQuizName }),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(data?.error || `Could not create quiz. Status: ${response.status}`);
        }

        await this.fetchQuizList();
        // fetchQuizList sets focus to the last (new) quiz
      } catch (err) {
        console.error('Error creating quiz:', err);
        this.showErrorOverlay(
          'Could not create quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // delete a quiz
    async deleteQuiz() {
      const quiz_id = this.quizSelected;

      try {
        const response = await fetch(`/api/quizzes/grading/delete/${quiz_id}`, {
          method: 'DELETE'
        });

        if (response.status === 204) {
          console.log(`Quiz ${quiz_id} successfully deleted.`);
        } else if (response.status === 404) {
          console.warn(`Quiz ${quiz_id} was already deleted or is no longer accessible.`);
        } else {
          const data = await response.json().catch(() => null);
          throw new Error(data?.error || `Unexpected status code: ${response.status}`);
        }

        // Refresh quiz list and auto-select latest quiz if any
        await this.fetchQuizList();

      } catch (error) {
        console.error(`Error deleting Quiz ${quiz_id}`, error);
        this.showErrorOverlay("Error deleting quiz", `${error.message}`);
      }
    },

    // begin rename
    startEditingQuizName() {
      this.quizNameDraft = this.quizName;
      this.editingQuizName = true;
    },

    // save-new-quiz-name
    async saveQuizName() {
      this.editingQuizName = false;
      const trimmedName = this.quizNameDraft.trim();

      if (!trimmedName || trimmedName === this.quizName) {
        this.quizNameDraft = this.quizName;
        return;
      }

      if (!this.quizSelected) {
        return;
      }

      try {
        const response = await fetch(`/api/quizzes/rename/${this.quizSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName }),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to rename quiz. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        const finalName = data?.name || trimmedName;
        this.quizName = finalName;
        this.quizNameDraft = finalName;

        const quiz = this.quizList.find(q => q.quiz_id === this.quizSelected);
        if (quiz) {
          quiz.name = finalName;
        }
      } catch (err) {
        console.error('Error renaming quiz:', err);
        this.quizNameDraft = this.quizName;

        if (err.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Error renaming quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
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

          const data = await response.json().catch(() => null);
          if (!response.ok) {
            const error = new Error(
              data?.error || `Upload failed. Status: ${response.status}`
            );
            error.status = response.status;
            error.data = data;
            throw error;
          }

          const result = data;

          // update everything in view:
          // fetch quiz list then re-focus:
          const quiz_id = this.quizSelected;
          await this.fetchQuizList();
          this.quizSelected = quiz_id;
          await this.getFullQuiz(this.quizSelected);
          // validation report cleared for this quiz:
          this.validationReport = null
          this.analysisReport = null
        } catch (err) {
          console.error("Error uploading quiz:", err);

          if (err.status === 400 && err.data?.code === 'markdown_parse_error') {
            const contextLabel = err.data.question_name
              ? `Question: ${err.data.question_name}`
              : 'Question context';

            this.showDetailedErrorOverlay('Error parsing your quiz file', {
              message: err.data.error,
              hint: err.data.hint,
              contextLabel,
              context: err.data.context,
            });
            return;
          }

          if (err.status === 404) {
            this.showErrorOverlay(
              'Quiz not found',
              'This quiz may have been deleted, or you may no longer have access to it.'
            );
            await this.fetchQuizList();
            return;
          }

          this.showErrorOverlay(
            'Upload failed',
            err.message || 'This might be a network issue. Try refreshing the page.'
          );
        } finally {
          event.target.value = '';
        }

      };

      reader.onerror = () => {
        console.error("Error reading quiz file:", reader.error);
        this.showErrorOverlay(
          'Upload failed',
          'Could not read the selected file.'
        );
        event.target.value = '';
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
          body: JSON.stringify({ }),
        });

        const result = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            result?.error || `Validation failed. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        console.log("Validation started:", result);

        // clear old report from view:
        this.$nextTick(() => {
          setTimeout(() => {
            this.validationReport = null;
            this.analysisReport = null;
          }, 0);
        });

        // Start polling immediately
        await this.pollValidationStatus();

      } catch (error) {
        console.error("Error during validation:", error);

        if (error.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Validation error',
          error.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // (periodically) ask the server whether validation status changed
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

        // TODO: handle errors better, update status message. 
      } catch (err) {
        console.error("Validation polling error:", err);
        this.validationStatus = "error";
      }
    },

    // export quiz to a csv that Brightspace accepts
    async exportQuiz() {
      const safeName = (this.quizName || "quiz").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/brightspace/${this.quizSelected}`,
          filename: `${safeName}.csv`,
          mimeType: "text/csv;charset=utf-8"
        });
      } catch (err) {
        // TODO: can this be improved to be made more informative? does it ever fail?
        this.showErrorOverlay("Export failed", err.message);
      }
    },

    // afer the exam, upload the attempts file:
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

          const result = await response.json().catch(() => null);
          if (!response.ok) {
            const error = new Error(
              result?.error || `Upload failed. Status: ${response.status}`
            );
            error.status = response.status;
            error.data = result;
            throw error;
          }

          console.log("Attempts upload successful:", result);

          // Refresh UI: quiz state likely changed
          await this.getFullQuiz(this.quizSelected);

        } catch (err) {
          console.error("Error uploading attempts:", err);

          if (err.status === 404) {
            this.showErrorOverlay(
              'Quiz not found',
              'This quiz may have been deleted, or you may no longer have access to it.'
            );
            await this.fetchQuizList();
            return;
          }

          if (err.status === 400 && err.data?.code === 'brightspace_attempts_merge_error') {
            this.showDetailedErrorOverlay('Could not upload attempts file', {
              message: err.data.error,
              hint: err.data.hint,
              contextLabel: 'Details',
              context: err.data.context,
            });
            return;
          }

          this.showErrorOverlay(
            'Upload failed',
            err.message || 'This might be a network issue. Try refreshing the page.'
          );
        } finally {
          event.target.value = '';
        }
      };

      reader.onerror = () => {
        console.error("Error reading attempts file:", reader.error);
        this.showErrorOverlay(
          'Upload failed',
          'Could not read the selected file.'
        );
        event.target.value = '';
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
          body: JSON.stringify({}),
        });

        const result = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            result?.error || `Grading failed. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        console.log("Grading started:", result);

        // clear old report from view:
        this.$nextTick(() => {
          setTimeout(() => {
            this.analysisReport = null;
          }, 0);
        });

        await this.pollGradingStatus();

      } catch (error) {
        console.error("Error during grading:", error);

        if (error.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          "Grading error",
          error.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    // (periodically) ask the server whether grading status changed
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
        // TODO: does this need to be improved? 
        console.error("Grading polling error:", err);
        this.gradingStatus = "error";
      }
    },

    // export scores, to a format Brightspace likes
    async exportScores(){
      this.spinExportScores = true;

      const safeName = (this.quizName || "scores").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/grades/${this.quizSelected}`,
          filename: `${safeName}_grades.csv`,
          mimeType: "text/csv;charset=utf-8",
          method: "POST",
          body: {
            normalize_scores: true,
            grading_formula: "ug_bss"
          }
        });
      } catch (err) {
        if (err.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportScores = false;
      }
    },
    
    // export the Quantitative item analysis (csv)
    async exportItemAnalysis(){
      this.spinExportItemAnalysis = true;

      const safeName = (this.quizName || "item_analysis").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/difficulty_and_discrimination/${this.quizSelected}`,
          filename: `${safeName}_item_analysis.csv`,
          mimeType: "text/csv;charset=utf-8",
          method: "GET",
        });
      } catch (err) {
        if (err.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportItemAnalysis = false;
      }
    },

    // export the per-student feedback reports 
    async exportAnalysis(){
      this.spinExportFeedback = true;

      const safeName = (this.quizName || "feedback").replace(/\s+/g, "_");
      try {
        await this.downloadFile({
          endpoint: `/api/quizzes/export/feedback/${this.quizSelected}`,
          filename: `${safeName}_feedback.zip`,
          mimeType: "application/zip",
          method: "POST",
          body: {
            normalize_scores: true,
            grading_formula: "ug_bss"
          },
          isBinary: true
        });
      } catch (err) {
        if (err.status === 404) {
          this.showErrorOverlay(
            'Quiz not found',
            'This quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportFeedback = false;
      }
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
  
  }),

  computed: {
    quizStateLabel() {
      const labels = {
        empty: "This quiz is empty. Upload a quiz file to get started.",
        has_questions: "Questions have been uploaded. Validate (recommended) before administering quiz.",
        has_attempts: "Attempts have been uploaded. Ready to grade this quiz!",
        has_scores: "Grading is complete. Look at scores & analyses next."
      };
      if (this.quizState === 'error') {
        return "The selected quiz could not be loaded.";
      }
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
      return ['has_questions', 'has_attempts', 'has_scores'].includes(this.quizState)
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
      if (!['empty', 'has_questions', 'has_attempts', 'has_scores'].includes(this.quizState)){
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
      // only if the quiz has questions:
      if (!['has_questions', 'has_attempts', 'has_scores'].includes(this.quizState)){
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

window.registerCommonVueComponents(app);
app.mount('#app');
