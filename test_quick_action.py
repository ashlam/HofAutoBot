from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scripts.log_manager import LogManager
from scripts.action_executor import ActionExecutor
import os
import json
import time

def get_server_url(server_id: int) -> str:
    """获取服务器地址"""
    with open('configs/server_address.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for server in config['server_address']:
        if server['id'] == server_id:
            return server['url']
    
    raise ValueError(f'找不到服务器ID: {server_id}')

def get_account_info(server_id: int) -> tuple[str, str]:
    """获取账号信息"""
    config_path = os.path.join('configs', f'server_0{server_id}', 'account_config.json')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f'找不到账号配置文件: {config_path}')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get('user_name'), config.get('password')

def main():
    logger = LogManager.get_instance()
    
    # 设置Chrome选项
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')  # 最大化窗口
    options.add_argument('--disable-notifications')  # 禁用通知
    
    # 创建Chrome浏览器实例
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)  # 设置显式等待时间为10秒
    
    try:
        # 获取服务器地址和账号信息
        url = get_server_url(1)
        username, password = get_account_info(1)
        
        # 访问游戏登录页面
        logger.info(f'正在连接服务器：{url}')
        driver.get(url)
        
        # 等待并填充用户名和密码
        username_input = wait.until(EC.presence_of_element_located((By.NAME, 'id')))
        password_input = driver.find_element(By.NAME, 'pass')
        
        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)
        
        # 点击登录按钮
        # login_button = driver.find_element(By.CSS_SELECTOR, 'input[name="Login"][class="btn"]')
        # login_button.click()
        
        logger.info('账号信息已填充，输入y执行动作组，其他键退出：')
        user_input = input().strip().lower()
        
        if user_input == 'y':
            # 直接访问指定URL
            
            target_url = 'https://pim0110.com/hall/index.php?union=8#'
            logger.info(f'正在访问：{target_url}')
            driver.get(target_url)
            
            # 等待100秒
            logger.info('页面加载完成，等待100秒...')
            time.sleep(100)
        
    except Exception as e:
        logger.error(f'发生错误：{str(e)}')
    finally:
        input('按回车键关闭浏览器...')
        driver.quit()

if __name__ == '__main__':
    main()
