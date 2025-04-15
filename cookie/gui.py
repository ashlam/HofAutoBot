import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable, Dict
from .models import CookieConfig
from .manager import CookieManager

class CookieManagementFrame(ttk.Frame):
    def __init__(self, parent, on_cookie_updated: Callable = None):
        super().__init__(parent)
        self.on_cookie_updated = on_cookie_updated
        self.cookie_manager = CookieManager()
        self.create_widgets()

    def create_widgets(self):
        # 创建输入区域
        input_frame = ttk.LabelFrame(self, text="输入CURL数据", padding=10)
        input_frame.pack(fill="x", padx=5, pady=5)
        
        self.curl_text = scrolledtext.ScrolledText(input_frame, height=5)
        self.curl_text.pack(fill="x", expand=True)
        
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill="x", pady=5)
        
        ttk.Button(button_frame, text="分析", command=self.analyze_curl).pack(side="left", padx=5)
        ttk.Button(button_frame, text="清空", command=self.clear_data).pack(side="left", padx=5)
        ttk.Button(button_frame, text="读取", command=self.load_cookie).pack(side="left", padx=5)
        ttk.Button(button_frame, text="保存Cookie", command=self.save_cookie).pack(side="left", padx=5)
        
        # 创建Cookie参数区域
        param_frame = ttk.LabelFrame(self, text="Cookie参数", padding=10)
        param_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 创建参数输入框
        self.cookie_vars: Dict[str, tk.StringVar] = {}
        row = 0
        for field in CookieConfig.__dataclass_fields__:
            frame = ttk.Frame(param_frame)
            frame.pack(fill="x", pady=2)
            
            ttk.Label(frame, text=field, width=30).pack(side="left")
            self.cookie_vars[field] = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=self.cookie_vars[field], width=50)
            entry.pack(side="left", padx=5)
            
            ttk.Button(frame, text="复制", 
                      command=lambda v=self.cookie_vars[field]: self.copy_to_clipboard(v.get())
                      ).pack(side="left")

    def clear_data(self):
        self.curl_text.delete("1.0", tk.END)
        for var in self.cookie_vars.values():
            var.set("")

    def analyze_curl(self):
        curl_data = self.curl_text.get("1.0", tk.END).strip()
        cookie_config = self.cookie_manager.parse_curl(curl_data)
        if cookie_config:
            self.update_cookie_vars(cookie_config)

    def update_cookie_vars(self, cookie_config: CookieConfig):
        for field, var in self.cookie_vars.items():
            var.set(getattr(cookie_config, field))

    def save_cookie(self):
        cookie_config = CookieConfig(**{
            field: var.get()
            for field, var in self.cookie_vars.items()
        })
        self.cookie_manager.save_config(cookie_config)
        if self.on_cookie_updated:
            self.on_cookie_updated()

    def load_cookie(self):
        cookie_config = self.cookie_manager.load_config()
        self.update_cookie_vars(cookie_config)

    def copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def get_cookie_string(self) -> str:
        cookie_config = CookieConfig(**{
            field: var.get()
            for field, var in self.cookie_vars.items()
        })
        return cookie_config.to_cookie_string() 