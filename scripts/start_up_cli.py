import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)
import json
import argparse
import time
import signal
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome
from scripts.captcha_recognizer import recognize_captcha
from scripts.hof_auto_bot_main import HofAutoBot
from scripts.account_config_reader import get_account_config

_GLOBAL_DRIVER = None
_GLOBAL_BOT = None

def _pid_path(p):
    if not p:
        return os.path.join(os.path.dirname(__file__), "..", "hof_auto_bot.pid")
    if os.path.isabs(p):
        return p
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", p))

def _write_pid(pid_file):
    try:
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return False

def _read_pid(pid_file):
    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            s = f.read().strip()
            return int(s) if s else None
    except Exception:
        return None

def _process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def _remove_pid_file(pid_file):
    try:
        if os.path.exists(pid_file):
            os.remove(pid_file)
    except Exception:
        pass

def _handle_signal(signum, frame):
    try:
        if _GLOBAL_BOT:
            try:
                _GLOBAL_BOT.cleanup()
            except Exception:
                pass
        if _GLOBAL_DRIVER:
            try:
                _GLOBAL_DRIVER.quit()
            except Exception:
                pass
    finally:
        pid_file = os.environ.get("HOF_PID_FILE")
        if pid_file:
            _remove_pid_file(pid_file)
        os._exit(0)

def _load_server(server_id=None, server_name=None):
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "configs", "server_address.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    servers = data.get("server_address", [])
    if server_id is not None:
        for s in servers:
            if int(s.get("id")) == int(server_id):
                return s
    if server_name:
        for s in servers:
            if s.get("name") == server_name:
                return s
    return servers[0] if servers else None

def _open_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    os.environ.setdefault("WDM_LOCAL", "1")
    service = Service(ChromeDriverManager().install())
    return Chrome(service=service, options=options)

def _login_and_start(server, headless=True, refresh_max=None, refresh_interval=None, map_file=None, tesseract_path=None):
    if tesseract_path:
        os.environ["TESSERACT_PATH"] = tesseract_path
    driver = _open_driver(headless=headless)
    globals()["_GLOBAL_DRIVER"] = driver
    driver.get(server["url"])
    driver.implicitly_wait(8)
    user_name, password = get_account_config(server["config_path"])
    username_input = driver.find_element(By.NAME, "id")
    username_input.clear()
    username_input.send_keys(user_name)
    password_input = driver.find_element(By.NAME, "pass")
    password_input.clear()
    password_input.send_keys(password)
    attempts = int(refresh_max if refresh_max is not None else server.get("captcha_refresh_max", 5))
    interval = float(refresh_interval if refresh_interval is not None else server.get("captcha_refresh_interval_sec", 1.0))
    code, info = recognize_captcha(driver, selector="#captchaImage", attempts=attempts, interval=interval, len_min=4, len_max=5, map_file=map_file)
    len_min, len_max = 4, 5
    if code and code.isdigit() and len(code) >= len_min and len(code) <= len_max:
        captcha_input = driver.find_element(By.NAME, "captcha")
        captcha_input.clear()
        captcha_input.send_keys(code)
        login_button = driver.find_element(By.CSS_SELECTOR, 'input[name="Login"][class="btn"]')
        login_button.click()
        time.sleep(1.0)
        elems_img = driver.find_elements(By.CSS_SELECTOR, "#captchaImage")
        elems_span = driver.find_elements(By.XPATH, "//span[contains(@onclick, 'getCaptcha()')]")
        if not elems_img and not elems_span:
            bot = HofAutoBot()
            globals()["_GLOBAL_BOT"] = bot
            bot.initialize_with_driver(server["id"], driver)
            try:
                bot.run()
            except KeyboardInterrupt:
                bot.cleanup()
            return 0
        return 1
    print(f"自动验证码失败: {info}")
    try:
        captcha = input("请输入验证码并回车，或直接回车取消: ").strip()
    except Exception:
        captcha = ""
    if not captcha:
        print("已取消自动登录")
        try:
            driver.quit()
        except Exception:
            pass
        return 2
    try:
        captcha_input = driver.find_element(By.NAME, "captcha")
        captcha_input.clear()
        captcha_input.send_keys(captcha)
        login_button = driver.find_element(By.CSS_SELECTOR, 'input[name="Login"][class="btn"]')
        login_button.click()
        time.sleep(1.0)
        elems_img = driver.find_elements(By.CSS_SELECTOR, "#captchaImage")
        elems_span = driver.find_elements(By.XPATH, "//span[contains(@onclick, 'getCaptcha()')]")
        if not elems_img and not elems_span:
            bot = HofAutoBot()
            globals()["_GLOBAL_BOT"] = bot
            bot.initialize_with_driver(server["id"], driver)
            try:
                bot.run()
            except KeyboardInterrupt:
                bot.cleanup()
            return 0
        print("登录后仍检测到验证码元素，登录可能失败")
        return 3
    except Exception as e:
        print(f"填写验证码失败: {e}")
        try:
            driver.quit()
        except Exception:
            pass
        return 4

