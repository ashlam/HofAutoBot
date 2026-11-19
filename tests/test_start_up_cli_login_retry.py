"""登录重试链路的测试：验证码失败不能再"静默退出"。

11-19 16:33 那次重启就是这么没的：验证码没认出来 → 老代码 return 2 →
进程退出，而 stdio 被重定向到 /dev/null，于是没人知道它死了。
"""

import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import start_up_cli as cli  # noqa: E402
from scripts.captcha_fingerprint import CaptchaFingerprintDB  # noqa: E402
from scripts.captcha_recognizer import CaptchaResult  # noqa: E402


class FakeEl:
    def __init__(self, driver, sel):
        self.driver = driver
        self.sel = sel or ''

    def clear(self):
        pass

    def send_keys(self, value):
        pass

    def click(self):
        d = self.driver
        d.submit_count += 1
        # 模拟服务端：前 fail_submits 次提交失败（还停在登录页）
        d.on_login = d.submit_count <= d.fail_submits


class FakeDriver:
    def __init__(self, fail_submits=0):
        self.fail_submits = fail_submits
        self.submit_count = 0
        self.on_login = True
        self.page_loads = 0
        self.quit_called = False

    def get(self, url):
        self.page_loads += 1
        self.on_login = True

    def implicitly_wait(self, seconds):
        pass

    def find_element(self, by, sel):
        return FakeEl(self, sel)

    def find_elements(self, by, sel):
        return [object()] if self.on_login else []

    def quit(self):
        self.quit_called = True


SERVER = {'id': 1, 'url': 'http://example.invalid/login', 'config_path': 'configs/server_01'}


@pytest.fixture()
def workdir():
    p = tempfile.mkdtemp(prefix='login_retry_')
    yield p
    shutil.rmtree(p, ignore_errors=True)


@pytest.fixture()
def patched(monkeypatch, workdir):
    db = CaptchaFingerprintDB(os.path.join(workdir, 'captcha_db_01.json'))

    def install(driver, result=None):
        monkeypatch.setattr(cli, '_open_driver', lambda **kw: driver)
        monkeypatch.setattr(cli, 'get_account_config', lambda p: ('user', 'pass'))
        monkeypatch.setattr(cli, 'open_captcha_db', lambda *a, **k: db)
        monkeypatch.setattr(cli, '_start_bot', lambda server, drv: 0)
        monkeypatch.setattr(cli.time, 'sleep', lambda s: None)
        monkeypatch.setattr(cli, 'recognize_captcha_ex',
                            lambda *a, **k: result if result is not None else CaptchaResult('12345', '未在表中'))
        return db

    return install


def _set_non_interactive(monkeypatch):
    class _Stdin:
        @staticmethod
        def isatty():
            return False

    monkeypatch.setattr(cli.sys, 'stdin', _Stdin())


class TestLoginRetry:
    def test_retries_after_failed_submit_and_returns_0(self, patched, monkeypatch):
        driver = FakeDriver(fail_submits=1)
        patched(driver)
        _set_non_interactive(monkeypatch)
        rc = cli._login_and_start(SERVER, headless=True, login_retry_max=3)
        assert rc == 0
        assert driver.submit_count == 2          # 第一次失败，第二次成功
        assert driver.page_loads == 2            # 每轮都重新打开登录页

    def test_gives_up_with_exit_code_2_when_non_interactive(self, patched, monkeypatch):
        driver = FakeDriver(fail_submits=99)
        patched(driver)
        _set_non_interactive(monkeypatch)
        rc = cli._login_and_start(SERVER, headless=True, login_retry_max=2)
        assert rc == 2
        assert driver.submit_count == 2          # 两轮都试过了
        assert driver.page_loads == 2
        assert driver.quit_called is True        # 退出前把浏览器收掉

    def test_never_submits_when_code_unrecognized(self, patched, monkeypatch):
        driver = FakeDriver()
        patched(driver, result=CaptchaResult('', '空值'))
        _set_non_interactive(monkeypatch)
        rc = cli._login_and_start(SERVER, headless=True, login_retry_max=3)
        assert rc == 2
        assert driver.submit_count == 0
        assert driver.page_loads == 3            # 没认出来也要重开页面再来

    def test_zero_rounds_still_tries_once(self, patched, monkeypatch):
        driver = FakeDriver(fail_submits=0)
        patched(driver)
        _set_non_interactive(monkeypatch)
        rc = cli._login_and_start(SERVER, headless=True, login_retry_max=0)
        assert rc == 0
        assert driver.page_loads == 1

    def test_round_count_from_server_config(self, patched, monkeypatch):
        driver = FakeDriver(fail_submits=99)
        patched(driver)
        _set_non_interactive(monkeypatch)
        server = dict(SERVER, captcha_login_retry_max=4)
        rc = cli._login_and_start(server, headless=True)
        assert rc == 2
        assert driver.page_loads == 4

    def test_success_writes_fingerprint_to_db(self, patched, monkeypatch, workdir):
        driver = FakeDriver(fail_submits=0)
        res = CaptchaResult('20481', '未在表中', 'abcdefabcdefabcd', False, None)
        db = patched(driver, result=res)
        _set_non_interactive(monkeypatch)
        rc = cli._login_and_start(SERVER, headless=True, login_retry_max=1)
        assert rc == 0
        assert db.lookup('abcdefabcdefabcd')[0] == '20481'
        assert CaptchaFingerprintDB(os.path.join(workdir, 'captcha_db_01.json')).lookup(
            'abcdefabcdefabcd')[0] == '20481'

    def test_db_answer_rejected_gets_forgotten(self, patched, monkeypatch):
        """库里的答案提交后被否 → 从库里摘掉，下次走 OCR，而不是一直错下去。"""
        driver = FakeDriver(fail_submits=99)
        fp = 'abcdefabcdefabcd'
        res = CaptchaResult('11111', '指纹精确命中', fp, True, None)
        db = patched(driver, result=res)
        db.record(fp, '11111')
        _set_non_interactive(monkeypatch)
        cli._login_and_start(SERVER, headless=True, login_retry_max=1)
        assert db.lookup(fp)[0] is None
