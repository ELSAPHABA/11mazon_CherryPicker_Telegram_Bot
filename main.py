import asyncio
import json
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.error import Forbidden, BadRequest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import time

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

# ----------- 크롤러 함수들 ---------------

def get_product_links(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    soup = BeautifulSoup(driver.page_source, "html.parser")
    li_list = soup.select("#blckSn-7732 > li.l-grid__col.l-grid__col--12.medium-6")
    links = []
    for li in li_list:
        a_tag = li.select_one("div > div:nth-child(1) > div > a")
        if a_tag and a_tag.has_attr('href'):
            link = a_tag['href']
            if link.startswith('/'):
                link = "https://m.11st.co.kr" + link
            links.append(link)
    driver.quit()
    return links

def get_input_value_from_product(product_url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(product_url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    btn = soup.select_one(
        "#layBodyWrap > div > div > div > div > div.l_product_buy_wrap.l_product_buy_wrap_amazon.fixed_sm.notranslate > div > div > p.btn > a"
    )

    value = None
    try:
        if btn:
            button_xpath = '//*[@id="layBodyWrap"]/div/div/div/div/div[2]/div/div/p[2]/a'
            try:
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, button_xpath))).click()
                time.sleep(2)
            except Exception as e:
                print(f"[{product_url}] 버튼 클릭 실패:", e)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            input_tag = soup.select_one(
                "#layBodyWrap > div > div > div > div > div.l_product_buy_wrap.l_product_buy_wrap_amazon.fixed_sm.notranslate > div.l_product_buy_list > div > ul > li > div.c-card-item__info > dl > div.c-card-item__cart > dd > div > input"
            )
        else:
            input_tag = soup.select_one(
                "#layBodyWrap > div > div > div > div > div.l_product_buy_wrap.l_product_buy_wrap_amazon.fixed_sm.notranslate > div.l_product_buy_list > div > ul > li > div > dl > div.c-card-item__cart > dd > div > input"
            )
        if input_tag and input_tag.has_attr('value'):
            value = int(input_tag['value'])
    except Exception as e:
        print(f"[{product_url}] 파싱 실패:", e)
    finally:
        driver.quit()
    return value

# ----------- 텔레그램 봇 설정 ---------------

TOKEN = "8406261198:AAEPTwxuvJx3CqOtmL3MmfOG38P8x89VLIg"  # 봇 토큰

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
        self.pause_event.set()  # 초기 상태는 '실행 중' (일시중지 아님)
        self.sent_links = set()
        self.task = None
        self.current_url = None

state = BotState()

async def crawl_and_send(context: ContextTypes.DEFAULT_TYPE, chat_id_manager: ChatIdManager):
    while state.running:
        try:
            await state.pause_event.wait()  # 일시중지 상태면 여기서 대기

            if not state.current_url:
                ids_to_remove = []
                for chat_id in chat_id_manager.get_ids():
                    await context.bot.send_message(chat_id=chat_id, text="오류: 탐색 URL이 설정되지 않았습니다. /stop 후 다시 시도해주세요.")
                for chat_id in ids_to_remove:
                    chat_id_manager.remove_id(chat_id)
                state.running = False
                break

            links = get_product_links(state.current_url)
            for link in links:
                await state.pause_event.wait()  # 각 링크 처리 전 일시중지 확인
                if not state.running:
                    break
                if link in state.sent_links:
                    continue
                value = get_input_value_from_product(link)
                if value == 1:
                    ids_to_remove = []
                    for chat_id in chat_id_manager.get_ids():
                        try:
                            await context.bot.send_message(chat_id=chat_id, text=link)
                        except (Forbidden, BadRequest) as e:
                            error_msg = str(e).lower()
                            if "chat not found" in error_msg or "bot was blocked" in error_msg or "user is deactivated" in error_msg:
                                logging.warning(f"메시지 전송 실패로 chat_id {chat_id}를 제거합니다: {e}")
                                ids_to_remove.append(chat_id)
                            else:
                                logging.error(f"chat_id {chat_id}로 메시지 전송 중 에러 발생: {e}")
                    
                    for chat_id in ids_to_remove:
                        chat_id_manager.remove_id(chat_id)
                    state.sent_links.add(link)
            
            if state.running:
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"크롤링 또는 메시지 전송 중 에러 발생: {e}")
            ids_to_remove = []
            for chat_id in chat_id_manager.get_ids():
                try:
                    await context.bot.send_message(chat_id=chat_id, text=f"에러 발생: {e}")
                except (Forbidden, BadRequest):
                    ids_to_remove.append(chat_id)
            for chat_id in ids_to_remove:
                chat_id_manager.remove_id(chat_id)
            await asyncio.sleep(30)

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
    chat_id_manager: ChatIdManager = context.bot_data['chat_id_manager']

    if state.running:
        await query.edit_message_text(text="이미 탐색이 진행 중입니다.")
        return

    category = CATEGORIES.get(category_key)
    if not category:
        await query.edit_message_text(text="잘못된 선택입니다.")
        return

    state.running = True
    state.sent_links = set()
    state.pause_event.set()  # 시작 시 항상 '실행' 상태로 설정
    state.current_url = category["url"]
    await query.edit_message_text(text=f"'{category['name']}' 카테고리 상품 탐색을 시작합니다!")
    state.task = asyncio.create_task(crawl_and_send(context, chat_id_manager))

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
    state.pause_event.set()  # 다음 시작을 위해 '실행' 상태로 리셋
    state.sent_links = set()
    await update.message.reply_text("탐색을 중단하고 초기화했습니다.")

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.message.chat_id
        chat_id_manager: ChatIdManager = context.bot_data['chat_id_manager']
        if chat_id_manager.add_id(chat_id):
            await update.message.reply_text("알림 구독이 시작되었습니다. /start 명령어로 탐색을 시작하세요.")

# ----------- 봇 실행 ---------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    chat_id_mgr = ChatIdManager('chat_ids.json')

    app = ApplicationBuilder().token(TOKEN).build()
    app.bot_data['chat_id_manager'] = chat_id_mgr

    app.add_handler(MessageHandler(filters.COMMAND, register_user), group=-1)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("continue", continue_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()

# 주의사항
# 1. 텔레그램으로 /start 명령어를 보내야 봇이 작동

# 개선 계획
# 1. 탐색 상품 카테고리 다양화 및 카테고리별 모듈화 > 완료, 카테고리 추가 예정
# 2. 상품 가격 범위 조정 기능 추가
# 3. 텔레그램 봇 함수 이용하여 설정 변경 기능 추가
# 4. CAPTCHA 우회 기능 - user-agent 변경, 프록시 서버 사용 등
# 5. URL mobile용 → pc용 변경 기능 추가
# 6. /pause, /continue, /stop 명령어 기능화 > 완료