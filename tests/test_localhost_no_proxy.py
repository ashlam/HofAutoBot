"""代理环境下的 no_proxy 修正测试。

真实踩到的坑：沙箱里设了 http_proxy=http://127.0.0.1:60484，于是 selenium 连
chromedriver(127.0.0.1:port) 也走了代理，chromedriver 回 "unhandled request"，
表现成"浏览器起得来，但 driver.get 立刻失败"。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.start_up_cli import _ensure_localhost_no_proxy


def test_adds_localhost_to_empty_no_proxy():
    os.environ.pop("no_proxy", None)
    os.environ.pop("NO_PROXY", None)

    _ensure_localhost_no_proxy()

    for key in ("no_proxy", "NO_PROXY"):
        assert "127.0.0.1" in os.environ[key]
        assert "localhost" in os.environ[key]


def test_keeps_existing_entries_and_is_idempotent():
    os.environ["no_proxy"] = "example.com"
    os.environ["NO_PROXY"] = "example.com"

    _ensure_localhost_no_proxy()
    first = os.environ["NO_PROXY"]
    _ensure_localhost_no_proxy()

    assert os.environ["NO_PROXY"] == first, "重复调用不应反复追加"
    assert "example.com" in first
    assert "127.0.0.1" in first
    assert first.count("127.0.0.1") == 1


if __name__ == "__main__":
    test_adds_localhost_to_empty_no_proxy()
    test_keeps_existing_entries_and_is_idempotent()
    print("ok")
