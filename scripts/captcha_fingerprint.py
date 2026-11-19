"""验证码图片指纹库。

背景（2026-11-19 实测）：pim0110 的登录验证码不是每次随机渲染，而是服务端预生成
的一小批固定图片——**同一个答案永远返回字节完全相同的那一张**。70 次采样只出现
47 张唯一图（重复率 33%），跨 session（不同 cookie）也完全一致，且不同图之间的
phash 汉明距离最小 12，区分度很宽。

所以对这类验证码，最优解不是"识别得再准一点"，而是"认出这是库里哪一张图"：
命中即 100% 正确，且一次录入永久有效。

库的键是图片的感知哈希（phash），不是 OCR 的错串。这样做的原因是字符串映射
有两个无法修复的缺陷：
  1. 同一张图可能被 OCR 成不同错法，每种都要单独录；
  2. 不同的图可能被 OCR 成同一个错串，映射只能二选一，必错一边。

库会在登录成功时自动扩充：登录成功即证明本次提交的答案是正确的，这是免费的标注，
不需要任何人工录入。
"""

import json
import os
import time

import numpy as np
from PIL import Image

# 判定"同一张图"的汉明距离上界：实测不同图之间最小距离 12，取 6 留足余量，
# 既能容忍服务端将来对同一张图做轻微重编码，又不会把两张不同的图搞混。
DEFAULT_MATCH_THRESHOLD = 6

_BITS = 64
_HASH_SIDE = 8      # 低频 8x8 = 64 bit
_DCT_SIDE = 32      # 先缩到 32x32 再做 DCT


def _dct_matrix(n):
    """DCT-II 正交矩阵，用于纯 numpy 计算（避免依赖 cv2）。"""
    k = np.arange(n, dtype=np.float32)
    m = np.cos(np.pi * (2.0 * k[None, :] + 1.0) * k[:, None] / (2.0 * n))
    m *= np.sqrt(2.0 / n)
    m[0, :] *= np.sqrt(1.0 / 2.0)
    return m.astype(np.float32)


_CACHE = {}


def _matrix(n):
    if n not in _CACHE:
        _CACHE[n] = _dct_matrix(n)
    return _CACHE[n]


def _to_gray_array(img):
    """把 PIL.Image / bytes / 文件路径 / ndarray 统一成灰度 ndarray。"""
    if isinstance(img, (str, os.PathLike)):
        img = Image.open(img)
    if isinstance(img, (bytes, bytearray)):
        import io
        img = Image.open(io.BytesIO(img))
    if isinstance(img, np.ndarray):
        arr = img
        if arr.ndim == 3:
            # 按 BT.601 转灰度
            arr = arr[..., :3] @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        return arr.astype(np.float32)
    return np.asarray(img.convert('L'), dtype=np.float32)


def phash(img):
    """返回 64 bit 感知哈希（16 位十六进制字符串）。

    和 OCR 无关：只描述"这张图长什么样"，对整体亮度/轻微压缩不敏感。
    """
    arr = _to_gray_array(img)
    pil = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    small = pil.resize((_DCT_SIDE, _DCT_SIDE), Image.LANCZOS)
    a = np.asarray(small, dtype=np.float32)

    c = _matrix(_DCT_SIDE)
    d = c @ a @ c.T

    low = d[:_HASH_SIDE, :_HASH_SIDE].flatten()
    # 直流分量（low[0]）只反映整体亮度，把它排除在阈值统计之外
    threshold = float(np.median(low[1:]))
    bits = (low > threshold).astype(np.uint64)

    value = 0
    for bit in bits:
        value = (value << np.uint64(1)) | np.uint64(int(bit))
    return format(int(value), '016x')


def distance(h1, h2):
    """两个指纹的汉明距离。"""
    if not h1 or not h2:
        return _BITS
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count('1')
    except (TypeError, ValueError):
        return _BITS


