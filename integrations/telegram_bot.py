import asyncio
import threading
import os
import requests
import MetaTrader5 as mt5
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import shared_state
from utils.logger import logger

import config
TOKEN = config.TELEGRAM_TOKEN

telegram_loop = None

def get_system_context() -> str:
    # Engine status
    bot_state = "IDLE (Stopped)"
    if shared_state.bot_running:
        bot_state = "ACTIVE (Running)"
    if shared_state.panic_mode:
        bot_state = "PANIC HALT"
    elif shared_state.soft_stop:
        bot_state = "SOFT STOP ACTIVE"
        
    engine_state = getattr(shared_state, "engine_state", "WAITING")
    
    # MT5 status
    broker_connected = "Disconnected"
    latency = "N/A"
    if shared_state.broker:
        broker_connected = "Connected" if shared_state.broker.check_connection() else "Disconnected"
        try:
            latency = f"{shared_state.broker.get_latency():.2f} ms"
        except Exception:
            pass

    # Account info
    balance_str = "N/A"
    equity_str = "N/A"
    free_margin_str = "N/A"
    try:
        acc = mt5.account_info()
        if acc:
            balance_str = f"${acc.balance:,.2f}"
            equity_str = f"${acc.equity:,.2f}"
            free_margin_str = f"${acc.free_margin:,.2f}"
    except Exception:
        pass

    # Open positions
    positions_str = "No open positions."
    try:
        pos_list = mt5.positions_get()
        if pos_list:
            positions_str = ""
            for pos in pos_list:
                p_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                positions_str += f"- Ticket #{pos.ticket} | {pos.symbol} | {p_type} | {pos.volume} lot | Profit: ${pos.profit:+.2f}\n"
    except Exception:
        pass

    # Performance
    pnl_today = "N/A"
    pnl_weekly = "N/A"
    win_rate = "N/A"
    total_trades = "N/A"
    try:
        if shared_state.storage:
            r_data = shared_state.storage.get_report_data()
            pnl_today = f"${r_data['today_profit']:+.2f}"
            pnl_weekly = f"${r_data['weekly_profit']:+.2f}"
            win_rate = f"{r_data['win_rate']:.1f}%"
            total_trades = str(r_data['total_trades'])
    except Exception:
        pass

    context = (
        f"You are the conversational assistant for 'Nur Trading Bot', an AI-powered XAUUSD (Gold) trading bot.\n"
        f"The user is chatting with you via Telegram. Answer their questions politely, professionally, and concisely in English or Hindi/Hinglish (matching their language preference).\n\n"
        f"Current Bot State:\n"
        f"- Engine Status: {bot_state}\n"
        f"- State Machine State: {engine_state}\n"
        f"- MT5 Connection: {broker_connected} (Latency: {latency})\n"
        f"- Account Balance: {balance_str}\n"
        f"- Account Equity: {equity_str}\n"
        f"- Free Margin: {free_margin_str}\n"
        f"- Open Positions:\n{positions_str}\n"
        f"- Performance Today: PnL {pnl_today}, Total Trades: {total_trades}, Win Rate: {win_rate}\n"
        f"- Performance Weekly: PnL {pnl_weekly}\n"
        f"- Trading Symbol: {config.SYMBOL}\n"
        f"- Trading Mode: {'PAPER TRADING' if config.PAPER_TRADING else 'LIVE TRADING'}\n\n"
        f"If the user asks you to start/stop/panic the bot, remind them that they can use the Telegram slash commands (like /start_trading, /stop, /panic) to execute those actions directly, but do not promise that you can run them directly from plain text conversation unless they run the command."
    )
    return context

