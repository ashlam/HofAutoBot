# -*- coding: utf-8 -*-
"""VIP boss 狙击状态。

服务端只认"请求到达时 boss 是否已复活"，不认客户端有没有把页面渲染出来：
进入挑战页就是 GET index2.php?union=<id>，开战就是往同一个地址 POST
`char_<角色id>=1 ...&union_battle=1`（外加页面自带的几个空隐藏字段）。
也就是说，页面上"角色复选框有没有渲染出来"和"能不能发出这一刀"无关。

但历史实现恰恰卡在这里：预热时要求页面上已经存在角色复选框，boss 还没
刷出来时页面里没有这些元素 → 判成"预热失败" → 到 T 才重新 get 一次页面
（实测 0.7~1.2 秒）→ 请求落点被推到 T+0.7s 以后，白扔掉整条快速通道。

现在的做法：
    T - warmup_lead   把页面拿在手里，并把整张待提交表单**预先构造好**
                      （不等 boss 刷出、不等复选框出现），只差最后一下 submit
    T - fire_cost     只做一次 form.submit()，几毫秒，请求压在 T 上

只有"预热阶段连页面都没拿到"（进程不在游戏域、导航失败）时，才会退化成
到 T 再加载页面的一次盲试——这是兜底，不是常态。
"""

import time
from datetime import datetime

from .base_state import BaseState
from .state_factory import StateFactory


# 预热：把整张"开战表单"预先构造好，但不提交。
# 关键点是：**不要求页面上已经有角色复选框**——boss 没刷出时页面里本来就没有，
# 但服务端只读 POST body，所以缺的元素我们自己补上就行。
_PREPARE_JS = """
var ids = arguments[0] || [];
var battleName = arguments[1];
var unionId = arguments[2];

if (!document.body) { return { ok: false, reason: 'no_body' }; }

var form = document.forms.Form_Hu_Union;
var created = false;
if (!form) {
    // 页面上没有队伍表单（boss 还没刷出来时会这样）：自己造一个，
    // 提交地址和参数跟页面原生表单完全一致。
    form = document.createElement('form');
    form.id = 'Form_Hu_Union';
    form.name = 'Form_Hu_Union';
    form.method = 'post';
    form.action = 'index2.php?union=' + unionId;
    document.body.appendChild(form);
    created = true;
}
form.method = 'post';
if (!created) {
    // 原生表单的 action 里已经带了 union 参数，照抄它的文件名（别把 index2.php 写死）
    var actionBase = 'index2.php';
    var m = /([^\\/?#]+)\\?union=/.exec(form.getAttribute('action') || '');
    if (m) { actionBase = m[1]; }
    form.action = actionBase + '?union=' + unionId;
}

// 表单里那几个空隐藏字段（type/type2/sort/sort_type）是页面自带的，有就留着，
// 没有（我们自己造的表单）也无所谓——服务端不靠它们决定打不打。
// 角色勾选：先把全部取消，再只勾目标角色，避免"旧队 + 新队"一起提交。
Array.prototype.slice.call(form.querySelectorAll('input[name^="char_"]'))
    .forEach(function (el) { el.checked = false; });

var added = 0;
var reused = 0;
ids.forEach(function (id) {
    var el = form.querySelector('input[name="' + id + '"]');
    if (el) {
        el.checked = true;
        reused++;
        return;
    }
    el = document.createElement('input');
    el.type = 'checkbox';
    el.name = id;
    el.value = '1';
    el.checked = true;
    el.setAttribute('data-snipe-synth', '1');
    form.appendChild(el);
    added++;
});

// 开战字段：**必须是 hidden，不能是 submit 按钮**。
// `form.submit()` 不会序列化提交按钮，所以如果页面上只有 name=union_battle 的
// submit 按钮（这正是原生页面的样子），提交出去的 body 里就根本没有 union_battle，
// 服务端直接当无事发生——不报错、不记战报、不给冷却。
// 2026-11-13 19:42 实测：原生表单里除了两个 submit 按钮，本来还有一个
// `<input type="hidden" name="union_battle" value="1">`，浏览器真正发出的 body 是
//   type=&type2=&sort=&sort_type=&char_xxx=1&...&union_battle=1
// 缺的正是最后这一项。
var hiddenBattle = form.querySelector('input[type="hidden"][name="' + battleName + '"]');
if (!hiddenBattle) {
    hiddenBattle = document.createElement('input');
    hiddenBattle.type = 'hidden';
    hiddenBattle.name = battleName;
    hiddenBattle.value = '1';
    hiddenBattle.setAttribute('data-snipe-synth', '1');
    form.appendChild(hiddenBattle);
}
// 原生表单自带的那几个空隐藏字段（type/type2/sort/sort_type）有就留着；
// 我们自建表单时也补上，保证 body 与浏览器原生提交一模一样。
['type', 'type2', 'sort', 'sort_type'].forEach(function (key) {
    if (!form.querySelector('input[name="' + key + '"]')) {
        var h = document.createElement('input');
        h.type = 'hidden';
        h.name = key;
        h.value = '';
        h.setAttribute('data-snipe-synth', '1');
        form.appendChild(h);
    }
});

var battle = Array.prototype.slice
    .call(document.getElementsByName(battleName))
    .filter(function (el) { return el.type === 'submit'; })[0];
var hasNativeButton = !!battle;

return {
    ok: true,
    created: created,
    checked: ids.length,
    reused: reused,
    added: added,
    has_native_button: hasNativeButton,
    has_battle_field: true,
    form_action: form.getAttribute('action')
};
"""

