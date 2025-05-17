import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QTextEdit,
                             QComboBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

class ActionEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('动作编辑器')
        self.setGeometry(100, 100, 800, 600)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images', 'main_icon', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 基本信息区域
        basic_info = QWidget()
        basic_layout = QVBoxLayout(basic_info)
        
        # 名称输入
        name_widget = QWidget()
        name_layout = QHBoxLayout(name_widget)
        name_label = QLabel('名称：')
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        basic_layout.addWidget(name_widget)
        
        # 备注输入
        note_widget = QWidget()
        note_layout = QHBoxLayout(note_widget)
        note_label = QLabel('备注：')
        self.note_input = QTextEdit()
        self.note_input.setMaximumHeight(100)
        note_layout.addWidget(note_label)
        note_layout.addWidget(self.note_input)
        basic_layout.addWidget(note_widget)
        
        layout.addWidget(basic_info)
        
        # 动作信息表格
        self.action_table = QTableWidget()
        self.action_table.setColumnCount(4)
        self.action_table.setHorizontalHeaderLabels(['触发类型', '元素信息', '容器信息', '等待时间(ms)'])
        header = self.action_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.action_table)
        
        # 按钮区域
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        add_row_btn = QPushButton('添加动作')
        add_row_btn.clicked.connect(self.add_row)
        delete_row_btn = QPushButton('删除动作')
        delete_row_btn.clicked.connect(self.delete_row)
        save_btn = QPushButton('保存')
        save_btn.clicked.connect(self.save_action)
        
        button_layout.addWidget(add_row_btn)
        button_layout.addWidget(delete_row_btn)
        button_layout.addWidget(save_btn)
        
        layout.addWidget(button_widget)
        
        # 初始化一行
        self.add_row()
    
    def add_row(self):
        row = self.action_table.rowCount()
        self.action_table.insertRow(row)
        
        # 触发类型下拉框
        trigger_type = QComboBox()
        trigger_type.addItems(['按钮', '复选框', '跳转'])
        self.action_table.setCellWidget(row, 0, trigger_type)
        
        # 元素信息输入框
        element_info = QLineEdit()
        self.action_table.setCellWidget(row, 1, element_info)
        
        # 容器信息输入框
        container_info = QLineEdit()
        self.action_table.setCellWidget(row, 2, container_info)
        
        # 等待时间输入框
        wait_time = QSpinBox()
        wait_time.setRange(0, 60000)  # 0-60000ms
        wait_time.setSingleStep(100)  # 步进值100ms
        wait_time.setValue(1000)  # 默认1000ms
        self.action_table.setCellWidget(row, 3, wait_time)
    
    def delete_row(self):
        current_row = self.action_table.currentRow()
        if current_row >= 0:
            self.action_table.removeRow(current_row)
    
    def save_action(self):
        try:
            # 读取现有配置
            try:
                with open('configs/action_config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    next_id = max(int(k) for k in config.keys()) + 1 if config else 1
            except FileNotFoundError:
                config = {}
                next_id = 1
            
            # 收集当前动作数据
            action_data = {
                'name': self.name_input.text(),
                'note': self.note_input.toPlainText(),
                'actions': []
            }
            
            # 收集表格中的动作信息
            for row in range(self.action_table.rowCount()):
                action_info = {
                    'trigger_type': self.action_table.cellWidget(row, 0).currentText(),
                    'element_info': self.action_table.cellWidget(row, 1).text(),
                    'container_info': self.action_table.cellWidget(row, 2).text(),
                    'wait_time': self.action_table.cellWidget(row, 3).value()
                }
                action_data['actions'].append(action_info)
            
            # 添加到配置中
            config[str(next_id)] = action_data
            
            # 保存配置
            with open('configs/action_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            # 清空输入
            self.name_input.clear()
            self.note_input.clear()
            self.action_table.setRowCount(0)
            self.add_row()
            
        except Exception as e:
            print(f'保存失败：{str(e)}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = ActionEditor()
    editor.show()
    sys.exit(app.exec_())