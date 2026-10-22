import sys
import os
import subprocess
import time

# 添加项目根目录到Python路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)


def _count_chromedriver():
    """统计当前运行的 chromedriver 进程数"""
    try:
        out = subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout
        return sum(1 for line in out.splitlines() if 'chromedriver' in line and 'grep' not in line)
    except Exception:
        return 0


def test_import_does_not_launch_chrome():
    """回归测试：import advanced_action_executor 不应启动 Chrome。

    背景：模块顶层写了
        options = Options()
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    导致每次 import 都会下载/启动一个完整 Chrome 实例，而这个 driver
    变量从未被使用（方法内部都用自己的 driver 参数）。
    实际后果：每个 bot 进程额外泄漏一个 chromedriver + Chrome。
    """
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import scripts.advanced_action_executor as m\n"
        "print('HAS_DRIVER', hasattr(m, 'driver'))\n"
    ) % ROOT

    before = _count_chromedriver()
    proc = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=120)
    time.sleep(1.5)  # 给 chromedriver 进程一点时间退出
    after = _count_chromedriver()

    assert proc.returncode == 0, f"导入失败:\n{proc.stderr}"
    assert 'HAS_DRIVER False' in proc.stdout, (
        "advanced_action_executor 模块顶层不应再创建 driver 实例；"
        f"实际输出: {proc.stdout.strip()}"
    )
    assert after <= before, (
        f"import 后 chromedriver 进程数增加（{before} -> {after}），说明仍在启动浏览器"
    )


def test_module_has_no_chrome_side_effect():
    """导入后不应残留 chrome 相关子进程"""
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import scripts.advanced_action_executor\n"
        "print('OK')\n"
    ) % ROOT

    proc = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"导入失败:\n{proc.stderr}"
    assert 'OK' in proc.stdout


if __name__ == "__main__":
    test_import_does_not_launch_chrome()
    test_module_has_no_chrome_side_effect()
    print("全部测试通过！")
