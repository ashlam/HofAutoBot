import time
import threading
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)

# 模拟修补后的_wait方法
def patched_wait(seconds, is_pvp=False):
    """等待指定的毫秒数，使用事件等待和补偿机制提供更精确的等待时间控制"""
    if seconds <= 0:
        return
    
    # 记录开始时间
    start_wait = time.perf_counter()  # 使用高精度计时器
    
    # 根据是否为PVP场景选择不同的补偿因子
    compensation_factor = 0.9 if is_pvp else 0.95
    
    logging.info(f"[等待日志] 开始等待 {seconds} 毫秒，{'PVP模式' if is_pvp else '普通模式'}")
    print(f"\033[96m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] _wait 开始等待 {seconds} 毫秒，{'PVP模式' if is_pvp else '普通模式'}\033[0m")
    
    # 应用补偿因子计算实际等待时间
    adjusted_seconds = seconds * compensation_factor
    
    # 新加的调试信息，显示原始和补偿后的等待时间
    print(f"\033[93m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] DEBUG: 等待 {adjusted_seconds / 1000:.4f} 秒 (补偿后，原始={seconds})\033[0m")
    
    # 计算目标结束时间（基于原始毫秒数，而非调整后的值）
    target_end_time = start_wait + (seconds / 1000)
    
    # 使用事件等待
    event = threading.Event()
    
    # 首先等待调整后的大部分时间
    initial_wait = adjusted_seconds / 1000
    if initial_wait > 0:
        event.wait(initial_wait)
    
    # 使用短循环等待剩余时间，以获得更精确的控制
    while time.perf_counter() < target_end_time:
        # 非常短的等待，避免CPU过度使用
        event.wait(0.0001)  # 0.1毫秒的微小等待
    
    # 记录结束时间和实际等待时间
    end_wait = time.perf_counter()
    actual_wait_ms = (end_wait - start_wait) * 1000
    
    logging.info(f"[等待日志] 结束等待，实际耗时: {actual_wait_ms:.2f} 毫秒，预期: {seconds} 毫秒")
    print(f"\033[96m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] _wait 结束等待，实际耗时: {actual_wait_ms:.2f} 毫秒，预期: {seconds} 毫秒\033[0m")
    
    return actual_wait_ms

# 模拟原始的time.sleep方法
def original_sleep(seconds):
    """使用原始的time.sleep方法等待指定的毫秒数"""
    if seconds <= 0:
        return
    
    start_wait = time.perf_counter()
    print(f"\033[95m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] 原始sleep开始等待 {seconds} 毫秒\033[0m")
    
    time.sleep(seconds / 1000)
    
    end_wait = time.perf_counter()
    actual_wait_ms = (end_wait - start_wait) * 1000
    print(f"\033[95m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] 原始sleep结束等待，实际耗时: {actual_wait_ms:.2f} 毫秒，预期: {seconds} 毫秒\033[0m")
    
    return actual_wait_ms

# 测试函数
def test_wait_functions():
    print("\n=== 测试原始time.sleep ===")
    for ms in [50, 100, 200]:
        original_sleep(ms)
    
    print("\n=== 测试修补后的普通等待函数 ===")
    for ms in [50, 100, 200]:
        patched_wait(ms, is_pvp=False)
    
    print("\n=== 测试修补后的PVP等待函数 ===")
    for ms in [50, 100, 200]:
        patched_wait(ms, is_pvp=True)

# 在多线程环境中测试
def test_in_threads():
    print("\n=== 在多线程环境中测试等待函数 ===")
    
    def background_task():
        """后台任务，模拟其他线程的工作"""
        for _ in range(10):
            # 模拟一些工作
            sum([i**2 for i in range(100000)])
            # 短暂休眠，让出CPU
            time.sleep(0.01)
    
    # 启动后台线程
    threads = []
    for _ in range(3):
        t = threading.Thread(target=background_task)
        t.daemon = True
        t.start()
        threads.append(t)
    
    # 在有后台线程的情况下测试等待
    print("\n=== 多线程环境中测试原始time.sleep ===")
    for ms in [50, 100, 200]:
        original_sleep(ms)
    
    print("\n=== 多线程环境中测试修补后的普通等待函数 ===")
    for ms in [50, 100, 200]:
        patched_wait(ms, is_pvp=False)
    
    print("\n=== 多线程环境中测试修补后的PVP等待函数 ===")
    for ms in [50, 100, 200]:
        patched_wait(ms, is_pvp=True)
    
    # 等待所有线程完成
    for t in threads:
        t.join(timeout=1)

# 模拟动作执行器
class MockActionExecutor:
    def __init__(self, name):
        self.name = name
    
    def execute(self, value=None, idle_before=0, idle_after=100, is_pvp=False):
        print(f"\n=== 执行{self.name}动作 ===")
        print(f"参数: value={value}, idle_before={idle_before}, idle_after={idle_after}, is_pvp={is_pvp}")
        
        print(f"执行前等待...")
        patched_wait(idle_before, is_pvp=is_pvp)
        
        print(f"执行动作: {self.name}")
        # 模拟动作执行
        time.sleep(0.05)
        
        print(f"执行后等待...")
        patched_wait(idle_after, is_pvp=is_pvp)
        
        print(f"动作执行完成: {self.name}")
        return True

# 测试模拟动作执行
def test_mock_action_executor():
    print("\n=== 测试模拟动作执行器 ===")
    
    # 创建模拟执行器
    normal_executor = MockActionExecutor("普通动作")
    pvp_executor = MockActionExecutor("PVP动作")
    
    # 执行普通动作
    normal_executor.execute(value="test", idle_before=100, idle_after=200, is_pvp=False)
    
    # 执行PVP动作
    pvp_executor.execute(value="test", idle_before=100, idle_after=200, is_pvp=True)

if __name__ == "__main__":
    print("开始测试修补后的等待函数...")
    test_wait_functions()
    test_in_threads()
    test_mock_action_executor()
    print("测试完成！")