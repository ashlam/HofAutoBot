import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
import json
from config import DEFAULT_CONFIG, HEADERS
import urllib.parse
import re
from character import CharacterManagementFrame, CharacterManager
from cookie import CookieManagementFrame, CookieManager
from tag import TagManagementFrame

class AutoBattleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("自动战斗工具")
        self.root.geometry("800x600")
        
        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)
        
        # 主界面
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="主界面")
        
        # Cookie管理界面
        self.cookie_frame = CookieManagementFrame(self.notebook, self.on_cookie_updated)
        self.notebook.add(self.cookie_frame, text="Cookie管理")
        
        # 角色管理界面
        self.character_frame = CharacterManagementFrame(self.notebook, self.refresh_character_section)
        self.notebook.add(self.character_frame, text="角色管理")

        # 标签管理界面
        self.tag_frame = TagManagementFrame(self.notebook)
        self.notebook.add(self.tag_frame, text="标签管理")
        
        # 创建主界面
        self.create_main_interface()

    def create_main_interface(self):
        # 创建角色选择区域
        self.create_character_section()
        # 创建战斗控制区域
        self.create_battle_section()
        # 创建日志区域
        self.create_log_section()

    def create_character_section(self):
        char_frame = ttk.LabelFrame(self.main_frame, text="角色选择", padding=10)
        char_frame.pack(fill="x", padx=5, pady=5)

        self.char_vars = {}
        row = 0
        col = 0
        character_manager = CharacterManager()
        characters = character_manager.get_characters()
        
        for char_id, char_name in characters.items():
            self.char_vars[char_id] = tk.BooleanVar(value=True)
            ttk.Checkbutton(char_frame, text=f"{char_name} ({char_id})", 
                           variable=self.char_vars[char_id]).grid(row=row, column=col, padx=5, pady=2)
            col += 1
            if col > 2:
                col = 0
                row += 1

    def create_battle_section(self):
        battle_frame = ttk.Frame(self.main_frame, padding=10)
        battle_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(battle_frame, text="开始战斗", command=self.start_battle).pack(side="left", padx=5)
        ttk.Button(battle_frame, text="继续战斗", command=self.continue_battle).pack(side="left", padx=5)

    def create_log_section(self):
        log_frame = ttk.LabelFrame(self.main_frame, text="日志", padding=10)
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.pack(fill="both", expand=True)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def get_selected_characters(self):
        return {char_id: "1" for char_id, var in self.char_vars.items() if var.get()}

    def make_request(self, battle_type="戰鬥!"):
        headers = HEADERS.copy()
        headers['Cookie'] = self.cookie_frame.get_cookie_string()

        data = {
            "monster_battle": battle_type,
            "Monster_Round": "1"
        }
        data.update(self.get_selected_characters())

        try:
            response = requests.post(
                DEFAULT_CONFIG['url'],
                headers=headers,
                data=data
            )
            self.log(f"请求状态: {response.status_code}")
            self.log(f"响应内容: {response.text[:200]}...")
        except Exception as e:
            self.log(f"错误: {str(e)}")

    def start_battle(self):
        self.make_request("戰鬥!")

    def continue_battle(self):
        self.make_request("繼續戰鬥!")

    def refresh_character_section(self):
        # 重新创建角色选择区域
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, ttk.LabelFrame) and widget.winfo_children() and \
               isinstance(widget.winfo_children()[0], ttk.Checkbutton):
                widget.destroy()
        self.create_character_section()

    def on_cookie_updated(self):
        # Cookie更新时的回调函数
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoBattleGUI(root)
    root.mainloop() 