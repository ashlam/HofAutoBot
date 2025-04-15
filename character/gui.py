import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable
from .parser import CharacterParser
from .manager import CharacterManager
from .models import Character

class CharacterManagementFrame(ttk.Frame):
    def __init__(self, parent, on_data_updated: Callable = None):
        super().__init__(parent)
        self.on_data_updated = on_data_updated
        self.character_manager = CharacterManager()
        self.create_widgets()

    def create_widgets(self):
        # 创建输入区域
        input_frame = ttk.LabelFrame(self, text="输入角色列表数据", padding=10)
        input_frame.pack(fill="x", padx=5, pady=5)
        
        self.char_text = scrolledtext.ScrolledText(input_frame, height=5)
        self.char_text.pack(fill="x", expand=True)
        
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill="x", pady=5)
        
        ttk.Button(button_frame, text="分析", command=self.analyze_characters).pack(side="left", padx=5)
        ttk.Button(button_frame, text="清空", command=self.clear_character_data).pack(side="left", padx=5)
        ttk.Button(button_frame, text="读取", command=self.load_characters).pack(side="left", padx=5)
        ttk.Button(button_frame, text="确认写入", command=self.save_character_data).pack(side="left", padx=5)
        
        # 创建信息显示区域
        info_frame = ttk.LabelFrame(self, text="角色信息", padding=10)
        info_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 创建表格
        columns = ("序号", "ID", "角色姓名", "角色信息")
        self.char_tree = ttk.Treeview(info_frame, columns=columns, show="headings")
        
        # 设置列标题
        for col in columns:
            self.char_tree.heading(col, text=col)
            self.char_tree.column(col, width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.char_tree.yview)
        self.char_tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.char_tree.pack(fill="both", expand=True)
        
        # 绑定选择事件
        self.char_tree.bind('<<TreeviewSelect>>', self.on_character_select)

    def clear_character_data(self):
        self.char_text.delete("1.0", tk.END)
        for item in self.char_tree.get_children():
            self.char_tree.delete(item)

    def analyze_characters(self):
        # 清空现有数据
        for item in self.char_tree.get_children():
            self.char_tree.delete(item)
        
        html_data = self.char_text.get("1.0", tk.END).strip()
        characters = CharacterParser.parse_html(html_data)
        
        # 显示在表格中
        for char in characters:
            self.char_tree.insert("", "end", values=char.to_list())

    def save_character_data(self):
        characters = []
        for item in self.char_tree.get_children():
            values = self.char_tree.item(item)['values']
            char = Character(
                id=values[1],
                name=values[2],
                order=values[0],
                job_info=values[3],
                level="",  # 这些信息在保存时不需要
                type=""
            )
            characters.append(char)
        
        # 保存角色数据
        self.character_manager.save_characters(characters)
        
        # 通知主界面更新
        if self.on_data_updated:
            self.on_data_updated()

    def load_characters(self):
        # 清空现有数据
        for item in self.char_tree.get_children():
            self.char_tree.delete(item)
        
        # 从配置文件加载数据
        config = self.character_manager.load_config()
        character_info = config.get('character_info', {})
        
        # 将数据转换为Character对象并排序
        characters = []
        for char_id, info in character_info.items():
            char = Character(
                id=char_id,
                name=info['name'],
                order=info['order'],
                job_info=info['job_info'],
                level="",  # 这些信息在配置中没有保存
                type=""
            )
            characters.append(char)
        
        # 按序号排序
        characters.sort(key=lambda x: x.order)
        
        # 显示在表格中
        for char in characters:
            self.char_tree.insert("", "end", values=char.to_list())

    def on_character_select(self, event):
        # 获取选中项
        selection = self.char_tree.selection()
        if selection:
            item = selection[0]
            values = self.char_tree.item(item)['values']
            # 复制ID到剪贴板
            self.copy_to_clipboard(values[1])

    def copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update() 