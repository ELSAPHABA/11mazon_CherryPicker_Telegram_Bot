from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import time

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