import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.boss_check_watchdog import BossCheckWatchdog, DEFAULT_MAX_GAP_SECONDS


class _Clock:
    """可控时钟，避免用例依赖真实时间。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_not_overdue_right_after_check():
    clock = _Clock()
    dog = BossCheckWatchdog(max_gap_provider=lambda: 180, clock=clock)
    clock.advance(179)
    assert dog.overdue() is False


def test_overdue_after_gap():
    clock = _Clock()
    dog = BossCheckWatchdog(max_gap_provider=lambda: 180, clock=clock)
    clock.advance(181)
    assert dog.overdue() is True


def test_mark_checked_resets_the_clock():
    clock = _Clock()
    dog = BossCheckWatchdog(max_gap_provider=lambda: 180, clock=clock)
    clock.advance(179)
    dog.mark_checked()
    clock.advance(90)
    assert dog.overdue() is False
    clock.advance(91)
    assert dog.overdue() is True


def test_zero_gap_disables_watchdog():
    """boss_check_max_gap_seconds <= 0 时看门狗关闭，不能反过来把状态机踢个不停。"""
    clock = _Clock()
    dog = BossCheckWatchdog(max_gap_provider=lambda: 0, clock=clock)
    clock.advance(10000)
    assert dog.overdue() is False


def test_clock_rollback_does_not_trigger():
    """系统校时把时间往回拨时不该触发（否则会来回强制切状态）。"""
    clock = _Clock()
    dog = BossCheckWatchdog(max_gap_provider=lambda: 180, clock=clock)
    clock.advance(-500)
    assert dog.overdue() is False


def test_bad_provider_falls_back_to_default():
    clock = _Clock()

    def _boom():
        raise RuntimeError('配置坏了')

    dog = BossCheckWatchdog(max_gap_provider=_boom, clock=clock)
    assert dog.max_gap() == DEFAULT_MAX_GAP_SECONDS
    clock.advance(DEFAULT_MAX_GAP_SECONDS + 1)
    assert dog.overdue() is True