# 出手：只提交，不做任何加载/构造。一次同步 JS 调用，毫秒级。
# 提交前在 window 上留一个标记：页面一旦被 POST 的响应替换掉，这个标记就没了，
# 于是"标记不见了 + readyState=complete"就等价于"服务端已经答复了我们"。
# 这是判断"这一枪有没有结果"的唯一可靠信号——靠固定 sleep 猜会误判。
_FIRE_JS = """
var form = document.forms.Form_Hu_Union;
if (!form) { return 'no_form'; }
window.__snipe_mark = (window.__snipe_mark || 0) + 1;
// 有些表单里会有 name="submit" 的元素把 form.submit 顶掉，稳妥起见走原型
HTMLFormElement.prototype.submit.call(form);
return 'submitted';
"""

# 读落地页：判断"服务端到底受理了没有"。
# navigated=False 说明我们还在原来那张页面上（提交还没答复/被拦下），不能当结论。
_VERDICT_JS = """
var body = document.body;
return {
  navigated: (typeof window.__snipe_mark === 'undefined'),
  ready: document.readyState,
  text: body ? (body.innerText || '').replace(/\\s+/g, ' ').slice(0, 400) : ''
};
"""

# 落地页里出现这句话，才是"服务端明确拒绝、没有生成战斗"的证据。
_REJECT_MARKERS = ('Defeated or not Exists', 'Defeated or not Exists.')


