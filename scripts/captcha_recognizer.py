import os
import io
import time
from typing import Tuple
from PIL import Image
import requests
from selenium.webdriver.common.by import By
import json

try:
    from scripts.captcha_fingerprint import phash
except ImportError:  # 作为脚本直接运行时的兜底
    from captcha_fingerprint import phash

# 单次识别最多刷新几张图。配置里写成 100 也按这个上限截断 —— 一次登录刷上百张图，
# 在任何一个站点眼里都跟压力测试没什么区别，不值得为了一次登录去冒这个险。
MAX_CAPTCHA_ATTEMPTS = 12


class CaptchaResult:
    """一次验证码识别的结果。

    兼容老写法 `code, info = recognize_captcha(...)`（只解出前两项），
    同时带上指纹与图片来源，方便调用方在登录成功后回写指纹库。
    """

    __slots__ = ('code', 'info', 'fingerprint', 'from_db', 'image')

    def __init__(self, code='', info='', fingerprint=None, from_db=False, image=None):
        self.code = code
        self.info = info
        self.fingerprint = fingerprint
        self.from_db = from_db
        self.image = image

    def __iter__(self):
        return iter((self.code, self.info))

    def __repr__(self):
        return f'CaptchaResult(code={self.code!r}, info={self.info!r}, from_db={self.from_db})'

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

def _get_captcha_src(driver, selector="#captchaImage"):
    try:
        elem = driver.find_element(By.CSS_SELECTOR, selector)
        src = driver.execute_script("return arguments[0].getAttribute('src')", elem)
        return src or ""
    except Exception:
        return ""

def _refresh_captcha_js(driver):
    """通过JS刷新验证码，避免触发前台焦点"""
    driver.execute_script(
        "var s=document.querySelector(\"span[onclick*='getCaptcha']\");"
        "if(s){try{s.click()}catch(e){}}"
        "else if(window.getCaptcha){try{getCaptcha()}catch(e){}}"
    )

def _download_image_by_cookies(driver, url):
    if not url:
        return None
    try:
        # 处理相对路径
        if url.startswith("/"):
            origin = driver.execute_script("return location.origin")
            url = origin + url
        cookies = driver.get_cookies()
        s = requests.Session()
        for c in cookies:
            s.cookies.set(c.get("name"), c.get("value"), domain=c.get("domain"), path=c.get("path"))
        r = s.get(url, timeout=5)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content))
    except requests.exceptions.RequestException:
        return None
    except (IOError, Image.UnidentifiedImageError):
        return None

def _grab_captcha_image(driver, elem, selector="#captchaImage"):
    """取验证码图片：优先按 cookie 直连下载（不触发前台焦点），失败再截屏裁剪。"""
    src = _get_captcha_src(driver, selector=selector)
    net_img = _download_image_by_cookies(driver, src)
    if net_img is not None:
        return net_img
    try:
        rect, dpr = _get_element_rect(driver, elem)
        shot, _dpr = _capture_page_screenshot(driver)
        return _crop_by_rect(shot, (rect["x"], rect["y"], rect["width"], rect["height"]), dpr=dpr)
    except Exception:
        return None


def _click_refresh(driver, elem):
    """刷新验证码：先点图片本身，失败再走页面上的刷新入口。"""
    try:
        driver.execute_script("if(arguments[0]) { try { arguments[0].click(); } catch(e){} }", elem)
        return True
    except Exception:
        pass
    try:
        _refresh_captcha_js(driver)
        return True
    except Exception:
        return False


