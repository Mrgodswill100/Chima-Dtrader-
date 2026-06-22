const axios = require("axios");

async function getCandles(pair, interval) {
  try {
    const res = await axios.get(
      `${process.env.API_URL}/time_series?symbol=${pair}&interval=${interval}&outputsize=200&apikey=${process.env.API_KEY}`
    );

    return res.data.values.map(c => parseFloat(c.close)).reverse();
  } catch (e) {
    return [];
  }
}

module.exports = { getCandles };
