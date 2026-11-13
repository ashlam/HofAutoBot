import os
import sys
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
from selenium.webdriver import Chrome
from scripts.captcha_recognizer import recognize_captcha
from scripts.hof_auto_bot_main import HofAutoBot
from scripts.account_config_reader import get_account_config

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
        # 没有可用 stdin 时（后台/nohup/由其它程序拉起）收不到 c 命令，
        # 只能靠 kill -USR1 <pid> 触发重载：信号处理只置位，真正的重载在主循环里做，
        # 避免和正在执行的动作撞车。
        self.reload_requested = threading.Event()
        self._reload_lock = threading.Lock()
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)

    def _input_loop(self):
        while not self.stopped.is_set():
            try:
                line = sys.stdin.readline()
            except (EOFError, OSError, ValueError):
                break
            if line == '':
                # 真正的 EOF（例如 </dev/null、nohup）。原来这里会 continue，
                # 于是空转成死循环狂吃 CPU；直接退出输入线程即可，主循环照常跑。
                break
            cmd = line.strip().lower()
            if not cmd:
                continue
            if cmd in ('p', 'pause'):
                self.paused.set()
                print('[CLI] 已暂停（当前操作完成后生效）', flush=True)
            elif cmd in ('r', 'resume'):
                if self.paused.is_set():
                    self.paused.clear()
                    self.request_reload()
                    print('[CLI] 已恢复', flush=True)
                else:
                    print('[CLI] 当前未暂停', flush=True)
            elif cmd in ('c', 'config'):
                self.request_reload()
            elif cmd in ('s', 'status'):
                state_name = getattr(self.bot, 'current_state_str', None) or '未知'
                print(f'[CLI] 当前状态: {state_name}', flush=True)
            elif cmd in ('q', 'quit'):
                print('[CLI] 正在停止...', flush=True)
                self.stop()
            elif cmd in ('h', 'help'):
                print('[CLI] 命令: p=暂停, r=恢复, c=重载配置, s=状态, q=退出, h=帮助', flush=True)
            else:
                print(f'[CLI] 未知命令: {cmd}，输入 h 查看帮助', flush=True)

    def request_reload(self, prefix='[CLI]'):
        """立刻重载配置（信号通道也走这里）。

        能立刻做就立刻做（和按 c 等价：旧配置对象整份换掉，发呆中的状态会被唤醒重算）；
        万一另一个线程正在重载，就只置位，交给主循环下一次迭代补做。
        """
        if not self._reload_lock.acquire(blocking=False):
            self.reload_requested.set()
            return None
        try:
            return self._reload_and_report(prefix=prefix)
        finally:
            self._reload_lock.release()

    def _reload_and_report(self, prefix='[CLI]'):
        """重载配置并把读到的东西打出来；失败时只报错不抛出。"""
        try:
            summary = self.bot.reload_configs()
        except Exception as e:
            print(f'{prefix} 重载配置失败: {e}', flush=True)
            return None
        self._print_reload_summary(summary, prefix=prefix)
        return summary

    def _print_reload_summary(self, summary, prefix='[CLI]'):
        """把"到底读到了什么"打出来：配置文件、文件时间、几个关键值。

        全部 flush=True：后台/重定向运行时 stdout 是块缓冲，不刷新的话这些提示
        会攒着不出现，看着就像"命令没生效"。
        """
        if not summary:
            print(f'{prefix} 重载配置被跳过（当前服务器配置未初始化）', flush=True)
            return
        print(f'{prefix} 配置已重载：{summary["path"]}（文件时间 {summary["mtime"]}）', flush=True)
        print(f'{prefix}   普通boss清单={summary["normal_boss"]}  VIP监视={summary["vip_boss"]}', flush=True)
        print(f'{prefix}   挑战冷却={summary["cooldown"]}秒  发呆={summary["idle"]}秒  '
              f'狙击偏移={summary["snipe_offset_ms"]:+.0f}ms  '
              f'动作组={summary["action_groups"]}个  动作类型={summary["action_types"]}类', flush=True)
        missing = summary.get('missing_action_ids') or []
        if missing:
            print(f'{prefix}   ⚠ 有 {len(missing)} 处配置对不上（跑到这些项会被直接跳过）：', flush=True)
            for m in missing:
                target = f"boss/关卡 {m['target']}" if m['target'] not in ('', None) else "某项"
                print(f'{prefix}     {m["field"]} 的{target} 引用动作组 {m["action_id"]}，动作配置里没有', flush=True)
            print(f'{prefix}     改法：把 loop 里的 plan_action_id 改成动作配置里真实存在的 id，或补一个动作组', flush=True)
        print(f'{prefix}   注意：发呆中的等待会被立刻打断重算；正在执行的动作/狙击倒计时不会被打断', flush=True)

    def run(self):
        print('[CLI] 输入命令: p=暂停, r=恢复, c=重载配置, s=状态, q=退出, h=帮助', flush=True)
        print('[CLI] 后台运行（stdin 不可用）时可用 kill -USR1 <pid> 触发重载', flush=True)
        self.input_thread.start()
        while not self.stopped.is_set() and not self.bot.is_finished:
            if self.reload_requested.is_set():
                self.reload_requested.clear()
                self._reload_and_report(prefix='[CLI][USR1]')
                continue
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

def _handle_usr1(signum, frame):
    """后台运行时唯一的控制通道：直接触发一次重载。

    和按 c 走同一条路（旧配置对象整份换掉 + epoch 加一），所以正在发呆的状态
    会在 0.5 秒内醒来按新配置重新决策，不用等这一觉睡完（冷却期可能睡 20 分钟）。
    """
    try:
        if _GLOBAL_RUNNER:
            _GLOBAL_RUNNER.request_reload(prefix='[CLI][USR1]')
    except Exception:
        pass


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

def _ensure_localhost_no_proxy():
    """把本机地址加进 no_proxy。

    代理环境下的坑：只要环境里有 http_proxy，selenium 连 chromedriver
    (127.0.0.1:port) 的请求也会被丢给代理，代理看不懂 WebDriver 协议，
    chromedriver 就收到一个畸形的请求并回 "unhandled request" —— 表现是
    浏览器能创建成功，但第一次 driver.get 立刻失败，看着像网站/驱动坏了。
    """
    hosts = ("127.0.0.1", "localhost", "::1")
    for key in ("no_proxy", "NO_PROXY"):
        parts = [p.strip() for p in os.environ.get(key, "").split(",") if p.strip()]
        for host in hosts:
            if host not in parts:
                parts.append(host)
        os.environ[key] = ",".join(parts)


def _open_driver(headless=True):
    _ensure_localhost_no_proxy()
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin and os.path.exists(chrome_bin):
        options.binary_location = chrome_bin
    os.environ.setdefault("WDM_LOCAL", "1")
    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    if driver_path and os.path.exists(driver_path):
        service = Service(driver_path)
    else:
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
            runner = CLIBotRunner(bot)
            globals()["_GLOBAL_RUNNER"] = runner
            try:
                runner.run()
            except KeyboardInterrupt:
                runner.stop()
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
    if hasattr(signal, "SIGUSR1"):
        # 后台运行（stdin 不是终端）时 c 命令没人能敲，用 kill -USR1 也能触发重载
        signal.signal(signal.SIGUSR1, _handle_usr1)

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
    try:
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
    finally:
        # 登录/初始化阶段抛异常时也要清掉 pid 文件，否则 --status 会看到一个死 pid
        _remove_pid_file(pid_file)

if __name__ == "__main__":
    main()
