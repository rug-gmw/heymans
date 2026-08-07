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
      sourceDocRequiresPublic: false,

      showCreatePanel: true,
      showOverviewPanel: true,
      showStatsPanel: false,

      createForm: {
        document_id: null,
        public: false,
        enabled_skills: [...allBloomSkills],
      },

      quizName: 'You currently do not have any chat quizzes',
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
    clearSelectedQuiz() {
      this.quizSelected = null;
      this.fullQuizData = null;
      this.creatingNewQuiz = false;
      this.editingExistingQuizSettings = false;
      this.sourceDocRequiresPublic = false;
      this.quizName = this.quizList.length
        ? 'Select or create a new chat quiz'
        : 'You currently do not have any chat quizzes';
      this.quizNameDraft = this.quizName;
    },

    async fetchQuizList() {
      try {
        const response = await fetch('/api/interactive_quizzes/list');

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        this.quizList = await response.json();

        this.quizSelected = this.quizList.length
          ? this.quizList[this.quizList.length - 1].quiz_id
          : null;

        if (this.quizSelected) {
          await this.getFullQuiz(this.quizSelected, true);
        } else {
          this.quizSelected = null;
          this.fullQuizData = null;
          this.quizName = 'You currently do not have any chat quizzes';
          this.quizNameDraft = this.quizName;
        }
      } catch (err) {
        console.error('Error loading chat quiz list:', err);
        this.showErrorOverlay(
          'Could not load list of chat quizzes',
          'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    async fetchDocumentList() {
      try {
        const includePublic = this.showPublicDocuments ? 1 : 0;
        const response = await fetch(`/api/documents/list/${includePublic}`);

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        this.documentList = await response.json();

        if (
          this.createForm.document_id &&
          !this.documentList.some(doc => doc.document_id === this.createForm.document_id)
        ) {
          this.createForm.document_id = null;
        }
      } catch (err) {
        console.error('Error loading document list:', err);
        this.showErrorOverlay(
          'Could not load list of documents',
          'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    async documentRequiresPublic(documentId) {
      if (!documentId) {
        return false;
      }

      const response = await fetch('/api/documents/list/0');
      const documents = await response.json().catch(() => null);
      if (!response.ok) {
        const error = new Error(
          documents?.error || `Failed to check document access. Status: ${response.status}`
        );
        error.status = response.status;
        throw error;
      }

      return !documents.some(doc => Number(doc.document_id) === Number(documentId));
    },

    async startNewQuiz() {
      this.creatingNewQuiz = true;
      this.editingExistingQuizSettings = false;
      this.sourceDocRequiresPublic = false;
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
        const selectedQuiz = this.quizList.find(q => q.quiz_id === this.quizSelected);
        const originalName = (
          this.fullQuizData?.name ||
          selectedQuiz?.name ||
          'Select or create a new chat quiz'
        );

        this.creatingNewQuiz = false;
        this.editingExistingQuizSettings = false;
        this.editingQuizName = false;
        this.sourceDocRequiresPublic = false;
        this.quizName = originalName;
        this.quizNameDraft = originalName;
        this.showOverviewPanel = true;
        return;
      }
      this.creatingNewQuiz = false;
      this.editingQuizName = false;
      this.sourceDocRequiresPublic = false;

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
      this.$nextTick(() => {
        this.$refs.titleInput?.focus();
        this.$refs.titleInput?.select();
      });
    },

    async selectQuizDocument(doc) {
      if (!doc || doc.document_id === this.createForm.document_id) return;

      this.createForm.document_id = doc.document_id;

      if (this.editingExistingQuizSettings) {
        try {
          this.sourceDocRequiresPublic =
            await this.documentRequiresPublic(doc.document_id);
          if (this.sourceDocRequiresPublic) {
            this.showPublicDocuments = true;
          }
        } catch (err) {
          console.error('Error checking selected document access:', err);
          this.showErrorOverlay(
            'Could not check document access',
            err.message || 'This might be a network issue. Try refreshing the page.'
          );
        }
      }

      const documentName = (doc.name || '').trim();
      if (!documentName) return;

      this.quizName = documentName;
      this.quizNameDraft = documentName;
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
        this.quizNameDraft = trimmedName;
        return;
      }

      // But if quiz already exists, edited name involves a POST
      try {
        const response = await fetch(`/api/interactive_quizzes/rename/${this.quizSelected}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName }),
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to rename chat quiz. Status: ${response.status}`
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
        console.error('Error renaming chat quiz:', err);
        this.quizNameDraft = this.quizName;

        if (err.status === 404) {
          this.clearSelectedQuiz();

          this.showErrorOverlay(
            'Chat quiz not found',
            'This chat quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Error renaming chat quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    async createNewQuiz() {
      const trimmedName = this.quizNameDraft.trim();
      if (!trimmedName || !this.createForm.document_id) {
        return;
      }

      try {
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

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Could not create chat quiz. Status: ${response.status}`
          );
          error.status = response.status;
          error.data = data;
          throw error;
        }

        this.creatingNewQuiz = false;
        this.editingQuizName = false;
        this.sourceDocRequiresPublic = false;
        this.quizName = trimmedName;
        this.quizNameDraft = trimmedName;
        this.showOverviewPanel = true;

        await this.fetchQuizList();

        this.quizSelected = data.interactive_quiz_id;
        await this.getFullQuiz(data.interactive_quiz_id, false);
      } catch (err) {
        console.error('Error creating chat quiz:', err);

        if (err.status === 404) {
          this.createForm.document_id = null;
          this.showErrorOverlay(
            'Document not found',
            'This document may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchDocumentList();
          return;
        }

        this.showErrorOverlay(
          'Could not create chat quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
    },

    async saveExistingQuizSettings() {
      if (!this.quizSelected) return;
      if (!this.createForm.document_id || !this.createForm.enabled_skills.length) return;

      const trimmedName = this.quizNameDraft.trim();
      if (!trimmedName) return;

      try {
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

        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            data?.error || `Failed to update chat quiz settings. Status: ${response.status}`
          );
          error.status = response.status;
          error.data = data;
          throw error;
        }

        const currentName = (this.fullQuizData?.name || '').trim();
        if (trimmedName !== currentName) {
          const renameResponse = await fetch(`/api/interactive_quizzes/rename/${this.quizSelected}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: trimmedName }),
          });

          const renameData = await renameResponse.json().catch(() => null);
          if (!renameResponse.ok) {
            const error = new Error(
              renameData?.error || `Failed to rename chat quiz. Status: ${renameResponse.status}`
            );
            error.status = renameResponse.status;
            error.data = renameData;
            throw error;
          }

          const finalName = renameData?.name || trimmedName;
          this.quizName = finalName;
          this.quizNameDraft = finalName;

          const quiz = this.quizList.find(q => q.quiz_id === this.quizSelected);
          if (quiz) {
            quiz.name = finalName;
          }
        }

        this.creatingNewQuiz = false;
        this.editingExistingQuizSettings = false;
        this.sourceDocRequiresPublic = false;
        this.showOverviewPanel = true;
        await this.getFullQuiz(this.quizSelected, false);
      } catch (err) {
        console.error('Error updating chat quiz settings:', err);
        this.quizNameDraft = this.quizName;

        if (err.status === 404) {
          const message = err.message || '';
          const isDocumentError = message.toLowerCase().includes('document');

          if (isDocumentError) {
            this.createForm.document_id = null;
            this.showErrorOverlay(
              'Document not found',
              'This document may have been deleted, or you may no longer have access to it.'
            );
            await this.fetchDocumentList();
            return;
          }

          this.clearSelectedQuiz();
          this.showErrorOverlay(
            'Chat quiz not found',
            'This chat quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Could not update chat quiz settings',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
      }
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
        const quizData = await response.json().catch(() => null);
        if (!response.ok) {
          const error = new Error(
            quizData?.error || `Failed to fetch chat quiz. Status: ${response.status}`
          );
          error.status = response.status;
          throw error;
        }

        this.quizSelected = quiz_id;
        this.fullQuizData = quizData;

        this.quizName = quizData.name || '(Unnamed chat quiz)';
        this.quizNameDraft = this.quizName;
      } catch (err) {
        console.error('Error loading chat quiz:', err);

        if (err.status === 404) {
          this.clearSelectedQuiz();
          this.showErrorOverlay(
            'Chat quiz not found',
            'This chat quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Error loading chat quiz',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
        return;
      }

      if (showLoading && overlayStart) {
        const elapsed = Date.now() - overlayStart;
        const minVisible = 300;
        const remaining = Math.max(0, minVisible - elapsed);

        setTimeout(() => {
          this.closeOverlay();
        }, remaining);
      }
    },

    startTestConversation() {
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

        const selectedDocumentId = this.createForm.document_id;
        this.sourceDocRequiresPublic =
          await this.documentRequiresPublic(selectedDocumentId);
        const selectedDocumentIsVisible = this.documentList.some(
          doc => Number(doc.document_id) === Number(selectedDocumentId)
        );
        if (
          selectedDocumentId &&
          (this.sourceDocRequiresPublic || !selectedDocumentIsVisible) &&
          !this.showPublicDocuments
        ) {
          this.showPublicDocuments = true;
          await this.fetchDocumentList();
        } else if (!this.documentList.length) {
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
          const deletedId = this.quizSelected;

          try {
            const response = await fetch(
              `/api/interactive_quizzes/delete/${deletedId}`,
              { method: 'DELETE' }
            );

            if (response.ok) {
              console.log(`Chat quiz ${deletedId} successfully deleted.`);
            } else if (response.status === 404) {
              console.warn(`Chat quiz ${deletedId} was already deleted or is no longer accessible.`);
            } else {
              const data = await response.json().catch(() => null);
              throw new Error(data?.error || `Unexpected status code: ${response.status}`);
            }

            this.clearSelectedQuiz();
            await this.fetchQuizList();

            if (this.quizList.length) {
              const fallbackQuiz =
                this.quizList.find(q => q.quiz_id !== deletedId) || this.quizList[this.quizList.length - 1];
              if (fallbackQuiz) {
                await this.getFullQuiz(fallbackQuiz.quiz_id, false);
              }
            }
          } catch (err) {
            console.error(`Error deleting chat quiz ${deletedId}:`, err);
            this.showErrorOverlay(
              'Failed to delete chat quiz',
              err.message || 'This might be a network issue. Try refreshing the page.'
            );
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
        console.error('Error exporting chat quiz scores:', err);

        if (err.status === 404) {
          this.clearSelectedQuiz();
          this.showErrorOverlay(
            'Chat quiz not found',
            'This chat quiz may have been deleted, or you may no longer have access to it.'
          );
          await this.fetchQuizList();
          return;
        }

        this.showErrorOverlay(
          'Export failed',
          err.message || 'This might be a network issue. Try refreshing the page.'
        );
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
