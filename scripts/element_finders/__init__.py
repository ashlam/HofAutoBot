from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class ElementFinder(ABC):
    @abstractmethod
    def find_element(self, driver, element_info, container_info=None, timeout=10):
        pass

class HtmlElementFinder(ElementFinder):
    def find_element(self, driver, element_info, container_info=None, timeout=10):
        from scripts.element_finder import find_element_by_html
        return find_element_by_html(driver, element_info, container_info, timeout)

class TextAndUrlElementFinder(ElementFinder):
    def find_element(self, driver, text, url, timeout=10):
        from scripts.element_finder import find_element_by_text_and_url
        return find_element_by_text_and_url(driver, text, url)

class SimpleTextElementFinder(ElementFinder):
    def find_element(self, driver, text, timeout=10):
        try:
            xpath = f"//a[contains(text(),'{text}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    return element
            return None
        except Exception:
            return None