def recognize_captcha_ex(driver, selector="#captchaImage", attempts=5, interval=1.0,
                         len_min=4, len_max=5, map_file=None, db=None):
    """识别验证码，返回 CaptchaResult。

    识别顺序（重要）：
      1. 先算图片指纹，查指纹库 —— 命中就直接用库里的答案，**完全不做 OCR**。
         这类验证码是服务端预生成的固定图池，同一个答案永远返回同一张图，
         所以命中即 100% 正确。
      2. 未命中才走 tesseract，并过一遍 captcha_map 白名单/纠错表。
      3. 结果不是 4~5 位数字就刷新验证码重来（最多 attempts 次）。

    任何异常都不会抛给调用方：最坏情况是返回空 code，由登录流程去决定重试还是转人工。
    """
    try:
        import pytesseract
    except Exception:
        return CaptchaResult('', '依赖缺失')
    _ensure_tesseract_path()

    try:
        elem = driver.find_element(By.CSS_SELECTOR, selector)
    except Exception as e:
        return CaptchaResult('', f'找不到验证码元素({type(e).__name__})')

    last = ''
    last_fp = None
    last_img = None
    try:
        asked = int(attempts)
    except (TypeError, ValueError):
        asked = 5
    tries = max(1, min(asked, MAX_CAPTCHA_ATTEMPTS))
    if asked > MAX_CAPTCHA_ATTEMPTS:
        print(f"[验证码] 配置的刷新次数 {asked} 超过上限 {MAX_CAPTCHA_ATTEMPTS}，按上限执行（避免把站点当压力测试）")

    for _ in range(tries):
        img = _grab_captcha_image(driver, elem, selector)
        if img is None:
            last = ''
        else:
            last_img = img
            try:
                last_fp = phash(img)
            except Exception:
                last_fp = None
            if db is not None and last_fp:
                try:
                    code, detail = db.lookup(last_fp)
                except Exception:
                    code, detail = None, {}
                if code and str(code).isdigit() and len_min <= len(str(code)) <= len_max:
                    how = '指纹精确命中' if detail.get('exact') else f'指纹命中(距离{detail.get("distance")})'
                    return CaptchaResult(str(code), f'{how}，库内 {detail.get("entries")} 张',
                                         last_fp, True, img)
            try:
                processed = _preprocess_image_advanced(img)
                config = "--psm 8 --oem 1 -c tessedit_char_whitelist=0123456789"
                text = pytesseract.image_to_string(processed, lang="eng", config=config).strip()
                last = _normalize_digits(text, len_min=len_min, len_max=len_max)
            except Exception:
                last = ''

        if len(last) >= len_min and len(last) <= len_max and last.isdigit():
            break
        last = ''
        _click_refresh(driver, elem)
        time.sleep(interval)

    code, info = last, '未在表中'
    if code and map_file:
        try:
            data = _load_captcha_map(map_file)
            code, info = _apply_captcha_map_info(code, data)
        except Exception:
            pass
    return CaptchaResult(code, info, last_fp, False, last_img)


def recognize_captcha(driver, selector="#captchaImage", attempts=5, interval=1.0,
                      len_min=4, len_max=5, map_file=None, db=None):
    """兼容旧接口：返回 (code, info)。需要指纹/图片时改用 recognize_captcha_ex。"""
    result = recognize_captcha_ex(driver, selector=selector, attempts=attempts, interval=interval,
                                  len_min=len_min, len_max=len_max, map_file=map_file, db=db)
    return result.code, result.info


def record_captcha_failure(db, result, logger=None, reason='login_failed'):
    """用了库里的答案却没过 —— 把这条标注摘掉，下次退回 OCR 重新确认。

    只在 `result.from_db` 为真时动手：OCR 出来的答案错了跟库没关系，
    不能因为它误删已经验证过的好条目。
    """
    if db is None or result is None:
        return False
    if not getattr(result, 'from_db', False):
        return False
    fp = getattr(result, 'fingerprint', None)
    if not fp:
        return False
    try:
        removed = db.forget(fp, reason=reason)
        db.save()
        if removed and logger:
            logger.warning(f"验证码指纹答案被证伪，已摘除: {fp}（下次走 OCR）")
        return bool(removed)
    except Exception as e:
        if logger:
            logger.warning(f"验证码指纹摘除失败（不影响重试）: {e}")
        return False


def open_captcha_db(config_path, server_id=None, logger=None):
    """按配置目录打开该服的指纹库（失败返回 None，绝不抛异常）。"""
    try:
        from scripts.captcha_fingerprint import open_db_safe
    except ImportError:
        try:
            from captcha_fingerprint import open_db_safe
        except Exception:
            return None
    db = open_db_safe(config_path, server_id)
    if db is None and logger:
        logger.warning("验证码指纹库打开失败，本次退回纯 OCR")
    return db


def record_captcha_success(db, result, logger=None):
    """登录成功后把「这张图 → 这次提交的答案」写进指纹库。

    登录成功是服务端给的硬证据，等于免费标注：下次遇到同一张图直接命中，
    100% 正确、零 OCR。库里已有且答案相同时只累加计数，不产生冲突。
    """
    if db is None or result is None:
        return False
    fp = getattr(result, 'fingerprint', None)
    code = getattr(result, 'code', None)
    if not fp or not code:
        return False
    try:
        db.record(fp, code, source='login_success')
        db.save()
        if logger:
            logger.info(f"验证码指纹入库: {fp} -> {code}")
        return True
    except Exception as e:
        if logger:
            logger.warning(f"验证码指纹入库失败（不影响本次登录）: {e}")
        return False


