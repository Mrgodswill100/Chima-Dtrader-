const TelegramBot = require("node-telegram-bot-api");
const { analyze } = require("./strategy");

const bot = new TelegramBot(process.env.TELEGRAM_TOKEN, { polling: true });

// USER START
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(msg.chat.id, "🔥 Select Forex Pair:", {
    reply_markup: {
      inline_keyboard: [
        [{ text: "EUR/USD", callback_data: "EURUSD" }],
        [{ text: "GBP/USD", callback_data: "GBPUSD" }],
        [{ text: "USD/JPY", callback_data: "USDJPY" }],
        [{ text: "XAU/USD", callback_data: "XAUUSD" }]
      ]
    }
  });
});

// HANDLE SELECTION
bot.on("callback_query", async (q) => {
  const chatId = q.message.chat.id;
  const pair = q.data;

  bot.sendMessage(chatId, "⏳ Analyzing market...");

  const signal = await analyze(pair);

  bot.sendMessage(chatId, `📊 SIGNAL FOR ${pair}: ${signal}`);
});
