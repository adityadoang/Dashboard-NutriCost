import subprocess
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

p = subprocess.Popen(["streamlit", "run", "c:/projekin/metc-dt/utils/app.py", "--server.port", "8503", "--server.headless", "true"])
time.sleep(5)

try:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    
    driver.get("http://localhost:8503")
    time.sleep(5)
    
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    head_content = str(soup.head)
    
    if "dicoding" in head_content.lower():
        print("FOUND DICODING IN THE ACTUAL <HEAD>!")
    else:
        print("NOT FOUND IN HEAD.")
        
    driver.quit()
finally:
    p.kill()
