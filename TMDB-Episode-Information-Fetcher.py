from PyQt6 import QtWidgets
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QComboBox, QMessageBox, QFileDialog, 
    QInputDialog, QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
import sys
import os
import logging
import traceback
import requests

def resource_path(relative_path):
    """ 获取资源的绝对路径 """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 设置日志记录
def setup_logging():
    log_file = 'app.log'
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# 异常处理装饰器
def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            logging.error(traceback.format_exc())
            # 如果是主窗口，显示错误消息
            if hasattr(args[0], 'show'):
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    args[0],
                    '错误',
                    f'发生错误：{str(e)}',
                    QMessageBox.StandardButton.Ok
                )
    return wrapper

def get_api_key_path():
    """ 获取 API key 文件的路径 """
    try:
        # 获取程序所在目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的 exe
            base_path = os.path.dirname(sys.executable)
        else:
            # 如果是 Python 脚本
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        return os.path.join(base_path, 'api_key.txt')
    except Exception as e:
        logging.error(f"Error getting API key path: {str(e)}")
        # 如果出错，返回当前目录
        return 'api_key.txt'

class FetchEpisodesThread(QThread):
    update_results = pyqtSignal(list)  # 更新结果信号

    def __init__(self, show_name, language, api_key):
        super().__init__()
        self.show_name = show_name
        self.language = language
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.session = None  # 延迟初始化 session
        
    def run(self):
        logging.info(f"Starting fetch thread for show: {self.show_name}")
        import requests  # 在线程中导入 requests
        self.session = requests.Session()
        try:
            episodes = self.get_show_episodes()
            logging.info(f"Found {len(episodes)} seasons")
            self.update_results.emit(episodes)
        except Exception as e:
            logging.error(f"Error in fetch thread: {str(e)}")
            logging.error(traceback.format_exc())
        finally:
            self.session.close()
            logging.info("Fetch thread completed")

    def get_show_episodes(self):
        search_url = f"{self.base_url}/search/tv"
        params = {
            'api_key': self.api_key,
            'query': self.show_name,
            'language': self.language
        }
        
        logging.info(f"Searching for show: {self.show_name} in language: {self.language}")
        try:
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()

            if 'results' in data and data['results']:
                show_id = data['results'][0]['id']
                show_name = data['results'][0]['name']
                logging.info(f"Found show: {show_name} (ID: {show_id})")
                return self.fetch_season_episodes(show_id)
            
            logging.warning(f"No results found for: {self.show_name}")
            return []

        except requests.RequestException as e:
            logging.error(f"Network error in get_show_episodes: {str(e)}")
            return []

    def fetch_season_episodes(self, show_id):
        seasons_url = f"{self.base_url}/tv/{show_id}"
        params = {
            'api_key': self.api_key,
            'language': self.language
        }
        
        logging.info(f"Fetching seasons for show ID: {show_id}")
        try:
            seasons_response = self.session.get(seasons_url, params=params)
            seasons_response.raise_for_status()
            seasons_data = seasons_response.json()
            
            if 'seasons' in seasons_data:
                all_episodes = []
                total_seasons = len(seasons_data['seasons'])
                logging.info(f"Found {total_seasons} seasons")
                
                for i, season in enumerate(seasons_data['seasons'], 1):
                    season_number = season['season_number']
                    season_name = season['name']
                    logging.info(f"Fetching episodes for season {season_number} ({i}/{total_seasons})")
                    
                    episodes_url = f"{self.base_url}/tv/{show_id}/season/{season_number}"
                    episodes_response = self.session.get(episodes_url, params=params)
                    episodes_response.raise_for_status()
                    episodes_data = episodes_response.json()
                    
                    episode_count = len(episodes_data['episodes'])
                    logging.info(f"Found {episode_count} episodes in season {season_number}")
                    
                    season_episodes = [episode['name'] for episode in episodes_data['episodes']]
                    all_episodes.append(f"第{season_number}季——{season_name}：\n" + "\n".join(season_episodes))

                return all_episodes
            
            logging.warning(f"No seasons found for show ID: {show_id}")
            return []

        except requests.RequestException as e:
            logging.error(f"Network error while fetching seasons: {str(e)}")
            return []

