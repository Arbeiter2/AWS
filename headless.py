from selenium import selenium, webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
import time


def doLogin(browser):
    browser.get("http://www.airwaysim.com") # Load page
    time.sleep(0.2)
    assert "AirwaySim" in browser.title

    selenium.wait_for_page_to_load(5000)

    try:
        loginLink = browser.find_element_by_link_text("Login")
    except InvalidSelectorException:
        return True
        
    browser.get("http://www.airwaysim.com/Login") # Load page
    selenium.wait_for_page_to_load(5000)

    name = browser.find_element_by_id("name") # Find the query box
    pwd = browser.find_element_by_id("passwrd") # Find the query box

    name.send_keys("SteveHunt")
    pwd.send_keys("hekmatyar9")

    browser.find_element_by_id("submitBtn").click()
    selenium.wait_for_page_to_load(5000)

    return True

browser = webdriver.Chrome() # Get local session of chrome

doLogin(browser)
print(browser.get_cookies())


browser.close()
