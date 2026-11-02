"""
End-to-end UI automation using Selenium WebDriver. Needs the app running
separately (python app.py) and Chrome installed.
Run: pytest tests/test_selenium_ui.py -v
"""
import uuid
import pytest

selenium = pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture()
def driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--use-fake-ui-for-media-stream")
    drv = webdriver.Chrome(options=options)
    drv.implicitly_wait(3)
    yield drv
    drv.quit()


def unique_email():
    return f"selenium_{uuid.uuid4().hex[:8]}@test.com"


def test_homepage_loads(driver):
    driver.get(BASE_URL)
    assert "Civic" in driver.title or "Civic" in driver.page_source


def test_user_can_register_and_login(driver):
    email = unique_email()
    driver.get(BASE_URL + "/register")
    driver.find_element(By.NAME, "name").send_keys("Selenium Tester")
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "password").send_keys("Secret123")
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

    WebDriverWait(driver, 5).until(EC.url_contains("/login"))
    driver.find_element(By.ID, "email-input").send_keys(email)
    driver.find_element(By.ID, "password-input").send_keys("Secret123")
    driver.find_element(By.ID, "login-btn").click()

    WebDriverWait(driver, 5).until(EC.url_contains("/complaints"))
    assert "complaints" in driver.page_source.lower()


def test_public_map_loads(driver):
    driver.get(BASE_URL + "/map")
    assert "map" in driver.page_source.lower()


def test_invalid_login_shows_error_message(driver):
    driver.get(BASE_URL + "/login")
    driver.find_element(By.ID, "email-input").send_keys("doesnotexist@test.com")
    driver.find_element(By.ID, "password-input").send_keys("WrongPass1")
    driver.find_element(By.ID, "login-btn").click()
    WebDriverWait(driver, 5).until(lambda d: "Invalid" in d.page_source)
    assert "Invalid email or password" in driver.page_source
