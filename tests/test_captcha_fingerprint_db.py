"""验证码指纹库 + 登录成功自动标注的测试。

核心断言：
  1. phash 对同一张图稳定、对不同图分得开（阈值 6 有足够余量）；
  2. 库能落盘、能重载、能精确命中；
  3. 只有"登录成功"才写库，写库不会因为库文件损坏而抛异常。
"""

import json
import os
import shutil
import sys
import tempfile

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.captcha_fingerprint import (  # noqa: E402
    DEFAULT_MATCH_THRESHOLD,
    CaptchaFingerprintDB,
    db_path_for,
    distance,
    open_db,
    open_db_safe,
    phash,
)
from scripts.captcha_recognizer import (  # noqa: E402
    CaptchaResult,
    record_captcha_failure,
    record_captcha_success,
)


def _fake_captcha(code, size=(100, 40)):
    """造一张"像验证码"的图：白底、五位数字、外加随 code 变化的大块图案。

    大块图案是必须的——phash 取的是低频 DCT 系数，只有细笔画的图彼此太像。
    """
    img = Image.new('RGB', size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(code):
        n = int(ch)
        x0 = 4 + i * 19
        d.rectangle([x0, 40 - 6 - n * 3, x0 + 8 + n, 38], fill=(n * 20 % 250, 0, 0))
        d.line([(x0, 2), (x0 + n * 2, 20)], fill=(0, 0, n * 25 % 250), width=2)
        d.text((x0 + 2, 10), ch, fill=(20, 20, 20))
    return img


@pytest.fixture()
def tmpdir():
    p = tempfile.mkdtemp(prefix='capdb_')
    yield p
    shutil.rmtree(p, ignore_errors=True)


class TestPhash:
    def test_same_image_same_hash(self):
        img = _fake_captcha('31842')
        assert phash(img) == phash(img.copy())

    def test_hash_is_16_hex(self):
        h = phash(_fake_captcha('12345'))
        assert len(h) == 16 and int(h, 16) >= 0

    def test_different_images_are_far(self):
        """不同答案的图，汉明距离应远超阈值，不会被误判成同一张。"""
        codes = ['13579', '24680', '11111', '90210', '58473']
        hashes = [phash(_fake_captcha(c)) for c in codes]
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                assert distance(hashes[i], hashes[j]) > DEFAULT_MATCH_THRESHOLD

    def test_distance_edge_cases(self):
        assert distance('', 'abc') == 64
        assert distance('zz', 'zz') == 64   # 非法十六进制不抛异常
        assert distance(phash(_fake_captcha('1')), phash(_fake_captcha('1'))) == 0


class TestDB:
    def test_record_and_exact_lookup(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'), scope='server_1')
        fp = phash(_fake_captcha('31842'))
        assert db.lookup(fp)[0] is None
        db.record(fp, '31842')
        code, detail = db.lookup(fp)
        assert code == '31842'
        assert detail['exact'] is True and detail['distance'] == 0

    def test_persist_and_reload(self, tmpdir):
        path = os.path.join(tmpdir, 'db.json')
        db = CaptchaFingerprintDB(path)
        fp = phash(_fake_captcha('70001'))
        db.record(fp, '70001')
        assert db.save() is True
        again = CaptchaFingerprintDB(path)
        assert again.lookup(fp)[0] == '70001'

    def test_save_without_change_is_noop(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        assert db.save() is False
        db.record(phash(_fake_captcha('22222')), '22222')
        assert db.save() is True
        assert db.save() is False

    def test_duplicate_record_keeps_one_entry(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        fp = phash(_fake_captcha('44444'))
        db.record(fp, '44444')
        db.record(fp, '44444')
        assert db.stats()['entries'] == 1
        assert db._entries[fp]['samples'] == 2

    def test_conflict_prefers_new_answer(self, tmpdir):
        """登录成功是硬证据：同图不同答案时以新答案为准，但记一次 conflicts。"""
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        fp = phash(_fake_captcha('55555'))
        db.record(fp, '55555')
        db.record(fp, '66666')
        code, _ = db.lookup(fp)
        assert code == '66666'
        assert db._entries[fp]['conflicts'] == 1
        assert db._entries[fp]['prev_code'] == '55555'

    def test_corrupted_file_does_not_raise(self, tmpdir):
        path = os.path.join(tmpdir, 'db.json')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{ this is not json')
        db = CaptchaFingerprintDB(path)
        assert db.stats()['entries'] == 0
        db.record(phash(_fake_captcha('99999')), '99999')
        assert db.save() is True

    def test_entry_without_code_is_dropped(self, tmpdir):
        path = os.path.join(tmpdir, 'db.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'entries': {'deadbeefdeadbeef': {'hits': 1}, 'aa': {'code': '1234'}}}, f)
        db = CaptchaFingerprintDB(path)
        assert list(db._entries) == ['aa']

    def test_fuzzy_lookup_within_threshold(self, tmpdir):
        """同一张图轻微改动（重编码）仍能命中。"""
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        img = _fake_captcha('13790')
        db.record(phash(img), '13790')
        # 整体亮度微调，phash 应几乎不变
        bright = Image.eval(img, lambda v: min(255, v + 3))
        code, detail = db.lookup(phash(bright))
        assert code == '13790'
        assert detail['distance'] <= DEFAULT_MATCH_THRESHOLD


class TestPaths:
    def test_db_path_is_per_server(self):
        p1 = db_path_for('configs/server_01')
        p2 = db_path_for('configs/server_02')
        assert p1 != p2
        assert p1.endswith('captcha_db_01.json') and p2.endswith('captcha_db_02.json')

    def test_open_db_safe_returns_none_on_bad_input(self):
        assert open_db_safe(None) is None

    def test_open_db_creates_dir_on_save(self, tmpdir):
        db = open_db(os.path.join(tmpdir, 'nested', 'configs', 'server_01'))
        db.record(phash(_fake_captcha('80808')), '80808')
        assert db.save() is True
        assert os.path.exists(db.path)


class TestRecordOnLoginSuccess:
    def test_records_fingerprint_when_code_present(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        img = _fake_captcha('20481')
        res = CaptchaResult('20481', '指纹精确命中', phash(img), True, img)
        assert record_captcha_success(db, res) is True
        assert db.lookup(phash(img))[0] == '20481'
        # 已落盘
        assert CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json')).lookup(phash(img))[0] == '20481'

    def test_no_record_without_fingerprint(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        assert record_captcha_success(db, CaptchaResult('1234', '未在表中')) is False
        assert db.stats()['entries'] == 0

    def test_no_record_without_code(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        img = _fake_captcha('12345')
        assert record_captcha_success(db, CaptchaResult('', '空值', phash(img), False, img)) is False

    def test_none_db_is_harmless(self):
        assert record_captcha_success(None, CaptchaResult('1234', 'x', 'aa')) is False

    def test_broken_db_does_not_raise(self):
        class Broken:
            def record(self, *a, **k):
                raise IOError('disk full')

            def save(self):
                return True

        res = CaptchaResult('1234', 'x', 'abcdefabcdefabcd')
        assert record_captcha_success(Broken(), res) is False


class TestWrongAnswerSelfHeals:
    """库里的答案是错的怎么办：摘掉它，别让同一张图永远错下去。"""

    def test_failure_only_forgets_db_hits(self, tmpdir):
        path = os.path.join(tmpdir, 'db.json')
        db = CaptchaFingerprintDB(path)
        img = _fake_captcha('31415')
        fp = phash(img)
        db.record(fp, '31415')

        # OCR 出来的答案错了（from_db=False），不能因为登录失败就删库里的好条目
        ocr_res = CaptchaResult('31415', '未在表中', fp, False, img)
        assert record_captcha_failure(db, ocr_res) is False
        assert db.lookup(fp)[0] == '31415'

        # 库里的答案被证伪 → 摘掉，且落盘
        db_res = CaptchaResult('31415', '指纹精确命中', fp, True, img)
        assert record_captcha_failure(db, db_res) is True
        assert db.lookup(fp)[0] is None
        assert CaptchaFingerprintDB(path).lookup(fp)[0] is None

    def test_retired_keeps_trace(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        fp = phash(_fake_captcha('27182'))
        db.record(fp, '27182')
        db.forget(fp, reason='login_failed')
        assert db.stats()['retired'] == 1
        assert db._retired[fp]['code'] == '27182'
        assert db._retired[fp]['retired_reason'] == 'login_failed'

    def test_retired_is_capped(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        for i in range(105):
            fp = '%016x' % i
            db.record(fp, '12345')
            db.forget(fp, reason='login_failed')
        assert len(db._retired) <= 100

    def test_forget_unknown_fp_is_noop(self, tmpdir):
        db = CaptchaFingerprintDB(os.path.join(tmpdir, 'db.json'))
        assert db.forget('ffffffffffffffff') is False
        assert db.forget(None) is False


class TestAttemptsAreCapped:
    """配置里写 100 次刷新也只会按上限来 —— 一次登录刷上百张图就是压测。"""

    def test_attempts_capped(self, monkeypatch):
        import types

        from scripts import captcha_recognizer as cr

        fake_tess = types.SimpleNamespace(
            pytesseract=types.SimpleNamespace(tesseract_cmd=''),
            image_to_string=lambda img, lang=None, config=None: '12',  # 太短，永远不合格
        )
        monkeypatch.setitem(sys.modules, 'pytesseract', fake_tess)
        monkeypatch.setattr(cr, '_grab_captcha_image', lambda *a, **k: _fake_captcha('12345'))
        monkeypatch.setattr(cr, '_preprocess_image_advanced', lambda img: img)
        monkeypatch.setattr(cr.time, 'sleep', lambda s: None)

        class _El:
            def __init__(self):
                self.clicks = 0

            def click(self):
                self.clicks += 1

        class _Drv:
            def __init__(self):
                self.el = _El()
                self.script_calls = 0

            def find_element(self, by, sel):
                return self.el

            def execute_script(self, *a, **k):
                # 刷新是走 JS 点的（`_click_refresh`），所以用脚本调用次数计刷新次数
                self.script_calls += 1
                return None

        drv = _Drv()
        res = cr.recognize_captcha_ex(drv, attempts=500)
        assert res.code == ''
        assert drv.script_calls == cr.MAX_CAPTCHA_ATTEMPTS


class TestCaptchaResultCompat:
    def test_unpacks_as_two_tuple(self):
        """老代码 `code, info = recognize_captcha(...)` 必须继续能解。"""
        res = CaptchaResult('31964', '直接匹配')
        code, info = res
        assert (code, info) == ('31964', '直接匹配')
