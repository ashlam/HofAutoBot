#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-

import os
import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QPushButton, QMessageBox, QInputDialog, QDialog, QLineEdit, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from selenium import webdriver
import atexit

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.update_character_source import update_character_source
from scripts.parse_characters import CharacterParser
from scripts.hof_auto_bot_main import HofAutoBot
from scripts.states.state_factory import StateFactory
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class BotThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status_update = pyqtSignal(dict)
    
    def __init__(self, server_id, driver):
        super().__init__()
        self.server_id = server_id
        self.driver = driver
        self.bot = None
        self.is_running = False
    
    def run(self):
        self.is_running = True
        self.bot = HofAutoBot()
        self.bot.status_update_signal = self.status_update
        self.bot.initialize_with_driver(self.server_id, self.driver)
        self.bot.run()
        # try:
            # self.is_running = True
            # self.bot = HofAutoBot()
            # self.bot.status_update_signal = self.status_update
            # self.bot.initialize_with_driver(self.server_id, self.driver)
            # self.bot.run()
        # except Exception as e:
        #     self.error.emit(str(e))
        # finally:
        #     self.is_running = False
        #     self.finished.emit()
    
    def stop(self):
        if self.bot and self.is_running:
            self.is_running = False
            self.bot.cleanup()
            self.bot = None

