const app = Vue.createApp({
  data() {
    return {
      conversationId: window.CONVERSATION_ID || null,
      token: window.QUIZ_TOKEN || null,
      initialReply: window.INITIAL_REPLY || '',

      chatTitle: 'Interactive quiz',
      chatStatus: 'Ready',
      messages: [],
      draftMessage: '',
      isSending: false,
      isFinished: false,
    };
  },

  created() {
    console.log("conversationId:", this.conversationId);
    console.log("token:", this.token);

    if (this.initialReply) {
      this.messages.push({
        role: 'assistant',
        text: this.initialReply,
      });
    }
  },

  methods: {
    async sendMessage() {
      const text = this.draftMessage.trim();
      if (!text || this.isSending || this.isFinished) return;

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