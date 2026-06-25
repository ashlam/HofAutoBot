import os
import sys
import subprocess
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)
import json
import argparse
import time
import signal
import threading
import glob
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver import Chrome

_GLOBAL_DRIVER = None
_GLOBAL_BOT = None
_GLOBAL_RUNNER = None

def _pid_path(p, server_id=None):
    if not p:
        name = f"hof_auto_bot_server_{server_id}.pid" if server_id is not None else "hof_auto_bot.pid"
        return os.path.join(os.path.dirname(__file__), "..", name)
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

class CLIBotRunner:
    """CLI 交互控制器：支持暂停/恢复/重载配置/停止"""

    def __init__(self, bot):
        self.bot = bot
        self.paused = threading.Event()
        self.stopped = threading.Event()
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)

    def _input_loop(self):
        while not self.stopped.is_set():
            try:
                cmd = sys.stdin.readline().strip().lower()
            except EOFError:
                break
            if not cmd:
                continue
            if cmd in ('p', 'pause'):
                self.paused.set()
                print('[CLI] 已暂停（当前操作完成后生效）')
            elif cmd in ('r', 'resume'):
                if self.paused.is_set():
                    self.paused.clear()
                    try:
                        self.bot.reload_configs()
                        print('[CLI] 已恢复，配置已重载')
                    except Exception as e:
                        print(f'[CLI] 恢复成功，但重载配置失败: {e}')
                else:
                    print('[CLI] 当前未暂停')
            elif cmd in ('c', 'config'):
                try:
                    self.bot.reload_configs()
                    print('[CLI] 配置已重载')
                except Exception as e:
                    print(f'[CLI] 重载配置失败: {e}')
            elif cmd in ('s', 'status'):
                state_name = getattr(self.bot, 'current_state_str', None) or '未知'
                print(f'[CLI] 当前状态: {state_name}')
            elif cmd in ('q', 'quit'):
                print('[CLI] 正在停止...')
                self.stop()
            elif cmd in ('h', 'help'):
                print('[CLI] 命令: p=暂停, r=恢复, c=重载配置, s=状态, q=退出, h=帮助')
            else:
                print(f'[CLI] 未知命令: {cmd}，输入 h 查看帮助')

    def run(self):
        print('[CLI] 输入命令: p=暂停, r=恢复, c=重载配置, s=状态, q=退出, h=帮助')
        self.input_thread.start()
        while not self.stopped.is_set() and not self.bot.is_finished:
            if self.paused.is_set():
                time.sleep(0.5)
                continue
            self.bot.run_once()

    def stop(self):
        self.stopped.set()
        if self.bot:
            self.bot.is_finished = True


def _handle_signal(signum, frame):
    try:
        if _GLOBAL_RUNNER:
            try:
                _GLOBAL_RUNNER.stop()
            except Exception:
                pass
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

def _find_local_chromedriver():
    """查找项目本地 drivers/chrome/ 下最新版本的 chromedriver"""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "drivers", "chrome"))
    if not os.path.isdir(root):
        return None
    candidates = []
    for version_dir in os.listdir(root):
        exe_path = os.path.join(root, version_dir, "chromedriver-win64", "chromedriver.exe")
        if os.path.exists(exe_path):
            candidates.append((version_dir, exe_path))
    if not candidates:
        return None
    # 按版本号字符串倒序，取最新
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def _open_driver(headless=True):
    options = Options()
    options.page_load_strategy = "eager"
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--enable-logging")
    options.add_argument("--v=1")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--safebrowsing-disable-auto-update")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--allow-insecure-content")
    options.add_argument("--allow-running-insecure-content")
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin and os.path.exists(chrome_bin):
        print(f"[启动] 使用 Chrome/Chromium 二进制: {chrome_bin}")
        options.binary_location = chrome_bin
    else:
        print("[启动] 警告: 未找到 CHROME_BIN 指定的浏览器，将使用系统默认 Chrome")
    os.environ.setdefault("WDM_LOCAL", "1")
    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    if driver_path and os.path.exists(driver_path):
        print(f"[启动] 使用指定 ChromeDriver: {driver_path}")
        service = Service(driver_path, log_output=subprocess.STDOUT)
    else:
        local_driver = _find_local_chromedriver()
        if local_driver:
            print(f"[启动] 使用本地 ChromeDriver: {local_driver}")
            service = Service(local_driver, log_output=subprocess.STDOUT)
        else:
            print("[启动] 正在通过 webdriver_manager 下载 ChromeDriver...")
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install(), log_output=subprocess.STDOUT)
    return Chrome(service=service, options=options)

