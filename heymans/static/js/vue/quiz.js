const app = Vue.createApp({
  data() {
    return {
      quizList: [],
      quizSelected: null,
      quizName: '',
      gradingStatus: '',
      gradingResult: null,
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
        this.pollGradingStatus(this.quizSelected);
      }
    },

    // Get the grading status from the server:
    async pollGradingStatus(quiz_id) {
      this.quizSelected = quiz_id;
      const response = await fetch(`/api/quizzes/grading/poll/${quiz_id}`);
      this.gradingStatus = await response.json();

    if (this.gradingStatus["message"] === 'grading_done') {
        const quizResponse = await fetch(`/api/quizzes/get/${quiz_id}`);
        this.gradingResult = JSON.stringify(await quizResponse.json(), null, 2);
      } else if (this.gradingStatus['message'] == 'needs_grading') {
        const quizResponse = await fetch(`/api/quizzes/get/${quiz_id}`);
        this.gradingResult = JSON.stringify(await quizResponse.json(), null, 2);
      } else { // grading_in_progress.
        // setTimeout(this.pollGradingStatus, 1000);
		setTimeout(() => this.pollGradingStatus(quiz_id), 1000);
      }
    },

    // After upload, the quiz gets parsed and the quiz gets populated..
    async handleQuizUpload(event) {
      console.log("handling quiz upload ")
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = async (e) => {    
          try {

            const quizData = JSON.parse(e.target.result);
            await this.createNewQuiz(quizData);

          } catch (error) {
            // If error is a syntax error in JSON.parse
            if (error instanceof SyntaxError) {
              console.error('Error processing JSON file:', error);
              this.showOverlay("File is not valid JSON", error.message);
            } else {
              // If error is from createNewQuiz
              console.error('Error creating new quiz:', error);
              this.showOverlay("Error creating quiz from JSON", error.message);
            }
          }
        };
        reader.readAsText(file);
      }
    },

    // creating a new quiz (by default, it's empty)
    async createNewQuiz(quizData) {
      console.log("Posting new quiz data:")
      const response = await fetch('/api/quizzes/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(quizData),
      });

      // Check if the response is not ok
      ok = await response.ok
      if (!ok) {
        // Throw an error with the response status text
        throw new Error(`Error: ${response.statusText}`);
      }      
      // Otherwise: pull result, refresh the list
      const data = await response.json();
      await this.fetchQuizList();
      // fetchQuizList already sets it to the last quiz
      // new quiz is usually last quiz. This step probably superfluous
      this.quizSelected = data.quiz_id
    },

    // Start grading OR restart grading:
    async startGrading() {
      this.isGrading = true;
      await fetch('/api/quizzes/grading/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({'quiz_id': this.quizSelected,
                              'model': 'mistral-medium'}),
    });
      this.pollGradingStatus(this.quizSelected);
    },
    // When 'New quiz' gets clicked, the item is created
    triggerFileUpload() {
      document.getElementById('file-upload').click();
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