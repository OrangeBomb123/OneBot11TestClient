import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
from PIL import Image, ImageTk
import io
import requests
import websockets
import asyncio
import datetime
import re

class OneBotClient:
    def __init__(self, root):
        self.root = root
        self.root.title("OneBot11客户端")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        
        # 设置主题颜色
        self.bg_color = "#f5f5f5"
        self.text_bg = "#ffffff"
        self.sidebar_bg = "#343a40"
        self.sidebar_text = "#ffffff"
        self.message_self_bg = "#dcf8c6"
        self.message_other_bg = "#ffffff"
        self.message_time_color = "#8e8e93"
        self.header_bg = "#1976d2"
        self.header_text = "#ffffff"
        self.button_bg = "#1976d2"
        self.button_text = "#ffffff"
        
        # 初始化变量
        self.current_conversation = None
        self.conversations = {}
        self.websocket = None
        self.is_connected = False
        self.lock = threading.RLock()
        self.group_members = {}  # 存储群成员信息
        self.image_cache = {}  # 缓存已加载的图片
        
        # 加载配置
        self.config = self.load_config()
        
        # 创建界面
        self.create_widgets()
        
        # 加载聊天记录
        self.load_chat_history()
        
        # 启动异步事件循环线程
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.run_event_loop, daemon=True)
        self.loop_thread.start()
    
    def load_config(self):
        config_path = "config.json"
        default_config = {
            "websocket_server": "ws://localhost:8080",
            "token": "",
            "auto_reconnect": True
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                messagebox.showerror("错误", "加载配置文件失败，使用默认配置")
        
        return default_config
    
    def save_config(self):
        config_path = "config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except:
            messagebox.showerror("错误", "保存配置文件失败")
    
    def load_chat_history(self):
        history_dir = "chat_history"
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
            return
        
        for filename in os.listdir(history_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(history_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.conversations[data["id"]] = data
                        self.add_conversation_to_sidebar(data["id"], data["name"], data.get("avatar", "👤"))
                except:
                    pass
    
    def save_chat_history(self, conversation_id):
        if conversation_id not in self.conversations:
            return
        
        history_dir = "chat_history"
        if not os.path.exists(history_dir):
            os.makedirs(history_dir)
        
        try:
            with open(os.path.join(history_dir, f"{conversation_id}.json"), 'w', encoding='utf-8') as f:
                json.dump(self.conversations[conversation_id], f, ensure_ascii=False, indent=2)
        except:
            messagebox.showerror("错误", "保存聊天记录失败")
    
    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧边栏
        sidebar_frame = ttk.Frame(main_frame, width=200)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_frame.config(style="Sidebar.TFrame")
        
        # 创建自定义样式
        self.create_styles()
        
        # 侧边栏标题
        ttk.Label(sidebar_frame, text="对话列表", style="Sidebar.TLabel").pack(pady=10, padx=10, anchor="w")
        
        # 连接按钮
        connect_button = ttk.Button(sidebar_frame, text="连接服务器", command=self.toggle_connection)
        connect_button.pack(pady=5, padx=10, fill=tk.X)
        
        # 配置按钮
        config_button = ttk.Button(sidebar_frame, text="服务器设置", command=self.show_config)
        config_button.pack(pady=5, padx=10, fill=tk.X)
        
        # 刷新群成员按钮
        refresh_members_button = ttk.Button(sidebar_frame, text="刷新群成员", command=self.refresh_group_members)
        refresh_members_button.pack(pady=5, padx=10, fill=tk.X)
        
        # 分割线
        ttk.Separator(sidebar_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # 对话列表
        self.conversation_list_frame = ttk.Frame(sidebar_frame)
        self.conversation_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建右侧聊天区域
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 聊天区域头部
        self.chat_header = ttk.Label(chat_frame, text="选择一个对话开始聊天", style="Header.TLabel")
        self.chat_header.pack(fill=tk.X, padx=10, pady=5)
        
        # 创建可嵌入图片的聊天区域
        self.chat_canvas_frame = ttk.Frame(chat_frame)
        self.chat_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Canvas作为滚动容器
        self.chat_canvas = tk.Canvas(self.chat_canvas_frame, bg=self.text_bg)
        # 设置Canvas背景色
        self.chat_canvas.configure(bg=self.text_bg)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        self.chat_scrollbar = ttk.Scrollbar(self.chat_canvas_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.config(yscrollcommand=self.chat_scrollbar.set)
        
        # 创建内容框架
        self.message_frame = ttk.Frame(self.chat_canvas)
        self.chat_canvas.create_window((0, 0), window=self.message_frame, anchor="nw")
        
        # 绑定事件更新滚动区域
        self.message_frame.bind("<Configure>", self.on_message_frame_configure)
        self.chat_canvas.bind("<Configure>", self.on_chat_canvas_configure)
        
        # 输入框和发送按钮
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=3, font=("微软雅黑", 12))
        self.input_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_text.bind("<Return>", self.send_message)
        
        send_button = ttk.Button(input_frame, text="发送", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    def create_styles(self):
        style = ttk.Style()
        style.configure("Sidebar.TFrame", background=self.sidebar_bg)
        style.configure("Sidebar.TLabel", background=self.sidebar_bg, foreground=self.sidebar_text, font=("微软雅黑", 10, "bold"))
        style.configure("Header.TLabel", background=self.header_bg, foreground=self.header_text, font=("微软雅黑", 12, "bold"))
        style.configure("MessageFrame.TFrame", background=self.message_other_bg, relief="flat", borderwidth=0)
        style.configure("SelfMessageFrame.TFrame", background=self.message_self_bg, relief="flat", borderwidth=0)
    
    def add_conversation_to_sidebar(self, conversation_id, name, avatar="👤"):
        # 创建对话项框架
        conversation_frame = ttk.Frame(self.conversation_list_frame)
        conversation_frame.pack(fill=tk.X, padx=5, pady=2)
        conversation_frame.bind("<Button-1>", lambda e, cid=conversation_id: self.select_conversation(cid))
        
        # 头像
        avatar_label = ttk.Label(conversation_frame, text=avatar, font=("微软雅黑", 14))
        avatar_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 名称
        name_label = ttk.Label(conversation_frame, text=name, font=("微软雅黑", 10))
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5, anchor="w")
        
        # 存储对话ID
        conversation_frame.conversation_id = conversation_id
    
    def on_message_frame_configure(self, event=None):
        """更新Canvas的滚动区域"""
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        
    def on_chat_canvas_configure(self, event=None):
        """当Canvas大小改变时调整内容框架宽度"""
        width = event.width
        self.chat_canvas.itemconfig(self.chat_canvas.find_all()[0], width=width)
    
    def select_conversation(self, conversation_id):
        # 更新当前选中的对话
        self.current_conversation = conversation_id
        
        # 清空聊天区域
        if conversation_id not in self.conversations:
            self.chat_header.config(text="未选择对话")
            return
        
        conv = self.conversations[conversation_id]
        self.chat_header.config(text=conv["name"])
        
        # 清空消息框架
        for widget in self.message_frame.winfo_children():
            widget.destroy()
        
        # 显示聊天记录
        for msg in conv.get("messages", []):
            self.display_message(msg["sender"], msg["content"], msg["time"], msg["is_self"])
        
        # 如果是群聊，自动获取群成员信息
        if conversation_id.startswith('group_'):
            group_id = conversation_id[6:]
            # 如果群成员信息不存在或为空，自动获取
            if group_id not in self.group_members or not self.group_members.get(group_id, {}):
                asyncio.run_coroutine_threadsafe(self.fetch_group_members(group_id), self.loop)
        
        # 滚动到底部
        self.root.after(0, lambda: self.chat_canvas.yview_moveto(1.0))
    
    def display_message(self, sender, content, time_str, is_self):
        # 创建消息容器
        message_container = ttk.Frame(self.message_frame)
        message_container.pack(fill=tk.X, padx=5, pady=5)
        
        # 发送者信息标签 - 添加日志输出
        print(f"显示消息 - 发送者: {sender}, 类型: {'自己' if is_self else '他人'}")
        sender_label = ttk.Label(message_container, text=f"{sender} {time_str}", 
                               font=("微软雅黑", 9, "italic"), foreground=self.message_time_color)
        sender_label.pack(anchor="w" if not is_self else "e", padx=10)
        
        # 创建消息内容容器
        content_frame = ttk.Frame(message_container, style="MessageFrame.TFrame" if not is_self else "SelfMessageFrame.TFrame")
        content_frame.pack(anchor="w" if not is_self else "e", padx=10, fill=tk.X)
        
        # 检查是否包含图片 - 添加更详细的日志
        image_pattern = re.compile(r'\[CQ:image,file=(.*?),url=(.*?)\]')
        image_matches = image_pattern.findall(content)
        
        if image_matches:
            print(f"检测到包含图片的消息，共{len(image_matches)}张图片")
            # 处理文本部分
            text_parts = image_pattern.split(content)
            for i, part in enumerate(text_parts):
                if part and not (i > 0 and i % 3 == 1) and not (i > 0 and i % 3 == 2):
                    # 这是文本部分
                    if part.strip():
                        text_label = ttk.Label(content_frame, text=part, font=("微软雅黑", 10), 
                                             background=self.message_other_bg if not is_self else self.message_self_bg,
                                             wraplength=400)
                        text_label.pack(anchor="w" if not is_self else "e", padx=5, pady=2)
                elif i > 0 and i % 3 == 2:
                    # 这是图片URL
                    image_url = part
                    print(f"处理图片URL: {image_url}")
                    self.display_image(content_frame, image_url, is_self)
        else:
            # 纯文本消息
            text_label = ttk.Label(content_frame, text=content, font=("微软雅黑", 10), 
                                 background=self.message_other_bg if not is_self else self.message_self_bg,
                                 wraplength=400)
            text_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
        
        # 更新滚动区域
        self.on_message_frame_configure()
        
    def display_image(self, parent_frame, image_url, is_self):
        """显示图片"""
        try:
            print(f"开始处理图片URL: {image_url}")
            # 清理URL，移除可能的转义字符并解码HTML实体
            import html
            import urllib.parse
            
            # 解码HTML实体
            image_url = html.unescape(image_url.strip())
            print(f"HTML解码后: {image_url}")
            
            # 修复URL中的常见问题
            image_url = image_url.replace('&amp;', '&')
            
            # 处理URL编码问题
            try:
                # 检查是否已经是有效的URL，尝试解码一次
                if '%' in image_url:
                    image_url = urllib.parse.unquote(image_url)
                    print(f"URL解码后: {image_url}")
            except Exception as decode_error:
                print(f"URL解码失败: {decode_error}")
            
            # 处理特殊格式的URL，如QQ图片URL末尾的file_size参数
            if ',file_size=' in image_url:
                image_url = image_url.split(',file_size=')[0]
                print(f"移除file_size参数后: {image_url}")
            
            # 确保URL格式正确
            if not image_url.startswith(('http://', 'https://', 'file:///')):
                # 尝试添加默认协议
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif '.' in image_url and ('/' in image_url or '\\' in image_url):
                    # 可能是相对路径或不完整URL，尝试添加https协议
                    image_url = 'https://' + image_url
                print(f"修正协议后: {image_url}")
            
            # 检查缓存
            if image_url in self.image_cache:
                photo = self.image_cache[image_url]
                image_label = ttk.Label(parent_frame, image=photo)
                image_label.image = photo  # 保持引用防止被垃圾回收
                image_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
                print(f"使用缓存的图片: {image_url}")
                return
            
            # 在单独的线程中加载图片
            threading.Thread(target=self._load_and_display_image, 
                           args=(parent_frame, image_url, is_self)).start()
        except Exception as e:
            print(f"显示图片失败: {e}")
            # 显示错误文本
            if parent_frame.winfo_exists():
                error_label = ttk.Label(parent_frame, text="[图片加载失败]", font=("微软雅黑", 10), foreground="red")
                error_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
    
    def _load_and_display_image(self, parent_frame, image_url, is_self):
        """在线程中加载图片"""
        try:
            print(f"尝试加载图片: {image_url}")
            
            # 处理可能的本地文件路径
            if image_url.startswith("file:///"):
                # 处理本地文件路径
                file_path = image_url[8:]  # 移除 'file:///'
                if os.path.exists(file_path):
                    # 打开本地图片
                    image = Image.open(file_path)
                else:
                    raise FileNotFoundError(f"本地图片文件不存在: {file_path}")
            else:
                # 处理CQ码图片的特殊情况
                # 对于OneBot协议，file参数可能是本地文件ID而不是URL
                # 我们可以尝试从消息中提取file参数而不是使用url
                if "file=" in image_url and ",url=" in image_url:
                    # 这可能是一个CQ码，我们提取file部分
                    file_match = re.search(r'file=([^,]+)', image_url)
                    if file_match:
                        file_id = file_match.group(1)
                        # 对于无法直接访问的URL，我们可以尝试使用本地文件或显示占位符
                        print(f"检测到CQ码图片，文件ID: {file_id}")
                        
                        # 在主线程中显示一个图片占位符
                        def show_placeholder():
                            if parent_frame.winfo_exists():
                                placeholder_label = ttk.Label(parent_frame, text=f"[图片: {file_id[:10]}...]", 
                                                          font=("微软雅黑", 10), foreground="blue")
                                placeholder_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
                                self.on_message_frame_configure()
                        
                        self.root.after(0, show_placeholder)
                        return
                
                # 下载网络图片
                # 增强HTTP请求头，特别是针对QQ图片
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'image/webp,*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Referer': 'https://im.qq.com/',  # 添加QQ相关引用来源
                    'Connection': 'keep-alive',
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache'
                }
                
                # 为QQ图片添加特定处理
                if 'qq.com' in image_url:
                    print(f"处理QQ图片URL: {image_url}")
                    # 尝试直接下载QQ图片到本地缓存
                    try:
                        # 创建本地缓存目录
                        import os
                        cache_dir = os.path.join(os.getcwd(), 'cache', 'pictures')
                        if not os.path.exists(cache_dir):
                            os.makedirs(cache_dir)
                            print(f"创建缓存目录: {cache_dir}")
                        
                        # 生成文件名（使用URL的哈希值作为文件名）
                        import hashlib
                        file_hash = hashlib.md5(image_url.encode()).hexdigest()
                        file_extension = '.jpg'  # 默认使用jpg扩展名
                        file_path = os.path.join(cache_dir, f"{file_hash}{file_extension}")
                        
                        # 检查是否已缓存
                        if os.path.exists(file_path):
                            print(f"使用缓存的本地图片: {file_path}")
                            image = Image.open(file_path)
                        else:
                            print(f"尝试下载图片到缓存: {file_path}")
                            # 增强HTTP请求头以尝试绕过QQ图片的限制
                            qq_headers = headers.copy()
                            qq_headers['Referer'] = 'https://im.qq.com/'
                            qq_headers['Origin'] = 'https://im.qq.com'
                            qq_headers['Accept-Encoding'] = 'gzip, deflate, br'
                            
                            # 下载图片
                            response = requests.get(image_url, headers=qq_headers, timeout=20, 
                                                  allow_redirects=True, stream=True)
                            response.raise_for_status()
                            
                            # 保存图片到本地
                            with open(file_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                            
                            print(f"图片保存成功: {file_path}")
                            # 打开已保存的图片
                            image = Image.open(file_path)
                        
                        # 继续处理图片（调整大小等）
                        # 注意：这里不return，让代码继续执行后面的图片处理逻辑
                    except Exception as qq_error:
                        print(f"QQ图片下载失败: {qq_error}")
                        # 如果下载失败，再显示占位符作为后备方案
                
                # 处理URL中的特殊字符
                try:
                    import urllib.parse
                    image_url = urllib.parse.unquote(image_url)
                except:
                    pass
                
                try:
                    response = requests.get(image_url, headers=headers, timeout=15, allow_redirects=True)
                    response.raise_for_status()  # 检查响应状态
                    
                    # 验证是否为图片数据
                    content_type = response.headers.get('Content-Type', '')
                    if not content_type.startswith('image/'):
                        raise ValueError(f"不是有效的图片格式: {content_type}")
                    
                    image_data = io.BytesIO(response.content)
                    # 打开图片并调整大小
                    image = Image.open(image_data)
                except Exception as inner_e:
                    print(f"下载图片失败，尝试备用方法: {inner_e}")
                    # 备用方案：显示图片URL作为文本
                    def show_url_as_text():
                        if parent_frame.winfo_exists():
                            url_label = ttk.Label(parent_frame, text=f"[图片URL: {image_url[:30]}...]", 
                                                font=("微软雅黑", 10), foreground="blue")
                            url_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
                            self.on_message_frame_configure()
                    
                    self.root.after(0, show_url_as_text)
                    return
            
            # 调整图片大小
            max_width, max_height = 300, 300
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 转换为Tkinter可用的格式
            photo = ImageTk.PhotoImage(image)
            
            # 缓存图片
            self.image_cache[image_url] = photo
            
            # 在主线程中更新UI
            def update_ui():
                 if parent_frame.winfo_exists():
                     image_label = ttk.Label(parent_frame, image=photo)
                     image_label.image = photo  # 保持引用
                     image_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
                     # 更新滚动区域
                     self.on_message_frame_configure()
            
            self.root.after(0, update_ui)
        except Exception as e:
            print(f"加载图片失败: {e}, URL: {image_url}")
            
            # 显示更详细的错误信息
            error_msg = f"[图片加载失败: {str(e)[:20]}...]"
            
            def update_error_ui():
                 # 确保parent_frame是有效的窗口对象
                 if parent_frame.winfo_exists():
                     error_label = ttk.Label(parent_frame, text=error_msg, font=("微软雅黑", 10), foreground="red")
                     error_label.pack(anchor="w" if not is_self else "e", padx=5, pady=5)
                     self.on_message_frame_configure()
            
            self.root.after(0, update_error_ui)
    
    def send_message(self, event=None):
        if not self.is_connected or not self.current_conversation:
            return
        
        content = self.input_text.get("1.0", tk.END).strip()
        if not content:
            return
        
        self.input_text.delete("1.0", tk.END)
        
        # 获取当前时间
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 显示自己发送的消息
        self.display_message("我", content, time_str, True)
        self.root.after(0, lambda: self.chat_canvas.yview_moveto(1.0))
        
        # 添加到聊天记录
        if self.current_conversation not in self.conversations:
            return
        
        if "messages" not in self.conversations[self.current_conversation]:
            self.conversations[self.current_conversation]["messages"] = []
        
        self.conversations[self.current_conversation]["messages"].append({
            "sender": "我",
            "content": content,
            "time": time_str,
            "is_self": True
        })
        
        # 保存聊天记录
        self.save_chat_history(self.current_conversation)
        
        # 发送到WebSocket
        asyncio.run_coroutine_threadsafe(self.send_websocket_message(content), self.loop)
    
    async def send_websocket_message(self, content):
        if not self.websocket or not self.is_connected:
            return
        
        try:
            # 构建OneBot11消息格式
            action = {
                "action": "send_msg",
                "params": {}
            }
            
            # 判断是群聊还是私聊
            if self.current_conversation.startswith("group_"):
                group_id = int(self.current_conversation[6:])  # 去除 "group_" 前缀
                action["params"]["group_id"] = group_id
            else:
                user_id = int(self.current_conversation)
                action["params"]["user_id"] = user_id
            
            action["params"]["message"] = content
            
            await self.websocket.send(json.dumps(action))
        except Exception as e:
            print(f"发送消息失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"发送消息失败: {str(e)}"))
    
    def show_config(self):
        dialog = ConfigDialog(self.root, self.config)
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.config = dialog.result
            self.save_config()
    
    def toggle_connection(self):
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
    
    async def connect(self):
        try:
            self.is_connected = True
            self.root.after(0, lambda: self.chat_header.config(text="正在连接服务器..."))
            
            uri = self.config["websocket_server"]
            if self.config["token"]:
                uri += f"?access_token={self.config['token']}"
            
            self.websocket = await websockets.connect(uri)
            self.root.after(0, lambda: self.chat_header.config(text="已连接到服务器"))
            
            # 开始监听消息
            self.loop.create_task(self.listen_messages())
            
            # 发送认证请求
            await self.websocket.send(json.dumps({
                "action": "verify",
                "params": {
                    "access_token": self.config["token"]
                }
            }))
            
            # 等待一小段时间确保认证完成
            await asyncio.sleep(1)
            
            # 自动获取会话列表
            await self.fetch_conversations()
            
        except Exception as e:
            self.is_connected = False
            print(f"连接失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"连接服务器失败: {str(e)}"))
            self.root.after(0, lambda: self.chat_header.config(text="连接失败"))
    
    async def disconnect(self):
        try:
            if self.websocket:
                await self.websocket.close()
            self.is_connected = False
            self.root.after(0, lambda: self.chat_header.config(text="已断开连接"))
        except Exception as e:
            print(f"断开连接失败: {e}")
    
    async def listen_messages(self):
        try:
            while self.is_connected and self.websocket:
                message = await self.websocket.recv()
                self.handle_message(message)
        except Exception as e:
            print(f"监听消息失败: {e}")
            self.is_connected = False
            self.root.after(0, lambda: self.chat_header.config(text="连接已断开"))
            
            # 尝试重连
            if self.config.get("auto_reconnect", True):
                self.root.after(5000, lambda: asyncio.run_coroutine_threadsafe(self.connect(), self.loop))
    
    def handle_message(self, message):
        try:
            data = json.loads(message)
            
            # 处理消息事件
            if "message_type" in data and data["message_type"] in ["private", "group"]:
                self.process_chat_message(data)
            
            # 处理API调用结果
            elif "status" in data and "data" in data:
                self.process_api_response(data)
                
        except Exception as e:
            print(f"处理消息失败: {e}")
    
    def process_chat_message(self, data):
        # 获取消息内容和发送者信息
        message_id = data.get("message_id")
        message = data.get("raw_message", "")
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        if data["message_type"] == "private":
            # 私聊消息
            user_id = str(data.get("user_id"))
            nickname = self.get_user_nickname(user_id)
            conversation_id = user_id
            avatar = "👤"
        else:
            # 群聊消息
            group_id = str(data.get("group_id"))
            user_id = str(data.get("user_id"))
            print(f"处理群聊消息: group_id={group_id}, user_id={user_id}")
            
            # 优先从data.sender获取昵称信息（最高优先级）
            nickname = ""
            if "sender" in data and isinstance(data["sender"], dict):
                nickname = data["sender"].get("card", data["sender"].get("nickname", ""))
                print(f"优先从sender获取的昵称: {nickname}")
            
            # 如果从sender获取不到昵称或为空，尝试从群成员缓存获取
            if not nickname:
                nickname = self.get_group_member_nickname(group_id, user_id)
                print(f"通过get_group_member_nickname获取的昵称: {nickname}")
            
            # 确保昵称不为空
            if not nickname or nickname.startswith("群成员"):
                # 如果还是默认昵称，设置一个更好的默认值
                nickname = f"群成员{user_id[:4]}...{user_id[-2:]}" if len(user_id) > 6 else f"群成员{user_id}"
                print(f"使用默认昵称: {nickname}")
            
            # 如果群成员信息不存在或为空，自动获取
            if group_id not in self.group_members or not self.group_members.get(group_id, {}).get(user_id):
                print(f"群成员信息不存在，获取群{group_id}成员信息")
                # 异步获取群成员信息，但不阻塞当前消息处理
                asyncio.run_coroutine_threadsafe(self.fetch_group_members(group_id), self.loop)
            conversation_id = f"group_{group_id}"
            avatar = "👥"
        
        # 确保对话存在
        if conversation_id not in self.conversations:
            if data["message_type"] == "private":
                name = nickname
            else:
                name = self.get_group_name(group_id)
            
            self.conversations[conversation_id] = {
                "id": conversation_id,
                "name": name,
                "avatar": avatar,
                "messages": []
            }
            self.root.after(0, lambda: self.add_conversation_to_sidebar(conversation_id, name, avatar))
        
        # 添加消息
        self.conversations[conversation_id]["messages"].append({
            "sender": nickname,
            "content": message,
            "time": time_str,
            "is_self": False
        })
        
        # 保存聊天记录
        self.save_chat_history(conversation_id)
        
        # 如果当前正在查看此对话，显示消息
        if self.current_conversation == conversation_id:
            self.root.after(0, lambda: self.display_message(nickname, message, time_str, False))
            self.root.after(0, lambda: self.chat_canvas.yview_moveto(1.0))
            
    def get_group_member_nickname(self, group_id, user_id):
        """获取群成员昵称"""
        print(f"获取群成员昵称 - group_id: {group_id}, user_id: {user_id}")
        # 首先尝试从群成员缓存获取
        if group_id in self.group_members:
            print(f"  群成员信息存在，共有{len(self.group_members[group_id])}个成员")
            if user_id in self.group_members[group_id]:
                member_info = self.group_members[group_id][user_id]
                # 获取card（群名片）和nickname（昵称），并确保不为空
                card = member_info.get("card", "")
                nickname = member_info.get("nickname", "")
                
                # 优先使用非空的群名片，其次是昵称
                if card.strip():
                    print(f"  使用群名片: {card}")
                    return card.strip()
                elif nickname.strip():
                    print(f"  使用昵称: {nickname}")
                    return nickname.strip()
                else:
                    print(f"  群名片和昵称都为空")
            else:
                print(f"  用户{user_id}不在群{group_id}的成员列表中")
        else:
            print(f"  群{group_id}的成员信息不存在")
        
        # 如果没有获取到有效的昵称，返回格式化的用户ID
        formatted_user_id = f"群成员{user_id[:4]}...{user_id[-2:]}" if len(user_id) > 6 else f"群成员{user_id}"
        print(f"  返回格式化用户ID: {formatted_user_id}")
        return formatted_user_id
    
    def refresh_group_members(self):
        """刷新当前选中群的成员信息"""
        if not self.current_conversation or not self.current_conversation.startswith("group_"):
            messagebox.showinfo("提示", "请先选择一个群聊")
            return
        
        group_id = self.current_conversation[6:]  # 去除"group_"前缀
        asyncio.run_coroutine_threadsafe(self.fetch_group_members(group_id), self.loop)
    
    async def fetch_group_members(self, group_id):
        """获取群成员列表"""
        if not self.websocket or not self.is_connected:
            return
        
        try:
            print(f"开始获取群{group_id}的成员列表")
            # 发送获取群成员列表请求
            await self.websocket.send(json.dumps({
                "action": "get_group_member_list",
                "params": {
                    "group_id": int(group_id)
                }
            }))
            
            # 更新状态
            self.root.after(0, lambda: messagebox.showinfo("提示", "正在获取群成员列表..."))
        except Exception as e:
            print(f"获取群成员列表失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"获取群成员列表失败: {str(e)}"))
            
    async def fetch_conversations(self):
        """连接成功后获取会话列表"""
        if not self.websocket or not self.is_connected:
            return
        
        try:
            # 获取好友列表
            await self.websocket.send(json.dumps({
                "action": "get_friend_list",
                "params": {}
            }))
            
            # 等待一小段时间
            await asyncio.sleep(0.5)
            
            # 获取群列表
            await self.websocket.send(json.dumps({
                "action": "get_group_list",
                "params": {}
            }))
            
        except Exception as e:
            print(f"获取会话列表失败: {e}")
            self.root.after(0, lambda: messagebox.showinfo("提示", "获取会话列表失败，但不影响基本功能"))
    
    def process_api_response(self, data):
        """处理API调用结果"""
        # 处理好友列表
        if "data" in data and isinstance(data["data"], list) and data["data"]:
            # 判断是好友列表还是群列表还是群成员列表
            first_item = data["data"][0]
            if "user_id" in first_item and "nickname" in first_item and "group_id" not in first_item:
                # 好友列表
                for friend in data["data"]:
                    user_id = str(friend["user_id"])
                    nickname = friend["nickname"]
                    conversation_id = user_id
                    
                    if conversation_id not in self.conversations:
                        self.conversations[conversation_id] = {
                            "id": conversation_id,
                            "name": nickname,
                            "avatar": "👤",
                            "messages": []
                        }
                        self.root.after(0, lambda cid=conversation_id, name=nickname: 
                                      self.add_conversation_to_sidebar(cid, name, "👤"))
                    else:
                        # 更新名称
                        self.conversations[conversation_id]["name"] = nickname
            
            elif "group_id" in first_item and "group_name" in first_item and "user_id" not in first_item:
                # 群列表
                for group in data["data"]:
                    group_id = str(group["group_id"])
                    group_name = group["group_name"]
                    conversation_id = f"group_{group_id}"
                    
                    if conversation_id not in self.conversations:
                        self.conversations[conversation_id] = {
                            "id": conversation_id,
                            "name": group_name,
                            "avatar": "👥",
                            "messages": []
                        }
                        self.root.after(0, lambda cid=conversation_id, name=group_name: 
                                      self.add_conversation_to_sidebar(cid, name, "👥"))
                    else:
                        # 更新名称
                        self.conversations[conversation_id]["name"] = group_name
            
            elif "group_id" in first_item and "user_id" in first_item and "nickname" in first_item:
                # 群成员列表
                group_id = str(first_item["group_id"])
                self.group_members[group_id] = {}
                
                for member in data["data"]:
                    user_id = str(member["user_id"])
                    self.group_members[group_id][user_id] = {
                        "nickname": member.get("nickname", ""),
                        "card": member.get("card", ""),  # 群名片
                        "role": member.get("role", "member")
                    }
                
                # 如果当前正在查看这个群，重新显示消息以更新昵称
                if self.current_conversation == f"group_{group_id}":
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"群成员列表更新成功，共{len(data['data'])}人"))
                    # 重新加载消息以显示正确的昵称
                    self.root.after(0, lambda: self.select_conversation(self.current_conversation))
    
    def get_user_nickname(self, user_id):
        """获取用户昵称"""
        if user_id in self.conversations:
            return self.conversations[user_id]["name"]
        return f"用户{user_id}"
    
    def get_group_name(self, group_id):
        """获取群组名称"""
        conversation_id = f"group_{group_id}"
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]["name"]
        return f"群组{group_id}"
    
    def run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

class ConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, config):
        self.config = config.copy()
        self.result = None
        super().__init__(parent, title="服务器设置")
    
    def body(self, master):
        ttk.Label(master, text="WebSocket服务器地址:").grid(row=0, sticky=tk.W, pady=5)
        ttk.Label(master, text="访问令牌:").grid(row=1, sticky=tk.W, pady=5)
        
        self.server_entry = ttk.Entry(master, width=40)
        self.server_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        self.server_entry.insert(0, self.config.get("websocket_server", "ws://localhost:8080"))
        
        self.token_entry = ttk.Entry(master, width=40)
        self.token_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        self.token_entry.insert(0, self.config.get("token", ""))
        
        self.auto_reconnect_var = tk.BooleanVar(value=self.config.get("auto_reconnect", True))
        self.auto_reconnect_check = ttk.Checkbutton(master, text="自动重连", variable=self.auto_reconnect_var)
        self.auto_reconnect_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        return self.server_entry
    
    def apply(self):
        self.result = {
            "websocket_server": self.server_entry.get(),
            "token": self.token_entry.get(),
            "auto_reconnect": self.auto_reconnect_var.get()
        }

if __name__ == "__main__":
    root = tk.Tk()
    app = OneBotClient(root)
    root.mainloop()