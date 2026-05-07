const md = window.markdownit({
  breaks: true,
  linkify: true,
});

const app = Vue.createApp({
  data() {
    return {
      interactiveQuizId: window.INTERACTIVE_QUIZ_ID || null,
      username: window.LOG_USERNAME || window.CHAT_USERNAME || '',

      chatTitle: 'Loading chat logs...',
      chatStatus: 'Loading...',
      startedCount: 0,
      finishedCount: 0,
      conversations: [],
      showOnlyFinished: false,
    };
  },

  created() {
    this.loadLogs();
  },

  computed: {
    displayedConversations() {
      if (!this.showOnlyFinished) {
        return this.conversations;
      }
      return this.conversations.filter((conversation) => conversation.finished);
    },
  },

  methods: {
    renderMarkdown(text) {
      if (!text) return '';
      return md.render(text);
    },

    stripFinishedTag(text) {
      if (!text) {
        return '';
      }
      const finishedTag = '<FINISHED>';
      const idx = text.indexOf(finishedTag);
      if (idx === -1) {
        return text;
      }
      return text.slice(0, idx).trim();
    },

    async loadLogs() {
      if (!this.interactiveQuizId || !this.username) {
        this.chatTitle = 'Interactive quiz logs';
        this.chatStatus = 'Missing quiz or username';
        this.conversations = [];
        return;
      }

      this.chatStatus = 'Loading...';
      this.conversations = [];

      try {
        const response = await fetch(
          `/api/interactive_quizzes/logs/${this.interactiveQuizId}/${encodeURIComponent(this.username)}`
        );
        if (!response.ok) {
          throw new Error(`Failed to fetch chat logs. Status: ${response.status}`);
        }

        const data = await response.json();
        this.username = (data.student_username || this.username || '').trim();
        this.startedCount = Number(data.started_count || 0);
        this.finishedCount = Number(data.finished_count || 0);
        this.chatTitle = data.quiz_name || 'Interactive quiz';
        this.chatStatus = `${this.startedCount} chat(s) loaded`;
        this.conversations = (data.conversations || []).map((conversation, index) => {
          const normalizedMessages = (conversation.messages || []).map((message) => ({
            message_id: message.message_id,
            role: message.role === 'assistant' ? 'assistant' : 'user',
            text: message.text || '',
          }));
          if (conversation.finished && normalizedMessages.length > 0) {
            const lastMessage = normalizedMessages[normalizedMessages.length - 1];
            normalizedMessages[normalizedMessages.length - 1] = {
              ...lastMessage,
              text: this.stripFinishedTag(lastMessage.text),
            };
          }
          return {
            conversation_id: conversation.conversation_id,
            attempt_number: index + 1,
            finished: !!conversation.finished,
            messages: normalizedMessages,
          };
        });
      } catch (err) {
        console.error('Error loading chat logs:', err);
        this.chatStatus = 'Error loading logs';
        this.conversations = [];
      }
    },
  },
});

app.mount('#app');
