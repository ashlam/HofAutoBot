import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QSpinBox, QCheckBox, QComboBox, QPushButton,
                             QTabWidget, QScrollArea, QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt

class AutoBotConfigEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('自动机器人配置编辑器')
        self.setGeometry(100, 100, 1200, 800)
        
        # 加载配置文件
        self.load_configs()
        
        # 创建主界面
        self.init_ui()
    
    def load_configs(self):
        """加载所有配置文件"""
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs/server_01')
        
        # 加载auto_bot_loop_config.json
        auto_bot_config_path = os.path.join(config_dir, 'auto_bot_loop_config.json')
        with open(auto_bot_config_path, 'r', encoding='utf-8') as f:
            self.auto_bot_config = json.load(f)
        
        # 加载boss_config.json
        boss_config_path = os.path.join(config_dir, 'boss_config.json')
        with open(boss_config_path, 'r', encoding='utf-8') as f:
            self.boss_config = json.load(f)
        
        # 加载action_config.json
        action_config_path = os.path.join(config_dir, 'action_config.json')
        with open(action_config_path, 'r', encoding='utf-8') as f:
            self.action_config = json.load(f)
    
    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 基本设置标签页
        basic_settings_tab = self.create_basic_settings_tab()
        tab_widget.addTab(basic_settings_tab, '基本设置')
        
        # VIP Boss设置标签页
        vip_boss_tab = self.create_vip_boss_tab()
        tab_widget.addTab(vip_boss_tab, 'VIP Boss设置')
        
        # 普通Boss设置标签页
        normal_boss_tab = self.create_normal_boss_tab()
        tab_widget.addTab(normal_boss_tab, '普通Boss设置')
        
        # 小怪设置标签页
        stage_tab = self.create_stage_tab()
        tab_widget.addTab(stage_tab, '小怪设置')
        
        # 保存按钮
        save_button = QPushButton('保存配置')
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)
    
    def create_basic_settings_tab(self):
        """创建基本设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 体力设置组
        stamina_group = QGroupBox('体力设置')
        stamina_layout = QVBoxLayout()
        
        # 体力消耗设置
        stamina_settings = [
            ('boss_cost_stamina', 'Boss战斗消耗体力'),
            ('quest_cost_stamina', '任务消耗体力'),
            ('stage_cost_stamina', '小怪战斗消耗体力'),
            ('max_stamnia_limit', '体力上限'),
            ('recover_stamina_per_hour', '每小时恢复体力'),
            ('keep_stamnia_for_change_stage', '切换小怪保留体力')
        ]
        
        for setting_key, label_text in stamina_settings:
            hlayout = QHBoxLayout()
            label = QLabel(label_text)
            spinbox = QSpinBox()
            spinbox.setRange(0, 10000)
            spinbox.setValue(self.auto_bot_config.get(setting_key, 0))
            spinbox.setObjectName(setting_key)
            hlayout.addWidget(label)
            hlayout.addWidget(spinbox)
            stamina_layout.addLayout(hlayout)
        
        stamina_group.setLayout(stamina_layout)
        layout.addWidget(stamina_group)
        
        # 功能开关组
        feature_group = QGroupBox('功能开关')
        feature_layout = QVBoxLayout()
        
        # 功能开关设置
        feature_settings = [
            ('is_challenge_vip_boss', '挑战VIP Boss'),
            ('is_challenge_vip_stage', '挑战VIP小怪'),
            ('is_challenge_pvp', '挑战竞技场'),
            ('is_challenge_world_pvp', '挑战世界PVP')
        ]
        
        for setting_key, label_text in feature_settings:
            checkbox = QCheckBox(label_text)
            checkbox.setChecked(self.auto_bot_config.get(setting_key, False))
            checkbox.setObjectName(setting_key)
            feature_layout.addWidget(checkbox)
        
        feature_group.setLayout(feature_layout)
        layout.addWidget(feature_group)
        
        return tab
    
    def create_vip_boss_tab(self):
        """创建VIP Boss设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建VIP Boss列表
        vip_boss_group = QGroupBox('VIP Boss监控列表')
        vip_boss_layout = QVBoxLayout()
        
        # 添加现有的VIP Boss
        for vip_boss in self.auto_bot_config.get('vip_boss_need_watch', []):
            boss_widget = self.create_boss_entry_widget(vip_boss, is_vip=True)
            vip_boss_layout.addWidget(boss_widget)
        
        # 添加新VIP Boss按钮
        add_button = QPushButton('添加VIP Boss')
        add_button.clicked.connect(lambda: self.add_boss_entry(vip_boss_layout, is_vip=True))
        vip_boss_layout.addWidget(add_button)
        
        vip_boss_group.setLayout(vip_boss_layout)
        layout.addWidget(vip_boss_group)
        
        return tab
    
    def create_normal_boss_tab(self):
        """创建普通Boss设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建普通Boss列表
        normal_boss_group = QGroupBox('普通Boss循环顺序')
        normal_boss_layout = QVBoxLayout()
        
        # 添加现有的普通Boss
        for normal_boss in self.auto_bot_config.get('normal_boss_loop_order', []):
            boss_widget = self.create_boss_entry_widget(normal_boss)
            normal_boss_layout.addWidget(boss_widget)
        
        # 添加新普通Boss按钮
        add_button = QPushButton('添加普通Boss')
        add_button.clicked.connect(lambda: self.add_boss_entry(normal_boss_layout))
        normal_boss_layout.addWidget(add_button)
        
        normal_boss_group.setLayout(normal_boss_layout)
        layout.addWidget(normal_boss_group)
        
        return tab
    
    def create_stage_tab(self):
        """创建小怪设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 创建小怪列表
        stage_group = QGroupBox('小怪循环顺序')
        stage_layout = QVBoxLayout()
        
        # 添加现有的小怪
        for stage in self.auto_bot_config.get('normal_stage_loop_order', []):
            stage_widget = self.create_stage_entry_widget(stage)
            stage_layout.addWidget(stage_widget)
        
        # 添加新小怪按钮
        add_button = QPushButton('添加小怪')
        add_button.clicked.connect(lambda: self.add_stage_entry(stage_layout))
        stage_layout.addWidget(add_button)
        
        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)
        
        return tab
    
    def create_boss_entry_widget(self, boss_data, is_vip=False):
        """创建Boss条目组件"""
        group = QGroupBox()
        layout = QHBoxLayout(group)
        
        # Boss选择下拉框
        boss_combo = QComboBox()
        for boss in self.boss_config['boss_list']:
            boss_combo.addItem(f"{boss['name']} (ID: {boss['union_id']})", boss['union_id'])
        
        # 设置当前选中的Boss
        current_index = -1
        for i in range(boss_combo.count()):
            if boss_combo.itemData(i) == boss_data.get('union_id'):
                current_index = i
                break
        if current_index >= 0:
            boss_combo.setCurrentIndex(current_index)
        
        layout.addWidget(boss_combo)
        
        # 动作ID输入框
        action_combo = QComboBox()
        for action_id, action_info in self.action_config.items():
            if 'boss' in action_info.get('tag', []):
                action_combo.addItem(f"{action_info['name']} (ID: {action_id})", action_id)
        
        # 设置当前选中的动作
        current_index = -1
        for i in range(action_combo.count()):
            if action_combo.itemData(i) == str(boss_data.get('plan_action_id')):
                current_index = i
                break
        if current_index >= 0:
            action_combo.setCurrentIndex(current_index)
        
        layout.addWidget(action_combo)
        
        # VIP Boss特有的击杀冷却时间
        if is_vip:
            cooldown_spinbox = QSpinBox()
            cooldown_spinbox.setRange(0, 86400)  # 最大24小时
            cooldown_spinbox.setValue(boss_data.get('kill_cooldown_seconds', 14400))
            cooldown_spinbox.setSuffix(' 秒')
            layout.addWidget(QLabel('击杀冷却:'))
            layout.addWidget(cooldown_spinbox)
        
        # 删除按钮
        delete_button = QPushButton('删除')
        delete_button.clicked.connect(lambda: group.deleteLater())
        layout.addWidget(delete_button)
        
        return group
    
    def create_stage_entry_widget(self, stage_data):
        """创建小怪条目组件"""
        group = QGroupBox()
        layout = QHBoxLayout(group)
        
        # 小怪名称输入框
        stage_name = QLineEdit(stage_data.get('stage_name', ''))
        layout.addWidget(QLabel('小怪名称:'))
        layout.addWidget(stage_name)
        
        # 动作ID选择
        action_combo = QComboBox()
        for action_id, action_info in self.action_config.items():
            action_combo.addItem(f"{action_info['name']} (ID: {action_id})", action_id)
        
        # 设置当前选中的动作
        current_index = -1
        for i in range(action_combo.count()):
            if action_combo.itemData(i) == str(stage_data.get('plan_action_id')):
                current_index = i
                break
        if current_index >= 0:
            action_combo.setCurrentIndex(current_index)
        
        layout.addWidget(QLabel('动作:'))
        layout.addWidget(action_combo)
        
        # 删除按钮
        delete_button = QPushButton('删除')
        delete_button.clicked.connect(lambda: group.deleteLater())
        layout.addWidget(delete_button)
        
        return group
    
    def add_boss_entry(self, layout, is_vip=False):
        """添加新的Boss条目"""
        boss_data = {
            'union_id': 0,
            'plan_action_id': '600000'
        }
        if is_vip:
            boss_data['kill_cooldown_seconds'] = 14400
        
        boss_widget = self.create_boss_entry_widget(boss_data, is_vip)
        layout.insertWidget(layout.count() - 1, boss_widget)
    
    def add_stage_entry(self, layout):
        """添加新的小怪条目"""
        stage_data = {
            'stage_name': '',
            'plan_action_id': 1
        }
        stage_widget = self.create_stage_entry_widget(stage_data)
        layout.insertWidget(layout.count() - 1, stage_widget)
    
    def save_config(self):
        """保存配置到文件"""
        try:
            # 更新基本设置
            for setting_key in ['boss_cost_stamina', 'quest_cost_stamina', 'stage_cost_stamina',
                              'max_stamnia_limit', 'recover_stamina_per_hour', 'keep_stamnia_for_change_stage']:
                spinbox = self.findChild(QSpinBox, setting_key)
                if spinbox:
                    self.auto_bot_config[setting_key] = spinbox.value()
            
            # 更新功能开关
            for setting_key in ['is_challenge_vip_boss', 'is_challenge_vip_stage',
                              'is_challenge_pvp', 'is_challenge_world_pvp']:
                checkbox = self.findChild(QCheckBox, setting_key)
                if checkbox:
                    self.auto_bot_config[setting_key] = checkbox.isChecked()
            
            # 更新VIP Boss列表
            vip_boss_list = []
            vip_boss_group = self.findChild(QGroupBox, 'VIP Boss监控列表')
            if vip_boss_group:
                for i in range(vip_boss_group.layout().count() - 1):  # 减1是因为最后一个是添加按钮
                    widget = vip_boss_group.layout().itemAt(i).widget()
                    if widget:
                        boss_combo = widget.findChild(QComboBox)
                        action_combo = widget.findChildren(QComboBox)[1]
                        cooldown_spinbox = widget.findChild(QSpinBox)
                        if boss_combo and action_combo and cooldown_spinbox:
                            vip_boss_list.append({
                                'union_id': boss_combo.currentData(),
                                'plan_action_id': int(action_combo.currentData()),
                                'kill_cooldown_seconds': cooldown_spinbox.value()
                            })
            self.auto_bot_config['vip_boss_need_watch'] = vip_boss_list
            
            # 更新普通Boss列表
            normal_boss_list = []
            normal_boss_group = self.findChild(QGroupBox, '普通Boss循环顺序')
            if normal_boss_group:
                for i in range(normal_boss_group.layout().count() - 1):
                    widget = normal_boss_group.layout().itemAt(i).widget()
                    if widget:
                        boss_combo = widget.findChild(QComboBox)
                        action_combo = widget.findChildren(QComboBox)[1]
                        if boss_combo and action_combo:
                            normal_boss_list.append({
                                'union_id': boss_combo.currentData(),
                                'plan_action_id': int(action_combo.currentData())
                            })
            self.auto_bot_config['normal_boss_loop_order'] = normal_boss_list
            
            # 更新小怪列表
            stage_list = []
            stage_group = self.findChild(QGroupBox, '小怪循环顺序')
            if stage_group:
                for i in range(stage_group.layout().count() - 1):
                    widget = stage_group.layout().itemAt(i).widget()
                    if widget:
                        stage_name = widget.findChild(QLineEdit)
                        action_combo = widget.findChild(QComboBox)
                        if stage_name and action_combo:
                            stage_list.append({
                                'stage_name': stage_name.text(),
                                'plan_action_id': int(action_combo.currentData())
                            })
            self.auto_bot_config['normal_stage_loop_order'] = stage_list
            
            # 保存到文件
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                      'configs/server_01/auto_bot_loop_config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.auto_bot_config, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, '成功', '配置已保存')
        
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存配置时出错：{str(e)}')

def main():
    app = QApplication(sys.argv)
    editor = AutoBotConfigEditor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()