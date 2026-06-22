const express = require("express");
require("dotenv").config();
require("./bot");

const app = express();

app.get("/", (req, res) => {
  res.send("PRO Forex Bot Running...");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running on " + PORT));
