import asyncio
import json
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ----------- ChatIdManager 클래스 ---------------
class ChatIdManager:
    def __init__(self, filepath='chat_ids.json'):
        self.filepath = filepath
        self.chat_ids = self._load_ids()

    def _load_ids(self):
        if not os.path.exists(self.filepath):
            return set()
        try:
            with open(self.filepath, 'r') as f:
                return set(json.load(f))
        except (json.JSONDecodeError, FileNotFoundError):
            return set()

    def _save_ids(self):
        with open(self.filepath, 'w') as f:
            json.dump(list(self.chat_ids), f)

    def add_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.add(chat_id)
            self._save_ids()
            logging.info(f"새로운 chat_id {chat_id}가 등록되었습니다.")
            return True
        return False

    def remove_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)
            self._save_ids()
            logging.info(f"chat_id {chat_id}가 제거되었습니다.")

    def get_ids(self):
        return list(self.chat_ids)

# ----------- 봇 상태 및 설정 ---------------

CATEGORIES = {
    "1": {
        "name": "전체",
        "url": "https://m.11st.co.kr/page/a-category?sort=pop&fromPrice=5000&toPrice=7000"
    },
    "2": {
        "name": "식품/건강",
        "url": "https://m.11st.co.kr/page/a-category?dispCtgr1No=1149696&sort=pop&fromPrice=5000&toPrice=7000"
    },
    "3": {
        "name": "가전/디지털",
        "url": "https://m.11st.co.kr/page/a-category?dispCtgr1No=1149694&sort=pop&fromPrice=5000&toPrice=7000"
    },
    "4": {
        "name": "컴퓨터",
        "url": "https://m.11st.co.kr/page/a-category?dispCtgr1No=1149695&sort=pop&fromPrice=5000&toPrice=7000"
    }
}

class BotState:
    def __init__(self):
        self.running = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.sent_links = set()
        self.task = None
        self.current_url = None

state = BotState()

HELP_TEXT = """사용 가능한 명령어 안내

/help - 도움말을 표시합니다.
/start - 탐색할 카테고리를 선택하고 탐색을 시작합니다.
/pause - 진행 중인 탐색을 일시중지합니다.
/continue - 일시중지된 탐색을 재개합니다.
/stop - 탐색을 중단하고 상태를 초기화합니다.

사용 순서
1. /start 로 카테고리를 선택합니다.
2. 탐색 중 필요하면 /pause 로 일시중지합니다.
3. 다시 시작하려면 /continue 를 입력합니다.
4. 완전히 종료하려면 /stop 을 입력합니다.
"""

# ----------- 핸들러 함수들 ---------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(HELP_TEXT)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.running:
        await update.message.reply_text("이미 탐색 중입니다. 중단하려면 /stop을 입력하세요.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{key}. {cat['name']}", callback_data=key)] for key, cat in CATEGORIES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("탐색할 카테고리를 선택하세요:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category_key = query.data

    if state.running:
        await query.edit_message_text(text="이미 탐색이 진행 중입니다.")
        return

    category = CATEGORIES.get(category_key)
    if not category:
        await query.edit_message_text(text="잘못된 선택입니다.")
        return

    state.running = True
    state.sent_links = set()
    state.pause_event.set()
    state.current_url = category["url"]
    await query.edit_message_text(text=f"'{category['name']}' 카테고리 상품 탐색을 시작합니다!")
    
    # main.py에서 전달받은 크롤링 콜백 함수 실행
    if 'crawler_callback' in context.bot_data:
        state.task = asyncio.create_task(context.bot_data['crawler_callback'](context))

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.running:
        await update.message.reply_text("탐색이 시작되지 않았습니다. /start로 시작해주세요.")
        return
    if not state.pause_event.is_set():
        await update.message.reply_text("이미 일시중지 상태입니다.")
        return
    state.pause_event.clear()
    await update.message.reply_text("탐색을 일시중지합니다. /continue로 재개할 수 있습니다.")

async def continue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.running:
        await update.message.reply_text("탐색이 시작되지 않았습니다. /start로 시작해주세요.")
        return
    if state.pause_event.is_set():
        await update.message.reply_text("이미 탐색이 진행 중입니다. 일시중지하려면 /pause를 입력하세요.")
        return
    state.pause_event.set()
    await update.message.reply_text("탐색을 재개합니다.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.running:
        await update.message.reply_text("이미 중단 상태입니다.")
        return
    state.running = False
    if state.task:
        state.task.cancel()
        state.task = None
    state.current_url = None
    state.pause_event.set()
    state.sent_links = set()
    await update.message.reply_text("탐색을 중단하고 초기화했습니다.")

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.message.chat_id
        chat_id_manager: ChatIdManager = context.bot_data['chat_id_manager']
        if chat_id_manager.add_id(chat_id):
            await update.message.reply_text("알림 구독이 시작되었습니다. /help 로 사용 가능한 명령어를 확인하세요.")

def create_app(BOT_TOKEN, crawler_callback):
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN 값이 비어 있습니다.")

    chat_id_mgr = ChatIdManager('chat_ids.json')
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 데이터 및 콜백 주입
    app.bot_data['chat_id_manager'] = chat_id_mgr
    app.bot_data['crawler_callback'] = crawler_callback

    app.add_handler(MessageHandler(filters.COMMAND, register_user), group=-1)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("continue", continue_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    return app
