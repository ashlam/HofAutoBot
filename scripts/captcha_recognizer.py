import os
import io
import time
from typing import Tuple
from PIL import Image
from selenium.webdriver.common.by import By
import json

def _ensure_tesseract_path():
    try:
        import pytesseract
    except Exception:
        return False
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and os.path.exists(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return True
    common = ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]
    for p in common:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return True

def _capture_page_screenshot(driver):
    dpr = driver.execute_script("return window.devicePixelRatio") or 1
    png = driver.get_screenshot_as_png()
    img = Image.open(io.BytesIO(png))
    return img, dpr

def _get_element_rect(driver, elem):
    dpr = driver.execute_script("return window.devicePixelRatio") or 1
    rect = driver.execute_script(
        """
        var e = arguments[0];
        var r = e.getBoundingClientRect();
        var x = r.left, y = r.top, w = r.width, h = r.height;
        var f = window.frameElement;
        while (f) {
          var fr = f.getBoundingClientRect();
          x += fr.left;
          y += fr.top;
          f = f.ownerDocument.defaultView.frameElement;
        }
        return {x:x, y:y, width:w, height:h};
        """,
        elem,
    )
    return rect, dpr

def _crop_by_rect(img: Image.Image, rect: Tuple[float, float, float, float], dpr: float = 1.0) -> Image.Image:
    x, y, w, h = rect
    left = int(x * dpr)
    top = int(y * dpr)
    right = int((x + w) * dpr)
    bottom = int((y + h) * dpr)
    return img.crop((left, top, right, bottom))

def _preprocess_image_advanced(img):
    import numpy as np
    import cv2
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    den = cv2.medianBlur(gray, 3)
    _, bw = cv2.threshold(den, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    clean = cv2.morphologyEx(bw, cv2.MORPH_OPEN, ker, iterations=1)
    rgb = cv2.cvtColor(clean, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb)

def _normalize_digits(text, len_min=4, len_max=5):
    m = {"O": "0", "o": "0", "Q": "0", "l": "1", "I": "1", "|": "1", "J": "1", "Z": "2", "z": "2", "S": "5", "s": "5", "B": "8", "G": "6"}
    s = []
    for ch in text:
        if ch.isdigit():
            s.append(ch)
        elif ch in m:
            s.append(m[ch])
    digits = "".join(s)
    return digits

def _load_captcha_map(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        correct = set(data.get("correct_codes", []))
        wrong_map = dict(data.get("wrong_to_correct", {}))
        return {"correct_codes": correct, "wrong_to_correct": wrong_map}
    except Exception:
        return {"correct_codes": set(), "wrong_to_correct": {}}

def _apply_captcha_map_info(code, data):
    if not code:
        return code, "空值"
    if code in data.get("correct_codes", set()):
        return code, "直接匹配"
    mapped = data.get("wrong_to_correct", {}).get(code)
    if mapped:
        return mapped, f"映射自: {code}"
    return code, "未在表中"

def recognize_captcha(driver, selector="#captchaImage", attempts=5, interval=1.0, len_min=4, len_max=5, map_file=None):
    try:
        import pytesseract
    except Exception:
        return "", "依赖缺失"
    _ensure_tesseract_path()
    elem = driver.find_element(By.CSS_SELECTOR, selector)
    last = ""
    for _ in range(max(1, attempts)):
        rect, dpr = _get_element_rect(driver, elem)
        img, _dpr = _capture_page_screenshot(driver)
        crop = _crop_by_rect(img, (rect["x"], rect["y"], rect["width"], rect["height"]), dpr=dpr)
        processed = _preprocess_image_advanced(crop)
        config = "--psm 8 --oem 1 -c tessedit_char_whitelist=0123456789"
        text = pytesseract.image_to_string(processed, lang="eng", config=config).strip()
        digits = _normalize_digits(text, len_min=len_min, len_max=len_max)
        last = digits
        if len(digits) >= len_min and len(digits) <= len_max and digits.isdigit():
            break
        try:
            elem.click()
        except Exception:
            try:
                span = driver.find_element(By.XPATH, "//span[contains(@onclick, 'getCaptcha()')]")
                span.click()
            except Exception:
                pass
        time.sleep(interval)
    if map_file:
        data = _load_captcha_map(map_file)
        corrected, info = _apply_captcha_map_info(last, data)
        return corrected, info
    return last, "未在表中"

