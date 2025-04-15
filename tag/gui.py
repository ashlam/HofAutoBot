import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from typing import Dict, Optional
from .models import Tag, PREDEFINED_COLORS
from .manager import TagManager

class ColorButton(tk.Label):
    def __init__(self, parent, color: str, name: str, command=None):
        super().__init__(parent, width=2, height=1, bg=color)
        self.color = color
        self.name = name
        self.command = command
        self.bind("<Button-1>", self._on_click)
        
        # 添加工具提示
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
    def _on_click(self, event):
        if self.command:
            self.command(self.color)
            
    def _on_enter(self, event):
        x = self.winfo_rootx()
        y = self.winfo_rooty() + 20
        self.tooltip = tk.Toplevel()
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=f"{self.name} ({self.color})", 
                        bg="lightyellow", relief="solid", borderwidth=1)
        label.pack()
        
    def _on_leave(self, event):
        if hasattr(self, "tooltip"):
            self.tooltip.destroy()
            del self.tooltip

class TagManagementFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.tag_manager = TagManager()
        self.current_edit_id: Optional[str] = None
        self.create_widgets()

    def create_widgets(self):
        # 创建标签编辑区域
        edit_frame = ttk.LabelFrame(self, text="标签编辑", padding=10)
        edit_frame.pack(fill="x", padx=5, pady=5)

        # 标签ID输入
        id_frame = ttk.Frame(edit_frame)
        id_frame.pack(fill="x", pady=2)
        ttk.Label(id_frame, text="标签ID:").pack(side="left")
        self.tag_id_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=self.tag_id_var, width=30).pack(side="left", padx=5)

        # 标签名称输入
        name_frame = ttk.Frame(edit_frame)
        name_frame.pack(fill="x", pady=2)
        ttk.Label(name_frame, text="标签名称:").pack(side="left")
        self.name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.name_var, width=30).pack(side="left", padx=5)

        # 颜色选择
        color_frame = ttk.LabelFrame(edit_frame, text="颜色选择", padding=5)
        color_frame.pack(fill="x", pady=2)
        
        # 创建颜色网格
        colors_per_row = 16
        current_row = []
        for color, name in PREDEFINED_COLORS:
            if len(current_row) >= colors_per_row:
                self.create_color_row(color_frame, current_row)
                current_row = []
            current_row.append((color, name))
        
        if current_row:  # 处理最后一行
            self.create_color_row(color_frame, current_row)

        # 当前选择的颜色预览
        preview_frame = ttk.Frame(edit_frame)
        preview_frame.pack(fill="x", pady=2)
        ttk.Label(preview_frame, text="已选颜色:").pack(side="left")
        self.color_var = tk.StringVar(value=PREDEFINED_COLORS[0][0])
        self.color_preview = tk.Label(preview_frame, width=3, height=1, bg=self.color_var.get())
        self.color_preview.pack(side="left", padx=5)

        # 编辑按钮
        button_frame = ttk.Frame(edit_frame)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="新建", command=self.create_tag).pack(side="left", padx=5)
        ttk.Button(button_frame, text="更新", command=self.update_tag).pack(side="left", padx=5)
        ttk.Button(button_frame, text="删除", command=self.delete_tag).pack(side="left", padx=5)
        ttk.Button(button_frame, text="清空", command=self.clear_inputs).pack(side="left", padx=5)

        # 创建标签列表区域
        list_frame = ttk.LabelFrame(self, text="标签列表", padding=10)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 创建表格
        columns = ("ID", "名称", "颜色")
        self.tag_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.tag_tree.heading("ID", text="ID")
        self.tag_tree.heading("名称", text="名称")
        self.tag_tree.heading("颜色", text="颜色")
        
        self.tag_tree.column("ID", width=100)
        self.tag_tree.column("名称", width=150)
        self.tag_tree.column("颜色", width=50)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tag_tree.yview)
        self.tag_tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.tag_tree.pack(fill="both", expand=True)

        # 绑定选择事件
        self.tag_tree.bind('<<TreeviewSelect>>', self.on_tag_select)

        # 底部按钮
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(bottom_frame, text="保存配置", command=self.save_config).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="读取配置", command=self.load_config).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="清空所有", command=self.clear_all).pack(side="left", padx=5)

        # 存储标签数据
        self.tags: Dict[str, Tag] = {}

    def create_color_row(self, parent, colors):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=1)
        for color, name in colors:
            ColorButton(frame, color, name, self.select_color).pack(side="left", padx=0)

    def select_color(self, color: str):
        self.color_var.set(color)
        self.color_preview.configure(bg=color)

    def create_tag(self):
        tag_id = self.tag_id_var.get().strip()
        name = self.name_var.get().strip()
        if not tag_id or not name:
            messagebox.showwarning("警告", "标签ID和名称不能为空")
            return
        
        # 检查ID是否已存在
        for tag in self.tags.values():
            if tag.tag_id == tag_id:
                messagebox.showwarning("警告", "标签ID已存在")
                return
        
        uuid = self.tag_manager.generate_id()
        tag = Tag(id=uuid, tag_id=tag_id, name=name, color=self.color_var.get())
        self.tags[uuid] = tag
        self._insert_tag_to_tree(uuid, tag)
        self.clear_inputs()

    def update_tag(self):
        if not self.current_edit_id or self.current_edit_id not in self.tags:
            return

        tag_id = self.tag_id_var.get().strip()
        name = self.name_var.get().strip()
        if not tag_id or not name:
            messagebox.showwarning("警告", "标签ID和名称不能为空")
            return

        # 检查ID是否已被其他标签使用
        for uuid, tag in self.tags.items():
            if tag.tag_id == tag_id and uuid != self.current_edit_id:
                messagebox.showwarning("警告", "标签ID已存在")
                return

        tag = self.tags[self.current_edit_id]
        tag.tag_id = tag_id
        tag.name = name
        tag.color = self.color_var.get()
        self._update_tag_in_tree(self.current_edit_id, tag)
        self.clear_inputs()

    def _insert_tag_to_tree(self, uuid: str, tag: Tag):
        color_block = "■"  # 使用实心方块表示颜色
        self.tag_tree.tag_configure(uuid, foreground=tag.color)
        self.tag_tree.insert("", "end", uuid, values=(tag.tag_id, tag.name, color_block), tags=(uuid,))

    def _update_tag_in_tree(self, uuid: str, tag: Tag):
        color_block = "■"  # 使用实心方块表示颜色
        self.tag_tree.tag_configure(uuid, foreground=tag.color)
        self.tag_tree.item(uuid, values=(tag.tag_id, tag.name, color_block))

    def delete_tag(self):
        if not self.current_edit_id or self.current_edit_id not in self.tags:
            return

        del self.tags[self.current_edit_id]
        self.tag_tree.delete(self.current_edit_id)
        self.clear_inputs()

    def clear_inputs(self):
        self.tag_id_var.set("")
        self.name_var.set("")
        self.color_var.set(PREDEFINED_COLORS[0][0])
        self.color_preview.configure(bg=PREDEFINED_COLORS[0][0])
        self.current_edit_id = None

    def clear_all(self):
        self.clear_inputs()
        self.tags.clear()
        for item in self.tag_tree.get_children():
            self.tag_tree.delete(item)

    def on_tag_select(self, event):
        selection = self.tag_tree.selection()
        if not selection:
            return

        uuid = selection[0]
        tag = self.tags.get(uuid)
        if tag:
            self.current_edit_id = uuid
            self.tag_id_var.set(tag.tag_id)
            self.name_var.set(tag.name)
            self.color_var.set(tag.color)
            self.color_preview.configure(bg=tag.color)

    def save_config(self):
        self.tag_manager.save_tags(list(self.tags.values()))

    def load_config(self):
        self.clear_all()
        self.tags = self.tag_manager.load_config()
        for uuid, tag in self.tags.items():
            self._insert_tag_to_tree(uuid, tag) 