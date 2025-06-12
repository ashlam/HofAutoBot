import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QComboBox, QCheckBox, 
                             QLineEdit, QPushButton, QLabel, QScrollArea, 
                             QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QClipboard, QIcon

class BossActionEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('王战编辑器')
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images', 'main_icon', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 加载配置文件
        self.load_configs()
        
        # 创建主界面
        self.init_ui()
    
    def load_configs(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        
        # 加载服务器配置
        with open(os.path.join(base_path, 'configs', 'server_address.json'), 'r', encoding='utf-8') as f:
            self.server_config = json.load(f)
        
        # 设置默认服务器
        self.current_server = self.server_config['server_address'][0]
        self.configs_path = os.path.join(base_path, self.current_server['config_path'])
        
        # 加载boss配置
        with open(os.path.join(self.configs_path, 'boss_config.json'), 'r', encoding='utf-8') as f:
            self.boss_config = json.load(f)
            # 按union_id排序
            self.boss_config['boss_list'].sort(key=lambda x: x['union_id'])
        
        # 加载角色配置
        with open(os.path.join(self.configs_path, 'character_config.json'), 'r', encoding='utf-8') as f:
            self.character_config = json.load(f)
        
        # 加载action配置
        self.action_config_path = os.path.join(self.configs_path, 'action_config_advanced.json')
        try:
            with open(self.action_config_path, 'r', encoding='utf-8') as f:
                self.action_config = json.load(f)
        except FileNotFoundError:
            self.action_config = {}
            # 创建配置文件
            os.makedirs(os.path.dirname(self.action_config_path), exist_ok=True)
            with open(self.action_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.action_config, f, indent=2, ensure_ascii=False)
    
    def init_ui(self):
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 创建数据标签页
        create_tab = QWidget()
        create_layout = QVBoxLayout(create_tab)
        
        # 服务器和Boss选择区域
        select_layout = QHBoxLayout()
        
        # 服务器选择下拉框
        server_layout = QHBoxLayout()
        server_label = QLabel('选择服务器：')
        self.server_combo = QComboBox()
        for server in self.server_config['server_address']:
            self.server_combo.addItem(f"{server['name']}", server)
        self.server_combo.currentIndexChanged.connect(self.on_server_changed)
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_combo)
        select_layout.addLayout(server_layout)
        
        # Boss选择下拉框
        boss_layout = QHBoxLayout()
        boss_label = QLabel('选择Boss：')
        self.boss_combo = QComboBox()
        for boss in self.boss_config['boss_list']:
            self.boss_combo.addItem(f"({boss['union_id']}){boss['name']} Lv.{boss['level_limit']}", boss['union_id'])
        boss_layout.addWidget(boss_label)
        boss_layout.addWidget(self.boss_combo)
        select_layout.addLayout(boss_layout)
        
        select_layout.addStretch()
        create_layout.addLayout(select_layout)
        
        # 角色列表（使用滚动区域）
        char_scroll = QScrollArea()
        char_scroll.setWidgetResizable(True)
        char_widget = QWidget()
        self.char_layout = QVBoxLayout(char_widget)  # 外层仍然是垂直布局

        # 添加角色复选框
        self.char_checkboxes = []
        for char in self.character_config['characters']:
            # 为每个角色创建一个水平布局的容器
            hbox = QHBoxLayout()
            
            checkbox = QCheckBox()
            char_text = f"{char['name']} | L{char['level']} {char['job_name']}({char['udid']}) | <font color='gray'>{char['equipment'].replace('<br>', ' || ')}</font>"
            checkbox.setProperty('udid', char['udid'])
            checkbox.setProperty('name', char['name'])
            checkbox.setProperty('level', char['level'])
            checkbox.setProperty('job_name', char['job_name'])

            label = QLabel()
            label.setText(char_text)
            label.setTextFormat(Qt.TextFormat.RichText)

            self.char_checkboxes.append(checkbox)
            
            # 将复选框和标签添加到水平布局
            hbox.addWidget(checkbox)
            hbox.addWidget(label)
            hbox.addStretch()  # 让内容靠左
            
            # 将水平布局添加到外层垂直布局
            self.char_layout.addLayout(hbox)
        
        char_scroll.setWidget(char_widget)
        create_layout.addWidget(char_scroll)
        
        # 配置信息输入区域
        config_layout = QHBoxLayout()
        
        # ID输入
        id_layout = QHBoxLayout()
        id_label = QLabel('ID：')
        self.id_input = QLineEdit()
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.id_input)
        config_layout.addLayout(id_layout)
        
        # 名称输入
        name_layout = QHBoxLayout()
        name_label = QLabel('名称：')
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        config_layout.addLayout(name_layout)
        
        # 备注输入
        note_layout = QHBoxLayout()
        note_label = QLabel('备注：')
        self.note_input = QLineEdit()
        note_layout.addWidget(note_label)
        note_layout.addWidget(self.note_input)
        config_layout.addLayout(note_layout)
        
        create_layout.addLayout(config_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        create_button = QPushButton('创建')
        create_button.clicked.connect(self.create_action_config)
        write_button = QPushButton('写入')
        write_button.clicked.connect(self.write_action_config)
        reset_button = QPushButton('重置')
        reset_button.clicked.connect(self.reset_form)
        button_layout.addWidget(create_button)
        button_layout.addWidget(write_button)
        button_layout.addWidget(reset_button)
        create_layout.addLayout(button_layout)
        
        # 预览区域
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        create_layout.addWidget(self.preview_text)
        
        # 编辑标签页
        edit_tab = QWidget()
        edit_layout = QVBoxLayout(edit_tab)
        
        # 编辑标签页的服务器选择区域
        edit_select_layout = QHBoxLayout()
        edit_server_label = QLabel('选择服务器：')
        self.edit_server_combo = QComboBox()
        for server in self.server_config['server_address']:
            self.edit_server_combo.addItem(f"{server['name']}", server)
        self.edit_server_combo.currentIndexChanged.connect(self.on_edit_server_changed)
        edit_select_layout.addWidget(edit_server_label)
        edit_select_layout.addWidget(self.edit_server_combo)
        edit_select_layout.addStretch()
        edit_layout.addLayout(edit_select_layout)
        
        # ID选择区域
        id_select_layout = QHBoxLayout()
        id_select_label = QLabel('选择id：')
        self.id_select_combo = QComboBox()
        self.id_select_combo.currentIndexChanged.connect(self.on_id_selected)
        id_select_layout.addWidget(id_select_label)
        id_select_layout.addWidget(self.id_select_combo)
        id_select_layout.addStretch()
        edit_layout.addLayout(id_select_layout)
        
        # 角色列表（使用滚动区域）
        edit_char_scroll = QScrollArea()
        edit_char_scroll.setWidgetResizable(True)
        edit_char_widget = QWidget()
        self.edit_char_layout = QVBoxLayout(edit_char_widget)

        # 添加角色复选框
        self.edit_char_checkboxes = []
        for char in self.character_config['characters']:
            # 为每个角色创建一个水平布局的容器
            hbox = QHBoxLayout()
            
            checkbox = QCheckBox()
            char_text = f"{char['name']} | L{char['level']} {char['job_name']}({char['udid']}) | <font color='gray'>{char['equipment'].replace('<br>', ' || ')}</font>"
            checkbox.setProperty('udid', char['udid'])
            checkbox.setProperty('name', char['name'])
            checkbox.setProperty('level', char['level'])
            checkbox.setProperty('job_name', char['job_name'])

            label = QLabel()
            label.setText(char_text)
            label.setTextFormat(Qt.TextFormat.RichText)

            self.edit_char_checkboxes.append(checkbox)
            
            # 将复选框和标签添加到水平布局
            hbox.addWidget(checkbox)
            hbox.addWidget(label)
            hbox.addStretch()  # 让内容靠左
            
            # 将水平布局添加到外层垂直布局
            self.edit_char_layout.addLayout(hbox)
        
        edit_char_scroll.setWidget(edit_char_widget)
        edit_layout.addWidget(edit_char_scroll)
        
        # 编辑信息输入区域
        edit_config_layout = QHBoxLayout()
        
        # ID输入
        edit_id_layout = QHBoxLayout()
        edit_id_label = QLabel('ID：')
        self.edit_id_input = QLineEdit()
        edit_id_layout.addWidget(edit_id_label)
        edit_id_layout.addWidget(self.edit_id_input)
        edit_config_layout.addLayout(edit_id_layout)
        
        # 名称输入
        edit_name_layout = QHBoxLayout()
        edit_name_label = QLabel('名称：')
        self.edit_name_input = QLineEdit()
        edit_name_layout.addWidget(edit_name_label)
        edit_name_layout.addWidget(self.edit_name_input)
        edit_config_layout.addLayout(edit_name_layout)
        
        # 备注输入
        edit_note_layout = QHBoxLayout()
        edit_note_label = QLabel('备注：')
        self.edit_note_input = QLineEdit()
        edit_note_layout.addWidget(edit_note_label)
        edit_note_layout.addWidget(self.edit_note_input)
        edit_config_layout.addLayout(edit_note_layout)
        
        edit_layout.addLayout(edit_config_layout)
        
        # 编辑按钮区域
        edit_button_layout = QHBoxLayout()
        save_button = QPushButton('保存')
        save_button.clicked.connect(self.save_action_config)
        write_button = QPushButton('写入')
        write_button.clicked.connect(self.write_edit_config)
        reset_button = QPushButton('重置')
        reset_button.clicked.connect(self.reset_edit_form)
        edit_button_layout.addWidget(save_button)
        edit_button_layout.addWidget(write_button)
        edit_button_layout.addWidget(reset_button)
        edit_layout.addLayout(edit_button_layout)
        
        # 编辑预览区域
        self.edit_preview_text = QTextEdit()
        self.edit_preview_text.setReadOnly(True)
        edit_layout.addWidget(self.edit_preview_text)
        
        # 添加标签页到主标签页组件
        tab_widget.addTab(create_tab, '创建数据')
        tab_widget.addTab(edit_tab, '编辑数据')
        
        main_layout.addWidget(tab_widget)
        
        # 初始化编辑标签页的数据
        self.update_id_combo()
    
    def create_action_config(self):
        # 获取输入数据
        action_id = self.id_input.text().strip()
        name = self.name_input.text().strip()
        note = self.note_input.text().strip()
        boss_union_id = self.boss_combo.currentData()
        
        # 验证输入
        if not all([action_id, name]):
            QMessageBox.warning(self, '警告', '请填写ID和名称！')
            return
        
        # 获取选中的角色
        selected_chars = []
        for checkbox in self.char_checkboxes:
            if checkbox.isChecked():
                selected_chars.append({
                    'udid': checkbox.property('udid'),
                    'name': checkbox.property('name'),
                    'level': checkbox.property('level'),
                    'job_name': checkbox.property('job_name')
                })
        
        if not selected_chars:
            QMessageBox.warning(self, '警告', '请选择至少一个角色！')
            return
        
        # 创建action配置
        action_config = {
            action_id: {
                'name': name,
                'note': note,
                'tag': ['boss', 'need_character'],
                'actions': [
                    # {
                    #     "trigger_type": "click_sub_menu_boss",
                    #     "value": f"union={boss_union_id}"
                    # },
                    {
                        "trigger_type": "click_button_clear_team",
                        "value": "checkDelAll()"
                    }
                ]
            }
        }
        
        # 添加角色选择动作
        for char in selected_chars:
            action_config[action_id]['actions'].append({
                "trigger_type": "check_box_select_character",
                "value": f"char_{char['udid']}",
                '_memo': f"{char['name']} L{char['level']} {char['job_name']}"
            })
        
        # 添加战斗按钮动作
        action_config[action_id]['actions'].append({
            "trigger_type": "click_button_start_battle",
            "value": "union_battle"
        })
        
        # 更新预览
        self.preview_text.setText(json.dumps(action_config, indent=4, ensure_ascii=False))
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(json.dumps(action_config, indent=4, ensure_ascii=False))
        
        QMessageBox.information(self, '提示', '配置已创建并复制到剪贴板！')
    
    def reset_form(self):
        # 清空输入框
        self.id_input.clear()
        self.name_input.clear()
        self.note_input.clear()
        
        # 取消所有角色选择
        for checkbox in self.char_checkboxes:
            checkbox.setChecked(False)
        
        # 重置Boss选择到第一项
        self.boss_combo.setCurrentIndex(0)
        
        # 清空预览
        self.preview_text.clear()
    
    def write_action_config(self):
        try:
            # 获取预览文本
            config_text = self.preview_text.toPlainText()
            if not config_text:
                QMessageBox.warning(self, '警告', '请先创建配置！')
                return
            
            # 解析JSON
            new_config = json.loads(config_text)
            
            # 更新配置
            self.action_config.update(new_config)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.action_config_path), exist_ok=True)
            
            # 写入文件
            with open(self.action_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.action_config, f, indent=2, ensure_ascii=False)
            
            # 更新编辑标签页的ID下拉框
            self.update_id_combo()
            
            QMessageBox.information(self, '成功', '配置已成功写入文件！')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'写入配置文件时发生错误：{str(e)}')

    def on_server_changed(self, index):
        # 更新当前服务器
        self.current_server = self.server_combo.currentData()
        base_path = os.path.dirname(os.path.dirname(__file__))
        self.configs_path = os.path.join(base_path, self.current_server['config_path'])
        
        try:
            # 重新加载配置
            with open(os.path.join(self.configs_path, 'boss_config.json'), 'r', encoding='utf-8') as f:
                self.boss_config = json.load(f)
                self.boss_config['boss_list'].sort(key=lambda x: x['union_id'])
            
            with open(os.path.join(self.configs_path, 'character_config.json'), 'r', encoding='utf-8') as f:
                self.character_config = json.load(f)
            
            self.action_config_path = os.path.join(self.configs_path, 'action_config_advanced.json')
            try:
                with open(self.action_config_path, 'r', encoding='utf-8') as f:
                    self.action_config = json.load(f)
            except FileNotFoundError:
                self.action_config = {}
                os.makedirs(os.path.dirname(self.action_config_path), exist_ok=True)
                with open(self.action_config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.action_config, f, indent=2, ensure_ascii=False)
            
            # 更新界面
            self.reset_form()
            
            # 更新Boss下拉框
            self.boss_combo.clear()
            for boss in self.boss_config['boss_list']:
                self.boss_combo.addItem(f"({boss['union_id']}){boss['name']} Lv.{boss['level_limit']}", boss['union_id'])
            
            # 更新角色列表
            for i in reversed(range(self.char_layout.count())):
                item = self.char_layout.itemAt(i)
                if item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    item.layout().deleteLater()
            
            self.char_checkboxes = []
            for char in self.character_config['characters']:
                hbox = QHBoxLayout()
                
                checkbox = QCheckBox()
                char_text = f"{char['name']} | L{char['level']} {char['job_name']}({char['udid']}) | <font color='gray'>{char['equipment'].replace('<br>', ' || ')}</font>"
                checkbox.setProperty('udid', char['udid'])
                checkbox.setProperty('name', char['name'])
                checkbox.setProperty('level', char['level'])
                checkbox.setProperty('job_name', char['job_name'])

                label = QLabel()
                label.setText(char_text)
                label.setTextFormat(Qt.TextFormat.RichText)

                self.char_checkboxes.append(checkbox)
                
                hbox.addWidget(checkbox)
                hbox.addWidget(label)
                hbox.addStretch()
                
                self.char_layout.addLayout(hbox)
            
            # 同步更新编辑标签页的服务器选择
            self.edit_server_combo.setCurrentIndex(self.server_combo.currentIndex())
            
            QMessageBox.information(self, '成功', f'已切换到{self.current_server["name"]}！')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'切换服务器时发生错误：{str(e)}')
    
    def on_edit_server_changed(self, index):
        # 同步更新创建标签页的服务器选择
        self.server_combo.setCurrentIndex(index)
    
    def update_id_combo(self):
        # 清空当前列表
        self.id_select_combo.clear()
        
        # 获取所有带有boss和need_character标签的配置
        boss_configs = {}
        for action_id, config in self.action_config.items():
            if 'tag' in config and 'boss' in config['tag'] and 'need_character' in config['tag']:
                boss_configs[action_id] = config
        
        # 添加到下拉框
        for action_id in sorted(boss_configs.keys()):
            config = boss_configs[action_id]
            self.id_select_combo.addItem(f"{action_id} - {config.get('name', '')}", action_id)
    
    def on_id_selected(self, index):
        if index < 0:
            return
        
        # 获取选中的配置ID
        action_id = self.id_select_combo.currentData()
        if not action_id or action_id not in self.action_config:
            return
        
        # 获取配置
        config = self.action_config[action_id]
        
        # 更新输入框
        self.edit_id_input.setText(action_id)
        self.edit_name_input.setText(config.get('name', ''))
        self.edit_note_input.setText(config.get('note', ''))
        
        # 取消所有角色选择
        for checkbox in self.edit_char_checkboxes:
            checkbox.setChecked(False)
        
        # 根据配置选中对应的角色
        selected_udids = set()
        for action in config['actions']:
            if action['trigger_type'] == 'check_box_select_character':
                udid = action['value'].replace('char_', '')
                selected_udids.add(udid)
        
        for checkbox in self.edit_char_checkboxes:
            if checkbox.property('udid') in selected_udids:
                checkbox.setChecked(True)
    
    def save_action_config(self):
        # 获取当前选中的配置ID
        old_action_id = self.id_select_combo.currentData()
        if not old_action_id or old_action_id not in self.action_config:
            QMessageBox.warning(self, '警告', '请选择要编辑的配置！')
            return
        
        # 获取输入数据
        action_id = self.edit_id_input.text().strip()
        name = self.edit_name_input.text().strip()
        note = self.edit_note_input.text().strip()
        
        # 验证输入
        if not all([action_id, name]):
            QMessageBox.warning(self, '警告', '请填写ID和名称！')
            return
        
        # 获取选中的角色
        selected_chars = []
        for checkbox in self.edit_char_checkboxes:
            if checkbox.isChecked():
                selected_chars.append({
                    'udid': checkbox.property('udid'),
                    'name': checkbox.property('name'),
                    'level': checkbox.property('level'),
                    'job_name': checkbox.property('job_name')
                })
        
        if not selected_chars:
            QMessageBox.warning(self, '警告', '请选择至少一个角色！')
            return
        
        try:
            # 获取原配置
            config = self.action_config[old_action_id].copy()
            
            # 保留非角色选择的动作
            actions = [action for action in config['actions'] 
                      if action['trigger_type'] != 'check_box_select_character']
            
            # 添加新的角色选择动作
            for char in selected_chars:
                actions.append({
                    "trigger_type": "check_box_select_character",
                    "value": f"char_{char['udid']}",
                    '_memo': f"{char['name']} L{char['level']} {char['job_name']}"
                })
            
            # 创建新配置
            new_config = {
                action_id: {
                    'name': name,
                    'note': note,
                    'tag': config['tag'],
                    'actions': actions
                }
            }
            
            # 更新预览
            self.edit_preview_text.setText(json.dumps(new_config, indent=4, ensure_ascii=False))
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(json.dumps(new_config, indent=4, ensure_ascii=False))
            
            QMessageBox.information(self, '提示', '配置已创建并复制到剪贴板！')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存配置时发生错误：{str(e)}')

    def write_edit_config(self):
        try:
            # 获取预览文本
            config_text = self.edit_preview_text.toPlainText()
            if not config_text:
                QMessageBox.warning(self, '警告', '请先保存配置！')
                return
            
            # 解析JSON
            new_config = json.loads(config_text)
            
            # 获取当前选中的配置ID
            old_action_id = self.id_select_combo.currentData()
            if old_action_id and old_action_id in self.action_config:
                # 删除旧配置
                del self.action_config[old_action_id]
            
            # 获取所有配置项并按ID排序
            all_configs = {**self.action_config, **new_config}
            sorted_configs = dict(sorted(all_configs.items()))
            
            # 写入文件
            with open(self.action_config_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_configs, f, indent=2, ensure_ascii=False)
            
            # 更新配置和下拉框
            self.action_config = sorted_configs
            self.update_id_combo()
            
            QMessageBox.information(self, '成功', '配置已成功写入文件！')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'写入配置文件时发生错误：{str(e)}')
    
    def reset_edit_form(self):
        # 恢复到选中ID的初始状态
        self.on_id_selected(self.id_select_combo.currentIndex())
        # 清空预览
        self.edit_preview_text.clear()
    
    def write_action_config(self):
        try:
            # 获取预览文本
            config_text = self.preview_text.toPlainText()
            if not config_text:
                QMessageBox.warning(self, '警告', '请先创建配置！')
                return
            
            # 解析JSON
            new_config = json.loads(config_text)
            
            # 获取所有配置项并按ID排序
            all_configs = {**self.action_config, **new_config}
            sorted_configs = dict(sorted(all_configs.items()))
            
            # 写入文件
            with open(self.action_config_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_configs, f, indent=2, ensure_ascii=False)
            
            # 更新配置和下拉框
            self.action_config = sorted_configs
            self.update_id_combo()
            
            QMessageBox.information(self, '成功', '配置已成功写入文件！')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'写入配置文件时发生错误：{str(e)}')
    
def main():
    app = QApplication(sys.argv)
    editor = BossActionEditor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()