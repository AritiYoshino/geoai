import os
import tkinter as tk
from threading import Thread
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from ai_handler import AIHandler
from map_handler import MapHandler


class GISApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ACE 多 Agent 地理分析系统原型")
        self.root.geometry("1280x760")

        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.map_handler = MapHandler(left_frame)

        try:
            self.map_handler.load_shapefiles("geodata")
            self.map_handler.plot_all_layers()
        except Exception as e:
            messagebox.showerror("错误", f"加载地图数据失败: {e}")
            self.root.destroy()
            return

        self.create_right_panel()

        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            messagebox.showerror("错误", "请在 .env 文件中设置 DEEPSEEK_API_KEY")
            self.root.destroy()
            return
        self.ai_handler = AIHandler(api_key, self.map_handler)
        self.refresh_sessions()
        self.refresh_experience_banks()
        self.load_current_session_history()
        self.refresh_trace_view()
        self.refresh_experience_view()

    def create_right_panel(self):
        right_frame = tk.Frame(self.root, width=460, bg="#f5f7fa")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=6, pady=6)
        right_frame.pack_propagate(False)

        session_frame = tk.Frame(right_frame, bg="#f5f7fa")
        session_frame.pack(fill=tk.X, pady=(0, 6))
        self.session_var = tk.StringVar()
        self.session_combo = ttk.Combobox(
            session_frame,
            textvariable=self.session_var,
            state="readonly",
            font=("Microsoft YaHei", 9),
        )
        self.session_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.session_combo.bind("<<ComboboxSelected>>", self.on_session_selected)
        tk.Button(
            session_frame,
            text="新会话",
            command=self.create_new_session,
            bg="#475569",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.RIGHT, padx=(6, 0))

        self.tabs = ttk.Notebook(right_frame)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        chat_tab = tk.Frame(self.tabs, bg="#f5f7fa")
        trace_tab = tk.Frame(self.tabs, bg="#f5f7fa")
        exp_tab = tk.Frame(self.tabs, bg="#f5f7fa")
        self.tabs.add(chat_tab, text="对话")
        self.tabs.add(trace_tab, text="ACE 轨迹")
        self.tabs.add(exp_tab, text="经验库")

        self.chat_display = scrolledtext.ScrolledText(
            chat_tab, wrap=tk.WORD, font=("Microsoft YaHei", 10), state="disabled"
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        input_frame = tk.Frame(chat_tab, bg="#f5f7fa")
        input_frame.pack(fill=tk.X, pady=4)

        self.input_entry = tk.Text(input_frame, height=4, font=("Microsoft YaHei", 10))
        self.input_entry.grid(row=0, column=0, sticky="nsew")

        send_btn = tk.Button(
            input_frame,
            text="发送",
            command=self.send_message,
            width=8,
            bg="#2563eb",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
        )
        send_btn.grid(row=0, column=1, padx=(6, 0), sticky="ns")

        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_rowconfigure(0, weight=1)
        self.input_entry.bind("<Control-Return>", lambda _event: self.send_message())

        action_frame = tk.Frame(chat_tab, bg="#f5f7fa")
        action_frame.pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            action_frame,
            text="Ctrl+Enter 快速发送",
            font=("Microsoft YaHei", 8),
            fg="#64748b",
            bg="#f5f7fa",
        ).pack(side=tk.LEFT)
        tk.Button(
            action_frame,
            text="清除高亮",
            command=self.map_handler.clear_highlight,
            bg="#dc2626",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.RIGHT)

        feedback_frame = tk.Frame(chat_tab, bg="#f5f7fa")
        feedback_frame.pack(fill=tk.X, pady=(4, 4))
        tk.Button(
            feedback_frame,
            text="👍 正确",
            command=lambda: self.submit_feedback("correct"),
            bg="#16a34a",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT)
        tk.Button(
            feedback_frame,
            text="👎 不正确",
            command=lambda: self.submit_feedback("incorrect"),
            bg="#ea580c",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            feedback_frame,
            text="✍ 纠正",
            command=self.submit_correction,
            bg="#7c3aed",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT, padx=(6, 0))

        self.trace_display = scrolledtext.ScrolledText(
            trace_tab, wrap=tk.WORD, font=("Consolas", 9), state="disabled"
        )
        self.trace_display.pack(fill=tk.BOTH, expand=True)

        self.experience_display = scrolledtext.ScrolledText(
            exp_tab, wrap=tk.WORD, font=("Microsoft YaHei", 9), state="disabled"
        )
        self.experience_display.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        bank_frame = tk.Frame(exp_tab, bg="#f5f7fa")
        bank_frame.pack(fill=tk.X, pady=(0, 6))
        self.experience_bank_var = tk.StringVar()
        self.experience_bank_combo = ttk.Combobox(
            bank_frame,
            textvariable=self.experience_bank_var,
            state="readonly",
            font=("Microsoft YaHei", 9),
        )
        self.experience_bank_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.experience_bank_combo.bind("<<ComboboxSelected>>", self.on_experience_bank_selected)

        bank_button_frame = tk.Frame(exp_tab, bg="#f5f7fa")
        bank_button_frame.pack(fill=tk.X)
        tk.Button(
            bank_button_frame,
            text="新建空库",
            command=lambda: self.create_experience_bank("empty"),
            bg="#334155",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT)
        tk.Button(
            bank_button_frame,
            text="默认模板",
            command=lambda: self.create_experience_bank("default"),
            bg="#0f766e",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            bank_button_frame,
            text="复制当前",
            command=lambda: self.create_experience_bank("copy_current"),
            bg="#7c3aed",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(
            bank_button_frame,
            text="刷新经验库",
            command=self.refresh_experience_view,
            bg="#0f766e",
            fg="white",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.RIGHT)

    def send_message(self):
        user_input = self.input_entry.get("1.0", tk.END).strip()
        if not user_input:
            return
        self.input_entry.delete("1.0", tk.END)
        self.display_message("用户", user_input)
        self.display_message("系统", "正在由 Coder Agent 分析，并将工具反馈交给 Critic Agent 诊断...")
        Thread(target=self.process_ai, args=(user_input,), daemon=True).start()

    def process_ai(self, user_input):
        def highlight_callback(highlight_infos):
            self.root.after(0, lambda: self.map_handler.batch_highlight(highlight_infos))

        try:
            answer = self.ai_handler.process_message(user_input, highlight_callback)
        except Exception as e:
            answer = f"系统内部错误: {str(e)}"

        self.root.after(0, lambda: self.display_message("AI 助手", answer))
        self.root.after(0, self.refresh_sessions)
        self.root.after(0, self.refresh_trace_view)
        self.root.after(0, self.refresh_experience_view)

    def display_message(self, sender, message):
        self.chat_display.configure(state="normal")
        self.chat_display.insert(tk.END, f"{sender}:\n", "sender")
        self.chat_display.insert(tk.END, f"{message}\n\n", "message")
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)
        self.chat_display.tag_config(
            "sender", font=("Microsoft YaHei", 10, "bold"), foreground="#1e293b"
        )
        self.chat_display.tag_config("message", font=("Microsoft YaHei", 10), foreground="#334155")

    def refresh_trace_view(self):
        if not hasattr(self, "ai_handler"):
            return
        self._replace_text(self.trace_display, self.ai_handler.get_trace_text())

    def refresh_experience_view(self):
        if not hasattr(self, "ai_handler"):
            return
        text = self.ai_handler.get_experience_summary() or "经验库为空。"
        self._replace_text(self.experience_display, text)

    def refresh_experience_banks(self):
        if not hasattr(self, "ai_handler"):
            return
        self.experience_bank_options = []
        labels = []
        active = self.ai_handler.get_active_experience_bank()
        for bank in self.ai_handler.list_experience_banks():
            label = f"{bank.get('name', '未命名经验库')}  [{bank.get('id', '')}]"
            labels.append(label)
            self.experience_bank_options.append((label, bank["id"]))
        self.experience_bank_combo["values"] = labels
        for label, bank_id in self.experience_bank_options:
            if active and bank_id == active.get("id"):
                self.experience_bank_var.set(label)
                break

    def on_experience_bank_selected(self, _event=None):
        if not hasattr(self, "ai_handler"):
            return
        selected = self.experience_bank_var.get()
        bank_id = next(
            (bid for label, bid in self.experience_bank_options if label == selected),
            None,
        )
        if not bank_id:
            return
        bank = self.ai_handler.switch_experience_bank(bank_id)
        self.display_message("系统", f"已切换经验库：{bank['name']}")
        self.refresh_experience_view()

    def create_experience_bank(self, template):
        if not hasattr(self, "ai_handler"):
            return
        template_names = {
            "empty": "空白经验库",
            "default": "默认模板经验库",
            "copy_current": "当前经验库副本",
        }
        name = simpledialog.askstring(
            "新建经验库",
            f"请输入{template_names.get(template, '经验库')}名称：",
        )
        if not name:
            return
        bank = self.ai_handler.create_experience_bank(name, template)
        self.refresh_experience_banks()
        self.refresh_experience_view()
        self.display_message("系统", f"已创建并切换到经验库：{bank['name']}")

    def submit_feedback(self, feedback_type, correction=""):
        if not hasattr(self, "ai_handler"):
            return
        result = self.ai_handler.submit_feedback(feedback_type, correction)
        self.display_message("系统", f"已记录反馈并更新经验库：{result}")
        self.refresh_experience_view()

    def submit_correction(self):
        correction = simpledialog.askstring("纠正结果", "请说明正确结果或以后应遵循的规则：")
        if correction:
            self.submit_feedback("correction", correction)

    def refresh_sessions(self):
        if not hasattr(self, "ai_handler"):
            return
        self.session_options = []
        labels = []
        current = self.ai_handler.get_current_session()
        for session in self.ai_handler.list_sessions():
            label = f"{session.get('title', '未命名会话')}  [{session.get('updated_at', '')}]"
            labels.append(label)
            self.session_options.append((label, session["id"]))
        self.session_combo["values"] = labels
        for label, session_id in self.session_options:
            if current and session_id == current.get("id"):
                self.session_var.set(label)
                break

    def create_new_session(self):
        if not hasattr(self, "ai_handler"):
            return
        self.ai_handler.new_session()
        self.map_handler.clear_highlight()
        self.refresh_sessions()
        self.load_current_session_history()
        self.refresh_trace_view()

    def on_session_selected(self, _event=None):
        if not hasattr(self, "ai_handler"):
            return
        selected = self.session_var.get()
        session_id = next((sid for label, sid in self.session_options if label == selected), None)
        if not session_id:
            return
        self.ai_handler.switch_session(session_id)
        self.map_handler.clear_highlight()
        self.load_current_session_history()
        self.refresh_trace_view()

    def load_current_session_history(self):
        if not hasattr(self, "ai_handler"):
            return
        session = self.ai_handler.get_current_session()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", tk.END)
        for message in session.get("messages", []):
            sender = "用户" if message.get("role") == "user" else "AI 助手"
            self.chat_display.insert(tk.END, f"{sender}:\n", "sender")
            self.chat_display.insert(tk.END, f"{message.get('content', '')}\n\n", "message")
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)
        self.chat_display.tag_config(
            "sender", font=("Microsoft YaHei", 10, "bold"), foreground="#1e293b"
        )
        self.chat_display.tag_config("message", font=("Microsoft YaHei", 10), foreground="#334155")

    def _replace_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")
