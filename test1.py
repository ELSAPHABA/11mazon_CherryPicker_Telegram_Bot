from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from bs4 import BeautifulSoup

# 1. 셀레니움 드라이버 설정 및 페이지 접속
url = "https://m.11st.co.kr/page/a-category?sort=pop&fromPrice=5000&toPrice=7000"
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
driver.get(url)

# 2. 페이지 끝까지 스크롤
last_height = driver.execute_script("return document.body.scrollHeight")
while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

# 3. 페이지 소스 받아와서 BeautifulSoup으로 파싱
soup = BeautifulSoup(driver.page_source, "html.parser")

# 4. 상품 li 태그들 모두 추출
li_list = soup.select("#blckSn-7732 > li.l-grid__col.l-grid__col--12.medium-6")

# 5. 각 li에서 a href 링크 추출
links = []
for li in li_list:
    a_tag = li.select_one("div > div:nth-child(1) > div > a")
    if a_tag and a_tag.has_attr('href'):
        links.append(a_tag['href'])

driver.quit()

# 결과 출력
for link in links:
    print(link)