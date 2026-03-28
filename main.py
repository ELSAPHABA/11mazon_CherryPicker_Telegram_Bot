# main.py

import asyncio
import logging
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest
from elevenmazon_crawler import get_product_links, get_input_value_from_product
import Telegram_bot
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # 봇 토큰

async def crawl_and_send(context: ContextTypes.DEFAULT_TYPE):
    chat_id_manager = context.bot_data['chat_id_manager']
    
    while Telegram_bot.state.running:
        try:
            await Telegram_bot.state.pause_event.wait()  # 일시중지 상태면 여기서 대기

            if not Telegram_bot.state.current_url:
                ids_to_remove = []
                for chat_id in chat_id_manager.get_ids():
                    await context.bot.send_message(chat_id=chat_id, text="오류: 탐색 URL이 설정되지 않았습니다. /stop 후 다시 시도해주세요.")
                for chat_id in ids_to_remove:
                    chat_id_manager.remove_id(chat_id)
                Telegram_bot.state.running = False
                break

            links = get_product_links(Telegram_bot.state.current_url)
            for link in links:
                await Telegram_bot.state.pause_event.wait()  # 각 링크 처리 전 일시중지 확인
                if not Telegram_bot.state.running:
                    break
                if link in Telegram_bot.state.sent_links:
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
                    Telegram_bot.state.sent_links.add(link)
            
            if Telegram_bot.state.running:
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

# ----------- 봇 실행 ---------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN이 .env에 설정되어 있지 않습니다.")

    app = Telegram_bot.create_app(BOT_TOKEN, crawl_and_send)
    print("Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()

''' 
주의사항
1. 텔레그램으로 /start 명령어를 보내야 봇이 작동

개선 계획
1. 탐색 상품 카테고리 추가
2. 상품 가격 범위 조정 기능 추가 (&fromPrice=5000&toPrice=7000 쿼리 봇 실행시 입력)
3. 텔레그램 봇 함수 이용하여 설정 변경 기능 추가
4. CAPTCHA 우회 기능 - user-agent 변경, 프록시 서버 사용 등
5. URL mobile용 → pc용 변경 기능 추가
6. /Restart 명령어 구현
7. README 작성
'''