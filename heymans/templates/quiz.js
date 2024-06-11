const app = Vue.createApp({
  data() {
    return {
      quizList: [],
      quizSelected: null,
      gradingStatus: '',
      gradingResult: null,

      // isNewQuizCreated: false,
      // isGrading: false,
      // gradingStatus: '',
      // gradingResult: null,
      // newQuizId: null,
    };
  },
  created() {
    this.fetchQuizList();
  },

  methods: {
    async fetchQuizList() {
      const response = await fetch('/api/quizzes/list');
      this.quizList = await response.json();
      // By default, select the last quiz:
      this.quizSelected = this.quizList.length ? this.quizList[this.quizList.length - 1].quiz_id : null;
      if (this.quizList.length) {
        this.pollGradingStatus(this.quizSelected);
      }
    },

    async pollGradingStatus(quiz_id) {
      this.quizSelected = quiz_id;
      const response = await fetch(`/api/quizzes/grading/poll/${quiz_id}`);
      this.gradingStatus = await response.json();
      console.log(this.gradingStatus);

    if (this.gradingStatus["message"] === 'grading_done') {
        const quizResponse = await fetch(`/api/quizzes/get/${quiz_id}`);
        this.gradingResult = JSON.stringify(await quizResponse.json(), null, 2);
      } else if (this.gradingStatus['message'] == 'needs_grading') {
      	console.log('needs_grading. Was the result deleted?')
        const quizResponse = await fetch(`/api/quizzes/get/${quiz_id}`);
        this.gradingResult = JSON.stringify(await quizResponse.json(), null, 2);
      } else { // grading_in_progress.
      	console.log('grading_in_progress?; timeout')
        // setTimeout(this.pollGradingStatus, 1000);
		setTimeout(() => this.pollGradingStatus(quiz_id), 1000);
      }
    },

    // creating a new quiz (TODO: user data! (upload?))
    async createNewQuiz() {
      const quizData = {
        name: 'Quiz title',
        questions: [
          {
            text: 'Who is the cutest bunny?',
            answer_key: '- Must state that the cutest bunny is Boef',
            attempts: [
              {
                username: 's12345678',
                answer: 'The cutest bunny is Boef',
              },
              {
                username: 's12345678',
                answer: "Don't know. :-(",
              },
            ],
          },
        ],
      };
      const response = await fetch('/api/quizzes/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(quizData),
      });
      const data = await response.json();
      this.newQuizId = data.quizId;
      this.isNewQuizCreated = true;
      this.fetchQuizList();
    },

    // Start grading a freshly created quiz; OR restart grading an ungraded quiz?
    async startGrading() {
      this.isGrading = true;
      await fetch('/api/quizzes/grading/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({'quiz_id': this.newQuizId,
                              'model': 'mistral-medium'}),
    });
      this.pollGradingStatus(this.newQuizId);
    },
  },
});

app.mount('#app');