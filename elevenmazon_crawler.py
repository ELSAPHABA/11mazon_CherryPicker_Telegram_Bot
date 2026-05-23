from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin
import time

PRODUCT_LINK_SELECTOR = (
    'a.c-card-item__link[href*="productBasicInfo.tmall"][href*="prdNo="], '
    'a[data-log-actionid-area="amz_productlist"][data-log-actionid-label="product"][href*="prdNo="]'
)


def _get_attr(element, name):
    return element.get(name) or ""


def _is_deal_block(element):
    block_type = f"{_get_attr(element, 'data-type')} {_get_attr(element, 'data-testid')}"
    return "Deal" in block_type


def _extract_links_from_grid(grid):
    links = []
    seen = set()

    for a_tag in grid.select(PRODUCT_LINK_SELECTOR):
        link = a_tag.get("href")
        if not link:
            continue

        link = urljoin("https://m.11st.co.kr", link)
        if link in seen:
            continue

        seen.add(link)
        links.append(link)

    return links


def extract_standard_product_links(page_source):
    soup = BeautifulSoup(page_source, "html.parser")

    product_grids = soup.select(
        '[data-type="ProductGrid_Standard"], [data-testid="ProductGrid_Standard"]'
    )
    if not product_grids:
        product_grids = [
            row
            for row in soup.select(".carrier-list .l-grid__row, .carrier-list ul")
            if row.select(PRODUCT_LINK_SELECTOR) and not _is_deal_block(row)
        ]

    links = []
    seen = set()
    for grid in product_grids:
        for link in _extract_links_from_grid(grid):
            if link in seen:
                continue
            seen.add(link)
            links.append(link)

    return links


def get_product_links(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)

        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        return extract_standard_product_links(driver.page_source)
    finally:
        driver.quit()

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
