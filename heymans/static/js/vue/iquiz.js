const app = Vue.createApp({
  data() {
    const allBloomSkills = ['understand', 'apply', 'analyze', 'evaluate', 'create'];
    return {
      allBloomSkills,
      quizList: [],
      quizSelected: null,
      fullQuizData: null,

      creatingNewQuiz: false,
      editingExistingQuizSettings: false,
      documentList: [],
      showPublicDocuments: false,

      showCreatePanel: true,
      showOverviewPanel: true,
      showStatsPanel: false,

      createForm: {
        document_id: null,
        public: false,
        enabled_skills: [...allBloomSkills],
      },

      quizName: 'No quizzes available',
      quizNameDraft: 'New chat quiz',
      editingQuizName: false,

      spinExportScores: false,

    };
  },

  created() {
    this.fetchQuizList();
    this.fetchDocumentList();
  },

  methods: window.withCommonVueMethods({
    async fetchQuizList() {
      const response = await fetch('/api/interactive_quizzes/list');
      if (!response.ok) {
        throw new Error(`Error loading quiz list: ${response.statusText}`);
      }

      this.quizList = await response.json();

      if (this.quizList.length) {
        this.quizSelected = this.quizList[this.quizList.length - 1].quiz_id;
        this.getFullQuiz(this.quizSelected, showLoading=true);
      } else {
        this.quizSelected = null;
        this.fullQuizData = null;
        this.quizName = 'No quizzes available';
        this.quizNameDraft = this.quizName;
      }      
    },

    async fetchDocumentList() {
      const includePublic = this.showPublicDocuments ? 1 : 0;
      const response = await fetch(`/api/documents/list/${includePublic}`);
      if (!response.ok) {
        throw new Error(`Error loading document list: ${response.statusText}`);
      }

      this.documentList = await response.json();

      if (
        this.createForm.document_id &&
        !this.documentList.some(doc => doc.document_id === this.createForm.document_id)
      ) {
        this.createForm.document_id = null;
      }
    },

    async startNewQuiz() {
      this.creatingNewQuiz = true;
      this.editingExistingQuizSettings = false;
      this.quizSelected = null;
      this.fullQuizData = null;

      this.showCreatePanel = true;
      this.showOverviewPanel = false;

      this.quizName = 'New chat quiz';
      this.quizNameDraft = 'New chat quiz';
      this.editingQuizName = false;

      this.createForm = {
        document_id: null,
        public: false,
        enabled_skills: [...this.allBloomSkills],
      };

      if (!this.documentList.length) {
        await this.fetchDocumentList();
      }
    },

    cancelNewQuiz() {
      if (this.editingExistingQuizSettings && this.quizSelected) {
        this.creatingNewQuiz = false;
        this.editingExistingQuizSettings = false;
        this.showOverviewPanel = true;
        return;
      }
      this.creatingNewQuiz = false;
      this.editingQuizName = false;

      this.createForm = {
        document_id: null,
        public: false,
        enabled_skills: [...this.allBloomSkills],
      };

      if (this.quizList.length) {
        this.quizName = 'Select or create a new chat quiz';
      } else {
        this.quizName = 'You currently do not have any chat quizzes';
      }
      this.quizNameDraft = this.quizName;
    },

    startEditingQuizName() {
      this.quizNameDraft = this.quizName;
      this.editingQuizName = true;
    },

    async saveQuizName() {
      this.editingQuizName = false;
      const trimmedName = this.quizNameDraft.trim();

      if (!trimmedName || trimmedName === this.quizName) {
        this.quizNameDraft = this.quizName;
        return;
      }

      // If we're still creating and no real quiz exists yet, just update local draft
      if (!this.quizSelected || this.creatingNewQuiz) {
        this.quizName = trimmedName;
        return;
      }

      // But if quiz already exists, edited name involves a POST
      try {
        const response = await fetch(`/api/interactive_quizzes/rename/${this.quizSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName }),
        });

        if (!response.ok) {
          throw new Error(`Failed to rename chat quiz. Status: ${response.status}`);
        }

        this.quizName = trimmedName;

        const quiz = this.quizList.find(q => q.quiz_id === this.quizSelected);
        if (quiz) {
          quiz.name = trimmedName;
        }
      } catch (err) {
        console.error('Error renaming chat quiz:', err);
        this.showErrorOverlay('Error renaming chat quiz', err.message);
        this.quizNameDraft = this.quizName;
      }
    },

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
          enabled_skills: this.createForm.enabled_skills,
        }),
      });

      if (!response.ok) {
        let errMsg = `Error: ${response.statusText}`;
        try {
          const err = await response.json();
          errMsg = err.error || errMsg;
        } catch (_) {
          // keep fallback message
        }
        throw new Error(errMsg);
      }

      const data = await response.json();

      this.creatingNewQuiz = false;
      this.editingQuizName = false;
      this.quizName = trimmedName;
      this.quizNameDraft = trimmedName;
      this.showOverviewPanel = true;

      await this.fetchQuizList();

      this.quizSelected = data.interactive_quiz_id;
      await this.getFullQuiz(data.interactive_quiz_id, false);
    },

    async saveExistingQuizSettings() {
      if (!this.quizSelected) return;
      if (!this.createForm.document_id || !this.createForm.enabled_skills.length) return;

      const response = await fetch(
        `/api/interactive_quizzes/settings/${this.quizSelected}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            document_id: this.createForm.document_id,
            enabled_skills: this.createForm.enabled_skills,
          }),
        }
      );

      if (!response.ok) {
        let errMsg = `Error: ${response.statusText}`;
        try {
          const err = await response.json();
          errMsg = err.error || errMsg;
        } catch (_) {
          // keep fallback message
        }
        throw new Error(errMsg);
      }

      this.creatingNewQuiz = false;
      this.editingExistingQuizSettings = false;
      this.showOverviewPanel = true;
      await this.getFullQuiz(this.quizSelected, false);
    },

    async submitQuizForm() {
      if (this.editingExistingQuizSettings) {
        await this.saveExistingQuizSettings();
        return;
      }
      await this.createNewQuiz();
    },

    async getFullQuiz(quiz_id, showLoading = false) {
      if (!quiz_id) {
        console.error('getFullQuiz called without quiz_id');
        return;
      }

      let overlayStart = null;
      if (showLoading) {
        overlayStart = Date.now();
        this.showSpinnerOverlay('Loading chat quiz...');
      }

      try {
        this.quizSelected = quiz_id;
        this.creatingNewQuiz = false;
        this.editingExistingQuizSettings = false;
        this.editingQuizName = false;
        this.showOverviewPanel = true;

        const quizFromList = this.quizList.find(q => q.quiz_id === quiz_id);
        if (quizFromList) {
          this.quizName = quizFromList.name;
          this.quizNameDraft = quizFromList.name;
        }

        if (!this.documentList.length) {
          await this.fetchDocumentList();
        }

        const response = await fetch(`/api/interactive_quizzes/get/${quiz_id}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch interactive quiz. Status: ${response.status}`);
        }

        const quizData = await response.json();
        this.fullQuizData = quizData;

        this.quizName = quizData.name || '(Unnamed chat quiz)';
        this.quizNameDraft = this.quizName;
      } catch (err) {
        console.error('Error loading chat quiz:', err);
        this.showErrorOverlay('Error loading chat quiz', err.message);
      } finally {
        if (showLoading && overlayStart) {
          const elapsed = Date.now() - overlayStart;
          const minVisible = 300;
          const remaining = Math.max(0, minVisible - elapsed);

          setTimeout(() => {
            this.closeOverlay();
          }, remaining);
        }
      }
    },

    async startTestConversation() {
      if (!this.quizSelected) return;

      const sessionUrl =
        `/public/interactive_quizzes/start/${this.quizSelected}` +
        `?username=${encodeURIComponent('teacher_test')}`;

      window.open(sessionUrl, '_blank');
    },

    async startEditSettings() {
      if (!this.quizSelected || !this.fullQuizData) return;
      const beginEditMode = async () => {
        this.creatingNewQuiz = true;
        this.editingExistingQuizSettings = true;
        this.showCreatePanel = true;
        this.showOverviewPanel = false;
        this.editingQuizName = false;
        this.createForm = {
          document_id: this.fullQuizData.document_id || null,
          public: !!this.fullQuizData.public,
          enabled_skills: Array.isArray(this.fullQuizData.enabled_skills) &&
            this.fullQuizData.enabled_skills.length
            ? [...this.fullQuizData.enabled_skills]
            : [...this.allBloomSkills],
        };
        this.quizNameDraft = this.quizName;
        if (!this.documentList.length) {
          await this.fetchDocumentList();
        }
      };
      if (this.conversationsStarted > 0) {
        this.showConfirmationOverlay(
          'Change quiz settings?',
          'Students have already started this quiz. Saving new settings will clear existing chat conversations. Continue?',
          beginEditMode
        );
        return;
      }
      await beginEditMode();
    },

    async deleteQuiz() {
      if (!this.quizSelected) return;

      this.showConfirmationOverlay(
        'Delete this chat quiz?',
        'This will remove the chat quiz and all associated conversations.',
        async () => {
          try {
            const response = await fetch(
              `/api/interactive_quizzes/delete/${this.quizSelected}`,
              { method: 'DELETE' }
            );

            if (!response.ok) {
              throw new Error(`Failed to delete chat quiz. Status: ${response.status}`);
            }

            const deletedId = this.quizSelected;

            this.fullQuizData = null;
            this.quizSelected = null;
            this.quizName = 'No quizzes available';
            this.quizNameDraft = this.quizName;

            await this.fetchQuizList();

            if (this.quizList.length) {
              const fallbackQuiz =
                this.quizList.find(q => q.quiz_id !== deletedId) || this.quizList[this.quizList.length - 1];
              if (fallbackQuiz) {
                await this.getFullQuiz(fallbackQuiz.quiz_id, false);
              }
            }
          } catch (err) {
            console.error('Error deleting chat quiz:', err);
            this.showErrorOverlay('Failed to delete chat quiz', err.message);
          }
        }
      );
    },

    async exportScores() {
      if (!this.quizSelected) return;

      this.spinExportScores = true;

      const safeName = (this.quizName || "interactive_quiz")
        .trim()
        .replace(/\s+/g, "_")
        .replace(/[^\w\-]+/g, "");

      try {
        await this.downloadFile({
          endpoint: `/api/interactive_quizzes/export/finished/${this.quizSelected}`,
          filename: `${safeName}_finished.csv`,
          mimeType: "text/csv;charset=utf-8",
        });
      } catch (err) {
        this.showErrorOverlay("Export failed", err.message);
      } finally {
        this.spinExportScores = false;
      }
    },

    openUserLogs(studentUsername) {
      if (!this.quizSelected) return;
      const username = (studentUsername || '').trim();
      if (!username || username === '(unknown)') return;
      const logsUrl = `/app/iquiz/logs/${this.quizSelected}` +
        `?username=${encodeURIComponent(username)}`;
      window.open(logsUrl, '_blank');
    },

  }),

  computed: {
    studentConversations() {
      if (!this.fullQuizData || !Array.isArray(this.fullQuizData.conversations)) {
        return [];
      }
      return this.fullQuizData.conversations.filter(conversation =>
        ((conversation.username || '').trim() || '(unknown)') !== 'teacher_test'
      );
    },

    selectedDocumentName() {
      if (!this.fullQuizData || !this.fullQuizData.document_id) {
        return '';
      }

      const targetId = Number(this.fullQuizData.document_id);
      const doc = this.documentList.find(
        d => Number(d.document_id) === targetId
      );

      return doc ? doc.name : '';
    },

    conversationsStarted() {
      return this.studentConversations.length;
    },

    conversationsFinished() {
      return this.studentConversations.filter(c => c.finished).length;
    },

    conversationOverviewRows() {
      if (!this.studentConversations.length) {
        return [];
      }

      const countsByUsername = new Map();

      for (const conversation of this.studentConversations) {
        const username = (conversation.username || '').trim() || '(unknown)';

        if (!countsByUsername.has(username)) {
          countsByUsername.set(username, {
            username,
            started: 0,
            finished: 0,
          });
        }

        const row = countsByUsername.get(username);
        row.started += 1;

        if (conversation.finished) {
          row.finished += 1;
        }
      }

      return Array.from(countsByUsername.values()).sort((a, b) =>
        a.username.localeCompare(b.username)
      );
    },

    shareLink() {
      if (!this.quizSelected) {
        return '';
      }

      return `${window.location.origin}/public/interactive_quizzes/start/${this.quizSelected}` +
        `?username=${encodeURIComponent('student_username')}`;
    },

    selectedSkillsLabel() {
      const skills = this.fullQuizData?.enabled_skills;
      if (!Array.isArray(skills) || !skills.length) {
        return this.allBloomSkills.join(', ');
      }
      return skills.join(', ');
    },

    createCardTitle() {
      return this.editingExistingQuizSettings ? 'Edit chat quiz settings' : 'Create chat quiz';
    },

    submitQuizButtonLabel() {
      return this.editingExistingQuizSettings ? 'Save chat quiz' : 'Create chat quiz';
    },
  },
});

window.registerCommonVueComponents(app);
app.mount('#app');