def query_gemini(prompt: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        return "⚠️ Gemini API key is not configured in .env. Please add GEMINI_API_KEY to your .env file."
        
    context = get_system_context()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"{context}\n\nUser Message: {prompt}\nResponse:"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()
        else:
            logger.error(f"Gemini API error (status {response.status_code}): {response.text}")
            return "Sorry, I had trouble processing that request via the Gemini API."
    except Exception as e:
        logger.error(f"Exception during Gemini query: {e}")
        return "An error occurred while connecting to the AI service."

def restricted(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        if config.ALLOWED_CHAT_IDS and chat_id not in config.ALLOWED_CHAT_IDS:
            logger.warning(f"Unauthorized access attempt by Chat ID: {chat_id}")
            try:
                await update.message.reply_text("❌ *Unauthorized:* You are not permitted to control this bot.", parse_mode="Markdown")
            except Exception:
                pass
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_state.chat_id = update.effective_chat.id
    logger.info(f"📱 Telegram bot connected to Chat ID: {shared_state.chat_id}")
    await update.message.reply_text(
        "🤖 <b>NUR BOT CONNECTED</b>\n\n"
        "Available Commands:\n"
        "▶️ /start_trading - Enable trading loop\n"
        "🛑 /stop - Soft stop (cease new entries)\n"
        "📊 /status - System health and MT5 latency\n"
        "💰 /balance - Balance & equity\n"
        "📈 /positions - Active positions list\n"
        "📝 /report - PnL statistics summary\n"
        "🚨 /panic - EMERGENCY close all and halt"
    , parse_mode="HTML")

@restricted
async def stop_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_state.bot_running = False
    logger.info("🛑 Bot stopped trading via Telegram command.")
    await update.message.reply_text("🛑 <b>Trading Stopped (Bot Idle)</b>", parse_mode="HTML")

@restricted
async def start_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_state.bot_running = True
    shared_state.panic_mode = False
    shared_state.soft_stop = False
    shared_state.hard_stop = False
    logger.info("▶️ Bot started trading via Telegram command.")
    await update.message.reply_text("▶️ <b>Trading Started (Active)</b>", parse_mode="HTML")

@restricted
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Latency check
    latency = "N/A"
    broker_connected = "Disconnected"
    if shared_state.broker:
        broker_connected = "Connected" if shared_state.broker.check_connection() else "Disconnected"
        try:
            latency = f"{shared_state.broker.get_latency():.2f} ms"
        except Exception:
            pass
            
    bot_state = "IDLE (Stopped)"
    if shared_state.bot_running:
        bot_state = "ACTIVE"
    if shared_state.panic_mode:
        bot_state = "PANIC HALT"
    elif shared_state.soft_stop:
        bot_state = "SOFT STOP ACTIVE"
        
    engine_state = getattr(shared_state, "engine_state", "WAITING")

    msg = (
        f"📊 <b>NUR BOT STATUS</b>\n"
        f"▪️ <b>Engine Running:</b> {bot_state}\n"
        f"▪️ <b>State Machine:</b> {engine_state}\n"
        f"▪️ <b>MT5 Connection:</b> {broker_connected}\n"
        f"▪️ <b>MT5 Latency:</b> {latency}\n"
        f"▪️ <b>Soft Stop:</b> {shared_state.soft_stop}\n"
        f"▪️ <b>Panic Mode:</b> {shared_state.panic_mode}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

@restricted
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc = mt5.account_info()
    if acc is None:
        await update.message.reply_text("❌ Failed to fetch account information.")
        return
        
    msg = (
        f"💰 <b>ACCOUNT BALANCE</b>\n"
        f"▪️ <b>Balance:</b> ${acc.balance:,.2f}\n"
        f"▪️ <b>Equity:</b> ${acc.equity:,.2f}\n"
        f"▪️ <b>Margin Free:</b> ${acc.free_margin:,.2f}\n"
        f"▪️ <b>Leverage:</b> 1:{acc.leverage}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

@restricted
async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Retrieve positions directly from MT5
    pos_list = mt5.positions_get()
    if pos_list is None or len(pos_list) == 0:
        await update.message.reply_text("📭 No open positions.")
        return
        
    msg = "📈 <b>ACTIVE POSITIONS:</b>\n"
    for pos in pos_list:
        p_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        msg += f"▪️ #{pos.ticket} | {pos.symbol} | <b>{p_type}</b> | {pos.volume} lot | profit: <b>${pos.profit:+.2f}</b>\n"
        
    await update.message.reply_text(msg, parse_mode="HTML")

@restricted
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not shared_state.storage:
        await update.message.reply_text("❌ Database not initialized.")
        return
        
    r_data = shared_state.storage.get_report_data()
    agg = shared_state.storage.get_aggregated_stats()
    
    msg = (
        f"📝 <b>PERFORMANCE REPORT</b>\n"
        f"▪️ <b>Today's Profit:</b> ${r_data['today_profit']:+.2f}\n"
        f"▪️ <b>Weekly Profit:</b> ${r_data['weekly_profit']:+.2f}\n"
        f"▪️ <b>Total Profit:</b> ${r_data['total_profit']:+.2f}\n"
        f"▪️ <b>Total Trades:</b> {r_data['total_trades']}\n"
        f"▪️ <b>Win Rate:</b> {r_data['win_rate']:.1f}%\n"
        f"▪️ <b>Max Drawdown:</b> ${r_data['max_drawdown']:.2f}\n"
        f"▪️ <b>Profit Factor:</b> {agg['profit_factor']:.2f}\n"
        f"▪️ <b>Recovery Factor:</b> {agg['recovery_factor']:.2f}\n\n"
        f"📈 <b>Last 5 Trades:</b>\n"
    )
    
    if r_data["last_5"]:
        for t in r_data["last_5"]:
            msg += f"• #{t['ticket']} {t['symbol']} {t['type']} ({t['volume']} lot): <b>{t['profit']:+.2f}$</b> ({t['reason']})\n"
    else:
        msg += "No closed trades recorded."
        
    await update.message.reply_text(msg, parse_mode="HTML")

@restricted
async def panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared_state.panic_mode = True
    shared_state.bot_running = False
    shared_state.hard_stop = True
    
    logger.warning("🚨 Telegram initiated Emergency Panic Halt!")
    
    closed_count = 0
    if shared_state.broker:
        try:
            closed_count = shared_state.broker.panic_close_all("XAUUSD")
        except Exception as e:
            logger.error(f"Error during panic close: {e}")
            
    await update.message.reply_text(
        f"🚨 <b>PANIC DEPLOYED</b>\n"
        f"▪️ Emergency stop activated.\n"
        f"▪️ Liquidated <b>{closed_count}</b> positions.\n"
        f"▪️ Bot execution loop halted.",
        parse_mode="HTML"
    )

@restricted
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    if not user_msg:
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    loop = asyncio.get_running_loop()
    reply = await loop.run_in_executor(None, query_gemini, user_msg)
    await update.message.reply_text(reply)

def run_telegram():
    global telegram_loop
    # Configure event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    telegram_loop = loop

    from telegram.request import HTTPXRequest
    request_config = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(request_config).build()

    # Thread-safe message sender
    async def send_msg(text):
        if shared_state.chat_id:
            try:
                # Use Markdown-safe messages or fallback if parsing fails
                try:
                    await app.bot.send_message(chat_id=shared_state.chat_id, text=text, parse_mode="Markdown")
                except Exception:
                    await app.bot.send_message(chat_id=shared_state.chat_id, text=text)
            except Exception as e:
                logger.error(f"❌ Failed to send Telegram alert: {e}")

    def safe_send(text):
        if telegram_loop and telegram_loop.is_running():
            asyncio.run_coroutine_threadsafe(send_msg(text), telegram_loop)
        else:
            logger.warning(f"⚠️ Telegram event loop not running. Alert: {text}")

    # Set callback in shared state
    shared_state.send_message = safe_send

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_trading))
    app.add_handler(CommandHandler("start_trading", start_trading))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("panic", panic))
    
    # Conversational chat handler for general text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    logger.info("📡 Telegram bot starting polling loop...")
    
    # Run polling under this thread's event loop
    app.run_polling()