class VipSnipeState(BaseState):
    """在确定的刷新时刻 T 上只提交一次。"""

    def __init__(self, bot, union_id=None, advanced_action_config=None,
                 spawn_timestamp_us=None):
        super().__init__(bot)
        self.union_id = union_id
        self.advanced_action_config = advanced_action_config
        self.spawn_timestamp_us = spawn_timestamp_us

        self._warmup_ok = False
        self._warmup_cost = 0.0
        self._prepared = {}
        self._fire_result = None
        self._blind_tried = False
        self.last_delta_ms = None
        self.last_post_ms = None
        self._sent_ts = None
        self._last_verdict = None

    # ------------------------------------------------------------------ 配置

    def _cfg(self, name, default):
        try:
            return getattr(self.bot.auto_bot_config_manager, name)
        except AttributeError:
            return default

    @property
    def warmup_lead(self) -> float:
        """提前多久开始预热页面（加载 + 清队 + 勾人）。"""
        return float(self._cfg('vip_snipe_warmup_lead_seconds', 6.0))

    @property
    def fire_cost(self) -> float:
        """最后一次提交预留的往返预算：在 T 之前多少秒点下去。"""
        return float(self._cfg('vip_snipe_fire_cost_seconds', 0.03))

    @property
    def commit_offset(self) -> float:
        """整体平移提交时刻（秒）。负值=更早，正值=更晚，用于按实测微调。"""
        return float(self._cfg('vip_snipe_commit_offset_ms', 0)) / 1000.0

    @property
    def settle_seconds(self) -> float:
        """点完之后先等一会儿再刷新页面，别把正在提交的表单打断。"""
        return float(self._cfg('vip_snipe_settle_seconds', 1.0))

    @property
    def max_attempts(self) -> int:
        """一轮刷新最多出手几次（含第一枪）。只在被明确拒绝后才会用到。"""
        try:
            return max(1, int(self._cfg('vip_snipe_max_attempts', 3)))
        except (TypeError, ValueError):
            return 3

    @property
    def retry_gap(self) -> float:
        """两次出手之间的最小间隔（秒）：保证不会有两个请求同时在飞。"""
        try:
            return max(0.2, float(self._cfg('vip_snipe_retry_gap_seconds', 0.35)))
        except (TypeError, ValueError):
            return 0.35

    # ------------------------------------------------------------------ 主流程

    def process(self):
        self.log('VIP狙击：准备在刷新瞬间出手')
        if not self.union_id or not self.advanced_action_config:
            self.log('VIP狙击：缺少 boss 配置，放弃本轮')
            self._finish(success=False)
            return

        target_local = self._target_local_ts()
        if target_local is None:
            self.log('VIP狙击：没有可用的刷新时间，退化为直接打一次')
            self._blind_fire()
            self._finish(success=self._fired())
            return

        fire_at = target_local + self.commit_offset
        self.log(
            'VIP狙击时间轴：T={T}，预热于 T-{warm:.1f}s，提交预留 {cost:.0f}ms，'
            '提交偏移 {off:+.0f}ms，最多 {n} 枪（补枪仅限上一枪被明确拒绝）'.format(
                T=datetime.fromtimestamp(target_local).strftime('%H:%M:%S.%f')[:-3],
                warm=self.warmup_lead,
                cost=self.fire_cost * 1000,
                off=self.commit_offset * 1000,
                n=self.max_attempts,
            )
        )

        # 1) 预热：把页面拿在手里，并把整张待提交表单构造好（只在 T 之前做一次）
        self._wait_until(fire_at - self.warmup_lead)
        self._warmup_ok = self._warmup()
        if self._warmup_ok:
            self.log(
                f'VIP狙击：预热完成（耗时 {self._warmup_cost:.2f}s），表单已就绪'
                f'（复用页面角色 {self._prepared.get("reused", 0)} 个 / '
                f'补齐 {self._prepared.get("added", 0)} 个），只等 T 时刻 submit'
            )
        else:
            self.log('VIP狙击：预热失败（页面没拿到），改为到点加载页面后打一次')

        # 2) 定点提交 + 补枪
        #
        # 关键安全前提：同一时刻**只会有一个请求在飞**。补枪只在前一枪的落地页
        # 明确写着 "Defeated or not Exists"（服务端拒绝了、没有生成战斗）时才会发生，
        # 所以补枪不会在战报里留下第二条记录。反之只要落地页不是这句话（进战斗页、
        # 页面读不出来、提交点不到），一律当"已经有结果"收手。
        fire_ts = None
        for attempt in range(1, self.max_attempts + 1):
            if attempt == 1:
                self._wait_until(fire_at - self.fire_cost)
            else:
                # 上一枪已被拒绝：本页就是挑战页，重建表单后隔一小段再打
                if self.retry_gap > 0:
                    time.sleep(self.retry_gap)
                if not self._rewarm():
                    self.log('VIP狙击：补枪前重建表单失败，停止补枪')
                    break

            fire_ts = time.time()
            if attempt == 1 and not self._warmup_ok:
                # 预热就失败了：没有现成表单，只能现场加载一次再打（不打补枪）
                self._fire_result = self._blind_fire()
            else:
                self._fire_result = self._submit(allow_retry=(attempt > 1))
            self.last_delta_ms = (fire_ts - target_local) * 1000.0
            if self._fire_result == 'blocked':
                self.log('VIP狙击：被挑战闸门拦截，本轮不再发送任何请求')
                break
            if not self._result_sent(self._fire_result):
                # 表单没了（页面已被导航走）：只有第一枪才值得盲试一次
                if attempt == 1 and self._warmup_ok:
                    self.log(f'VIP狙击：预构建表单已失效（{self._fire_result}），重新加载页面盲试一次')
                    self._fire_result = self._blind_fire()
                break

            post_ms = '' if self.last_post_ms is None else f'，submit 耗时 {self.last_post_ms:.0f}ms'
            self.log(f'VIP狙击：第{attempt}枪 提交结果={self._fire_result}，'
                     f'起手相对 T {self.last_delta_ms:+.0f}ms{post_ms}')

            verdict = self._await_verdict()
            self._last_verdict = verdict
            if verdict == 'rejected':
                # 服务端说还没刷出：这一枪没有生成战斗，可以安全补枪。
                # 先把"被拒绝"落盘，闸门才会放行下一枪（它也只会因此放行）。
                self._record_verdict(accepted=False)
                if attempt < self.max_attempts:
                    self.log(f'VIP狙击：第{attempt}枪落空（服务端说还没刷出），准备补第 {attempt + 1} 枪')
                continue
            if verdict == 'accepted':
                self._record_verdict(accepted=True)
                break
            # unknown：读不到落地页就不赌，宁可少打一枪也不多发一次
            self.log('VIP狙击：读不到落地页结果，按"已出手"收手，不再补枪')
            break

        self._sent_ts = time.time()

        # 3) 结算
        self._settle()
        self._finish(success=self._fired())

    # ------------------------------------------------------------------ 时间轴

    def _server_clock_offset(self) -> float:
        """服务器时钟比本地时钟快多少秒（由战报响应的 Date 头估出来）。"""
        holders = (
            getattr(self.bot, 'battle_watcher_manager', None),
            self.bot,
        )
        for holder in holders:
            offset = getattr(holder, 'server_clock_offset', None)
            if offset:
                try:
                    return float(offset)
                except (TypeError, ValueError):
                    continue
        return 0.0

    def _target_local_ts(self):
        if not self.spawn_timestamp_us or self.spawn_timestamp_us <= 0:
            return None
        server_ts = self.spawn_timestamp_us / 1000000.0
        return server_ts - self._server_clock_offset()

    def _wait_until(self, target_ts):
        """睡到指定时刻，最后 30ms 自旋，把 sleep 的系统粒度误差吃掉。"""
        if target_ts is None:
            return
        remain = target_ts - time.time()
        if remain <= 0:
            return
        # 换到 monotonic，避免等待期间系统校时把时间轴拽走
        mono_target = time.monotonic() + remain
        while True:
            if getattr(self.bot, 'is_finished', False):
                return
            remain = mono_target - time.monotonic()
            if remain <= 0.03:
                break
            time.sleep(min(remain - 0.02, 0.5))
        while time.monotonic() < mono_target:
            pass

    # ------------------------------------------------------------------ 浏览器动作

    def _boss_url(self) -> str:
        server_url = self.bot.server_config_manager.current_server_data['url']
        return f"{server_url}index.php?union={self.union_id}#"

    def _char_ids(self):
        return [a['value'] for a in self.advanced_action_config['actions']
                if a.get('trigger_type') == 'check_box_select_character']

    def _battle_button(self) -> str:
        for action in self.advanced_action_config['actions']:
            if action.get('trigger_type') == 'click_button_start_battle':
                return action['value']
        return 'union_battle'

    def _wait_page_ready(self, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.bot.driver.execute_script('return document.readyState') == 'complete':
                    return True
            except Exception:
                pass
            time.sleep(0.05)
        return False

    def _warmup(self) -> bool:
        """把 boss 页面拿在手里，并把待提交的表单预构建好（不提交）。

        这里唯一的硬条件是"页面能打开"——boss 有没有刷出来、角色复选框有没有
        渲染，都不影响能不能构造这张表单。
        """
        t0 = time.time()
        try:
            self.bot.driver.get(self._boss_url())
            self._wait_page_ready()
            info = self.bot.driver.execute_script(
                _PREPARE_JS, self._char_ids(), self._battle_button(), self.union_id
            )
            self._warmup_cost = time.time() - t0
        except Exception as e:
            self._warmup_cost = time.time() - t0
            self.log(f'VIP狙击：预热异常 {type(e).__name__}: {e}')
            return False

        if not isinstance(info, dict) or not info.get('ok'):
            reason = info.get('reason') if isinstance(info, dict) else 'non_dict'
            self.log(f'VIP狙击：预热未能构造表单（{reason}）')
            return False

        self._prepared = info
        if not info.get('has_native_button'):
            self.log('VIP狙击：页面上还没有开战按钮（boss 未刷出），'
                     '已用同构表单顶替（union_battle 以 hidden 形式带上，到点直接 submit）')
        return True

    def _fired(self) -> bool:
        return self._result_sent(self._fire_result)

    @staticmethod
    def _result_sent(result) -> bool:
        """这次 execute_script 到底有没有把请求发出去。"""
        return result in ('clicked', 'submitted')

    # ------------------------------------------------------------------ 请求闸门

    def _guard(self):
        return getattr(self.bot, 'boss_challenge_guard', None)

    def _claim_shot(self, allow_retry: bool = False) -> bool:
        """发请求前先过闸门：同一轮刷新只允许一次**被受理的**出手。

        allow_retry=True 只在前一枪被服务端明确拒绝（落地页 Defeated or not Exists）
        之后才会传进来，闸门自己还会再核一遍次数和间隔。
        """
        guard = self._guard()
        if guard is None:
            return True
        try:
            return bool(guard.claim(
                self.union_id, self.spawn_timestamp_us, 'vip_snipe',
                allow_rejected_retry=allow_retry,
                retry_gap=self.retry_gap,
                max_attempts=self.max_attempts,
            ))
        except Exception as e:
            # 闸门自己出问题时宁可不出手，也不冒"发两次"的风险
            self.log(f'VIP狙击：挑战闸门异常（{type(e).__name__}: {e}），放弃本次出手')
            return False

    def _release_shot(self):
        """请求没真的发出去，把许可还回去，否则这只 boss 会被白锁一段时间。"""
        guard = self._guard()
        if guard is None:
            return
        try:
            guard.release(self.union_id, self.spawn_timestamp_us)
        except Exception:
            pass

    def _record_verdict(self, accepted: bool):
        """把"服务端有没有受理"落到闸门记录里，补枪许可就靠这条判据。"""
        guard = self._guard()
        if guard is None:
            return
        try:
            guard.record_result(self.union_id, accepted)
        except Exception as e:
            self.log(f'VIP狙击：记录出手结果失败 {type(e).__name__}: {e}')

    def _submit(self, allow_retry: bool = False):
        if not self._claim_shot(allow_retry):
            return 'blocked'
        t0 = time.time()
        try:
            result = self.bot.driver.execute_script(_FIRE_JS)
        except Exception as e:
            # 提交触发表单跳转后，execute_script 有可能来不及拿到返回值
            self.log(f'VIP狙击：提交时页面已跳转（{type(e).__name__}），按已提交处理')
            result = 'submitted'
        self.last_post_ms = (time.time() - t0) * 1000.0
        if not self._result_sent(result):
            self._release_shot()
        return result

    def _rewarm(self) -> bool:
        """在当前页（落地页就是挑战页）上把待提交表单再构造一次，不重新导航。"""
        try:
            info = self.bot.driver.execute_script(
                _PREPARE_JS, self._char_ids(), self._battle_button(), self.union_id
            )
        except Exception as e:
            self.log(f'VIP狙击：重建表单异常 {type(e).__name__}: {e}')
            return False
        if not isinstance(info, dict) or not info.get('ok'):
            reason = info.get('reason') if isinstance(info, dict) else 'non_dict'
            self.log(f'VIP狙击：重建表单失败（{reason}）')
            return False
        self._prepared = info
        return True

    def _await_verdict(self, timeout: float = None) -> str:
        """等服务端对我们这一枪的答复，返回 'rejected' / 'accepted' / 'unknown'。

        - rejected：落地页明确写着 Defeated or not Exists —— 这一枪没有生成战斗，
          补枪是安全的（不会在战报里留第二条记录）；
        - accepted：页面被换掉了、但没有那句拒绝话术 —— 当已出手，收手；
        - unknown：等到超时也没看到新页面 —— 读不到就不赌，同样收手。

        只有 rejected 才允许补枪，这是整套补枪逻辑的安全底线。
        """
        if timeout is None:
            try:
                timeout = float(self._cfg('vip_snipe_verdict_timeout_seconds', 3.0))
            except (TypeError, ValueError):
                timeout = 3.0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                info = self.bot.driver.execute_script(_VERDICT_JS)
            except Exception:
                # 导航过程中 execute_script 会抛（no such frame 之类），继续等
                time.sleep(0.05)
                continue
            if not isinstance(info, dict):
                time.sleep(0.05)
                continue
            text = info.get('text') or ''
            if info.get('navigated') and info.get('ready') == 'complete' and text:
                if any(marker in text for marker in _REJECT_MARKERS):
                    return 'rejected'
                return 'accepted'
            time.sleep(0.05)
        return 'unknown'

    def _blind_fire(self):
        """兜底：预热阶段没拿到页面时，才到 T 现场加载一次再提交。"""
        if self._blind_tried:
            return 'skipped'
        self._blind_tried = True
        try:
            self.bot.driver.get(self._boss_url())
            self._wait_page_ready()
            info = self.bot.driver.execute_script(
                _PREPARE_JS, self._char_ids(), self._battle_button(), self.union_id
            )
            self.log(f'VIP狙击：盲试构造表单 {info}')
        except Exception as e:
            self.log(f'VIP狙击：盲试加载页面异常 {type(e).__name__}: {e}')
            return 'error'
        return self._submit()

    # ------------------------------------------------------------------ 收尾

    def _settle(self):
        """点完之后稍等一下，让表单提交真正到达服务器。"""
        if self.settle_seconds > 0:
            time.sleep(self.settle_seconds)

    def _capture_landing(self):
        """把提交之后落地页的地址和正文头一段记下来。

        这是唯一能看见"服务端到底怎么回我们这一刀"的地方：受理了会进战斗页，
        被拒（boss 还没刷出/已经被别人打死）会回到 boss 列表并带一句提示。
        """
        try:
            url = self.bot.driver.current_url
        except Exception as e:
            self.log(f'VIP狙击：读取落地页地址失败 {type(e).__name__}: {e}')
            return
        text = ''
        try:
            text = self.bot.driver.execute_script(
                "return document.body ? (document.body.innerText || '')"
                ".replace(/\\s+/g, ' ').slice(0, 200) : ''"
            ) or ''
        except Exception:
            pass
        self.log(f'VIP狙击：落地页 {url} | {text}')

    def _finish(self, success: bool):
        # 先看一眼服务端到底返回了什么，再去做（会导航的）结果确认
        self._capture_landing()
        # 脚本说"点到了"不算数，但也不能只读一次页面：刚提交完的 hunt 页
        # 常常还是提交之前的快照（实测晚了 1 秒才更新），读一次会把打成误判成没打成。
        #
        # 不过如果刚才那几枪的落地页已经明确写着 "Defeated or not Exists"，
        # 结果其实已经知道了，没必要再轮询 4.8 秒——那 4.8 秒正是 boss 刷出来
        # 后被别人抢走的窗口（2026-11-19 15:42 就差这 1.3 秒）。
        confirm_kwargs = {}
        if self._last_verdict == 'rejected':
            confirm_kwargs = {'attempts': 2, 'interval': 0.5}
        try:
            success = self._confirm_challenge_result(
                self.union_id, first_wait=0, **confirm_kwargs)
        except Exception as e:
            self.log(f'VIP狙击：确认挑战结果失败 {type(e).__name__}: {e}')
            success = False
        guard = self._guard()
        if guard is not None:
            try:
                guard.record_result(self.union_id, success)
            except Exception:
                pass
        self.log(f'VIP狙击结束：{"已进入挑战冷却，打成了" if success else "没打成（被人抢了或还没刷出来）"}')

        # 记一笔"这一轮已经试过了"，防止上层又把同一轮 T 丢回来重试
        try:
            self.bot.vip_snipe_last_fire_ts = time.time()
        except Exception:
            pass

        self.bot.reset_waiting_vip_boss_spawn_info()
        if success:
            self.set_state(StateFactory.create_world_pvp_state(self.bot))
            return

        # 没打成要分两种：
        #   1) 真打上了但输了 → 本号进入挑战冷却，这一轮到此为止；
        #   2) 落地页写着 not exists（服务端还没刷出）→ 什么都没生成、没有冷却，
        #      而 boss 往往在几百毫秒后就刷出来了（2026-11-19 15:42 那轮只差 1.3 秒）。
        #      这种情况交给追打状态盯着，boss 一出现就补一刀。
        cooldown = getattr(self.bot, 'challenge_next_cooldown', 0) or 0
        if cooldown > 0:
            self.log(f'VIP狙击：本号已进入挑战冷却（{cooldown}秒），这一轮打完收工')
            self.set_state(StateFactory.create_prepare_boss_state(self.bot))
            return

        self.log('VIP狙击：这一枪被服务端拒绝（没生成战斗、没给冷却），'
                 '转去盯着 boss 刷出来的那一刻补打')
        self.set_state(StateFactory.create_vip_chase_state(
            self.bot, self.union_id, self.advanced_action_config,
            self.spawn_timestamp_us,
        ))
