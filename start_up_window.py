#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-

import os
import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QPushButton, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from selenium import webdriver
import atexit

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.update_character_source import update_character_source
from scripts.parse_characters import CharacterParser
from scripts.hof_auto_bot_main import HofAutoBot

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
        try:
            self.is_running = True
            self.bot = HofAutoBot()
            self.bot.status_update_signal = self.status_update
            self.bot.initialize_with_driver(self.server_id, self.driver)
            self.bot.run()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.is_running = False
            self.finished.emit()
    
    def stop(self):
        if self.bot and self.is_running:
            self.is_running = False
            self.bot.cleanup()
            self.bot = None

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

        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 创建服务器选择下拉框
        self.server_combo = QComboBox()
        layout.addWidget(self.server_combo)

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
        from PyQt5.QtWidgets import QLabel
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
        # try:
        # 获取选中的服务器配置
        self.current_server = self.server_combo.currentData()
        if not self.current_server:
            QMessageBox.warning(self, '警告', '请先选择服务器')
            return

        # 启动浏览器
        self.driver = webdriver.Chrome()
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


        # 弹出验证码输入框
        captcha, ok = QInputDialog.getText(self, '请输入验证码', '验证码:', text='8888')

        if ok and captcha.strip():
            try:
                # 定位验证码输入框并填写内容
                captcha_input = self.driver.find_element(By.NAME, "captcha")
                captcha_input.clear()
                captcha_input.send_keys(captcha.strip())
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
            # 用户点击取消或未输入内容
            QMessageBox.information(self, '提示', '您未输入验证码或点击了取消。')
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.update_btn.setEnabled(False)
            self.start_btn.setEnabled(False)

    def update_character(self):
        try:
            if not self.driver or not self.current_server:
                QMessageBox.warning(self, '警告', '请先打开浏览器并登录')
                return

            # 更新角色数据
            if not update_character_source(self.driver, self.current_server):
                QMessageBox.warning(self, '警告', '更新角色数据失败，请检查网络连接或登录状态')
                return

            # 解析角色数据
            source_file_name = f'source_code_character_{self.current_server["id"]}'
            parser = CharacterParser(source_file_name, server_id=self.current_server['id'])
            if parser.parse():
                QMessageBox.information(self, '成功', f'角色数据更新完成！\n配置文件位置: {parser.output_json}')
            else:
                QMessageBox.warning(self, '警告', '解析角色数据失败')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'更新角色数据时出错：{str(e)}')



    def closeEvent(self, event):
        # 关闭窗口时清理资源
        if self.driver:
            self.driver.quit()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()