class CaptchaFingerprintDB:
    """一个站点（或一个服）一份的图片指纹库。"""

    def __init__(self, path, scope='', match_threshold=DEFAULT_MATCH_THRESHOLD):
        self.path = os.path.abspath(path)
        self.scope = scope
        self.match_threshold = int(match_threshold)
        self._entries = {}
        self._retired = {}
        self._dirty = False
        self._load()

    # ------------------------------------------------------------------ 持久化

    def _load(self):
        self._entries = {}
        self._retired = {}
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            entries = data.get('entries') or {}
            if isinstance(entries, dict):
                # 只保留结构正确的条目，坏数据不让它拖垮整个库
                self._entries = {
                    str(k): dict(v) for k, v in entries.items()
                    if isinstance(v, dict) and v.get('code')
                }
            retired = data.get('retired') or {}
            if isinstance(retired, dict):
                self._retired = {str(k): dict(v) for k, v in retired.items() if isinstance(v, dict)}
        except FileNotFoundError:
            pass
        except Exception:
            # 库文件坏了就当空的重新开始，不能让登录流程因此失败
            self._entries = {}
            self._retired = {}

    def save(self, force=False):
        if not self._dirty and not force:
            return False
        data = {
            'version': 1,
            'scope': self.scope,
            'match_threshold': self.match_threshold,
            'saved_at': time.time(),
            'entries': self._entries,
            'retired': self._retired,
        }
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
        self._dirty = False
        return True

    # ------------------------------------------------------------------ 查询

    def lookup(self, fp):
        """返回 (code, 详情) —— 找不到时 code 为 None。

        详情里带 hit（是否精确命中）、distance、entries（库大小），方便打日志。
        """
        if not fp or not self._entries:
            return None, {'hit': False, 'distance': None, 'entries': len(self._entries)}

        exact = self._entries.get(fp)
        if exact:
            self._touch(fp, exact, exact=True)
            return exact.get('code'), {'hit': True, 'distance': 0,
                                       'entries': len(self._entries), 'exact': True}

        best_key, best_dist = None, _BITS
        for key in self._entries:
            d = distance(fp, key)
            if d < best_dist:
                best_key, best_dist = key, d
        if best_key is not None and best_dist <= self.match_threshold:
            entry = self._entries[best_key]
            # 把命中次数记在"库里那一条"上，便于以后清理/统计
            self._touch(best_key, entry, exact=False)
            return entry.get('code'), {'hit': True, 'distance': best_dist,
                                       'entries': len(self._entries), 'exact': False}
        return None, {'hit': False, 'distance': best_dist, 'entries': len(self._entries)}

    def _touch(self, key, entry, exact):
        entry['hits'] = int(entry.get('hits', 0)) + 1
        entry['last_hit'] = time.time()
        if not exact:
            entry['fuzzy_hits'] = int(entry.get('fuzzy_hits', 0)) + 1
        self._dirty = True

    # ------------------------------------------------------------------ 写入

    def record(self, fp, code, source='login_success'):
        """把一条「图片 → 答案」写进库。

        调用方必须在**确认答案正确**之后才调用（登录成功就是最好的确认）。
        已存在且答案不同时以新答案为准（登录成功是硬证据），但会记一次 conflicts，
        便于以后发现 phash 阈值是否放得太松。
        """
        if not fp or not code:
            return None
        code = str(code).strip()
        entry = self._entries.get(fp)
        now = time.time()
        if entry is None:
            entry = {
                'code': code,
                'hits': 0,
                'samples': 1,
                'source': source,
                'first_seen': now,
                'last_seen': now,
            }
            self._entries[fp] = entry
        else:
            if entry.get('code') != code:
                entry['conflicts'] = int(entry.get('conflicts', 0)) + 1
                entry['prev_code'] = entry.get('code')
                entry['code'] = code
            entry['samples'] = int(entry.get('samples', 1)) + 1
            entry['last_seen'] = now
        self._dirty = True
        return entry

    # ------------------------------------------------------------------ 统计

    def forget(self, fp, reason=''):
        """把一条标注从库里摘掉——用于"用了库里的答案却登录失败"。

        留着错答案只会让同一张图永远错下去，所以宁可摘掉、退回 OCR 重新确认。
        摘掉的条目不直接丢弃，挪到 retired 里留痕，方便以后判断阈值是不是放太松。
        """
        if not fp:
            return False
        entry = self._entries.pop(fp, None)
        if entry is None:
            return False
        entry['retired_at'] = time.time()
        entry['retired_reason'] = reason or 'unknown'
        self._retired[fp] = entry
        # retired 只留最近 100 条，别让它无限增长
        if len(self._retired) > 100:
            oldest = sorted(self._retired, key=lambda k: self._retired[k].get('retired_at', 0))
            for k in oldest[:len(self._retired) - 100]:
                self._retired.pop(k, None)
        self._dirty = True
        return True

    def stats(self):
        return {'entries': len(self._entries), 'retired': len(self._retired),
                'path': self.path, 'scope': self.scope,
                'match_threshold': self.match_threshold}


def db_path_for(config_dir, server_id=None):
    """库文件路径：按服（或按配置目录）隔离，不同服/不同站点绝不共用。"""
    if server_id is None:
        try:
            server_id = os.path.basename(os.path.normpath(config_dir)).split('_')[-1]
        except Exception:
            server_id = 'default'
    return os.path.join(config_dir, f'captcha_db_{server_id}.json')


def _resolve_server_id(config_dir, server_id):
    if server_id is not None:
        return server_id
    try:
        return os.path.basename(os.path.normpath(config_dir)).split('_')[-1]
    except Exception:
        return 'default'


def open_db(config_dir, server_id=None, match_threshold=DEFAULT_MATCH_THRESHOLD):
    server_id = _resolve_server_id(config_dir, server_id)
    path = db_path_for(config_dir, server_id)
    return CaptchaFingerprintDB(path, scope=f'server_{server_id}', match_threshold=match_threshold)


def open_db_safe(config_dir, server_id=None, match_threshold=DEFAULT_MATCH_THRESHOLD):
    """打开库，任何异常都退化成 None。

    凭据异常绝不能让登录流程失败——库打不开就当没有库，退回 OCR 一样能登。
    """
    if not config_dir:
        return None
    try:
        return open_db(config_dir, server_id, match_threshold)
    except Exception:
        return None
