import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import time

# ----------- 크롤러 함수들 ---------------

def get_product_links():
    url = "https://m.11st.co.kr/page/a-category?sort=pop&fromPrice=5000&toPrice=7000"
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

TOKEN = "8406261198:AAEPTwxuvJx3CqOtmL3MmfOG38P8x89VLIg"  # 본인 봇 토큰으로 변경
CHAT_ID = 5002639138  # 본인 텔레그램 user id 또는 그룹 id로 변경

class BotState:
    def __init__(self):
        self.running = False
        self.sent_links = set()
        self.task = None

state = BotState()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.running:
        await context.bot.send_message(chat_id=CHAT_ID, text="이미 탐색 중입니다.")
        return

    state.running = True
    state.sent_links = set()
    await context.bot.send_message(chat_id=CHAT_ID, text="상품 탐색을 시작합니다!")

    async def crawl_and_send():
        while state.running:
            try:
                links = get_product_links()
                for link in links:
                    if link in state.sent_links:
                        continue
                    value = get_input_value_from_product(link)
                    if value == 1:
                        await context.bot.send_message(chat_id=CHAT_ID, text=link)
                        state.sent_links.add(link)
                await asyncio.sleep(300)
            except Exception as e:
                await context.bot.send_message(chat_id=CHAT_ID, text=f"에러 발생: {e}")
                await asyncio.sleep(30)

    state.task = asyncio.create_task(crawl_and_send())

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.running:
        await context.bot.send_message(chat_id=CHAT_ID, text="이미 중단 상태입니다.")
        return

    state.running = False
    if state.task:
        state.task.cancel()
        state.task = None
    state.sent_links = set()
    await context.bot.send_message(chat_id=CHAT_ID, text="탐색을 중단하고 초기화했습니다.")

# ----------- 봇 실행 ---------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    print("Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()

# 주의사항
# 1. 텔레그램으로 /start 명령어를 보내야 봇이 작동

# 개선 계획
# 1. 탐색 상품 카테고리 다양화 및 카테고리별 모듈화
# 2. 상품 가격 범위 조정 기능 추가
# 3. 텔레그램 봇 함수 이용하여 설정 변경 기능 추가
# 4. CAPTCHA 우회 기능 - user-agent 변경, 프록시 서버 사용 등
# 5. URL mobile용 → pc용 변경 기능 추가