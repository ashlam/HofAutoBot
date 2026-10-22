import sys
import os
import tempfile

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.log_manager import LogManager


def _reset_logger():
    """LogManager 是单例，测试之间需要重置状态"""
    LogManager._log_path = None
    LogManager._is_debug = False
    LogManager._instance = None


def test_log_written_to_file_when_path_set():
    """回归测试：设置了日志路径后，logger.info 应写入文件。

    背景：2025-05-28 的提交 77de8d9 在重构时丢掉了 logger.info(msg, True)
    里的位置参数 True，导致 is_write_in_file 恒为 False，
    logs/ 下的文件从此再也没更新过（停留在 2025-05-28）。
    """
    _reset_logger()
    tmpdir = tempfile.mkdtemp(prefix='logtest-')
    log_path = os.path.join(tmpdir, 'log_server_test.txt')

    logger = LogManager.get_instance()
    logger.set_log_path(log_path)
    logger.info('第一条消息')

    assert os.path.exists(log_path), "日志文件没有被创建"
    content = open(log_path, encoding='utf-8').read()
    assert '第一条消息' in content, f"日志内容不对: {content!r}"
    assert '[INFO]' in content, "应包含日志级别标记"


def test_all_levels_written_to_file():
    """error/warning/success 都应落盘"""
    _reset_logger()
    tmpdir = tempfile.mkdtemp(prefix='logtest-')
    log_path = os.path.join(tmpdir, 'log_all.txt')

    logger = LogManager.get_instance()
    logger.set_log_path(log_path)
    logger.info('信息')
    logger.warning('警告')
    logger.error('错误')
    logger.success('成功')

    content = open(log_path, encoding='utf-8').read()
    for text in ('信息', '警告', '错误', '成功'):
        assert text in content, f"{text} 未写入文件"
    for level in ('[INFO]', '[WARNING]', '[ERROR]', '[SUCCESS]'):
        assert level in content, f"{level} 未写入文件"


def test_log_appends_instead_of_rewriting_whole_file():
    """回归测试：写日志应为追加(O(1))，而不是每次重写整个文件(O(n))。

    背景：原 _write_to_file 每次都读全量再整体写回，文件越大越慢
    （实测 3.2MB 文件 16ms/行，比 append 慢 126 倍）。
    """
    _reset_logger()
    tmpdir = tempfile.mkdtemp(prefix='logtest-')
    log_path = os.path.join(tmpdir, 'log_append.txt')

    logger = LogManager.get_instance()
    logger.set_log_path(log_path)

    logger.info('第一行')
    first_size = os.path.getsize(log_path)
    logger.info('第二行')
    second_size = os.path.getsize(log_path)

    # 追加模式下，文件只增长；prepend 模式下文件大小基本不变（重写后长度相近）
    assert second_size > first_size, \
        f"日志应追加写入，文件应增长：{first_size} -> {second_size}"

    content = open(log_path, encoding='utf-8').read()
    assert '第一行' in content and '第二行' in content, "两行都应保留"
    # 追加模式下按写入顺序排列
    assert content.index('第一行') < content.index('第二行'), "追加写入应保持时间顺序"


def test_rotation_keeps_file_bounded():
    """回归测试：日志文件超过阈值后应轮转，避免无限增长"""
    _reset_logger()
    tmpdir = tempfile.mkdtemp(prefix='logtest-')
    log_path = os.path.join(tmpdir, 'log_rotate.txt')

    logger = LogManager.get_instance()
    logger.set_log_path(log_path)
    logger.set_max_file_size(1024)  # 1KB 阈值，方便测试

    for i in range(200):
        logger.info(f'轮转测试消息 {i} ' + 'x' * 50)

    assert os.path.exists(log_path), "当前日志文件应存在"
    assert os.path.getsize(log_path) < 4 * 1024, \
        f"轮转后当前文件应被限制在阈值附近，实际 {os.path.getsize(log_path)}"
    assert os.path.exists(log_path + '.1'), "应保留一个历史备份文件"


def test_no_log_path_does_not_crash():
    """未设置日志路径时，logger 应只输出到stdout，不报错"""
    _reset_logger()
    logger = LogManager.get_instance()
    logger.info('没有日志路径的消息')  # 不应抛异常
    logger.error('也没有日志路径的错误')


if __name__ == "__main__":
    test_log_written_to_file_when_path_set()
    test_all_levels_written_to_file()
    test_log_appends_instead_of_rewriting_whole_file()
    test_rotation_keeps_file_bounded()
    test_no_log_path_does_not_crash()
    print("全部测试通过！")
