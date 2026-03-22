const app = Vue.createApp({
  data() {
    return {
      interactiveQuizId: window.INTERACTIVE_QUIZ_ID || null,
      username: window.CHAT_USERNAME || 'anonymous',

      conversationId: null,
      token: null,

      chatTitle: 'Interactive quiz',
      chatStatus: 'Starting conversation...',
      messages: [],
      draftMessage: '',
      isSending: false,
      isFinished: false,
      isStarting: false,
    };
  },

  created() {
    this.startConversation();
  },

  methods: {
    async startConversation() {
      if (!this.interactiveQuizId || this.isStarting) return;

      this.isStarting = true;
      this.chatStatus = 'Starting conversation...';

      try {
        const response = await fetch(
          `/api/interactive_quizzes/conversation/start/${this.interactiveQuizId}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: this.username,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to start conversation. Status: ${response.status}`);
        }

        const data = await response.json();

        this.conversationId = data.conversation_id;
        this.token = data.token;

        if (data.reply) {
          this.messages.push({
            role: 'assistant',
            text: data.reply,
          });
        }

        this.chatStatus = 'Ready';
      } catch (err) {
        console.error('Error starting conversation:', err);
        this.chatStatus = 'Error starting conversation';
      } finally {
        this.isStarting = false;
      }
    },

    async sendMessage() {
      const text = this.draftMessage.trim();
      if (!text || this.isSending || this.isFinished || !this.conversationId || !this.token) {
        return;
      }

      this.isSending = true;
      this.chatStatus = 'Thinking...';

      this.messages.push({
        role: 'user',
        text: text,
      });

      this.draftMessage = '';

      try {
        const response = await fetch(
          `/api/interactive_quizzes/conversation/send_message/${this.conversationId}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              token: this.token,
              text: text,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to send message. Status: ${response.status}`);
        }

        const data = await response.json();

        this.messages.push({
          role: 'assistant',
          text: data.reply,
        });

        this.isFinished = !!data.finished;
        this.chatStatus = this.isFinished ? 'Finished' : 'Ready';
      } catch (err) {
        console.error('Error sending message:', err);
        this.chatStatus = 'Error';
      } finally {
        this.isSending = false;
      }
    },
  },
});

app.mount('#app');