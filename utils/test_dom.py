import subprocess
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Run streamlit
p = subprocess.Popen(["streamlit", "run", "c:/projekin/metc-dt/utils/app.py", "--server.port", "8502", "--server.headless", "true"])
time.sleep(5) # wait for server to start

try:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    
    driver.get("http://localhost:8502")
    time.sleep(5) # wait for streamlit to load react
    
    html = driver.page_source
    if "dicoding" in html.lower():
        print("FOUND DICODING IN DOM!")
        print(html.lower()[html.lower().find("dicoding")-20:html.lower().find("dicoding")+100])
    else:
        print("NOT FOUND IN DOM.")
        
    driver.quit()
finally:
    p.kill()
