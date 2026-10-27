# -*- coding: utf-8 -*-
"""Boss 挑战请求闸门 —— 全工程唯一的出口。

背景：服务器对同一只 boss 的挑战是"先到先结算"，但写库完成之前到达的请求
同样会被当成合法请求。也就是说，同一个玩家在极短时间内对同一只 boss 发出
两次请求，两次都可能被结算、并且都会进战报公示。正常玩家点不出第二次
（客户端进战斗就锁界面了），所以一旦战报里出现同一个人连续两次打同一只
boss，等于自己承认用了非常手段。

而这个机器人恰恰很容易发出第二次请求：状态机把 challenge_next_cooldown > 0
当作"打成了"的唯一判据，而"被拒绝"和"服务器还没写完"读出来都是 0，于是它
会认为"没打成，再来一次"。

所以任何会真正发出挑战请求的地方，都必须先 claim() 成功才能动手。规则：

  1. 同一轮刷新（spawn_key 相同）只允许发一次请求；
  2. 同一个 boss 两次请求之间至少间隔 min_interval 秒（默认 600）；
  3. 记录落盘，进程重启也记得刚才打过 —— 重启后重复打是最容易翻车的一种。

claim() 在任何不确定的情况下都返回 False（宁可少打一只，也不多发一次）。
"""

import json
import os
import threading
import time

DEFAULT_MIN_INTERVAL_SECONDS = 600.0
# 记录保留时长：只是为了日志可回溯，超过这个时间的条目会被清掉
RECORD_TTL_SECONDS = 2 * 24 * 3600
DEFAULT_STATE_FILENAME = os.path.join('.runtime', 'boss_challenge_guard.json')


class BossChallengeGuard:
    """记录"谁在什么时候打过哪只 boss"，并据此拒绝重复请求。"""

    def __init__(self, state_path=None, min_interval_provider=None, logger=None):
        if state_path is None:
            state_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', DEFAULT_STATE_FILENAME,
            )
        self.state_path = os.path.abspath(state_path)
        self._min_interval_provider = min_interval_provider
        self._logger = logger
        self._lock = threading.RLock()
        self._records = {}
        self._load()

    # ------------------------------------------------------------------ 配置

    @property
    def min_interval(self) -> float:
        if callable(self._min_interval_provider):
            try:
                value = float(self._min_interval_provider())
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        return DEFAULT_MIN_INTERVAL_SECONDS

    # ------------------------------------------------------------------ 对外接口

    def claim(self, union_id, spawn_key=None, purpose='') -> bool:
        """申请一次出手许可。返回 False 表示绝不能再发请求。

        必须在"真的要把请求发出去"之前调用；调用成功但最终没发出去时，
        要调用 release() 把许可还回来，否则这个 boss 会被白锁一段时间。
        """
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        now = time.time()
        with self._lock:
            self._prune(now)
            record = self._records.get(uid)
            if record:
                if spawn is not None and record.get('spawn_key') == spawn:
                    self._warn(
                        f'挑战闸门拦截 boss({uid})：同一轮刷新({spawn})已经发过请求，拒绝重复发送'
                    )
                    return False
                age = now - self._float(record.get('ts'))
                remain = self.min_interval - age
                if remain > 0:
                    self._warn(
                        f'挑战闸门拦截 boss({uid})：距上次请求仅 {age:.0f}s，'
                        f'不足最小间隔 {self.min_interval:.0f}s（还差 {remain:.0f}s），拒绝重复发送'
                    )
                    return False
            self._records[uid] = {
                'ts': now,
                'spawn_key': spawn,
                'purpose': purpose,
                'accepted': None,
            }
            self._save()
            return True

    def release(self, union_id, spawn_key=None) -> None:
        """撤销刚才那次 claim：用于"许可拿到了但请求其实没发出去"。"""
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        with self._lock:
            record = self._records.get(uid)
            if not record:
                return
            if spawn is not None and record.get('spawn_key') != spawn:
                return
            self._records.pop(uid, None)
            self._save()

    def record_result(self, union_id, accepted: bool) -> None:
        """记一笔服务端是否真的受理了这次请求，只用于事后排查。"""
        uid = self._uid(union_id)
        with self._lock:
            record = self._records.get(uid)
            if not record:
                return
            record['accepted'] = bool(accepted)
            self._save()

    def seconds_until_allowed(self, union_id, spawn_key=None) -> float:
        """还要等多少秒才允许再对这只 boss 出手；0 表示现在就可以。"""
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        with self._lock:
            record = self._records.get(uid)
            if not record:
                return 0.0
            if spawn is not None and record.get('spawn_key') == spawn:
                # 同一轮刷新永远不会再放行，返回一个足够大的值让调用方去睡觉
                return self.min_interval
            remain = self.min_interval - (time.time() - self._float(record.get('ts')))
            return max(0.0, remain)

    def last_fire_age(self, union_id):
        """距这只 boss 上次请求过去了多少秒；没记录时返回 None。"""
        with self._lock:
            record = self._records.get(self._uid(union_id))
            if not record:
                return None
            return time.time() - self._float(record.get('ts'))

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _uid(union_id):
        return str(union_id)

    @staticmethod
    def _spawn(spawn_key):
        if spawn_key in (None, '', 0, -1, '0', '-1'):
            return None
        return str(spawn_key)

    @staticmethod
    def _float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _prune(self, now):
        expired = [uid for uid, rec in self._records.items()
                   if now - self._float(rec.get('ts')) > RECORD_TTL_SECONDS]
        for uid in expired:
            self._records.pop(uid, None)

    def _load(self):
        try:
            with open(self.state_path, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                self._records = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            self._records = {}

    def _save(self):
        # 落盘失败不影响判断：内存里的记录已经生效，只是重启后会忘
        try:
            directory = os.path.dirname(self.state_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp_path = self.state_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as fp:
                json.dump(self._records, fp, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.state_path)
        except OSError as e:
            self._warn(f'挑战闸门记录落盘失败（不影响本次判断）：{e}')

    def _warn(self, message):
        logger = self._logger
        if logger is None:
            return
        try:
            logger.warning(message)
        except AttributeError:
            try:
                logger.info(message)
            except AttributeError:
                pass
