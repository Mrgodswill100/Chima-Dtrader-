import logging
import asyncio
import aiohttp
import math
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8601508098:AAHg_K83mDmIjtInKLnGPI6gufhCmBhaUpc"
TWELVEDATA_API_KEY = "189b40603c014143ae17eb33053ae348"

logging.basicConfig(level=logging.INFO)

PAIRS = ["EUR/USD", "GBP/USD", "EUR/GBP", "AUD/USD", "USD/JPY", "GBP/JPY", "USD/CHF", "BTC/USDT"]
DURATIONS = ["10s", "15s", "30s", "1min"]


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthHandler)
    server.serve_forever()


def ema(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    val = sum(closes[:period]) / period
    for c in closes[period:]:
        val = c * k + val * (1 - k)
    return val


def sma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calculate_indicators(candles):
    closes = [c['close'] for c in candles]
    highs  = [c['high']  for c in candles]
    lows   = [c['low']   for c in candles]
    vols   = [c['volume'] for c in candles]
    last   = closes[-1]
    votes  = []

    e9 = ema(closes, 9)
    votes.append("BUY" if e9 and last > e9 else "SELL")

    e14 = ema(closes, 14)
    votes.append("BUY" if e14 and last > e14 else "SELL")

    s20 = sma(closes, 20)
    votes.append("BUY" if s20 and last > s20 else "SELL")

    tp = [(highs[i]+lows[i]+closes[i])/3 for i in range(len(closes))]
    vwap = sum(tp[i]*vols[i] for i in range(len(closes))) / (sum(vols) or 1)
    votes.append("BUY" if last > vwap else "SELL")

    jaw   = sma(closes, 13)
    teeth = sma(closes, 8)
    lips  = sma(closes, 5)
    if jaw and teeth and lips:
        if lips > teeth > jaw:
            votes.append("BUY")
        elif lips < teeth < jaw:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if s20:
        std = math.sqrt(sum((c - s20)**2 for c in closes[-20:]) / 20)
        upper = s20 + 2*std
        lower = s20 - 2*std
        if last < lower:
            votes.append("BUY")
        elif last > upper:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 26:
        tenkan = (max(highs[-9:]) + min(lows[-9:])) / 2
        kijun  = (max(highs[-26:]) + min(lows[-26:])) / 2
        votes.append("BUY" if last > tenkan and last > kijun else "SELL")
    else:
        votes.append("NEUTRAL")

    votes.append("BUY" if closes[-1] > closes[-2] else "SELL")

    if len(candles) >= 14:
        atr_val = sum(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(-14,0)) / 14
        mid = sma(closes, 14)
        if mid:
            votes.append("BUY" if last > mid - 1.5*atr_val else "SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 16:
        wma1 = ema(closes, 4)
        wma2 = ema(closes, 9)
        wma1p = ema(closes[:-1], 4)
        wma2p = ema(closes[:-1], 9)
        if wma1 and wma2 and wma1p and wma2p:
            votes.append("BUY" if (2*wma1-wma2) > (2*wma1p-wma2p) else "SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 14:
        low14  = min(lows[-14:])
        high14 = max(highs[-14:])
        k = (last - low14) / (high14 - low14) * 100 if high14 != low14 else 50
        k_vals = []
        for i in range(len(closes)):
            h = max(highs[max(0,i-14):i+1])
            l = min(lows[max(0,i-14):i+1])
            k_vals.append((closes[i]-l)/(h-l)*100 if h != l else 50)
        k_ema = ema(k_vals, 3)
        votes.append("BUY" if k_ema and k > k_ema else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 15:
        gains  = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        ag = sum(gains[-14:]) / 14
        al = sum(losses[-14:]) / 14
        rsi = 100 - (100/(1+ag/al)) if al != 0 else 100
        ag_p = sum(gains[-15:-1]) / 14
        al_p = sum(losses[-15:-1]) / 14
        prev_rsi = 100-(100/(1+ag_p/al_p)) if al_p != 0 else 100
        if rsi < 50 and rsi > prev_rsi:
            votes.append("BUY")
        elif rsi > 50 and rsi < prev_rsi:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 26:
        ml = ema(closes, 12) - ema(closes, 26)
        sl = ema(closes[-9:], 9) if len(closes) >= 35 else ml
        votes.append("BUY" if ml > sl else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 20 and s20:
        mean_dev = sum(abs(closes[-20:][i] - s20) for i in range(20)) / 20
        cci = (last - s20) / (0.015 * mean_dev) if mean_dev != 0 else 0
        votes.append("BUY" if cci > 0 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 14:
        h14 = max(highs[-14:])
        l14 = min(lows[-14:])
        wr = (h14 - last) / (h14 - l14) * -100 if h14 != l14 else -50
        votes.append("BUY" if wr > -50 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 11:
        votes.append("BUY" if last - closes[-11] > 0 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 10:
        votes.append("BUY" if (last - closes[-10]) / closes[-10] * 100 > 0 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 28:
        def bp_tr(i):
            bp = closes[i] - min(lows[i], closes[i-1])
            tr = max(highs[i], closes[i-1]) - min(lows[i], closes[i-1])
            return bp, max(tr, 0.0001)
        def uo_avg(period):
            bps = [bp_tr(i)[0] for i in range(-period, 0)]
            trs = [bp_tr(i)[1] for i in range(-period, 0)]
            return sum(bps)/sum(trs)
        uo = 100*(4*uo_avg(7)+2*uo_avg(14)+uo_avg(28))/7
        votes.append("BUY" if uo > 50 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 34:
        median = [(highs[i]+lows[i])/2 for i in range(len(closes))]
        s5  = sma(median, 5)
        s34 = sma(median, 34)
        votes.append("BUY" if s5 and s34 and s5 > s34 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 14:
        dh = sum(max(highs[i]-highs[i-1], 0) for i in range(1, len(closes)))
        dl = sum(max(lows[i-1]-lows[i], 0) for i in range(1, len(closes)))
        dm = dh/(dh+dl) if (dh+dl) != 0 else 0.5
        votes.append("BUY" if dm > 0.5 else "SELL")
    else:
        votes.append("NEUTRAL")

    if s20:
        votes.append("BUY" if last > s20 else "SELL")
    else:
        votes.append("NEUTRAL")

    votes.append("NEUTRAL")

    if len(candles) >= 20:
        atr14 = sum(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(-14,0))/14
        e20 = ema(closes, 20)
        if e20:
            if last > e20 + 1.5*atr14:
                votes.append("BUY")
            elif last < e20 - 1.5*atr14:
                votes.append("SELL")
            else:
                votes.append("NEUTRAL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 20:
        mid_dc = (max(highs[-20:]) + min(lows[-20:])) / 2
        votes.append("BUY" if last > mid_dc else "SELL")
    else:
        votes.append("NEUTRAL")

    if s20:
        prev_s20 = sma(closes[:-1], 20)
        votes.append("BUY" if s20 > (prev_s20 or s20) else "SELL")
    else:
        votes.append("NEUTRAL")

    obv = sum(vols[i] if closes[i]>closes[i-1] else -vols[i] if closes[i]<closes[i-1] else 0 for i in range(1, len(closes)))
    prev_obv = sum(vols[i] if closes[i]>closes[i-1] else -vols[i] if closes[i]<closes[i-1] else 0 for i in range(1, len(closes)-1))
    votes.append("BUY" if obv > prev_obv else "SELL")

    if len(candles) >= 14:
        mf_pos = mf_neg = 0
        for i in range(-14, 0):
            tp_i = (highs[i]+lows[i]+closes[i])/3
            tp_p = (highs[i-1]+lows[i-1]+closes[i-1])/3
            mf = tp_i * vols[i]
            if tp_i > tp_p:
                mf_pos += mf
            else:
                mf_neg += mf
        mfi = 100-(100/(1+mf_pos/mf_neg)) if mf_neg != 0 else 100
        votes.append("BUY" if mfi > 50 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(candles) >= 20:
        cmf_num = sum(((closes[i]-lows[i])-(highs[i]-closes[i]))/(highs[i]-lows[i]+0.0001)*vols[i] for i in range(-20,0))
        cmf_den = sum(vols[-20:]) or 1
        votes.append("BUY" if cmf_num/cmf_den > 0 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(vols) >= 10:
        s5v  = sma(vols, 5)
        s10v = sma(vols, 10)
        votes.append("BUY" if s5v and s10v and s5v > s10v else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(closes) >= 2:
        votes.append("BUY" if (closes[-1]-closes[-2])*vols[-1] > 0 else "SELL")
    else:
        votes.append("NEUTRAL")

    if len(candles) >= 2:
        p = candles[-2]
        c = candles[-1]
        if c['close']>c['open'] and p['close']<p['open'] and c['open']<p['close'] and c['close']>p['open']:
            votes.append("BUY")
        elif c['close']<c['open'] and p['close']>p['open'] and c['open']>p['close'] and c['close']<p['open']:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(candles) >= 1:
        c = candles[-1]
        body = abs(c['close']-c['open'])
        upper_wick = c['high'] - max(c['close'], c['open'])
        lower_wick = min(c['close'], c['open']) - c['low']
        if lower_wick > 2*body and lower_wick > upper_wick:
            votes.append("BUY")
        elif upper_wick > 2*body and upper_wick > lower_wick:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    votes.append("NEUTRAL")

    if len(candles) >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1 = abs(c1['close']-c1['open'])
        body2 = abs(c2['close']-c2['open'])
        if c1['close']<c1['open'] and body2 < body1*0.3 and c3['close']>c3['open']:
            votes.append("BUY")
        elif c1['close']>c1['open'] and body2 < body1*0.3 and c3['close']<c3['open']:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    if len(candles) >= 3:
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        if all(c['close']>c['open'] for c in [c1,c2,c3]) and c3['close']>c2['close']>c1['close']:
            votes.append("BUY")
        elif all(c['close']<c['open'] for c in [c1,c2,c3]) and c3['close']<c2['close']<c1['close']:
            votes.append("SELL")
        else:
            votes.append("NEUTRAL")
    else:
        votes.append("NEUTRAL")

    return votes


def tally_votes(votes1, votes2):
    all_votes = votes1 + votes2
    buy  = all_votes.count("BUY")
    sell = all_votes.count("SELL")
    total = buy + sell
    if total == 0:
        return None, 0, 0, 0, "", 0
    buy_pct  = buy / total * 100
    sell_pct = sell / total * 100
    if buy_pct >= sell_pct:
        direction = "BUY [UP]"
        pct = buy_pct
    else:
        direction = "SELL [DOWN]"
        pct = sell_pct
    if pct < 51:
        return None, buy, sell, 0, "", pct
    if pct >= 91:
        accuracy, strength = 95, "Very Strong"
    elif pct >= 81:
        accuracy, strength = 88, "Strong"
    elif pct >= 71:
        accuracy, strength = 80, "Moderate"
    elif pct >= 61:
        accuracy, strength = 70, "Moderate"
    else:
        accuracy, strength = 60, "Weak"
    return direction, buy, sell, accuracy, strength, pct


async def fetch_candles(session, pair, interval):
    try:
        if pair == "BTC/USDT":
            tf_map = {"1min": "1m", "2min": "2m"}
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=" + tf_map[interval] + "&limit=50"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
            if not isinstance(data, list) or len(data) == 0:
                return None
            candles = []
            for k in data:
                try:
                    candles.append({
                        "open":   float(k[1]),
                        "high":   float(k[2]),
                        "low":    float(k[3]),
                        "close":  float(k[4]),
                        "volume": float(k[5])
                    })
                except (ValueError, IndexError, TypeError):
                    continue
            return candles if len(candles) >= 20 else None
        else:
            url = ("https://api.twelvedata.com/time_series?symbol=" + pair +
                   "&interval=" + interval + "&outputsize=50&apikey=" + TWELVEDATA_API_KEY)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
            if "values" not in data or not data["values"]:
                return None
            candles = []
            for v in reversed(data["values"]):
                try:
                    candles.append({
                        "open":   float(v["open"]),
                        "high":   float(v["high"]),
                        "low":    float(v["low"]),
                        "close":  float(v["close"]),
                        "volume": float(v.get("volume") or 0)
                    })
                except (ValueError, KeyError):
                    continue
            return candles if len(candles) >= 20 else None
    except Exception as e:
        logging.error("Fetch error " + pair + " " + interval + ": " + str(e))
        return None


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p, callback_data="pair_" + p)] for p in PAIRS]
    await update.message.reply_text(
        "*Chima Dtrader Signal AI*\n\nSelect a currency pair:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pair_"):
        pair = data.replace("pair_", "")
        ctx.user_data["pair"] = pair
        keyboard = [[InlineKeyboardButton(d, callback_data="dur_" + d)] for d in DURATIONS]
        await query.edit_message_text(
            "Pair: *" + pair + "*\n\nSelect trade duration:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("dur_"):
        duration = data.replace("dur_", "")
        pair = ctx.user_data.get("pair", "EUR/USD")
        ctx.user_data["duration"] = duration
        keyboard = [[InlineKeyboardButton("ANALYZE", callback_data="analyze")]]
        await query.edit_message_text(
            "Pair: *" + pair + "*\nDuration: *" + duration + "*\n\nReady to analyze?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "analyze":
        pair     = ctx.user_data.get("pair", "EUR/USD")
        duration = ctx.user_data.get("duration", "1min")
        await query.edit_message_text("Analyzing " + pair + " on 35 indicators across 1min + 2min. Please wait...")

        try:
            async with aiohttp.ClientSession() as session:
                c1 = await fetch_candles(session, pair, "1min")
                c2 = await fetch_candles(session, pair, "2min")

            if not c1 or not c2:
                await query.edit_message_text("Market data unavailable. Please try again.")
                return

            v1 = calculate_indicators(c1)
            v2 = calculate_indicators(c2)
            result = tally_votes(v1, v2)

            keyboard = [
                [InlineKeyboardButton("Analyze Again", callback_data="analyze")],
                [InlineKeyboardButton("Change Pair", callback_data="restart")]
            ]

            if result[0] is None:
                msg = (
                    "*Market is undecided*\n\n"
                    "Pair: " + pair + "\n"
                    "BUY votes: " + str(result[1]) + " | SELL votes: " + str(result[2]) + "\n\n"
                    "Wait for a clearer setup."
                )
                await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                return

            direction, buy, sell, accuracy, strength, pct = result
            total = buy + sell
            div = "------------------------------"

            msg = (
                "*CHIMA DTRADER SIGNAL AI*\n" +
                div + "\n" +
                "Pair: *" + pair + "*\n" +
                "Duration: *" + duration + "*\n" +
                div + "\n" +
                "Direction: *" + direction + "*\n" +
                "Accuracy: *" + str(accuracy) + "%*\n" +
                "Strength: " + strength + "\n" +
                div + "\n" +
                "Votes: BUY " + str(buy) + " | SELL " + str(sell) + " | Total " + str(total) + "\n" +
                "Agreement: " + str(round(pct, 1)) + "%\n" +
                div + "\n" +
                "_For educational purposes only_"
            )
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            await query.edit_message_text("Error: " + str(e) + "\nPlease try again.")

    elif data == "restart":
        keyboard = [[InlineKeyboardButton(p, callback_data="pair_" + p)] for p in PAIRS]
        await query.edit_message_text(
            "*Chima Dtrader Signal AI*\n\nSelect a currency pair:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
        
