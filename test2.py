from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import time

options = webdriver.ChromeOptions()
options.add_argument('--headless')  # 브라우저 띄우지 않기

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://www.11st.co.kr/products/pa/3616182485"
    driver.get(url)
    time.sleep(2)  # 페이지 로딩 대기

    # 2. 버튼 클릭 (해당 요소가 나타날 때까지 대기 후 클릭)
    button_xpath = '//*[@id="layBodyWrap"]/div/div/div/div/div[2]/div/div/p[2]/a'
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, button_xpath))).click()
    time.sleep(2)  # 클릭 후 로딩 대기

    # 3. 현재 페이지 소스 가져오기
    html = driver.page_source

    # 4. BeautifulSoup으로 파싱
    soup = BeautifulSoup(html, 'html.parser')

    # 5. 해당 input 태그 찾기
    input_tag = soup.select_one(
        '#layBodyWrap > div > div > div > div > div.l_product_buy_wrap.l_product_buy_wrap_amazon.fixed_sm.notranslate > div.l_product_buy_list > div > ul > li > div.c-card-item__info > dl > div.c-card-item__cart > dd > div > input'
    )

    # 6. value 값 추출
    if input_tag and input_tag.has_attr('value'):
        value = int(input_tag['value'])
        print('value:', value)
    else:
        print('해당 input 태그를 찾지 못했습니다.')

finally:
    driver.quit()