def _login_and_start(server, headless=True, refresh_max=None, refresh_interval=None, map_file=None, tesseract_path=None):
    from scripts.captcha_recognizer import recognize_captcha
    from scripts.hof_auto_bot_main import HofAutoBot
    from scripts.account_config_reader import get_account_config
    if tesseract_path:
        os.environ["TESSERACT_PATH"] = tesseract_path
    print("[启动] 正在启动 Chrome 浏览器...")
    driver = _open_driver(headless=headless)
    globals()["_GLOBAL_DRIVER"] = driver
    print(f"[启动] 正在访问登录页面: {server['url']}")
    driver.get(server["url"])
    driver.implicitly_wait(8)
    print("[启动] 登录页加载完成，正在填充账号密码...")
    user_name, password = get_account_config(server["config_path"])
    username_input = driver.find_element(By.NAME, "id")
    username_input.clear()
    username_input.send_keys(user_name)
    password_input = driver.find_element(By.NAME, "pass")
    password_input.clear()
    password_input.send_keys(password)
    attempts = int(refresh_max if refresh_max is not None else server.get("captcha_refresh_max", 5))
    interval = float(refresh_interval if refresh_interval is not None else server.get("captcha_refresh_interval_sec", 1.0))
    print("[启动] 正在识别验证码...")
    code, info = recognize_captcha(driver, selector="#captchaImage", attempts=attempts, interval=interval, len_min=4, len_max=5, map_file=map_file)
    print(f"[启动] 验证码识别结果: code={code}, info={info}")
    len_min, len_max = 4, 5
    if code and code.isdigit() and len(code) >= len_min and len(code) <= len_max:
        print("[启动] 验证码符合要求，正在点击登录...")
        captcha_input = driver.find_element(By.NAME, "captcha")
        captcha_input.clear()
        captcha_input.send_keys(code)
        login_button = driver.find_element(By.CSS_SELECTOR, 'input[name="Login"][class="btn"]')
        login_button.click()
        time.sleep(1.0)
        elems_img = driver.find_elements(By.CSS_SELECTOR, "#captchaImage")
        elems_span = driver.find_elements(By.XPATH, "//span[contains(@onclick, 'getCaptcha()')]")
        if not elems_img and not elems_span:
            print("[启动] 登录成功，正在启动自动运行...")
            bot = HofAutoBot()
            globals()["_GLOBAL_BOT"] = bot
            bot.initialize_with_driver(server["id"], driver)
            runner = CLIBotRunner(bot)
            globals()["_GLOBAL_RUNNER"] = runner
            try:
                runner.run()
            except KeyboardInterrupt:
                runner.stop()
                bot.cleanup()
            return 0
        print("[启动] 登录后仍检测到验证码元素，登录可能失败")
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
            print("[启动] 登录成功，正在启动自动运行...")
            bot = HofAutoBot()
            globals()["_GLOBAL_BOT"] = bot
            bot.initialize_with_driver(server["id"], driver)
            runner = CLIBotRunner(bot)
            globals()["_GLOBAL_RUNNER"] = runner
            try:
                runner.run()
            except KeyboardInterrupt:
                runner.stop()
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
            "    python -m scripts.start_up_cli --status --server-id 2\n"
            "  停止正在运行的进程:\n"
            "    python -m scripts.start_up_cli --stop --server-id 2\n"
        )
    )
    p.add_argument("--server-id", type=int, help="服务器编号（如 1 或 2）；与 --server-name 二选一")
    p.add_argument("--server-name", help="服务器名称（如 '2服（测试服）'）；与 --server-id 二选一")
    p.add_argument("--no-headless", action="store_true", help="显示浏览器界面（默认不显示，适合 NAS）")
    p.add_argument("--refresh-max", type=int, help="验证码刷新最大次数；未提供则从 server_address.json 读取")
    p.add_argument("--refresh-interval", type=float, help="验证码刷新间隔秒数；未提供则从 server_address.json 读取")
    p.add_argument("--map-file", default=os.path.join(os.path.dirname(__file__), "..", "configs", "captcha_map.json"), help="验证码映射表路径")
    p.add_argument("--tesseract-path", help="Tesseract 可执行路径（如 /usr/local/bin/tesseract）")
    p.add_argument("--pid-file", help="PID 文件路径（默认按 server-id 自动命名为 hof_auto_bot_server_{id}.pid）")
    p.add_argument("--status", action="store_true", help="查看运行状态")
    p.add_argument("--stop", action="store_true", help="停止正在运行的进程")
    args = p.parse_args()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.status or args.stop:
        if args.pid_file:
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

        if args.status and args.server_id is None and not args.server_name:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            pattern = os.path.join(root_dir, "hof_auto_bot_server_*.pid")
            found_any = False
            for path in sorted(glob.glob(pattern)):
                basename = os.path.basename(path)
                sid = basename[len("hof_auto_bot_server_"):-len(".pid")]
                pid = _read_pid(path)
                if pid and _process_exists(pid):
                    print(f"pid({pid})  server_id({sid})")
                    found_any = True
            if not found_any:
                print("当前没有正在运行的进程")
            return

        server = _load_server(server_id=args.server_id, server_name=args.server_name)
        if not server or (args.server_id is None and not args.server_name):
            print("请通过 --server-id 或 --server-name 指定要操作的服务器，或使用 --pid-file 指定 PID 文件")
            return
        pid_file = _pid_path(None, server_id=server["id"])
        os.environ["HOF_PID_FILE"] = pid_file
        if args.status:
            pid = _read_pid(pid_file)
            if pid and _process_exists(pid):
                print(f"pid({pid})  server_id({server['id']})")
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
        return
    pid_file = _pid_path(args.pid_file, server_id=server["id"])
    os.environ["HOF_PID_FILE"] = pid_file
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
