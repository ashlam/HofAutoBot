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

  1. 同一轮刷新（spawn_key 相同）只允许发一次请求；唯一的例外是
     "上一枪被服务端明确拒绝（落地页 Defeated or not Exists）"之后补的那几枪
     ——被拒绝的请求不进战报、不给冷却，补枪在战报里是隐形的，但仍受
     次数上限和最小间隔约束，绝不会出现两个请求同时在飞；
  2. 同一个 boss 两次请求之间至少间隔 min_interval 秒（默认 600）；唯一的例外是
     "上一枪已被服务端明确拒绝"——那种请求什么都没生成，这只 boss 在服务端眼里
     仍然是没被碰过的，只保留一个 2 秒的补打间隔；
  3. 记录落盘，进程重启也记得刚才打过 —— 重启后重复打是最容易翻车的一种；
  4. 落盘的读写要跨进程加锁：同一个号开两个实例时，两个进程各自 hold 一份
     内存记录，只有进程内 RLock 是拦不住的（实测 2026-11-13 18:57 两个实例
     各发了一次，相差 18ms）。

claim() 在任何不确定的情况下都返回 False（宁可少打一只，也不多发一次）。
"""

import json
import os
import threading
import time
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # Windows 没有 flock，退化成进程内互斥
    fcntl = None

DEFAULT_MIN_INTERVAL_SECONDS = 600.0
# 上一枪被服务端**明确拒绝**（落地页写着 Defeated or not Exists）之后，这只 boss
# 允许隔这么短就再打一次：被拒绝的请求不生成战斗、不进战报、不给冷却，
# 服务端看它跟没发生过一样。2026-11-19 15:42 那轮就是被 600 秒卡死的——
# 狙击在 T+0.17s 打空，boss 1.3 秒后才刷出来，而闸门把这次"打空"当成
# "已经出过手"，把这只 boss 锁了整整 600 秒。
DEFAULT_REJECTED_RETRY_GAP_SECONDS = 2.0
# 只有 VIP 这条路允许"被拒之后马上补打"；普通 boss 仍然按 600 秒保守处理
VIP_RETRY_PURPOSES = ('vip_snipe', 'vip_chase')
# 记录保留时长：只是为了日志可回溯，超过这个时间的条目会被清掉
RECORD_TTL_SECONDS = 2 * 24 * 3600
DEFAULT_STATE_FILENAME = os.path.join('.runtime', 'boss_challenge_guard.json')


class BossChallengeGuard:
    """记录"谁在什么时候打过哪只 boss"，并据此拒绝重复请求。"""

    def __init__(self, state_path=None, min_interval_provider=None, logger=None,
                 rejected_retry_gap=None):
        if state_path is None:
            state_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', DEFAULT_STATE_FILENAME,
            )
        self.state_path = os.path.abspath(state_path)
        self._min_interval_provider = min_interval_provider
        self._logger = logger
        try:
            gap = float(rejected_retry_gap)
        except (TypeError, ValueError):
            gap = DEFAULT_REJECTED_RETRY_GAP_SECONDS
        self.rejected_retry_gap = max(0.0, gap)
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

    def claim(self, union_id, spawn_key=None, purpose='',
              allow_rejected_retry=False, retry_gap=0.0, max_attempts=1) -> bool:
        """申请一次出手许可。返回 False 表示绝不能再发请求。

        必须在"真的要把请求发出去"之前调用；调用成功但最终没发出去时，
        要调用 release() 把许可还回来，否则这个 boss 会被白锁一段时间。

        `allow_rejected_retry` 是唯一一个允许"同一轮刷新第二次出手"的口子，
        而且只在同时满足下面三条时才放行：

          1. 上一次请求已经被 **服务端明确拒绝**（落地页写着 Defeated or not Exists，
             由调用方核实后用 record_result(accepted=False) 落盘）；
          2. 这一轮累计出手次数还没到 max_attempts；
          3. 距上一次请求至少 retry_gap 秒（保证两次请求永远不会同时在飞）。

        被拒绝的请求不会生成战报、不会给冷却，所以补枪在战报里是隐形的；
        而"两个请求同时在飞"才是真正会把同一个人写进两条战报的情形——第 3 条
        就是专门堵这个的。
        """
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        now = time.time()
        with self._lock:
            with self._state_lock():
                # 先读一次盘：同一只号开两个实例时，另一个进程刚写的记录在这里才能看见
                self._load()
                self._prune(now)
                record = self._records.get(uid)
                if record:
                    if spawn is not None and record.get('spawn_key') == spawn:
                        attempts = int(record.get('attempts') or 1)
                        rejected = record.get('accepted') is False
                        gap = now - self._float(record.get('ts'))
                        if (allow_rejected_retry and rejected
                                and attempts < max(1, int(max_attempts))
                                and gap >= max(0.0, float(retry_gap))):
                            record['ts'] = now
                            record['attempts'] = attempts + 1
                            record['purpose'] = purpose
                            # 重置成"待判定"：下一枪的结果由调用方再写回来
                            record['accepted'] = None
                            self._save()
                            return True
                        self._warn(
                            f'挑战闸门拦截 boss({uid})：同一轮刷新({spawn})已经发过请求，拒绝重复发送'
                        )
                        return False
                    age = now - self._float(record.get('ts'))
                    if self._is_rejected(record):
                        # 上一枪被服务端明确拒绝：这只 boss 实际上没被碰过，
                        # 不该再锁一个完整的最小间隔，只留一个"别让两个请求同时在飞"的小间隔。
                        gap_required = max(self.rejected_retry_gap, float(retry_gap or 0.0))
                        remain = gap_required - age
                        if remain > 0:
                            self._warn(
                                f'挑战闸门拦截 boss({uid})：上一枪被拒后仅 {age:.1f}s，'
                                f'不足补打间隔 {gap_required:.1f}s（还差 {remain:.1f}s），拒绝重复发送'
                            )
                            return False
                    else:
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
                    'attempts': 1,
                }
                self._save()
                return True

    def release(self, union_id, spawn_key=None) -> None:
        """撤销刚才那次 claim：用于"许可拿到了但请求其实没发出去"。"""
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        with self._lock:
            with self._state_lock():
                self._load()
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
            with self._state_lock():
                self._load()
                record = self._records.get(uid)
                if not record:
                    return
                record['accepted'] = bool(accepted)
                self._save()

    def seconds_until_allowed(self, union_id, spawn_key=None) -> float:
        """还要等多少秒才允许再对这只 boss 出手；0 表示现在就可以。

        上一枪被服务端明确拒绝过的话，等待时间按补打间隔（默认 2 秒）算，
        而不是完整的最小间隔：那一次请求什么都没生成，服务端眼里这只 boss
        仍然是"没被碰过"的。
        """
        uid = self._uid(union_id)
        spawn = self._spawn(spawn_key)
        with self._lock:
            self._load()
            record = self._records.get(uid)
            if not record:
                return 0.0
            rejected = self._is_rejected(record)
            if spawn is not None and record.get('spawn_key') == spawn and not rejected:
                # 同一轮刷新的正常请求永远不会再放行，返回一个足够大的值让调用方去睡觉
                return self.min_interval
            gap_required = self.rejected_retry_gap if rejected else self.min_interval
            remain = gap_required - (time.time() - self._float(record.get('ts')))
            return max(0.0, remain)

    def last_fire_age(self, union_id):
        """距这只 boss 上次请求过去了多少秒；没记录时返回 None。"""
        with self._lock:
            self._load()
            record = self._records.get(self._uid(union_id))
            if not record:
                return None
            return time.time() - self._float(record.get('ts'))

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _uid(union_id):
        return str(union_id)

    @staticmethod
    def _is_rejected(record) -> bool:
        """这一枪是不是"服务端明确拒绝"（落地页 Defeated or not Exists）。

        只有 VIP 这条路（vip_snipe / vip_chase）才认这条：VIP 狙击必须在刷出
        瞬间反复试，而普通 boss 那一侧宁可保守——多锁一段时间最多少打一只，
        误判成"没打上"却可能真的多发一次请求。
        """
        if not record or record.get('accepted') is not False:
            return False
        return str(record.get('purpose') or '') in VIP_RETRY_PURPOSES

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

    @contextmanager
    def _state_lock(self):
        """跨进程排他锁：同一个号开多个实例时，读改写记录必须串行。

        只锁进程内的 RLock 是不够的 —— 两个进程各读一份文件、各自判定"没打过"，
        然后各自发一次请求（2026-11-13 18:57 实测相差 18ms 就发生了）。
        """
        if fcntl is None:
            yield
            return
        lock_path = self.state_path + '.lock'
        try:
            directory = os.path.dirname(lock_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            handle = open(lock_path, 'a+')
        except OSError as e:
            # 锁文件都建不出来，只能退化成进程内互斥，但要留痕
            self._warn(f'挑战闸门无法创建跨进程锁文件（降级为进程内互斥）：{e}')
            yield
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()

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
