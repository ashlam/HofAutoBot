# -*- coding: utf-8 -*-
"""VIP boss 狙击状态。

现状的问题是：睡到刷新时刻 T 之后，才去加载 boss 页面、清队、勾人、点开战。
光页面加载就要 1~2 秒，所以实际出手必然在 T+1~3 秒；而这个偏差会被
"下次刷新 = 本次击杀时间 + 4h" 的机制带进下一轮，越飘越远。

这个状态把"能提前做的"全部挪到 T 之前：
    T - warmup_lead   加载 boss 页面、清队、勾好角色（此时还不需要 boss 已存在）
    T - fire_cost     只做最后一次点击，让请求正好压在 T 上

如果 T 之前 boss 页面里还没有可提交的表单（预热失败），就退化成
"到 T 再加载一次页面、打一下"——也就是 T+0 之后盲试 1 次。
之后无论成败都不再重试，避免把一次抢怪变成对服务器的连续请求。
"""

import time
from datetime import datetime

from .base_state import BaseState
from .state_factory import StateFactory


# 预热：清队 + 勾好角色，但不点开战
_WARMUP_JS = """
var clearBtn = document.querySelector("input[onclick='checkDelAll()']");
if (clearBtn) { clearBtn.click(); }
var ids = arguments[0] || [];
var selected = 0, missing = 0;
ids.forEach(function (id) {
    var el = document.getElementsByName(id)[0];
    if (!el) { missing++; return; }
    if (!el.checked) { el.click(); }
    if (el.checked) { selected++; }
});
var battle = Array.prototype.slice
    .call(document.getElementsByName(arguments[1]))
    .filter(function (el) { return !el.getAttribute('data-snipe-synth'); })[0];
return {
    selected: selected,
    expected: ids.length,
    missing: missing,
    has_battle_button: !!battle,
    has_form: !!document.forms.Form_Hu_Union
};
"""

