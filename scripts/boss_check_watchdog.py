# -*- coding: utf-8 -*-
"""Boss 巡检看门狗 —— 保证 boss 主线至少每 N 秒被看一眼。

背景（2服 2026-10-27 16:55~17:00）：体力 2400，打 boss 只要 10 点，没有任何
冷却，VIP boss 就站在存活列表里，状态机却在
`PrepareStage -> TimeLimitedStage -> NormalStage -> PrepareStage` 里空转 5 分钟，
一次 boss 都没看。

根因是小怪闭环里"通向 boss"的边只有一条，而且条件是"体力低于阈值"——
既然打 boss 只要 10 点体力，这个条件本身就是错的判据：boss 能不能打只取决于
冷却，不取决于体力余量。

改状态转移图能修这一次，但挡不住以后再加一个状态、又把回主线的边弄丢
（这种环没有任何报错，只会安静地空转）。所以在主循环上加一条兜底：
超过 `max_gap` 秒没进过 PrepareBoss，就直接把当前状态换成 PrepareBoss。
"""

import time

# 默认 180 秒：比任何正常的小怪/PvP 循环都长，不会误伤，又能让空转最多持续 3 分钟
DEFAULT_MAX_GAP_SECONDS = 180.0


class BossCheckWatchdog:
    """记录"上次检查 boss 是什么时候"，并在超时时要求强制回主线。"""

    def __init__(self, max_gap_provider=None, clock=None):
        self._max_gap_provider = max_gap_provider
        self._clock = clock or time.time
        self.last_check_ts = self._clock()

    # ------------------------------------------------------------------ 配置

    def max_gap(self) -> float:
        provider = self._max_gap_provider
        if provider is None:
            return DEFAULT_MAX_GAP_SECONDS
        try:
            return float(provider())
        except (TypeError, ValueError):
            return DEFAULT_MAX_GAP_SECONDS
        except Exception:
            return DEFAULT_MAX_GAP_SECONDS

    # ------------------------------------------------------------------ 状态

    def mark_checked(self):
        self.last_check_ts = self._clock()

    def elapsed(self) -> float:
        return self._clock() - self.last_check_ts

    def overdue(self) -> bool:
        """该不该强制回 boss 主线。

        max_gap <= 0 视为关闭；时钟回拨（elapsed 为负）不触发，避免系统校时
        把状态机踢成来回抖动。
        """
        gap = self.max_gap()
        if gap <= 0:
            return False
        elapsed = self.elapsed()
        if elapsed <= 0:
            return False
        return elapsed > gap
