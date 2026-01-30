import argparse
import io
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple
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
    common_paths = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
    ]
    for p in common_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return True


def generate_image(text="1234 ABC", width=300, height=120, font_size=42):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = None
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    for path in candidates:
        try:
            if os.path.exists(path):
                font = ImageFont.truetype(path, font_size)
                break
        except Exception:
            pass
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            pass
    tw, th = draw.textsize(text, font=font)
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill=(0, 0, 0), font=font)
    return img


def preprocess_image(img, scale=2, threshold=160):
    gray = img.convert("L")
    bw = gray.point(lambda x: 255 if x > threshold else 0, "1")
    if scale and scale > 1:
        w, h = bw.size
        bw = bw.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
    return bw.convert("RGB")

def preprocess_image_advanced(img, scale=2):
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
    if scale and scale > 1:
        clean = cv2.resize(clean, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    rgb = cv2.cvtColor(clean, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb)

def normalize_digits(text, len_min=4, len_max=5):
    mapping = {
        "O": "0", "o": "0", "Q": "0",
        "l": "1", "I": "1", "|": "1", "J": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "B": "8",
        "G": "6",
    }
    s = []
    for ch in text:
        if ch.isdigit():
            s.append(ch)
        elif ch in mapping:
            s.append(mapping[ch])
    digits = "".join(s)
    if len_min and len_max and (len(digits) < len_min or len(digits) > len_max):
        return digits
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

def _save_captcha_map(path, data):
    out = {
        "correct_codes": sorted(list(data.get("correct_codes", set()))),
        "wrong_to_correct": dict(data.get("wrong_to_correct", {}))
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def _apply_captcha_map_info(code, data):
    if not code:
        return code, "空值"
    if code in data.get("correct_codes", set()):
        return code, "直接匹配"
    mapped = data.get("wrong_to_correct", {}).get(code)
    if mapped:
        return mapped, f"映射自: {code}"
    return code, "未在表中"

def run_tesseract(img, lang="eng", preprocess_mode="advanced", digits_only=False, len_min=4, len_max=5):
    try:
        import pytesseract
    except Exception as e:
        print("未安装 pytesseract")
        raise e
    _ensure_tesseract_path()
    processed = preprocess_image_advanced(img) if preprocess_mode == "advanced" else preprocess_image(img)
    config = "--psm 8 --oem 1"
    if digits_only:
        config += " -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(processed, lang=lang, config=config)
    out = text.strip()
    if digits_only:
        out = normalize_digits(out, len_min=len_min, len_max=len_max)
    return out


def run_paddleocr(img, lang="en"):
    try:
        from paddleocr import PaddleOCR
    except Exception as e:
        print("未安装 paddleocr")
        raise e
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        processed = preprocess_image(img)
        processed.save(tf.name)
        temp_path = tf.name
    ocr = PaddleOCR(lang=lang)
    result = ocr.ocr(temp_path)
    os.unlink(temp_path)
    lines = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, list):
                for _, rec in item:
                    if isinstance(rec, tuple) and len(rec) > 0:
                        lines.append(str(rec[0]))
    return "\n".join(lines).strip()

def run_easyocr(img, langs=None, digits_only=False, len_min=4, len_max=5, min_conf=0.3, preprocess_mode="advanced"):
    try:
        import easyocr
        import numpy as np
    except Exception as e:
        print("未安装 easyocr")
        raise e
    if langs is None:
        langs = ["en"]
    arr = np.array(preprocess_image_advanced(img) if preprocess_mode == "advanced" else preprocess_image(img))
    reader = easyocr.Reader(langs, gpu=False)
    result = reader.readtext(arr)
    if digits_only:
        best = ""
        best_conf = -1.0
        for r in result:
            if isinstance(r, (list, tuple)) and len(r) >= 3:
                text = str(r[1])
                conf = float(r[2])
                if conf < min_conf:
                    continue
                digits = normalize_digits(text, len_min=len_min, len_max=len_max)
                if len(digits) >= len_min and len(digits) <= len_max and conf > best_conf:
                    best = digits
                    best_conf = conf
        if best:
            return best
        parts = []
        for r in result:
            if isinstance(r, (list, tuple)) and len(r) >= 2:
                parts.append(normalize_digits(str(r[1]), len_min=len_min, len_max=len_max))
        joined = "".join(parts).strip()
        if not joined and preprocess_mode == "advanced":
            arr2 = np.array(preprocess_image(img))
            result2 = reader.readtext(arr2)
            parts2 = []
            for r in result2:
                if isinstance(r, (list, tuple)) and len(r) >= 2:
                    parts2.append(normalize_digits(str(r[1]), len_min=len_min, len_max=len_max))
            return "".join(parts2).strip()
        return joined
    else:
        lines = []
        for r in result:
            if isinstance(r, (list, tuple)) and len(r) >= 2:
                lines.append(str(r[1]))
        return "\n".join(lines).strip()

def _parse_rect(rect: str) -> Tuple[float, float, float, float]:
    parts = rect.split(",")
    x, y, w, h = [float(p.strip()) for p in parts]
    return x, y, w, h


def _crop_by_rect(img: Image.Image, rect: Tuple[float, float, float, float], dpr: float = 1.0, unit: str = "css") -> Image.Image:
    x, y, w, h = rect
    m = dpr if unit == "css" else 1.0
    left = int(x * m)
    top = int(y * m)
    right = int((x + w) * m)
    bottom = int((y + h) * m)
    return img.crop((left, top, right, bottom))


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


def _capture_page_screenshot(driver):
    dpr = driver.execute_script("return window.devicePixelRatio") or 1
    png = driver.get_screenshot_as_png()
    img = Image.open(io.BytesIO(png))
    return img, dpr


def capture_element_image(url, selector, wait_seconds=5, headless=True, keep_browser=False):
    from selenium.webdriver import Chrome
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    if keep_browser:
        options.add_experimental_option("detach", True)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    os.environ.setdefault("WDM_LOCAL", "1")
    driver = Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        elem = driver.find_element(By.CSS_SELECTOR, selector)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'})", elem)
        rect, dpr = _get_element_rect(driver, elem)
        img, _dpr = _capture_page_screenshot(driver)
        crop = _crop_by_rect(img, (rect["x"], rect["y"], rect["width"], rect["height"]), dpr=dpr, unit="css")
        return crop
    finally:
        try:
            if not keep_browser:
                driver.quit()
            else:
                driver.quit()
        except Exception:
            pass


def capture_element_image_by_xpath(url, xpath, wait_seconds=5, headless=True, keep_browser=False):
    from selenium.webdriver import Chrome
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    if keep_browser:
        options.add_experimental_option("detach", True)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    os.environ.setdefault("WDM_LOCAL", "1")
    driver = Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        elem = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'})", elem)
        rect, dpr = _get_element_rect(driver, elem)
        img, _dpr = _capture_page_screenshot(driver)
        crop = _crop_by_rect(img, (rect["x"], rect["y"], rect["width"], rect["height"]), dpr=dpr, unit="css")
        return crop
    finally:
        try:
            if not keep_browser:
                driver.quit()
            else:
                driver.quit()
        except Exception:
            pass


def capture_rect_image(url, rect_str, rect_unit="css", wait_seconds=5, headless=True, keep_browser=False):
    from selenium.webdriver import Chrome
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    if keep_browser:
        options.add_experimental_option("detach", True)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    os.environ.setdefault("WDM_LOCAL", "1")
    driver = Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        img, dpr = _capture_page_screenshot(driver)
        rect = _parse_rect(rect_str)
        crop = _crop_by_rect(img, rect, dpr=dpr, unit=rect_unit)
        return crop
    finally:
        try:
            if not keep_browser:
                driver.quit()
            else:
                driver.quit()
        except Exception:
            pass

def recognize_captcha_loop(url, selector=None, xpath=None, engine="tesseract", langs=None, digits_only=False, len_min=4, len_max=5, preprocess_mode="advanced", attempts=3, min_conf=0.3, wait_seconds=1.0, headless=True, keep_browser=False):
    from selenium.webdriver import Chrome
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    if keep_browser:
        options.add_experimental_option("detach", True)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    os.environ.setdefault("WDM_LOCAL", "1")
    driver = Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        elem = driver.find_element(By.CSS_SELECTOR, selector) if selector else driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'})", elem)
        last_out = ""
        for _ in range(max(1, attempts)):
            rect, dpr = _get_element_rect(driver, elem)
            img, _dpr = _capture_page_screenshot(driver)
            crop = _crop_by_rect(img, (rect["x"], rect["y"], rect["width"], rect["height"]), dpr=dpr, unit="css")
            if engine == "tesseract":
                out = run_tesseract(crop, preprocess_mode=preprocess_mode, digits_only=digits_only, len_min=len_min, len_max=len_max)
            elif engine == "easyocr":
                out = run_easyocr(crop, langs=langs, digits_only=digits_only, len_min=len_min, len_max=len_max, min_conf=min_conf, preprocess_mode=preprocess_mode)
            else:
                out = run_paddleocr(crop, lang=(langs[0] if langs else "en"))
            last_out = (out or "").strip()
            if digits_only and len(last_out) >= len_min and len(last_out) <= len_max and last_out.isdigit():
                break
            try:
                elem.click()
            except Exception:
                pass
            time.sleep(wait_seconds)
        return last_out
    finally:
        if not keep_browser:
            try:
                driver.quit()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["tesseract", "paddle", "easyocr"], default="tesseract")
    parser.add_argument("--lang", default="eng")
    parser.add_argument("--image")
    parser.add_argument("--text", default="1234 ABC")
    parser.add_argument("--url")
    parser.add_argument("--selector")
    parser.add_argument("--xpath")
    parser.add_argument("--rect")
    parser.add_argument("--rect_unit", choices=["css", "device"], default="css")
    parser.add_argument("--no_headless", action="store_true")
    parser.add_argument("--keep_browser", action="store_true")
    parser.add_argument("--digits_only", action="store_true")
    parser.add_argument("--len_min", type=int, default=4)
    parser.add_argument("--len_max", type=int, default=5)
    parser.add_argument("--min_conf", type=float, default=0.3)
    parser.add_argument("--preprocess", choices=["basic", "advanced"], default="advanced")
    parser.add_argument("--refresh_times", type=int, default=0)
    parser.add_argument("--map_file", default=os.path.join("configs", "captcha_map.json"))
    parser.add_argument("--no_map", action="store_true")
    parser.add_argument("--add_correct")
    parser.add_argument("--add_mapping", nargs=2)
    args = parser.parse_args()
    source_img = None
    headless = not args.no_headless
    keep_browser = args.keep_browser
    if args.add_correct or args.add_mapping:
        data = _load_captcha_map(args.map_file)
        if args.add_correct:
            code = normalize_digits(args.add_correct)
            if code:
                data["correct_codes"].add(code)
        if args.add_mapping:
            wrong = normalize_digits(args.add_mapping[0])
            right = normalize_digits(args.add_mapping[1])
            if wrong and right:
                data["wrong_to_correct"][wrong] = right
                data["correct_codes"].add(right)
        _save_captcha_map(args.map_file, data)
        print("OK")
        return
    if args.refresh_times and args.url and (args.selector or args.xpath):
        langs = ["ch_tra"] if args.lang.lower().startswith("chi") or args.lang.lower().startswith("zh") else ["en"]
        out = recognize_captcha_loop(
            url=args.url,
            selector=args.selector,
            xpath=args.xpath,
            engine=args.engine,
            langs=langs,
            digits_only=args.digits_only,
            len_min=args.len_min,
            len_max=args.len_max,
            preprocess_mode=args.preprocess,
            attempts=args.refresh_times,
            min_conf=args.min_conf,
            headless=headless,
            keep_browser=keep_browser
        )
        if not args.no_map and args.map_file:
            data = _load_captcha_map(args.map_file)
            corrected, info = _apply_captcha_map_info(out, data)
            print(f"{corrected} [{info}]")
        else:
            print(out)
        return
    if args.url and args.rect:
        source_img = capture_rect_image(args.url, args.rect, rect_unit=args.rect_unit, headless=headless, keep_browser=keep_browser)
    elif args.url and args.selector:
        source_img = capture_element_image(args.url, args.selector, headless=headless, keep_browser=keep_browser)
    elif args.url and args.xpath:
        source_img = capture_element_image_by_xpath(args.url, args.xpath, headless=headless, keep_browser=keep_browser)
    elif args.image:
        if args.rect:
            img = Image.open(args.image)
            rect = _parse_rect(args.rect)
            source_img = _crop_by_rect(img, rect, dpr=1.0, unit=args.rect_unit)
        else:
            source_img = Image.open(args.image)
    else:
        source_img = generate_image(args.text)
    if args.engine == "tesseract":
        out = run_tesseract(source_img, lang=args.lang, preprocess_mode=args.preprocess, digits_only=args.digits_only, len_min=args.len_min, len_max=args.len_max)
        if not args.no_map and args.map_file:
            data = _load_captcha_map(args.map_file)
            corrected, info = _apply_captcha_map_info(out, data)
            print(f"{corrected} [{info}]")
        else:
            print(out)
    else:
        if args.engine == "paddle":
            paddle_lang = "ch" if args.lang.lower().startswith("chi") or args.lang.lower().startswith("zh") else "en"
            print(run_paddleocr(source_img, lang=paddle_lang))
        else:
            langs = ["ch_tra"] if args.lang.lower().startswith("chi") or args.lang.lower().startswith("zh") else ["en"]
            out = run_easyocr(source_img, langs=langs, digits_only=args.digits_only, len_min=args.len_min, len_max=args.len_max, min_conf=args.min_conf, preprocess_mode=args.preprocess)
            if not args.no_map and args.map_file:
                data = _load_captcha_map(args.map_file)
                corrected, info = _apply_captcha_map_info(out, data)
                print(f"{corrected} [{info}]")
            else:
                print(out)


if __name__ == "__main__":
    main()
