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
      // quizName: '',
      // gradingStatus: '',
      // gradingResult: null,
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

      // get full quiz data for now...
      try {
        const response = await fetch(`/api/quizzes/get/${quiz_id}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch quiz. Status: ${response.status}`);
        }

        const quizData = await response.json();
        console.log("Quiz data received:", quizData);
        // Optional: display it in your app
        this.fullQuizData = JSON.stringify(quizData, null, 2);

      } catch (error) {
        console.error("Error fetching quiz:", error);
        this.fullQuizData = `Error: ${error.message}`;
      }
      console.log("yes, got quiz data")

      this.pollGradingStatus(this.quizSelected)      

    },

    // Get the grading status from the server:
    async pollGradingStatus(quiz_id) {
      console.log("polling grading status (NI!)")
    },

    // creating a new quiz (by default, it's empty)
    async createNewQuiz() {
      console.log("Creating new quiz (empty):")
      const response = await fetch('/api/quizzes/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({"name":"Quiz name"}),
      });
      console.log("got response...")
      console.log(response)

      // Check if the response is not ok
      ok = await response.ok
      if (!ok) {
        // Throw an error with the response status text
        throw new Error(`Error: ${response.statusText}`);
      }      
      // // Otherwise: pull result, refresh the list
      const data = await response.json();
      await this.fetchQuizList();
      // fetchQuizList already sets it to the last quiz
      // new quiz is usually last quiz. This step probably superfluous
      this.quizSelected = data.quiz_id
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
    isGrading() {
      return this.gradingStatus.message === 'grading_in_progress';
    },
    statusMessage() {
      switch (this.gradingStatus.message) {
        case 'grading_done':
          return "Finished grading this quiz";
        case 'needs_grading':
          return "Ready to grade this quiz";
        case 'grading_in_progress':
          return "Grading is in progress...";
        default:
          return ''; // Fallback message
      }
    }
  }
});

app.mount('#app');