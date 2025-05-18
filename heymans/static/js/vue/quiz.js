// /api/quizzes/list {'GET', 'OPTIONS', 'HEAD'}
// /api/quizzes/new {'POST', 'OPTIONS'}
// /api/quizzes/get/<int:quiz_id> {'GET', 'OPTIONS', 'HEAD'}
// /api/quizzes/state/<int:quiz_id> {'GET', 'OPTIONS', 'HEAD'}
// /api/quizzes/add/attempts/<int:quiz_id> {'POST', 'OPTIONS'}
// /api/quizzes/add/questions/<int:quiz_id> {'POST', 'OPTIONS'}
// /api/quizzes/export/brightspace/<int:quiz_id> {'GET', 'OPTIONS', 'HEAD'}
// /api/quizzes/grading/start/<int:quiz_id> {'POST', 'OPTIONS'}
// /api/quizzes/grading/poll/<int:quiz_id> {'GET', 'OPTIONS', 'HEAD'}
// /api/quizzes/grading/delete/<int:quiz_id> {'OPTIONS', 'DELETE'}
// /api/quizzes/validation/start/<int:quiz_id> {'POST', 'OPTIONS'}
// /api/quizzes/validation/poll/<int:quiz_id> {'GET', 'OPTIONS', 'HEAD'}

const app = Vue.createApp({
  data() {
    return {
      quizList: [],
      quizSelected: null,
      fullQuizData: '',
      quizName: '',
      quizState: '',
      // gradingResult: null,
      // collapsible sections
      showCreatePanel: true,
      showGradePanel: false,
      showAnalyzePanel: false
    };
  },
  created() {
    this.fetchQuizList();
  },

  methods: {
    // gets the quiz list; also poll result from last quiz:
    async fetchQuizList() {
      const response = await fetch('/api/quizzes/list');
      this.quizList = await response.json();
      // By default, select the last quiz:
      this.quizSelected = this.quizList.length ? this.quizList[this.quizList.length - 1].quiz_id : null;
      if (this.quizList.length) {
        this.getFullQuiz(this.quizSelected);
      }
    },

    // sets local variables, to see which quiz is selected
    async getFullQuiz(quiz_id) {

      this.quizSelected = quiz_id
      // Clicking this means selection changed. Get all quiz data:
      try {
        const response = await fetch(`/api/quizzes/get/${quiz_id}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch quiz. Status: ${response.status}`);
        }

        const quizData = await response.json();
        // For now, to display:
        this.fullQuizData = JSON.stringify(quizData, null, 2);
        // Set quiz name from full data
        this.quizName = quizData.name || '(Unnamed Quiz)';
      } catch (error) {
        console.error("Error fetching quiz:", error);
        this.fullQuizData = `Error: ${error.message}`;
        this.quizName = `Error loading name.`;
      }

      await this.getQuizState(quiz_id);
      // await this.pollGradingStatus(quiz_id)


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
        // console.log(`retrieved status  ${data.message} for quiz ${quiz_id}` )

      } catch (error) {
        console.error("Error polling state:", error);
        this.quizState = '(Error)';
      }
    },



    // Get the grading status from the server:
    async pollGradingStatus(quiz_id) {
      try {
        const response = await fetch(`/api/quizzes/grading/poll/${quiz_id}`);

        if (!response.ok) {
          throw new Error(`Failed to poll grading status. Status: ${response.status}`);
        }

        const data = await response.json();
        this.quizStatus = data.message;
        console.log(`retrieved status  ${data.message} for quiz ${quiz_id}` )

      } catch (error) {
        console.error("Error polling grading status:", error);
        this.quizStatus = '(Error)';
      }
    },


    // creating a new quiz (by default, it's empty)
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
      ok = await response.ok
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
      console.log(`Deleting Quiz ${quiz_id}`);

      try {
        const response = await fetch(`/api/quizzes/grading/delete/${quiz_id}`, {
          method: 'DELETE'
        });

        if (response.status === 204) {
          console.log("Quiz successfully deleted.");
        } else if (response.status === 404) {
          console.warn("Quiz not found.");
        } else {
          throw new Error(`Unexpected status code: ${response.status}`);
        }

        // Refresh quiz list and auto-select latest quiz if any
        await this.fetchQuizList();

      } catch (error) {
        console.error("Error deleting quiz:", error);
      }
    },

    // Start grading OR restart grading:
    async startGrading() {
    },

    // Whenever there's a user error:
    async showOverlay(primaryMessage, secondaryMessage = '') {
      const overlay = document.getElementById('overlay');
      const overlayMessage = document.getElementById('overlay-message');
      overlayMessage.innerHTML = `${primaryMessage}<br><i style="color: gray;">${secondaryMessage}</i>`;
      overlay.style.display = 'flex';
    },

    closeOverlay(){
      const overlay = document.getElementById('overlay');
      overlay.style.display = 'none';
    }

  },
  computed: {
    quizStateLabel() {
      const labels = {
        empty: "No questions yet",
        has_questions: "Questions added",
        has_attempts: "Awaiting grading",
        has_scores: "Grading complete"
      };
      return labels[this.quizState] || "Unknown";
    }

  }
});

app.mount('#app');