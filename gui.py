# gui.py - 确保发送按钮可见，并防止 UI 卡死
import tkinter as tk
from tkinter import scrolledtext, messagebox
from threading import Thread
from map_handler import MapHandler
from ai_handler import AIHandler

class GISApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GIS AI 助手 - 模块化版本")
        self.root.geometry("1200x700")   # 确保宽度足够
        
        # 左侧地图框架
        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.map_handler = MapHandler(left_frame)
        
        try:
            self.map_handler.load_shapefiles('geodata')
            self.map_handler.plot_all_layers()
        except Exception as e:
            messagebox.showerror("错误", f"加载地图数据失败: {e}")
            self.root.destroy()
            return
        
        # 右侧聊天面板
        self.create_chat_panel()
        
        # 初始化AI
        from dotenv import load_dotenv
        import os
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            messagebox.showerror("错误", "请在.env文件中设置DEEPSEEK_API_KEY")
            self.root.destroy()
            return
        self.ai_handler = AIHandler(api_key, self.map_handler)
    
    def create_chat_panel(self):
        # 右侧框架，固定宽度400
        right_frame = tk.Frame(self.root, width=400, bg='#f0f0f0')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_frame.pack_propagate(False)   # 防止收缩
        
        # 聊天显示区域
        self.chat_display = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=("微软雅黑", 10), state='disabled')
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        
        # 输入区域框架 - 使用 grid 布局
        input_frame = tk.Frame(right_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        # 多行文本框
        self.input_entry = tk.Text(input_frame, height=4, font=("微软雅黑", 10))
        self.input_entry.grid(row=0, column=0, sticky="nsew")
        
        # 发送按钮 - 绿色背景，白色文字，带图标
        send_btn = tk.Button(input_frame, text="✈️ 发送", command=self.send_message,
                             width=8, bg='#4CAF50', fg='white', font=("微软雅黑", 10, "bold"))
        send_btn.grid(row=0, column=1, padx=(5,0), sticky="ns")
        
        # 配置网格权重，使文本框可扩展
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_rowconfigure(0, weight=1)
        
        # 快捷键绑定：Ctrl+Enter 发送
        self.input_entry.bind("<Control-Return>", lambda e: self.send_message())
        
        # 提示标签
        hint_label = tk.Label(right_frame, text="提示：按 Ctrl+Enter 快速发送",
                              font=("微软雅黑", 8), fg="gray")
        hint_label.pack(pady=(0,5))
        
        # 清除高亮按钮
        clear_btn = tk.Button(right_frame, text="🗑️ 清除高亮", command=self.map_handler.clear_highlight,
                              bg='#f44336', fg='white', font=("微软雅黑", 10))
        clear_btn.pack(pady=5)
    
    def send_message(self):
        user_input = self.input_entry.get("1.0", tk.END).strip()
        if not user_input:
            return
        self.input_entry.delete("1.0", tk.END)
        self.display_message("用户", user_input)
        # 显示处理中提示
        self.display_temp_message("系统", "正在处理，请稍候...")
        # 启动后台线程处理 AI
        Thread(target=self.process_ai, args=(user_input,), daemon=True).start()
    
    def display_temp_message(self, sender, message):
        """显示临时消息（会被后续正式消息覆盖）"""
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n\n", "temp")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)
        self.chat_display.tag_config("temp", font=("微软雅黑", 10, "italic"), foreground="gray")
        self.temp_message_id = (sender, message)  # 记录以便删除
    
    def remove_temp_message(self):
        """删除临时消息（简单实现：清空并重新显示之前的消息，此处简化处理）"""
        # 由于 ScrolledText 删除特定行较复杂，此处我们选择覆盖而不是删除
        pass

    def process_ai(self, user_input):
        def highlight_callback(highlight_infos):
            # 确保在主线程中更新 UI
            self.root.after(0, lambda: self.map_handler.batch_highlight(highlight_infos))
        try:
            answer = self.ai_handler.process_message(user_input, highlight_callback)
        except Exception as e:
            answer = f"系统内部错误: {str(e)}"
        # 在主线程中显示最终回答
        self.root.after(0, lambda: self.display_message("AI助手", answer))
    
    def display_message(self, sender, message):
        self.chat_display.configure(state='normal')
        # 如果存在临时消息，先删除（此处简化为插入分隔线）
        self.chat_display.insert(tk.END, f"{sender}:\n", "sender")
        self.chat_display.insert(tk.END, f"{message}\n\n", "message")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)
        self.chat_display.tag_config("sender", font=("微软雅黑", 10, "bold"), foreground="#2c3e50")
        self.chat_display.tag_config("message", font=("微软雅黑", 10), foreground="#34495e")