def main():
    p = argparse.ArgumentParser(
        description="命令行一键自动登录并运行",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "示例用法:\n"
            "  读取配置自动运行:\n"
            "    python scripts/start_up_cli.py --server-id 2\n"
            "  自定义刷新策略与映射表:\n"
            "    python -m scripts.start_up_cli --server-id 2 --refresh-max 100 --refresh-interval 1.0 --map-file configs/captcha_map.json\n"
            "  指定 Tesseract 路径:\n"
            "    python -m scripts.start_up_cli --server-id 2 --tesseract-path /usr/local/bin/tesseract\n"
            "  查看进程状态:\n"
            "    python -m scripts.start_up_cli --status --pid-file hof_auto_bot.pid\n"
            "  停止正在运行的进程:\n"
            "    python -m scripts.start_up_cli --stop --pid-file hof_auto_bot.pid\n"
        )
    )
    p.add_argument("--server-id", type=int, help="服务器编号（如 1 或 2）；与 --server-name 二选一")
    p.add_argument("--server-name", help="服务器名称（如 '2服（测试服）'）；与 --server-id 二选一")
    p.add_argument("--no-headless", action="store_true", help="显示浏览器界面（默认不显示，适合 NAS）")
    p.add_argument("--refresh-max", type=int, help="验证码刷新最大次数；未提供则从 server_address.json 读取")
    p.add_argument("--refresh-interval", type=float, help="验证码刷新间隔秒数；未提供则从 server_address.json 读取")
    p.add_argument("--map-file", default=os.path.join(os.path.dirname(__file__), "..", "configs", "captcha_map.json"), help="验证码映射表路径")
    p.add_argument("--tesseract-path", help="Tesseract 可执行路径（如 /usr/local/bin/tesseract）")
    p.add_argument("--pid-file", help="PID 文件路径（默认项目根目录 hof_auto_bot.pid）")
    p.add_argument("--status", action="store_true", help="查看运行状态")
    p.add_argument("--stop", action="store_true", help="停止正在运行的进程")
    args = p.parse_args()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    pid_file = _pid_path(args.pid_file)
    os.environ["HOF_PID_FILE"] = pid_file
    if args.status:
        pid = _read_pid(pid_file)
        if pid and _process_exists(pid):
            print(f"运行中: PID={pid}")
        else:
            print("未运行或PID文件不存在")
        return
    if args.stop:
        pid = _read_pid(pid_file)
        if pid and _process_exists(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"已发送停止信号到 PID={pid}")
            except Exception as e:
                print(f"停止失败: {e}")
        else:
            print("未找到有效运行进程")
        return
    server = _load_server(server_id=args.server_id, server_name=args.server_name)
    if not server:
        print("未找到服务器配置")
    headless = not args.no_headless
    _write_pid(pid_file)
    rc = _login_and_start(server, headless=headless, refresh_max=args.refresh_max, refresh_interval=args.refresh_interval, map_file=args.map_file, tesseract_path=args.tesseract_path)
    if rc == 0:
        print("自动运行已启动")
    elif rc == 1:
        print("登录后仍看到验证码，未自动启动")
    elif rc == 2:
        print("已取消自动登录")
    elif rc == 3:
        print("登录可能失败，未自动启动")
    else:
        print("自动登录流程出错")
    _remove_pid_file(pid_file)

if __name__ == "__main__":
    main()