class CaptchaDialog(QDialog):
    def __init__(self, driver, parent=None):
        super().__init__(parent)
        self.driver = driver
        self.setWindowTitle('请输入验证码')
        self.setModal(True)
        self.captcha = ''
        self.init_ui()
        self.result = None

    def init_ui(self):
        layout = QVBoxLayout()
        label = QLabel('验证码:')
        self.input = QLineEdit()
        self.input.setPlaceholderText('请输入验证码')
        layout.addWidget(label)
        layout.addWidget(self.input)
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton('登录')
        self.btn_refresh = QPushButton('换个验证码')
        self.btn_close = QPushButton('关闭')
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.btn_login.clicked.connect(self.login)
        self.btn_refresh.clicked.connect(self.refresh_captcha)
        self.btn_close.clicked.connect(self.close)

    def refresh_captcha(self):
        try:
            # 查找并点击 getCaptcha() 的span
            from selenium.webdriver.common.by import By
            span = self.driver.find_element(By.XPATH, "//span[contains(@onclick, 'getCaptcha()')]")
            span.click()
        except Exception as e:
            QMessageBox.warning(self, '警告', f'刷新验证码失败: {e}')

    def login(self):
        self.captcha = self.input.text().strip()
        if not self.captcha:
            QMessageBox.warning(self, '警告', '请输入验证码')
            return
        self.accept()

    def close(self):
        self.reject()

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.driver = None
        self.current_server = None
        self.load_server_config()
        self.hof_auto_bot = None
        self.bot_thread = None
        
        # 注册退出时清理资源
        atexit.register(self.cleanup_on_exit)

    def cleanup_on_exit(self):
        """程序退出时强制清理所有持有的浏览器实例"""
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
        if self.driver:
            print("正在清理主窗口持有的浏览器实例...")
            try:
                self.driver.quit()
            except Exception as e:
                print(f"清理浏览器实例时出错: {e}")
            finally:
                self.driver = None

    def closeEvent(self, event):
        """窗口关闭时主动清理资源"""
        self.cleanup_on_exit()
        event.accept()

    def start_run(self):
        if not self.driver or not self.current_server:
            QMessageBox.warning(self, '警告', '请先打开浏览器并登录')
            return
        
        # 创建并启动Bot线程
        self.bot_thread = BotThread(self.current_server["id"], self.driver)
        self.bot_thread.finished.connect(self.on_bot_finished)
        self.bot_thread.error.connect(self.on_bot_error)
        self.bot_thread.status_update.connect(self.on_status_update)
        self.bot_thread.start()
        
        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def on_status_update(self, status_info):
        """更新状态显示"""
        # state_map = {
        #     'boss': '挑战Boss',
        #     'pvp': 'PVP竞技场',
        #     'world_pvp': '世界PVP',
        #     'normal_stage': '普通关卡'
        # }
        # state_text = state_map.get(status_info['state'], '未知状态')
        state_text = status_info['state']
        self.state_label.setText(f'当前状态：{state_text}')
        self.stamina_label.setText(f'体力值：{status_info["stamina"]}')
        self.cooldown_label.setText(f'冷却时间：{status_info["cooldown"]}秒')
    
    def stop_run(self):
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
            self.bot_thread = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        if self.hof_auto_bot:
            self.hof_auto_bot.cleanup()
    
    def on_bot_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bot_thread = None
    
    def on_bot_error(self, error_msg):
        QMessageBox.critical(self, '错误', f'Bot运行出错：{error_msg}')
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def init_ui(self):
        self.setWindowTitle('HofAutoBot登录器')
        self.setFixedSize(300, 300)
        
        # 设置应用图标
        icon_path = os.path.join(os.path.dirname(__file__), 'images', 'main_icon', 'app_icon.svg')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建服务器选择下拉框
        self.server_combo = QComboBox()
        layout.addWidget(self.server_combo)

        # 重新读取配置按钮
        self.reload_config_btn = QPushButton('重新读取配置')
        self.reload_config_btn.clicked.connect(self.reload_config)
        layout.addWidget(self.reload_config_btn)

        # 创建按钮
        self.browser_btn = QPushButton('打开浏览器')
        self.update_btn = QPushButton('更新角色')
        self.start_btn = QPushButton('启动')
        self.stop_btn = QPushButton('停止')

        # 设置按钮状态
        self.update_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

        # 添加按钮到布局
        layout.addWidget(self.browser_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        # 创建状态显示标签
        self.state_label = QLabel('当前状态：未运行')
        self.stamina_label = QLabel('体力值：--')
        self.cooldown_label = QLabel('冷却时间：--')
        layout.addWidget(self.state_label)
        layout.addWidget(self.stamina_label)
        layout.addWidget(self.cooldown_label)

        # 绑定按钮事件
        self.browser_btn.clicked.connect(self.open_browser)
        self.update_btn.clicked.connect(self.update_character)
        self.start_btn.clicked.connect(self.start_run)
        self.stop_btn.clicked.connect(self.stop_run)

    def load_server_config(self):
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'configs', 'server_address.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                server_config = json.load(f)
                
            # 添加服务器选项到下拉框
            for server in server_config['server_address']:
                self.server_combo.addItem(server['name'], server)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载服务器配置失败：{str(e)}')

    def open_browser(self):
        # 获取选中的服务器配置
        self.current_server = self.server_combo.currentData()
        if not self.current_server:
            QMessageBox.warning(self, '警告', '请先选择服务器')
            return
    
        # 启动浏览器
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service)
        self.driver.get(self.current_server['url'])
        
        # 等待页面加载完成
        self.driver.implicitly_wait(8)
        
        from scripts.account_config_reader import get_account_config

        default_user_name, default_password = get_account_config(self.current_server["config_path"])
        
        from selenium.webdriver.common.by import By

        # 定位用户名输入框并填写内容
        username_input = self.driver.find_element(By.NAME, "id")
        username_input.clear()
        username_input.send_keys(default_user_name)

        # 定位密码输入框并填写内容
        password_input = self.driver.find_element(By.NAME, "pass")
        password_input.clear()
        password_input.send_keys(default_password)

        # 弹出自定义验证码输入框
        dlg = CaptchaDialog(self.driver, self)
        if dlg.exec_() == QDialog.Accepted and dlg.captcha:
            captcha = dlg.captcha
            try:
                # 定位验证码输入框并填写内容
                captcha_input = self.driver.find_element(By.NAME, "captcha")
                captcha_input.clear()
                captcha_input.send_keys(captcha)
                print("账号、密码和验证码已成功填写！")

                login_button = self.driver.find_element(By.CSS_SELECTOR, 'input[name="Login"][class="btn"]')
                login_button.click()
                print("登录按钮已点击！")

                # 启用更新角色和启动按钮
                self.update_btn.setEnabled(True)
                self.start_btn.setEnabled(True)

            except Exception as e:
                QMessageBox.critical(self, '错误', f'填写验证码失败：{str(e)}')
                if self.driver:
                    self.driver.quit()
                    self.driver = None
                self.update_btn.setEnabled(False)
                self.start_btn.setEnabled(False)
        else:
            # 用户点击关闭，视为已手动登录成功
            QMessageBox.information(self, '提示', '您未输入验证码或点击了关闭。')
            # 启用更新角色和启动按钮
            self.update_btn.setEnabled(True)
            self.start_btn.setEnabled(True)

    def update_character(self):
        try:
            if not self.driver or not self.current_server:
                QMessageBox.warning(self, '警告', '请先打开浏览器并登录')
                return

            # 如果没有初始化HofAutoBot，则先初始化
            if not self.hof_auto_bot:
                self.hof_auto_bot = HofAutoBot()
                self.hof_auto_bot.initialize_with_driver(self.current_server['id'], self.driver)
            
            # 创建更新角色数据状态
            update_character_state = StateFactory.create_update_character_state(self.hof_auto_bot)
            
            # 设置完成后的回调
            def on_update_finished():
                QMessageBox.information(self, '成功', '角色数据更新完成！')
            
            # 创建一个临时的线程来执行更新操作
            class UpdateThread(QThread):
                finished = pyqtSignal()
                error = pyqtSignal(str)
                
                def __init__(self, state):
                    super().__init__()
                    self.state = state
                    self.is_stopped = False
                
                def run(self):
                    try:
                        self.state.process()
                        if not self.is_stopped:
                            self.finished.emit()
                    except Exception as e:
                        if not self.is_stopped:
                            self.error.emit(str(e))
                
                def stop(self):
                    self.is_stopped = True
            
            # 创建并启动线程
            self.update_thread = UpdateThread(update_character_state)
            self.update_thread.finished.connect(on_update_finished)
            self.update_thread.error.connect(lambda msg: QMessageBox.critical(self, '错误', f'更新角色数据时出错：{msg}'))
            self.update_thread.start()

        except Exception as e:
            QMessageBox.critical(self, '错误', f'更新角色数据时出错：{str(e)}')

    def reload_config(self):
        try:
            if not self.current_server or not self.driver:
                QMessageBox.warning(self, '警告', '请先打开浏览器并登录')
                return
            if not self.hof_auto_bot:
                self.hof_auto_bot = HofAutoBot()
            self.hof_auto_bot.initialize_with_driver(self.current_server['id'], self.driver)
            QMessageBox.information(self, '成功', '配置已重新读取！')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'重新读取配置失败: {e}')

def main():
    app = QApplication(sys.argv)
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(__file__), 'images', 'main_icon', 'app_icon.svg')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()