class ShowEpisodesApp(QWidget):
    def __init__(self):
        try:
            super().__init__()
            logging.info("Initializing main window")
            # 从资源路径加载图标
            icon_path = resource_path('logo.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            self.is_dark_mode = False
            self.setup_delayed_init()
        except Exception as e:
            logging.error(f"Error in initialization: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    @exception_handler
    def setup_delayed_init(self):
        logging.info("Starting delayed initialization")
        try:
            logging.info("Loading API key...")
            self.api_key = self.load_api_key()
            if not self.api_key:
                logging.info("No API key found, requesting from user...")
                self.api_key = self.get_api_key()
            
            logging.info("Initializing UI...")
            self.initUI()
            
            logging.info("Setting up styles...")
            self.setup_styles()
            
            self.episodes_window = None
            self.fetch_thread = None
            logging.info("Delayed initialization completed successfully")
        except Exception as e:
            logging.error(f"Error during delayed initialization: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    def setup_styles(self):
        logging.info(f"Setting up styles (Dark mode: {self.is_dark_mode})")
        try:
            if self.is_dark_mode:
                self.setStyleSheet("""
                    QWidget {
                        background-color: #1e1e1e;
                        font-family: 'Microsoft YaHei', Arial;
                        color: #e0e0e0;
                    }
                    QLabel {
                        background-color: transparent;
                        color: #e0e0e0;
                    }
                    QLineEdit {
                        padding: 8px 15px;
                        border: 1px solid #383838;
                        border-radius: 6px;
                        background-color: #2d2d2d;
                        font-size: 14px;
                        min-height: 20px;
                        color: #e0e0e0;
                    }
                    QLineEdit::placeholder {
                        color: #888;
                    }
                    QLineEdit:focus {
                        border-color: #1890ff;
                        background-color: #323232;
                    }
                    QPushButton {
                        background-color: #1890ff;
                        color: white;
                        padding: 8px 15px;
                        border: none;
                        border-radius: 6px;
                        font-size: 14px;
                        min-width: 120px;
                        min-height: 35px;
                    }
                    QPushButton:hover {
                        background-color: #40a9ff;
                    }
                    QPushButton:pressed {
                        background-color: #096dd9;
                    }
                    QPushButton#themeButton {
                        background-color: transparent;
                        border: 1px solid #1890ff;
                        min-width: 40px;
                        max-width: 40px;
                        min-height: 40px;
                        max-height: 40px;
                        border-radius: 20px;
                        color: #1890ff;
                    }
                    QPushButton#themeButton:hover {
                        background-color: rgba(24, 144, 255, 0.1);
                    }
                    QComboBox {
                        padding: 8px 15px;
                        border: 1px solid #383838;
                        border-radius: 6px;
                        background-color: #2d2d2d;
                        min-width: 150px;
                        min-height: 20px;
                        color: #e0e0e0;
                        font-size: 14px;
                    }
                    QComboBox:hover {
                        border-color: #1890ff;
                        background-color: #323232;
                    }
                    QComboBox::drop-down {
                        border: none;
                        width: 20px;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-style: solid;
                        border-width: 5px;
                        border-color: #888 transparent transparent transparent;
                    }
                    QComboBox::down-arrow:hover {
                        border-color: #1890ff transparent transparent transparent;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #2d2d2d;
                        border: 1px solid #383838;
                        border-radius: 6px;
                        padding: 5px;
                        outline: none;
                        selection-background-color: #323232;
                    }
                    QComboBox QAbstractItemView::item {
                        height: 35px;
                        padding: 5px 15px;
                        border: none;
                        color: #e0e0e0;
                    }
                    QComboBox QAbstractItemView::item:hover {
                        background-color: #383838;
                        border-radius: 4px;
                    }
                    QComboBox QAbstractItemView::item:selected {
                        background-color: #404040;
                        color: #1890ff;
                        border-radius: 4px;
                    }
                    QFrame#contentFrame {
                        background-color: #2d2d2d;
                        border: 1px solid #383838;
                        border-radius: 8px;
                    }
                    QLabel {
                        color: #e0e0e0;
                    }
                    QLabel#titleLabel {
                        color: #1890ff;
                        font-size: 24px;
                        font-weight: bold;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QWidget {
                        background-color: white;
                        font-family: 'Microsoft YaHei', Arial;
                    }
                    QLabel {
                        background-color: transparent;
                        color: #333;
                    }
                    QLineEdit {
                        padding: 8px 15px;
                        border: 1px solid #d9d9d9;
                        border-radius: 6px;
                        background-color: white;
                        font-size: 14px;
                        min-height: 20px;
                        color: #333;
                    }
                    QLineEdit::placeholder {
                        color: #999;
                    }
                    QLineEdit:focus {
                        border-color: #1890ff;
                    }
                    QPushButton {
                        background-color: #1890ff;
                        color: white;
                        padding: 8px 15px;
                        border: none;
                        border-radius: 6px;
                        font-size: 14px;
                        min-width: 120px;
                        min-height: 35px;
                    }
                    QPushButton:hover {
                        background-color: #40a9ff;
                    }
                    QPushButton:pressed {
                        background-color: #096dd9;
                    }
                    QPushButton#themeButton {
                        background-color: transparent;
                        border: 1px solid #1890ff;
                        min-width: 40px;
                        max-width: 40px;
                        min-height: 40px;
                        max-height: 40px;
                        border-radius: 20px;
                        color: #1890ff;
                    }
                    QPushButton#themeButton:hover {
                        background-color: rgba(24, 144, 255, 0.1);
                    }
                    QComboBox {
                        padding: 8px 15px;
                        border: 1px solid #d9d9d9;
                        border-radius: 6px;
                        background-color: white;
                        min-width: 150px;
                        min-height: 20px;
                        color: #333;
                        font-size: 14px;
                    }
                    QComboBox:hover {
                        border-color: #1890ff;
                    }
                    QComboBox::drop-down {
                        border: none;
                        width: 20px;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-style: solid;
                        border-width: 5px;
                        border-color: #666 transparent transparent transparent;
                    }
                    QComboBox QAbstractItemView {
                        background-color: white;
                        border: 1px solid #d9d9d9;
                        border-radius: 6px;
                        padding: 5px;
                        outline: none;
                        color: #333;
                    }
                    QComboBox QAbstractItemView::item {
                        height: 35px;
                        padding: 5px 15px;
                        border: none;
                        color: #333;
                    }
                    QComboBox QAbstractItemView::item:hover {
                        background-color: #f5f5f5;
                        border-radius: 4px;
                        color: #333;
                    }
                    QComboBox QAbstractItemView::item:selected {
                        background-color: #e6f7ff;
                        color: #1890ff;
                        border-radius: 4px;
                    }
                    QFrame#contentFrame {
                        background-color: white;
                        border: 1px solid #e8e8e8;
                        border-radius: 8px;
                    }
                    QLabel#titleLabel {
                        color: #1890ff;
                        font-size: 24px;
                        font-weight: bold;
                    }
                """)
            logging.info("Styles setup completed")
        except Exception as e:
            logging.error(f"Error during style setup: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    def initUI(self):
        logging.info("Starting UI initialization")
        try:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(20)
            main_layout.setContentsMargins(30, 30, 30, 30)

            # 添加顶部布局用于放置标题和主题切换按钮
            top_layout = QHBoxLayout()

            # 标题
            title_label = QLabel("TMDB剧集查询工具", self)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("""
                font-size: 24px;
                color: #0078d4;
                font-weight: bold;
                margin: 10px 0;
            """)
            
            # 主题切换按钮
            self.theme_button = QPushButton("🌙" if not self.is_dark_mode else "☀️", self)
            self.theme_button.setObjectName("themeButton")
            self.theme_button.clicked.connect(self.toggle_theme)
            self.theme_button.setToolTip("切换主题模式")

            top_layout.addWidget(title_label)
            top_layout.addWidget(self.theme_button)
            main_layout.addLayout(top_layout)

            # 输入区域
            input_frame = QFrame()
            input_frame.setObjectName("contentFrame")
            input_layout = QVBoxLayout(input_frame)
            input_layout.setSpacing(15)
            input_layout.setContentsMargins(20, 20, 20, 20)

            # 剧集名称输入
            name_layout = QHBoxLayout()
            name_label = QLabel("剧集名称：")
            self.show_name_input = QLineEdit()
            self.show_name_input.setPlaceholderText("请输入要查询的剧集名称")
            name_layout.addWidget(name_label)
            name_layout.addWidget(self.show_name_input)
            input_layout.addLayout(name_layout)

            # 语言选择
            language_layout = QHBoxLayout()
            language_label = QLabel("选择语言：")
            self.language_selector = QComboBox()
            self.language_codes = {
                "简体中文": "zh-CN",
                "English": "en-US",
                "Español": "es-ES",
                "Français": "fr-FR"
            }
            self.language_selector.addItems(list(self.language_codes.keys()))
            self.language_selector.setFixedWidth(200)  # 设置固定宽度
            language_layout.addWidget(language_label)
            language_layout.addWidget(self.language_selector)
            language_layout.addStretch()  # 添加弹性空间
            input_layout.addLayout(language_layout)

            main_layout.addWidget(input_frame)

            # 当前剧集显示
            self.current_show_label = QLabel("当前剧集名称")
            self.current_show_label.setStyleSheet("padding: 10px 0;")
            main_layout.addWidget(self.current_show_label)

            # 查询按钮
            button_layout = QHBoxLayout()
            self.search_button = QPushButton("查询剧集名称")
            self.search_button.setFixedHeight(40)
            button_layout.addStretch()
            button_layout.addWidget(self.search_button)
            button_layout.addStretch()
            main_layout.addLayout(button_layout)

            self.search_button.clicked.connect(self.on_search)

            # 设置窗口
            self.setLayout(main_layout)
            self.setWindowTitle("TMDB剧集查询工具")
            self.setMinimumWidth(600)
            self.setMinimumHeight(450)
            self.center_window()
            logging.info("UI initialization completed")
        except Exception as e:
            logging.error(f"Error during UI initialization: {str(e)}")
            logging.error(traceback.format_exc())
            raise

    def center_window(self):
        # 将窗口居中显示
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def load_api_key(self):
        api_key_file = get_api_key_path()
        logging.info(f"Checking for API key file: {api_key_file}")
        if os.path.exists(api_key_file):
            try:
                with open(api_key_file, 'r', encoding='utf-8') as f:
                    api_key = f.readline().strip()
                    logging.info("API key loaded successfully")
                    return api_key
            except Exception as e:
                logging.error(f"Error reading API key file: {str(e)}")
                return None
        logging.info("API key file not found")
        return None

    def get_api_key(self):
        logging.info("Requesting API key from user")
        api_key, ok = QInputDialog.getText(self, '输入API密钥', '请输入您的TMDB API密钥:')
        if ok and api_key:
            try:
                # 保存到当前目录
                api_key_file = get_api_key_path()
                with open(api_key_file, 'w', encoding='utf-8') as f:
                    f.write(api_key)
                logging.info(f"API key saved to: {api_key_file}")
                return api_key
            except Exception as e:
                logging.error(f"Error saving API key: {str(e)}")
                # 即使保存失败也返回 API key
                return api_key
        logging.info("User cancelled API key input")
        return None

    def on_search(self):
        show_name = self.show_name_input.text()
        selected_language = self.language_selector.currentText()
        language_code = self.language_codes[selected_language]
        
        logging.info(f"Starting search for show: {show_name}")
        logging.info(f"Selected language: {selected_language} ({language_code})")
        
        if not show_name:
            logging.warning("Empty show name")
            QMessageBox.warning(self, '警告', '请输入剧集名称')
            return
            
        self.current_show_label.setText(f"当前剧集名称：{show_name}")
        logging.info("Starting fetch thread")
        
        # 开始线程来获取剧集名称
        self.fetch_thread = FetchEpisodesThread(show_name, language_code, self.api_key)
        self.fetch_thread.update_results.connect(self.open_episodes_window)
        self.fetch_thread.start()

    def open_episodes_window(self, episodes):
        logging.info(f"Opening episodes window with {len(episodes)} seasons")
        self.episodes_window = EpisodesWindow(episodes, self.is_dark_mode)
        self.episodes_window.show()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.theme_button.setText("☀️" if self.is_dark_mode else "🌙")
        self.setup_styles()
        # 如果有打开的剧集窗口，也需要更新其主题
        if hasattr(self, 'episodes_window') and self.episodes_window is not None:
            self.episodes_window.is_dark_mode = self.is_dark_mode
            self.episodes_window.setup_styles()

class EpisodesWindow(QWidget):
    def __init__(self, episodes, is_dark_mode=False):
        super().__init__()
        # 从资源路径加载图标
        icon_path = resource_path('logo.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.episodes = episodes
        self.is_dark_mode = is_dark_mode
        self.initUI()
        self.setup_styles()

    def setup_styles(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
                QWidget {
                    background-color: #1e1e1e;
                    font-family: 'Microsoft YaHei', Arial;
                }
                QLabel#titleLabel {
                    font-size: 24px;
                    color: #1890ff;
                    font-weight: bold;
                    padding: 20px;
                }
                QTextEdit {
                    border: none;
                    background-color: #2d2d2d;
                    font-size: 14px;
                    color: #e0e0e0;
                    line-height: 1.6;
                    padding: 10px;
                    selection-background-color: #404040;
                    selection-color: #ffffff;
                }
                QTextEdit QScrollBar:vertical {
                    width: 8px;
                    background: transparent;
                }
                QTextEdit QScrollBar::handle:vertical {
                    background: #404040;
                    border-radius: 4px;
                    min-height: 30px;
                }
                QTextEdit QScrollBar::handle:vertical:hover {
                    background: #4a4a4a;
                }
                QTextEdit QScrollBar::add-line:vertical,
                QTextEdit QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QTextEdit QScrollBar::add-page:vertical,
                QTextEdit QScrollBar::sub-page:vertical {
                    background: none;
                }
                QPushButton {
                    background-color: #1890ff;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 6px;
                    font-size: 15px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #40a9ff;
                }
                QPushButton:pressed {
                    background-color: #096dd9;
                }
                #contentFrame {
                    background-color: #2d2d2d;
                    border: 1px solid #383838;
                    border-radius: 8px;
                }
            """)
        else:
            # 原有的浅色主题样式
            self.setStyleSheet("""
                QWidget {
                    background-color: #f0f2f5;
                    font-family: 'Microsoft YaHei', Arial;
                }
                QLabel#titleLabel {
                    font-size: 28px;
                    color: #1a1a1a;
                    font-weight: bold;
                    padding: 20px;
                    background: transparent;
                }
                QTextEdit {
                    border: none;
                    background-color: white;
                    font-size: 14px;
                    color: #333;
                    line-height: 1.6;
                    selection-background-color: #e3f2fd;
                    selection-color: #1a1a1a;
                }
                QTextEdit QScrollBar:vertical {
                    width: 8px;
                    background: transparent;
                }
                QTextEdit QScrollBar::handle:vertical {
                    background: #d0d0d0;
                    border-radius: 4px;
                    min-height: 30px;
                }
                QTextEdit QScrollBar::handle:vertical:hover {
                    background: #a8a8a8;
                }
                QTextEdit QScrollBar::add-line:vertical,
                QTextEdit QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QTextEdit QScrollBar::add-page:vertical,
                QTextEdit QScrollBar::sub-page:vertical {
                    background: none;
                }
                QPushButton {
                    background-color: #1890ff;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 6px;
                    font-size: 15px;
                    font-weight: 500;
                    min-width: 160px;
                }
                QPushButton:hover {
                    background-color: #40a9ff;
                }
                QPushButton:pressed {
                    background-color: #096dd9;
                }
                #contentFrame {
                    background-color: white;
                    border-radius: 12px;
                    border: 1px solid #e8e8e8;
                }
                #seasonTitle {
                    font-size: 18px;
                    color: #1890ff;
                    font-weight: bold;
                    margin-top: 15px;
                    margin-bottom: 10px;
                }
                #episodeItem {
                    color: #333;
                    padding: 8px 0;
                    border-bottom: 1px solid #f0f0f0;
                }
            """)

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(40, 20, 40, 30)

        # 标题
        title_label = QLabel("剧集列表", self)
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 内容框架
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(25, 25, 25, 25)

        # 文本显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(400)
        content_layout.addWidget(self.text_edit)

        if self.episodes:
            formatted_text = ""
            for i, episode in enumerate(self.episodes):
                if i > 0:
                    formatted_text += "\n\n" + "─" * 80 + "\n\n"
                # 分离季标题和剧集列表
                season_parts = episode.split('：\n', 1)
                if len(season_parts) == 2:
                    season_title, episodes_list = season_parts
                    # 根据主题模式设置不同的颜色
                    title_color = "#e0e0e0" if self.is_dark_mode else "#1890ff"
                    text_color = "#e0e0e0" if self.is_dark_mode else "#333"
                    border_color = "#383838" if self.is_dark_mode else "#f0f0f0"
                    
                    formatted_text += f"<div style='color: {title_color}; font-size: 18px; font-weight: bold; margin: 10px 0;'>{season_title}：</div>\n"
                    episodes = episodes_list.split('\n')
                    for ep in episodes:
                        formatted_text += f"<div style='color: {text_color}; padding: 8px 0; border-bottom: 1px solid {border_color};'>{ep}</div>\n"
                else:
                    formatted_text += episode

            self.text_edit.setHtml(formatted_text)

        main_layout.addWidget(content_frame)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 20, 0, 0)
        self.export_button = QPushButton("导出剧集名称")
        self.export_button.setFixedHeight(45)
        self.export_button.setFixedWidth(160)
        self.export_button.clicked.connect(self.export_to_txt)
        button_layout.addStretch()
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("剧集名称")
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        self.center_window()

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )

    def export_to_txt(self):
        if not self.episodes:
            logging.warning("No episodes to export")
            QMessageBox.warning(self, '警告', '没有可导出的剧集名称。')
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self, 
            "保存剧集名称", 
            "", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_name:
            logging.info(f"Exporting episodes to: {file_name}")
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    for episode in self.episodes:
                        f.write(episode + '\n')
                logging.info("Export completed successfully")
                QMessageBox.information(
                    self, 
                    '导出成功', 
                    '剧集名称已成功导出为TXT文件。'
                )
            except Exception as e:
                logging.error(f"Export failed: {str(e)}")
                logging.error(traceback.format_exc())
                QMessageBox.critical(
                    self, 
                    '导出失败', 
                    f'导出过程中发生错误：{str(e)}'
                )
        else:
            logging.info("Export cancelled by user")

if __name__ == "__main__":
    try:
        # 设置高 DPI 支持
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"

        setup_logging()
        logging.info("Application starting")
        
        # 创建应用实例
        app = QApplication(sys.argv)
        logging.info("QApplication created")
        
        # 设置应用程序信息
        app.setApplicationName("TMDB剧集查询工具")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("Your Company")
        logging.info("Application info set")
        
        # 设置样式表
        app.setStyle("Fusion")
        logging.info("Style set to Fusion")
        
        # 从资源路径加载图标
        try:
            icon_path = resource_path('logo.ico')
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                app.setWindowIcon(app_icon)
                logging.info(f"Icon loaded from: {icon_path}")
            else:
                logging.warning(f"Icon file not found at: {icon_path}")
        except Exception as e:
            logging.error(f"Error loading icon: {str(e)}")
        
        # 创建并显示主窗口
        try:
            logging.info("Creating main window")
            main_window = ShowEpisodesApp()
            main_window.setWindowState(Qt.WindowState.WindowActive)  # 设置窗口为活动状态
            main_window.show()
            logging.info("Main window show() called")
            
            # 强制窗口显示在前台
            main_window.raise_()
            main_window.activateWindow()
            main_window.setWindowState(Qt.WindowState.WindowActive)
            logging.info("Window raised and activated")
            
            # 处理所有待处理的事件
            app.processEvents()
            
            # 进入事件循环
            logging.info("Entering event loop")
            return_code = app.exec()
            logging.info(f"Application exited with code: {return_code}")
            sys.exit(return_code)
            
        except Exception as e:
            logging.critical(f"Error creating/showing main window: {str(e)}")
            logging.critical(traceback.format_exc())
            QMessageBox.critical(
                None,
                '严重错误',
                f'窗口创建失败：{str(e)}',
                QMessageBox.StandardButton.Ok
            )
            sys.exit(1)
            
    except Exception as e:
        logging.critical(f"Critical error during startup: {str(e)}")
        logging.critical(traceback.format_exc())
        try:
            QMessageBox.critical(
                None,
                '严重错误',
                f'程序启动失败：{str(e)}',
                QMessageBox.StandardButton.Ok
            )
        except:
            print(f"Fatal error: {str(e)}")
        sys.exit(1)
