import sys
import os
import json
import logging
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QTextEdit, QPushButton, QLabel, 
                           QLineEdit, QSpinBox, QFileDialog, QProgressBar,
                           QTabWidget, QCheckBox, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt, QSettings
from config import Config
from downloader import PatentDownloader

class PatentBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        # 加载配置
        self.config = Config()
        
        # 设置日志
        self.setup_logging()
        
        # 设置UI
        self.setup_ui()
        
        # 加载保存的状态
        self.load_state()
        
        self.browser_thread = None
        self.driver = None
        
        # 创建下载目录
        os.makedirs(self.download_dir_input.text(), exist_ok=True)
    
    def setup_logging(self):
        """设置日志系统"""
        # 日志级别映射
        log_level_map = {
            "调试": "DEBUG",
            "信息": "INFO",
            "警告": "WARNING",
            "错误": "ERROR",
            "严重": "CRITICAL"
        }
        
        # 获取配置中的日志级别，如果是中文则转换为英文
        config_log_level = self.config.get("log_level", "信息")
        english_level = log_level_map.get(config_log_level, config_log_level)
        
        log_dir = self.config.get("download_dir", os.path.join(os.getcwd(), "downloads"))
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, english_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=os.path.join(log_dir, "patent_downloader.log"),
            filemode='a'
        )
        self.logger = logging.getLogger("PatentBrowser")
    
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("专利批量下载工具")
        self.setGeometry(100, 100, 800, 700)  # 调整窗口大小
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局为水平布局
        main_layout = QHBoxLayout()
        
        # 左侧面板 - 包含输入和未检索到的专利
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # 待检索专利号输入框
        input_group = QWidget()
        input_layout = QVBoxLayout()
        
        # 添加导入文件按钮
        import_layout = QHBoxLayout()
        self.patent_count_label = QLabel("待检索专利号: (0个)")
        import_button = QPushButton("导入文件")
        import_button.clicked.connect(self.import_patents_from_file)
        import_layout.addWidget(self.patent_count_label)
        import_layout.addWidget(import_button)
        input_layout.addLayout(import_layout)
        
        self.patent_input = QTextEdit()
        self.patent_input.setPlaceholderText("请输入待检索的专利号，每行一个")
        self.patent_input.textChanged.connect(self.update_patent_count)
        input_layout.addWidget(self.patent_input)
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group, 1)  # 分配更多空间给输入框
        
        # 未检索到的专利号显示框
        failed_group = QWidget()
        failed_layout = QVBoxLayout()
        
        # 添加导出失败专利按钮
        failed_header_layout = QHBoxLayout()
        self.failed_count_label = QLabel("未检索到的专利号: (0个)")
        export_failed_button = QPushButton("导出失败专利")
        export_failed_button.clicked.connect(self.export_failed_patents)
        failed_header_layout.addWidget(self.failed_count_label)
        failed_header_layout.addWidget(export_failed_button)
        failed_layout.addLayout(failed_header_layout)
        
        self.failed_patents = QTextEdit()
        #self.failed_patents.setReadOnly(True)
        failed_layout.addWidget(self.failed_patents)
        failed_group.setLayout(failed_layout)
        left_layout.addWidget(failed_group, 1)  # 分配较少空间给未检索专利
        
        left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel, 1)  # 左侧面板占用较多空间
        
        # 右侧面板 - 包含日志和控制面板
        right_panel = QTabWidget()
        
        # 日志标签页
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        
        # 日志工具栏
        log_toolbar = QHBoxLayout()
        clear_log_button = QPushButton("清除日志")
        clear_log_button.clicked.connect(self.clear_log)
        export_log_button = QPushButton("导出日志")
        export_log_button.clicked.connect(self.export_log)
        log_toolbar.addWidget(clear_log_button)
        log_toolbar.addWidget(export_log_button)
        log_toolbar.addStretch()
        log_layout.addLayout(log_toolbar)
        
        # 日志显示
        self.log_display = QTextEdit()
        #self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        log_tab.setLayout(log_layout)
        
        # 设置标签页
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        
        # 下载目录设置
        download_dir_layout = QHBoxLayout()
        self.download_dir_input = QLineEdit()
        #self.download_dir_input.setReadOnly(True)
        self.download_dir_input.setText(self.config.get("download_dir", os.path.join(os.getcwd(), "downloads")))
        download_dir_button = QPushButton("选择目录")
        download_dir_button.clicked.connect(self.select_download_dir)
        download_dir_layout.addWidget(QLabel("下载目录:"))
        download_dir_layout.addWidget(self.download_dir_input)
        download_dir_layout.addWidget(download_dir_button)
        settings_layout.addLayout(download_dir_layout)
        
        # 代理设置
        proxy_layout = QHBoxLayout()
        self.proxy_input = QLineEdit()
        self.proxy_input.setText(self.config.get("proxy", "127.0.0.1:7890"))
        self.proxy_input.setPlaceholderText("代理地址 (例如: 127.0.0.1:7890)")
        proxy_layout.addWidget(QLabel("代理设置:"))
        proxy_layout.addWidget(self.proxy_input)
        settings_layout.addLayout(proxy_layout)
        
        # 延时设置
        delay_layout = QHBoxLayout()
        self.delay_input = QSpinBox()
        self.delay_input.setRange(1, 60)
        self.delay_input.setValue(self.config.get("delay", 5))
        delay_layout.addWidget(QLabel("检索延时(秒):"))
        delay_layout.addWidget(self.delay_input)
        settings_layout.addLayout(delay_layout)
        
        # 超时设置
        timeout_layout = QHBoxLayout()
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(5, 120)
        self.timeout_input.setValue(self.config.get("timeout", 30))
        timeout_layout.addWidget(QLabel("下载超时(秒):"))
        timeout_layout.addWidget(self.timeout_input)
        settings_layout.addLayout(timeout_layout)
        
        # 重试次数设置
        retry_layout = QHBoxLayout()
        self.retry_input = QSpinBox()
        self.retry_input.setRange(0, 10)
        self.retry_input.setValue(self.config.get("retry_count", 3))
        retry_layout.addWidget(QLabel("重试次数:"))
        retry_layout.addWidget(self.retry_input)
        settings_layout.addLayout(retry_layout)
        
        # 日志级别选择
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("日志级别:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["调试", "信息", "警告", "错误", "严重"])
        self.log_level_combo.setCurrentText(self.config.get("log_level", "信息"))
        log_level_layout.addWidget(self.log_level_combo)
        settings_layout.addLayout(log_level_layout)
        
        # 断点续传选项
        self.resume_checkbox = QCheckBox("启用断点续传")
        self.resume_checkbox.setChecked(self.config.get("resume_download", True))
        settings_layout.addWidget(self.resume_checkbox)
        
        # 保存设置按钮
        save_settings_button = QPushButton("保存设置")
        save_settings_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(save_settings_button)
        
        # 添加控制面板到设置页面
        settings_layout.addWidget(QLabel("下载控制:"))
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        settings_layout.addWidget(QLabel("下载进度:"))
        settings_layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("浏览器状态: 未启动")
        settings_layout.addWidget(self.status_label)
        
        # 开始检索按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始检索")
        self.start_button.clicked.connect(self.start_search)
        button_layout.addWidget(self.start_button)
        
        # 继续检索按钮
        self.resume_button = QPushButton("继续检索")
        self.resume_button.clicked.connect(self.resume_search)
        self.resume_button.setEnabled(False)
        button_layout.addWidget(self.resume_button)
        
        settings_layout.addLayout(button_layout)
        
        settings_layout.addStretch()
        settings_tab.setLayout(settings_layout)
        
        # 添加标签页
        right_panel.addTab(settings_tab, "功能区")
        right_panel.addTab(log_tab, "日志区")
        right_panel.setCurrentIndex(0) 
        
        # 创建垂直布局来放置右侧面板
        right_container = QWidget()
        right_container_layout = QVBoxLayout()
        right_container_layout.addWidget(right_panel)
        right_container.setLayout(right_container_layout)
        
        main_layout.addWidget(right_container, 3)
        
        main_widget.setLayout(main_layout)
    
    def load_state(self):
        """加载上次会话的状态"""
        settings = QSettings("PatentDownloader", "PatentBrowser")
        
        # 加载上次输入的专利号
        patents = settings.value("patents", "")
        self.patent_input.setText(patents)
        
        # 加载上次的失败专利
        failed_patents = settings.value("failed_patents", "")
        self.failed_patents.setText(failed_patents)
        self.update_failed_count()
    
    def save_state(self):
        """保存当前会话状态"""
        settings = QSettings("PatentDownloader", "PatentBrowser")
        
        # 保存当前输入的专利号
        settings.setValue("patents", self.patent_input.toPlainText())
        
        # 保存当前的失败专利
        settings.setValue("failed_patents", self.failed_patents.toPlainText())
    
    def save_settings(self):
        """保存设置"""
        # 更新配置
        self.config.set("download_dir", self.download_dir_input.text())
        self.config.set("proxy", self.proxy_input.text())
        self.config.set("delay", self.delay_input.value())
        self.config.set("timeout", self.timeout_input.value())
        self.config.set("retry_count", self.retry_input.value())
        self.config.set("resume_download", self.resume_checkbox.isChecked())
        self.config.set("log_level", self.log_level_combo.currentText())
        
        QMessageBox.information(self, "设置保存", "设置已成功保存")
        
        # 更新日志级别 - 添加中文到英文的映射
        log_level_map = {
            "调试": "DEBUG",
            "信息": "INFO",
            "警告": "WARNING",
            "错误": "ERROR",
            "严重": "CRITICAL"
        }
        
        # 获取当前日志级别并转换
        current_level = self.config.get("log_level", "信息")
        english_level = log_level_map.get(current_level, current_level)
        
        # 设置日志级别
        logging.getLogger().setLevel(getattr(logging, english_level))
      

    def update_patent_count(self):
        # 更新待检索专利数量
        patents = [p for p in self.patent_input.toPlainText().strip().split('\n') if p]
        self.patent_count_label.setText(f"待检索专利号: ({len(patents)}个)")

    def update_failed_count(self):
        # 更新未检索到的专利数量
        failed = [p for p in self.failed_patents.toPlainText().strip().split('\n') if p]
        self.failed_count_label.setText(f"未检索到的专利号: ({len(failed)}个)")

    def add_log_entry(self, patent, filename, strategy_num):
        # 添加日志记录
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] 专利号: {patent} | 文件名: {filename} | 策略{strategy_num}成功"
        current_text = self.log_display.toPlainText()
        if current_text:
            self.log_display.setText(f"{current_text}\n{log_entry}")
        else:
            self.log_display.setText(log_entry)
        # 滚动到底部
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
        
        # 同时写入日志文件
        self.logger.info(f"专利号: {patent} | 文件名: {filename} | 策略{strategy_num}成功")  # 修复了缺少的右括号

    def add_failed_patent(self, patent):
        current_text = self.failed_patents.toPlainText()
        if current_text:
            self.failed_patents.setText(f"{current_text}\n{patent}")
        else:
            self.failed_patents.setText(patent)
        self.update_failed_count()
        
        # 记录到日志
        self.logger.warning(f"未找到专利: {patent}")

    def select_download_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", self.download_dir_input.text())
        if dir_path:
            self.download_dir_input.setText(dir_path)
            os.makedirs(dir_path, exist_ok=True)

    def start_search(self):
        if self.start_button.text() == "开始检索":
            patents = self.patent_input.toPlainText().strip().split('\n')
            if not patents or not patents[0]:
                self.status_label.setText("请输入专利号")
                return
            
            # 更新配置
            self.config.set("download_dir", self.download_dir_input.text())
            self.config.set("proxy", self.proxy_input.text())
            self.config.set("delay", self.delay_input.value())
            self.config.set("timeout", self.timeout_input.value())
            self.config.set("retry_count", self.retry_input.value())
            self.config.set("resume_download", self.resume_checkbox.isChecked())
            
            self.start_button.setText("停止检索")
            self.resume_button.setEnabled(False)
            self.patent_input.setReadOnly(True)
            self.progress_bar.setValue(0)
            self.failed_patents.clear()  # 清空未检索到的专利号
            
            # 保存原始专利列表，用于后续移除
            self.original_patents = patents.copy()
            
            self.browser_thread = PatentDownloader(patents, self.config)
            self.browser_thread.status_update.connect(self.update_status)
            self.browser_thread.failed_patent.connect(self.add_failed_patent)
            self.browser_thread.progress_update.connect(self.update_progress)
            self.browser_thread.finished.connect(self.search_finished)
            self.browser_thread.log_entry.connect(self.add_log_entry)
            self.browser_thread.success_patent.connect(self.remove_success_patent)  # 连接新信号
            self.browser_thread.start()
        else:
            if self.browser_thread:
                self.browser_thread.stop()
            self.search_finished()
    # 添加新方法，用于移除成功下载的专利号
    def remove_success_patent(self, patent):
        """从待检索区移除成功下载的专利号"""
        current_patents = self.patent_input.toPlainText().strip().split('\n')
        if patent in current_patents:
            current_patents.remove(patent)
            self.patent_input.setText('\n'.join(current_patents))
            self.update_patent_count()
            self.logger.info(f"已从待检索区移除专利: {patent}")
    def resume_search(self):
        """继续检索失败的专利"""
        failed_patents = [p for p in self.failed_patents.toPlainText().strip().split('\n') if p]
        if not failed_patents:
            self.status_label.setText("没有失败的专利需要重新检索")
            return
        
        # 将失败的专利设置为待检索专利
        self.patent_input.setText("\n".join(failed_patents))
        self.failed_patents.clear()
        self.update_failed_count()
        
        # 开始检索
        self.start_search()

    def update_status(self, status):
        self.status_label.setText(status)
        self.logger.info(status)

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def search_finished(self):
        self.start_button.setText("开始检索")
        self.patent_input.setReadOnly(False)
        self.status_label.setText("检索已完成")
        
        # 如果有失败的专利，启用继续检索按钮
        failed_patents = self.failed_patents.toPlainText().strip()
        self.resume_button.setEnabled(bool(failed_patents))
        
        # 保存当前状态
        self.save_state()

    def import_patents_from_file(self):
        """从文件导入专利号"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择专利号文件", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    patents = f.read().strip()
                
                current_patents = self.patent_input.toPlainText().strip()
                if current_patents:
                    self.patent_input.setText(f"{current_patents}\n{patents}")
                else:
                    self.patent_input.setText(patents)
                
                self.logger.info(f"从文件导入专利号: {file_path}")
                QMessageBox.information(self, "导入成功", f"成功从文件导入专利号")
            except Exception as e:
                error_msg = f"导入文件失败: {str(e)}"
                self.logger.error(error_msg)
                QMessageBox.critical(self, "导入失败", error_msg)

    def export_failed_patents(self):
        """导出失败的专利号到文件"""
        failed_patents = self.failed_patents.toPlainText().strip()
        if not failed_patents:
            QMessageBox.information(self, "导出失败专利", "没有失败的专利需要导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存失败专利号", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(failed_patents)
                
                self.logger.info(f"导出失败专利号到文件: {file_path}")
                QMessageBox.information(self, "导出成功", f"成功导出失败专利号到文件")
            except Exception as e:
                error_msg = f"导出文件失败: {str(e)}"
                self.logger.error(error_msg)
                QMessageBox.critical(self, "导出失败", error_msg)

    def clear_log(self):
        """清除日志显示"""
        self.log_display.clear()

    def export_log(self):
        """导出日志到文件"""
        log_text = self.log_display.toPlainText().strip()
        if not log_text:
            QMessageBox.information(self, "导出日志", "没有日志需要导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_text)
                
                self.logger.info(f"导出日志到文件: {file_path}")
                QMessageBox.information(self, "导出成功", f"成功导出日志到文件")
            except Exception as e:
                error_msg = f"导出文件失败: {str(e)}"
                self.logger.error(error_msg)
                QMessageBox.critical(self, "导出失败", error_msg)

    def closeEvent(self, event):
        """关闭窗口事件处理"""
        if self.browser_thread and self.browser_thread.isRunning():
            reply = QMessageBox.question(
                self, '确认退出', 
                "检索任务正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.browser_thread.stop()
                # 等待线程结束
                if not self.browser_thread.wait(3000):  # 等待3秒
                    self.browser_thread.terminate()
            else:
                event.ignore()
                return
        
        # 保存当前状态
        self.save_state()
        
        # 确保日志正确关闭
        logging.shutdown()
        
        event.accept()