import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
import sys
import random


try:
    from pynput import mouse, keyboard
except ImportError:
    print("缺少pynput库，请先安装: pip install pynput")
    sys.exit(1)

class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("Python 连点器 - 多边形区域随机点击")
        self.root.geometry("600x750")  # 增加宽度以容纳新控件
        self.root.resizable(True, True)
        
        self.clicking = False
        self.stop_event = threading.Event()
        self.mouse_positions = []
        self.current_position = (0, 0)
        self.key_listener = None
        self.hotkey = "f6"
        self.record_hotkey = "f7"
        self.click_position = None
        
        self.use_region = tk.BooleanVar(value=False)
        self.polygon_vertices = []
        self.defining_polygon = False
        self.add_vertex_hotkey = "f8"
        self.finish_polygon_hotkey = "f9"
        
        self.selecting_rectangle = False
        self.rect_start = None
        self.rect_end = None
        
        # 随机间隔相关变量
        self.use_random_interval = tk.BooleanVar(value=False)
        self.min_interval = tk.IntVar(value=1000)   # 毫秒
        self.max_interval = tk.IntVar(value=3000)   # 毫秒
        
        self.create_widgets()
        self.load_settings()
        
        self.mouse_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_mouse_click)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()
        
        self.start_keyboard_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 固定位置设置
        position_frame = ttk.LabelFrame(main_frame, text="固定点击位置", padding=10)
        position_frame.pack(fill=tk.X, pady=5)
        ttk.Label(position_frame, text="当前位置:").grid(row=0, column=0, sticky=tk.W)
        self.pos_label = ttk.Label(position_frame, text="(0, 0)")
        self.pos_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(position_frame, text="记录当前位置", command=self.record_position).grid(row=0, column=2, padx=5)
        ttk.Button(position_frame, text="设为点击位置", command=self.set_click_position).grid(row=0, column=3)
        ttk.Label(position_frame, text="已记录位置:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.position_listbox = tk.Listbox(position_frame, height=3, width=50)
        self.position_listbox.grid(row=1, column=1, columnspan=3, sticky=tk.W+tk.E, pady=5)
        
        # 多边形区域设置
        region_frame = ttk.LabelFrame(main_frame, text="多边形区域随机点击", padding=10)
        region_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(region_frame, text="启用多边形内随机点击", variable=self.use_region,
                        command=self.on_region_toggle).grid(row=0, column=0, sticky=tk.W)
        self.define_btn = ttk.Button(region_frame, text="开始定义区域", command=self.toggle_polygon_definition)
        self.define_btn.grid(row=0, column=1, padx=5)
        self.region_status_label = ttk.Label(region_frame, text="未定义多边形")
        self.region_status_label.grid(row=0, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(region_frame, text="多边形顶点:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.vertex_listbox = tk.Listbox(region_frame, height=4, width=50)
        self.vertex_listbox.grid(row=1, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5)
        
        btn_frame = ttk.Frame(region_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Button(btn_frame, text="添加顶点", command=self.add_vertex).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="完成区域", command=self.finish_polygon).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清除所有顶点", command=self.clear_polygon).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="框选矩形区域", command=self.start_rectangle_selection).pack(side=tk.LEFT, padx=2)
        
        hotkey_frame = ttk.Frame(region_frame)
        hotkey_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        ttk.Label(hotkey_frame, text="添加顶点热键:").pack(side=tk.LEFT, padx=(0,5))
        self.add_vertex_hotkey_var = tk.StringVar(value="F8")
        ttk.Entry(hotkey_frame, textvariable=self.add_vertex_hotkey_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(hotkey_frame, text="设置", command=self.set_add_vertex_hotkey).pack(side=tk.LEFT, padx=5)
        ttk.Label(hotkey_frame, text="完成区域热键:").pack(side=tk.LEFT, padx=(15,5))
        self.finish_polygon_hotkey_var = tk.StringVar(value="F9")
        ttk.Entry(hotkey_frame, textvariable=self.finish_polygon_hotkey_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(hotkey_frame, text="设置", command=self.set_finish_polygon_hotkey).pack(side=tk.LEFT, padx=5)
        
        self.region_tip_label = ttk.Label(region_frame, text="", foreground="gray")
        self.region_tip_label.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=2)
        self.update_region_tip()
        
        # 控制设置（增加随机间隔）
        control_frame = ttk.LabelFrame(main_frame, text="控制设置", padding=10)
        control_frame.pack(fill=tk.X, pady=5)
        
        # 第一行：点击次数和固定间隔
        ttk.Label(control_frame, text="点击次数:").grid(row=0, column=0, sticky=tk.W)
        self.click_count = ttk.Combobox(control_frame, values=["无限", "10", "50", "100", "200", "500", "1000"], width=8)
        self.click_count.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.click_count.current(0)
        
        ttk.Label(control_frame, text="固定间隔(毫秒):").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.interval = ttk.Spinbox(control_frame, from_=10, to=10000, increment=50, width=8)
        self.interval.grid(row=0, column=3, sticky=tk.W, padx=5)
        self.interval.set(100)
        
        # 第二行：随机间隔选项
        self.random_check = ttk.Checkbutton(control_frame, text="启用随机间隔", variable=self.use_random_interval,
                                            command=self.on_random_interval_toggle)
        self.random_check.grid(row=1, column=0, sticky=tk.W, pady=5)
        
        ttk.Label(control_frame, text="最小(毫秒):").grid(row=1, column=1, sticky=tk.W, padx=5)
        self.min_interval_spin = ttk.Spinbox(control_frame, from_=10, to=10000, increment=50, width=8,
                                             textvariable=self.min_interval)
        self.min_interval_spin.grid(row=1, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(control_frame, text="最大(毫秒):").grid(row=1, column=3, sticky=tk.W, padx=5)
        self.max_interval_spin = ttk.Spinbox(control_frame, from_=10, to=10000, increment=50, width=8,
                                             textvariable=self.max_interval)
        self.max_interval_spin.grid(row=1, column=4, sticky=tk.W, padx=5)
        
        # 第三行：点击按钮
        ttk.Label(control_frame, text="点击按钮:").grid(row=2, column=0, sticky=tk.W, pady=10)
        self.button_var = tk.StringVar(value="left")
        ttk.Radiobutton(control_frame, text="左键", variable=self.button_var, value="left").grid(row=2, column=1, sticky=tk.W)
        ttk.Radiobutton(control_frame, text="右键", variable=self.button_var, value="right").grid(row=2, column=2, sticky=tk.W)
        
        # 第四行：热键设置
        ttk.Label(control_frame, text="开始/停止热键:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.hotkey_var = tk.StringVar(value="F6")
        ttk.Entry(control_frame, textvariable=self.hotkey_var, width=5).grid(row=3, column=1, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="设置", command=self.set_hotkey).grid(row=3, column=2, padx=5)
        
        ttk.Label(control_frame, text="记录位置快捷键:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.record_hotkey_var = tk.StringVar(value="F7")
        ttk.Entry(control_frame, textvariable=self.record_hotkey_var, width=5).grid(row=4, column=1, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="设置", command=self.set_record_hotkey).grid(row=4, column=2, padx=5)
        
        # 状态区域
        status_frame = ttk.LabelFrame(main_frame, text="状态信息", padding=10)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar(value="就绪 - 按开始按钮或热键启动连点")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="开始", command=self.start_clicking, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="停止", command=self.stop_clicking, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="清除记录", command=self.clear_positions, width=10).pack(side=tk.RIGHT, padx=10)
        ttk.Button(button_frame, text="保存设置", command=self.save_settings, width=10).pack(side=tk.RIGHT, padx=10)
    
    def on_random_interval_toggle(self):
        """当随机间隔复选框状态改变时，更新相关控件的状态"""
        state = "启用" if self.use_random_interval.get() else "禁用"
        self.status_var.set(f"随机间隔已{state}")
    
    # ---------- 多边形定义核心 ----------
    def on_region_toggle(self):
        if self.use_region.get() and len(self.polygon_vertices) < 3:
            self.status_var.set("提示: 多边形至少需要3个顶点才能形成区域")
        else:
            state = "启用" if self.use_region.get() else "禁用"
            self.status_var.set(f"已{state}多边形区域随机点击")
    
    def toggle_polygon_definition(self):
        if not self.defining_polygon:
            self.defining_polygon = True
            self.define_btn.config(text="取消定义")
            self.status_var.set(f"多边形定义模式已开启 - 按 {self.add_vertex_hotkey.upper()} 添加顶点，{self.finish_polygon_hotkey.upper()} 完成")
        else:
            self.defining_polygon = False
            self.define_btn.config(text="开始定义区域")
            self.status_var.set("已取消多边形定义")
    
    def add_vertex(self):
        if not self.defining_polygon:
            self.status_var.set("请先点击'开始定义区域'进入定义模式")
            return
        x, y = self.current_position
        x, y = int(x), int(y)
        self.polygon_vertices.append((x, y))
        self.update_vertex_listbox()
        self.status_var.set(f"已添加顶点: ({x}, {y})，当前顶点数: {len(self.polygon_vertices)}")
    
    def finish_polygon(self):
        if not self.defining_polygon:
            self.status_var.set("当前不在多边形定义模式")
            return
        if len(self.polygon_vertices) < 3:
            self.status_var.set("至少需要3个顶点才能形成多边形区域")
            return
        self.defining_polygon = False
        self.define_btn.config(text="开始定义区域")
        self.update_region_status()
        self.status_var.set(f"多边形定义完成，共 {len(self.polygon_vertices)} 个顶点")
        if self.use_region.get():
            self.status_var.set(f"多边形区域已启用，顶点数: {len(self.polygon_vertices)}")
    
    def clear_polygon(self):
        self.polygon_vertices = []
        self.update_vertex_listbox()
        self.region_status_label.config(text="未定义多边形")
        self.status_var.set("已清除多边形顶点")
    
    def update_vertex_listbox(self):
        self.vertex_listbox.delete(0, tk.END)
        for i, (x, y) in enumerate(self.polygon_vertices):
            self.vertex_listbox.insert(tk.END, f"顶点{i+1}: ({x}, {y})")
    
    def update_region_status(self):
        if len(self.polygon_vertices) >= 3:
            self.region_status_label.config(text=f"多边形已定义，{len(self.polygon_vertices)} 个顶点")
        else:
            self.region_status_label.config(text=f"顶点数不足 ({len(self.polygon_vertices)}/3)")
    
    def update_region_tip(self):
        self.region_tip_label.config(
            text=f"提示：点击'开始定义区域'后，按 {self.add_vertex_hotkey.upper()} 添加顶点，"
                 f"按 {self.finish_polygon_hotkey.upper()} 完成；也可使用「框选矩形区域」快速添加矩形。"
        )
    
    # ---------- 框选矩形 ----------
    def start_rectangle_selection(self):
        if not self.defining_polygon:
            self.status_var.set("请先点击「开始定义区域」进入定义模式，再使用框选功能")
            return
        self.selecting_rectangle = True
        self.rect_start = None
        self.rect_end = None
        self.status_var.set("框选模式已启动：请按住鼠标左键并拖动以选择矩形区域，释放后自动添加四个顶点")
    
    def on_mouse_click(self, x, y, button, pressed):
        if self.selecting_rectangle:
            if button == mouse.Button.left:
                if pressed:
                    self.rect_start = (int(x), int(y))
                    self.status_var.set(f"框选起点: ({int(x)}, {int(y)})，正在拖动...")
                else:
                    self.rect_end = (int(x), int(y))
                    if self.rect_start and self.rect_end:
                        self.add_rectangle_vertices(self.rect_start, self.rect_end)
                    self.selecting_rectangle = False
                    self.status_var.set("框选完成，矩形顶点已添加")
    
    def add_rectangle_vertices(self, p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        vertices = [(left, top), (right, top), (right, bottom), (left, bottom)]
        self.polygon_vertices.extend(vertices)
        self.update_vertex_listbox()
        self.update_region_status()
        self.status_var.set(f"已添加矩形四个顶点，当前总顶点数: {len(self.polygon_vertices)}")
    
    # ---------- 热键设置 ----------
    def set_add_vertex_hotkey(self):
        new_hotkey = self.add_vertex_hotkey_var.get().strip().lower()
        if new_hotkey:
            self.add_vertex_hotkey = new_hotkey
            self.add_vertex_hotkey_var.set(new_hotkey.upper())
            self.status_var.set(f"添加顶点热键已设置为: {self.add_vertex_hotkey.upper()}")
            self.update_region_tip()
            if self.defining_polygon:
                self.status_var.set(f"多边形定义模式已开启 - 按 {self.add_vertex_hotkey.upper()} 添加顶点，{self.finish_polygon_hotkey.upper()} 完成")
    
    def set_finish_polygon_hotkey(self):
        new_hotkey = self.finish_polygon_hotkey_var.get().strip().lower()
        if new_hotkey:
            self.finish_polygon_hotkey = new_hotkey
            self.finish_polygon_hotkey_var.set(new_hotkey.upper())
            self.status_var.set(f"完成区域热键已设置为: {self.finish_polygon_hotkey.upper()}")
            self.update_region_tip()
            if self.defining_polygon:
                self.status_var.set(f"多边形定义模式已开启 - 按 {self.add_vertex_hotkey.upper()} 添加顶点，{self.finish_polygon_hotkey.upper()} 完成")
    
    # ---------- 固定位置功能 ----------
    def on_move(self, x, y):
        self.current_position = (int(x), int(y))
        self.pos_label.config(text=f"({int(x)}, {int(y)})")
    
    def record_position(self):
        pos = (int(self.current_position[0]), int(self.current_position[1]))
        self.mouse_positions.append(pos)
        self.update_position_list()
        self.status_var.set(f"已记录位置: {pos}")
    
    def set_click_position(self):
        if not self.mouse_positions:
            self.status_var.set("没有记录的位置")
            return
        try:
            selection = self.position_listbox.curselection()
            if selection:
                self.click_position = self.mouse_positions[selection[0]]
                self.status_var.set(f"已设置点击位置: {self.click_position}")
            else:
                self.status_var.set("请从列表中选择一个位置")
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
    
    def update_position_list(self):
        self.position_listbox.delete(0, tk.END)
        for i, pos in enumerate(self.mouse_positions):
            self.position_listbox.insert(tk.END, f"位置{i+1}: ({pos[0]}, {pos[1]})")
    
    def clear_positions(self):
        self.mouse_positions = []
        self.update_position_list()
        self.status_var.set("已清除所有位置记录")
    
    # ---------- 连点逻辑（支持随机间隔） ----------
    def start_clicking(self):
        if self.clicking:
            return
        
        if self.use_region.get():
            if len(self.polygon_vertices) < 3:
                messagebox.showwarning("无法启动", "多边形区域至少需要3个顶点！请先添加顶点并完成区域定义。")
                self.status_var.set("启动失败：多边形顶点不足3个")
                return
        else:
            if not self.click_position and not self.mouse_positions:
                messagebox.showwarning("无法启动", "没有设置点击位置！请先记录一个位置并设为点击位置。")
                self.status_var.set("启动失败：未设置点击位置")
                return
            if not self.click_position:
                self.click_position = self.mouse_positions[0]
                self.status_var.set(f"自动使用第一个记录位置: {self.click_position}")
        
        # 检查随机间隔参数合法性
        if self.use_random_interval.get():
            min_int = self.min_interval.get()
            max_int = self.max_interval.get()
            if min_int <= 0 or max_int <= 0 or min_int > max_int:
                messagebox.showwarning("参数错误", "随机间隔的最小值必须大于0，且不能大于最大值。")
                return
        
        # 获取固定间隔（作为备用，当随机间隔未启用时使用）
        try:
            fixed_interval = int(self.interval.get())
            if fixed_interval < 10:
                fixed_interval = 10
        except:
            fixed_interval = 100
        
        count_str = self.click_count.get()
        if count_str == "无限":
            click_count = -1
        else:
            try:
                click_count = int(count_str)
            except:
                click_count = 100
        
        self.clicking = True
        self.stop_event.clear()
        # 传递间隔参数：固定间隔和随机间隔的配置
        self.click_thread = threading.Thread(target=self.auto_click, args=(fixed_interval, click_count))
        self.click_thread.daemon = True
        self.click_thread.start()
        
        if self.use_region.get():
            self.status_var.set(f"开始多边形内随机点击 - 顶点数: {len(self.polygon_vertices)}")
        else:
            self.status_var.set(f"开始连点 - 位置: {self.click_position}")
        
        if self.use_random_interval.get():
            self.status_var.set(self.status_var.get() + f" (随机间隔 {self.min_interval.get()}-{self.max_interval.get()}ms)")
    
    def stop_clicking(self):
        if self.clicking:
            self.clicking = False
            self.stop_event.set()
            self.status_var.set("连点已停止")
    
    def point_in_polygon(self, x, y, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    def random_point_in_polygon(self, poly, max_attempts=1000):
        if len(poly) < 3:
            return None
        xs = [int(p[0]) for p in poly]
        ys = [int(p[1]) for p in poly]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        for _ in range(max_attempts):
            rx = random.randint(min_x, max_x)
            ry = random.randint(min_y, max_y)
            if self.point_in_polygon(rx, ry, poly):
                return (rx, ry)
        return (int(poly[0][0]), int(poly[0][1]))
    
    def auto_click(self, fixed_interval_ms, count):
        try:
            controller = mouse.Controller()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"无法初始化鼠标控制器：{str(e)}\n请尝试以管理员权限运行。"))
            self.root.after(0, self.stop_clicking)
            return
        
        clicks = 0
        try:
            while not self.stop_event.is_set() and (count == -1 or clicks < count):
                # 确定点击位置
                if self.use_region.get() and len(self.polygon_vertices) >= 3:
                    position = self.random_point_in_polygon(self.polygon_vertices)
                else:
                    position = self.click_position
                
                if position:
                    controller.position = (int(position[0]), int(position[1]))
                else:
                    time.sleep(0.01)
                    continue
                
                # 执行点击
                if self.button_var.get() == "left":
                    controller.click(mouse.Button.left)
                else:
                    controller.click(mouse.Button.right)
                
                clicks += 1
                self.root.after(0, lambda c=clicks: self.status_var.set(
                    f"点击中: {c}次 {'(无限)' if count == -1 else f'共: {count}'}"
                ))
                
                # 确定本次点击后的等待间隔
                if self.use_random_interval.get():
                    min_ms = self.min_interval.get()
                    max_ms = self.max_interval.get()
                    if min_ms > max_ms:
                        min_ms, max_ms = max_ms, min_ms
                    wait_ms = random.randint(min_ms, max_ms)
                else:
                    wait_ms = fixed_interval_ms
                
                wait_sec = wait_ms / 1000.0
                # 等待，期间可响应停止事件
                start_time = time.time()
                while time.time() - start_time < wait_sec and not self.stop_event.is_set():
                    time.sleep(0.005)
            
            self.root.after(0, self.stop_clicking)
        except Exception as e:
            error_msg = f"连点过程中出现异常：{str(e)}"
            self.root.after(0, lambda: messagebox.showerror("运行错误", error_msg))
            self.root.after(0, self.stop_clicking)
    
    # ---------- 键盘监听 ----------
    def start_keyboard_listener(self):
        self.key_listener = keyboard.Listener(on_press=self.on_key_press)
        self.key_listener.daemon = True
        self.key_listener.start()
    
    def on_key_press(self, key):
        try:
            key_str = None
            if hasattr(key, 'char') and key.char is not None:
                key_str = key.char.lower()
            elif hasattr(key, 'name'):
                key_str = key.name.lower()
            else:
                key_str = str(key).replace('Key.', '').lower()
            if key_str:
                if key_str == self.hotkey.lower():
                    if not self.clicking:
                        self.root.after(0, self.start_clicking)
                    else:
                        self.root.after(0, self.stop_clicking)
                elif key_str == self.record_hotkey.lower():
                    self.root.after(0, self.record_position)
                elif self.defining_polygon:
                    if key_str == self.add_vertex_hotkey.lower():
                        self.root.after(0, self.add_vertex)
                    elif key_str == self.finish_polygon_hotkey.lower():
                        self.root.after(0, self.finish_polygon)
        except Exception as e:
            print(f"热键处理错误: {str(e)}")
    
    # ---------- 保存/加载 ----------
    def set_hotkey(self):
        new_hotkey = self.hotkey_var.get().strip().lower()
        if new_hotkey:
            self.hotkey = new_hotkey
            self.status_var.set(f"开始/停止热键已设置为: {self.hotkey.upper()}")
    
    def set_record_hotkey(self):
        new_hotkey = self.record_hotkey_var.get().strip().lower()
        if new_hotkey:
            self.record_hotkey = new_hotkey
            self.status_var.set(f"记录位置快捷键已设置为: {self.record_hotkey.upper()}")
    
    def save_settings(self):
        positions_list = [list(pos) for pos in self.mouse_positions] if self.mouse_positions else []
        click_pos_list = list(self.click_position) if self.click_position else None
        polygon_list = [list(v) for v in self.polygon_vertices] if self.polygon_vertices else []
        settings = {
            'hotkey': self.hotkey,
            'record_hotkey': self.record_hotkey,
            'add_vertex_hotkey': self.add_vertex_hotkey,
            'finish_polygon_hotkey': self.finish_polygon_hotkey,
            'interval': self.interval.get(),
            'click_count': self.click_count.get(),
            'button': self.button_var.get(),
            'positions': positions_list,
            'click_position': click_pos_list,
            'use_region': self.use_region.get(),
            'polygon_vertices': polygon_list,
            # 新增随机间隔设置
            'use_random_interval': self.use_random_interval.get(),
            'min_interval': self.min_interval.get(),
            'max_interval': self.max_interval.get()
        }
        try:
            with open('autoclicker_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.status_var.set("设置已保存")
        except Exception as e:
            self.status_var.set(f"保存失败: {str(e)}")
    
    def load_settings(self):
        try:
            if os.path.exists('autoclicker_settings.json'):
                with open('autoclicker_settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                self.hotkey = settings.get('hotkey', 'f6')
                self.hotkey_var.set(self.hotkey.upper())
                self.record_hotkey = settings.get('record_hotkey', 'f7')
                self.record_hotkey_var.set(self.record_hotkey.upper())
                self.add_vertex_hotkey = settings.get('add_vertex_hotkey', 'f8')
                self.add_vertex_hotkey_var.set(self.add_vertex_hotkey.upper())
                self.finish_polygon_hotkey = settings.get('finish_polygon_hotkey', 'f9')
                self.finish_polygon_hotkey_var.set(self.finish_polygon_hotkey.upper())
                self.update_region_tip()
                self.interval.set(settings.get('interval', '100'))
                click_count = settings.get('click_count', '无限')
                if click_count in ["无限", "10", "50", "100", "200", "500", "1000"]:
                    self.click_count.set(click_count)
                self.button_var.set(settings.get('button', 'left'))
                positions = settings.get('positions', [])
                if positions:
                    self.mouse_positions = [tuple(pos) for pos in positions]
                    self.update_position_list()
                cp = settings.get('click_position')
                if cp:
                    self.click_position = tuple(cp)
                self.use_region.set(settings.get('use_region', False))
                polygon = settings.get('polygon_vertices', [])
                if polygon:
                    self.polygon_vertices = [tuple(v) for v in polygon]
                    self.update_vertex_listbox()
                    self.update_region_status()
                # 加载随机间隔设置
                self.use_random_interval.set(settings.get('use_random_interval', False))
                self.min_interval.set(settings.get('min_interval', 1000))
                self.max_interval.set(settings.get('max_interval', 3000))
                self.status_var.set("设置已加载")
        except Exception as e:
            print(f"加载设置出错: {e}")
    
    def on_close(self):
        self.stop_clicking()
        self.save_settings()
        if self.key_listener and self.key_listener.is_alive():
            self.key_listener.stop()
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClicker(root)
    root.mainloop()