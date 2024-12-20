import requests
import os
import sys
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QMessageBox, QFileDialog, QInputDialog, QTextEdit
)
from PyQt6.QtCore import QThread, pyqtSignal

API_KEY_FILE = 'api_key.txt'  # 用于存储API密钥的文件

class FetchEpisodesThread(QThread):
    update_results = pyqtSignal(list)  # 更新结果信号

    def __init__(self, show_name, language, api_key):
        super().__init__()
        self.show_name = show_name
        self.language = language
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def run(self):
        episodes = self.get_show_episodes()
        self.update_results.emit(episodes)

    def get_show_episodes(self):
        search_url = f"{self.base_url}/search/tv?api_key={self.api_key}&query={self.show_name}&language={self.language}"
        
        try:
            response = requests.get(search_url)
            response.raise_for_status()  # 确保请求成功
            data = response.json()

            if 'results' in data and data['results']:
                show_id = data['results'][0]['id']
                return self.fetch_season_episodes(show_id)
            
            return []  # No results found

        except requests.RequestException as e:
            print(f"Network error: {e}")
            return []  # Return empty list on failure

    def fetch_season_episodes(self, show_id):
        seasons_url = f"{self.base_url}/tv/{show_id}?api_key={self.api_key}&language={self.language}"
        try:
            seasons_response = requests.get(seasons_url)
            seasons_response.raise_for_status()
            seasons_data = seasons_response.json()
            
            if 'seasons' in seasons_data:
                all_episodes = []
                for season in seasons_data['seasons']:
                    season_number = season['season_number']
                    season_name = season['name']
                    episodes_url = f"{self.base_url}/tv/{show_id}/season/{season_number}?api_key={self.api_key}&language={self.language}"
                    episodes_response = requests.get(episodes_url)
                    episodes_response.raise_for_status()
                    episodes_data = episodes_response.json()
                    
                    season_episodes = [episode['name'] for episode in episodes_data['episodes']]
                    all_episodes.append(f"第{season_number}季——{season_name}：\n" + "\n".join(season_episodes))

                return all_episodes
            
            return []  # No seasons found

        except requests.RequestException as e:
            print(f"Network error while fetching seasons: {e}")
            return []  # Return empty list on failure

class ShowEpisodesApp(QtWidgets.QWidget):  # 使用 QWidget 作为基础类
    def __init__(self):
        super().__init__()
        self.api_key = self.load_api_key()  # 加载 API 密钥
        if not self.api_key:
            self.api_key = self.get_api_key()  # 提示用户输入 API 密钥
        self.initUI()  # 初始化 UI

    def load_api_key(self):
        if os.path.exists(API_KEY_FILE):
            with open(API_KEY_FILE, 'r') as f:
                return f.readline().strip()  # 返回去除空格和换行的内容
        return None  # 文件不存在，返回 None

    def get_api_key(self):
        api_key, ok = QInputDialog.getText(self, '输入API密钥', '请输入您的TMDB API密钥:')
        if ok and api_key:
            with open(API_KEY_FILE, 'w') as f:
                f.write(api_key)  # 将 API 密钥写入文件
            return api_key  # 返回用户输入的 API 密钥
        return None  # 未提供 API 密钥

    def initUI(self):
        layout = QVBoxLayout()  # 创建垂直布局

        # 输入剧集名称的文本框
        self.show_name_input = QLineEdit(self)
        self.show_name_input.setPlaceholderText("输入剧集名称")
        layout.addWidget(self.show_name_input)

        # 用于显示当前剧集名称的标签
        self.current_show_label = QLabel("当前剧集名称：", self)
        layout.addWidget(self.current_show_label)

        # 语言选择下拉框
        self.language_selector = QComboBox(self)
        self.language_selector.addItems(["zh-CN", "en-US", "es-ES", "fr-FR"])  # 可以根据需要添加其他语言
        layout.addWidget(self.language_selector)

        # 查询按钮
        self.search_button = QPushButton("获取剧集名称", self)
        self.search_button.clicked.connect(self.on_search)  # 连接按钮点击事件
        layout.addWidget(self.search_button)

        self.setLayout(layout)  # 设置窗口布局
        self.setWindowTitle("TMDB剧集查询工具")  # 设置窗口标题

    def on_search(self):
        show_name = self.show_name_input.text()  # 获取输入的剧集名称
        language = self.language_selector.currentText()  # 获取选择的语言
        self.current_show_label.setText(f"当前剧集名称：{show_name}")  # 更新标签显示当前剧集名称

        # 开始线程来获取剧集名称
        self.fetch_thread = FetchEpisodesThread(show_name, language, self.api_key)  # 传递 API 密钥
        self.fetch_thread.update_results.connect(self.open_episodes_window)  # 连接结果更新信号
        self.fetch_thread.start()  # 启动线程

    def open_episodes_window(self, episodes):
        self.episodes_window = EpisodesWindow(episodes)  # 创建新窗口实例
        self.episodes_window.show()  # 显示新窗口

class EpisodesWindow(QtWidgets.QWidget):
    def __init__(self, episodes):
        super().__init__()
        self.episodes = episodes
        self.initUI()  # 确保调用 initUI 方法

    def initUI(self):
        layout = QVBoxLayout()  # 创建垂直布局

        # 创建文本编辑器来显示剧集名称
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)  # 设置为只读
        layout.addWidget(self.text_edit)

        # 显示剧集名称
        if self.episodes:
            self.text_edit.setText("\n\n".join(self.episodes))  # 使用换行分隔每一季的内容

        # 导出按钮
        self.export_button = QPushButton("导出剧集名称为TXT", self)
        self.export_button.clicked.connect(self.export_to_txt)
        layout.addWidget(self.export_button)

        self.setLayout(layout)  # 设置布局
        self.setWindowTitle("剧集名称")  # 设置窗口标题

    def export_to_txt(self):
        if self.episodes:
            file_name, _ = QFileDialog.getSaveFileName(self, "保存剧集名称", "", "Text Files (*.txt);;All Files (*)")
            if file_name:
                with open(file_name, 'w', encoding='utf-8') as f:
                    for episode in self.episodes:
                        f.write(episode + '\n')
                QMessageBox.information(self, '成功', '剧集名称已导出为TXT文件。')
        else:
            QMessageBox.warning(self, '警告', '没有可导出的剧集名称。')

if __name__ == "__main__":
    app = QApplication(sys.argv)  # 创建 QApplication 实例
    ex = ShowEpisodesApp()  # 创建主窗口实例
    ex.show()  # 显示主窗口
    sys.exit(app.exec())  # 执行应用程序并等待退出