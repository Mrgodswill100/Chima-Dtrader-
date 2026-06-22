require("dotenv").config();

// LOAD BOT FILE (THIS MUST MATCH FILE NAME EXACTLY)
require("./bot");

const express = require("express");
const app = express();

// simple health check for Render
app.get("/", (req, res) => {
  res.send("🔥 Forex PRO Bot is LIVE and Running");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
