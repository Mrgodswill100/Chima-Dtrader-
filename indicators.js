const ti = require("technicalindicators");

function EMA(values, period) {
  return ti.EMA.calculate({ period, values }).slice(-1)[0];
}

function RSI(values) {
  return ti.RSI.calculate({ period: 14, values }).slice(-1)[0];
}

function MACD(values) {
  return ti.MACD.calculate({
    values,
    fastPeriod: 12,
    slowPeriod: 26,
    signalPeriod: 9
  }).slice(-1)[0];
}

function ATR(high, low, close) {
  return ti.ATR.calculate({
    period: 14,
    high,
    low,
    close
  }).slice(-1)[0];
}

function BB(values) {
  return ti.BollingerBands.calculate({
    period: 20,
    values,
    stdDev: 2
  }).slice(-1)[0];
}

module.exports = { EMA, RSI, MACD, ATR, BB };