# 出手：优先点页面上现成的开战按钮；页面上没有按钮（boss 还没刷出来）时，
# 就地复用同一个队伍表单提交，绝不为了一个按钮再加载一次页面。
_FIRE_JS = """
var ids = arguments[0] || [];
var battleName = arguments[1];
var unionId = arguments[2];

// 1) 页面上有现成的开战按钮 —— 直接用，这是最干净的一条路
//    注意要排除上一次重建表单时自己塞进去的 hidden input，否则会误判成按钮
var battle = Array.prototype.slice
    .call(document.getElementsByName(battleName))
    .filter(function (el) { return !el.getAttribute('data-snipe-synth'); })[0];
if (battle) {
    var missing = ids.filter(function (id) {
        return !document.getElementsByName(id)[0];
    });
    if (missing.length) { return 'not_ready:' + missing.length; }
    battle.click();
    return 'clicked';
}

// 2) 没有按钮：boss 大概率还没刷出来。不再重新加载页面，
//    直接在这个同源页面里重建一份一模一样的队伍表单提交出去。
try {
    var form = document.forms.Form_Hu_Union;
    // 提交地址优先照抄页面上现成表单的文件名，别把 index2.php 写死
    var actionBase = 'index2.php';
    var probe = form || document.querySelector('form[action*="union="]');
    if (probe) {
        var m = /([^\\/?#]+)\\?union=/.exec(probe.getAttribute('action') || '');
        if (m) { actionBase = m[1]; }
    }
    if (!form) {
        form = document.createElement('form');
        form.id = 'Form_Hu_Union';
        document.body.appendChild(form);
    }
    form.method = 'post';
    form.action = actionBase + '?union=' + unionId;
    // 先清掉页面自带的老队伍，避免提交"旧队 + 新队"
    Array.prototype.slice.call(form.querySelectorAll('input[name^="char_"]'))
        .forEach(function (el) { el.parentNode.removeChild(el); });
    // 也清掉上一次重建时塞进去的提交项，避免 POST body 出现两个同名参数
    Array.prototype.slice.call(form.querySelectorAll('input[data-snipe-synth]'))
        .forEach(function (el) { el.parentNode.removeChild(el); });
    ids.forEach(function (id) {
        var el = document.createElement('input');
        el.type = 'checkbox';
        el.name = id;
        el.value = '1';
        el.checked = true;
        form.appendChild(el);
    });
    var submitter = document.createElement('input');
    submitter.type = 'hidden';
    submitter.name = battleName;
    submitter.value = '1';
    submitter.setAttribute('data-snipe-synth', '1');
    form.appendChild(submitter);
    form.submit();
    return 'submitted';
} catch (e) {
    return 'rebuild_failed:' + e;
}
"""


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
        self._fire_result = None
        self._blind_tried = False
        self._used_button = False
        self._page_has_button = False
        self.last_delta_ms = None

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
            '提交偏移 {off:+.0f}ms'.format(
                T=datetime.fromtimestamp(target_local).strftime('%H:%M:%S.%f')[:-3],
                warm=self.warmup_lead,
                cost=self.fire_cost * 1000,
                off=self.commit_offset * 1000,
            )
        )

        # 1) 预热：把页面加载和选人这些"慢动作"全部放到 T 之前
        self._wait_until(fire_at - self.warmup_lead)
        self._warmup_ok = self._warmup()
        if self._warmup_ok:
            self.log(f'VIP狙击：预热完成（耗时 {self._warmup_cost:.2f}s），'
                     f'角色已勾好，只等 T 时刻提交')
        else:
            self.log('VIP狙击：预热失败（页面里还没有可提交的表单），'
                     '改为到点重新加载页面后打一次')

        # 2) 定点提交
        self._wait_until(fire_at - self.fire_cost)
        fire_ts = time.time()
        if self._warmup_ok:
            self._fire_result = self._submit()
            if self._fire_result == 'blocked':
                self.log('VIP狙击：被挑战闸门拦截，本轮不再发送任何请求')
            elif not self._result_sent(self._fire_result):
                # 预热页面上连队伍表单都用不了，只能重新加载页面盲试一次
                self.log(f'VIP狙击：预热页面无法提交（{self._fire_result}），重新加载页面盲试一次')
                self._fire_result = self._blind_fire()
        else:
            self._fire_result = self._blind_fire()

        self.last_delta_ms = (fire_ts - target_local) * 1000.0
        if self._fire_result == 'blocked':
            how = '未发送'
        else:
            how = '点按钮' if self._used_button else '重建表单'
        self.log(f'VIP狙击：提交结果={self._fire_result}（{how}），'
                 f'相对 T 的实际偏差 {self.last_delta_ms:+.0f}ms')

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
        """加载 boss 页面并把队伍勾好，但不点开战。"""
        t0 = time.time()
        try:
            self.bot.driver.get(self._boss_url())
            self._wait_page_ready()
            info = self.bot.driver.execute_script(
                _WARMUP_JS, self._char_ids(), self._battle_button()
            )
            self._warmup_cost = time.time() - t0
        except Exception as e:
            self._warmup_cost = time.time() - t0
            self.log(f'VIP狙击：预热异常 {type(e).__name__}: {e}')
            return False

        if not isinstance(info, dict):
            return False
        if info.get('selected', 0) < info.get('expected', 0):
            self.log(f"VIP狙击：只勾上 {info.get('selected')}/{info.get('expected')} 个角色")
            return False
        self._page_has_button = bool(info.get('has_battle_button'))
        if not self._page_has_button:
            self.log('VIP狙击：预热页面里还没有开战按钮（boss 未刷出来），'
                     '到点会复用同一个队伍表单直接提交，不再加载页面')
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

    def _claim_shot(self) -> bool:
        """发请求前先过闸门：同一只 boss 同一轮刷新只允许一次。"""
        guard = self._guard()
        if guard is None:
            return True
        try:
            return bool(guard.claim(self.union_id, self.spawn_timestamp_us, 'vip_snipe'))
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

    def _submit(self):
        if not self._claim_shot():
            return 'blocked'
        try:
            result = self.bot.driver.execute_script(
                _FIRE_JS, self._char_ids(), self._battle_button(), self.union_id
            )
        except Exception as e:
            # 点击触发表单提交后页面会开始跳转，execute_script 有可能来不及拿到返回值
            self.log(f'VIP狙击：提交时页面已跳转（{type(e).__name__}），按已提交处理')
            self._used_button = True
            return 'clicked'
        self._used_button = (result == 'clicked')
        if not self._result_sent(result):
            self._release_shot()
        return result

    def _blind_fire(self):
        """T 之后的唯一一次尝试：加载页面 + 立刻提交。"""
        if self._blind_tried:
            return 'skipped'
        self._blind_tried = True
        try:
            self.bot.driver.get(self._boss_url())
            self._wait_page_ready()
            self.bot.driver.execute_script(
                _WARMUP_JS, self._char_ids(), self._battle_button()
            )
        except Exception as e:
            self.log(f'VIP狙击：盲试加载页面异常 {type(e).__name__}: {e}')
            return 'error'
        return self._submit()

    # ------------------------------------------------------------------ 收尾

    def _settle(self):
        """点完之后稍等一下，让表单提交真正到达服务器。"""
        if self.settle_seconds > 0:
            time.sleep(self.settle_seconds)

    def _finish(self, success: bool):
        try:
            self.bot._update_info_from_hunt_page()
        except Exception as e:
            self.log(f'VIP狙击：更新 boss 信息失败 {type(e).__name__}: {e}')

        cooldown = getattr(self.bot, 'challenge_next_cooldown', 0) or 0
        # 脚本说"点到了"不算数：只有服务端真的给了挑战冷却才算打成
        # （被别人抢先时点下去也是成功的点击，但不会进冷却）
        success = cooldown > 0
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
        else:
            # 失败就用掉这一轮，不再连击；PrepareBoss 看到 cooldown 会自然进入别的流程
            self.set_state(StateFactory.create_prepare_boss_state(self.bot))
