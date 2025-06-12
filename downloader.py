import os
import time
import requests
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PyQt5.QtCore import QThread, pyqtSignal

class PatentDownloader(QThread):
    status_update = pyqtSignal(str)
    failed_patent = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    log_entry = pyqtSignal(str, str, int)
    success_patent = pyqtSignal(str)  # 添加新信号，用于通知成功下载的专利号
    
    def __init__(self, patents, config):
        super().__init__()
        self.patents = patents
        self.config = config
        self.is_running = True
        self.driver = None
        self.total_patents = len(patents)
        self.processed_patents = 0
        self.download_history = self.load_download_history()
        
        # 配置日志 - 将日志级别转换为英文
        log_level_map = {
            "调试": "DEBUG",
            "信息": "INFO",
            "警告": "WARNING",
            "错误": "ERROR",
            "严重": "CRITICAL"
        }
        
        # 获取配置中的日志级别，如果是中文则转换为英文
        config_log_level = self.config.get("log_level", "信息")
        log_level = log_level_map.get(config_log_level, config_log_level)
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=os.path.join(self.config.get("download_dir"), "patent_downloader.log"),
            filemode='a'
        )
        self.logger = logging.getLogger("PatentDownloader")
    
    def load_download_history(self):
        """加载下载历史记录，用于断点续传"""
        history_file = os.path.join(self.config.get("download_dir"), "download_history.json")
        try:
            if os.path.exists(history_file):
                import json
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"加载下载历史失败: {str(e)}")
            return {}
    
    def save_download_history(self):
        """保存下载历史记录"""
        history_file = os.path.join(self.config.get("download_dir"), "download_history.json")
        try:
            import json
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.error(f"保存下载历史失败: {str(e)}")
    
    def run(self):
        try:
            chrome_options = Options()
            if self.config.get("proxy"):
                chrome_options.add_argument(f'--proxy-server={self.config.get("proxy")}')
            
            # 添加无头模式选项，提高性能
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36')
            
            # 内存优化
            chrome_options.add_argument('--js-flags=--expose-gc')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-translate')
            
            self.status_update.emit("正在启动浏览器...")
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                                        options=chrome_options)
            
            for patent in self.patents:
                if not self.is_running:
                    break
                    
                patent = patent.strip()
                if not patent:
                    self.processed_patents += 1
                    self.update_progress()
                    continue
                
                # 断点续传检查
                if patent in self.download_history and os.path.exists(os.path.join(self.config.get("download_dir"), f"{patent}.pdf")):
                    self.status_update.emit(f"跳过已下载: {patent}")
                    self.processed_patents += 1
                    self.update_progress()
                    continue
                    
                self.status_update.emit(f"正在检索: {patent}")
                
                # 尝试通过搜索页面查找专利
                success = self.search_and_download_patent(patent)
                
                if not success:
                    self.failed_patent.emit(patent)
                else:
                    # 记录成功下载的专利
                    self.download_history[patent] = {
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "success"
                    }
                    self.save_download_history()
                
                self.processed_patents += 1
                self.update_progress()
                
                # 内存管理 - 定期清理
                if self.processed_patents % 10 == 0:
                    self.driver.execute_script("window.gc();")
                
            self.status_update.emit("检索完成")
            
        except Exception as e:
            error_msg = f"发生错误: {str(e)}"
            self.status_update.emit(error_msg)
            self.logger.error(error_msg)
        finally:
            if self.driver:
                self.driver.quit()
            self.save_download_history()

    def search_and_download_patent(self, patent):
        """搜索并下载专利PDF"""
        try:
            # 检查文件是否已存在
            file_path = os.path.join(self.config.get("download_dir"), f"{patent}.pdf")
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                self.status_update.emit(f"文件已存在: {patent}")
                self.log_entry.emit(patent, f"{patent}.pdf", 0)  # 策略0表示文件已存在
                if hasattr(self, 'success_patent'):
                    self.success_patent.emit(patent)
                return True
                
            # 尝试所有策略
            strategies = [
                self.test_strategy1,
                self.test_strategy2,
                self.test_strategy3,
                self.test_strategy4,
                self.test_strategy5
            ]
            
            for i, strategy in enumerate(strategies, 1):
                if not self.is_running:
                    return False
                    
                retry_count = 0
                max_retries = self.config.get("retry_count", 3)
                
                while retry_count < max_retries:
                    try:
                        success, pdf_url = strategy(patent)
                        if success:
                            if self.download_pdf(pdf_url, patent):
                                self.log_entry.emit(patent, f"{patent}.pdf", i)
                                self.success_patent.emit(patent)  # 发送成功信号
                                return True
                            break  # 如果下载失败，尝试下一个策略
                        break  # 如果策略失败，尝试下一个策略
                    except Exception as e:
                        retry_count += 1
                        error_msg = f"策略{i}尝试{retry_count}/{max_retries}失败: {str(e)}"
                        self.logger.warning(error_msg)
                        self.status_update.emit(error_msg)
                        time.sleep(2)  # 短暂等待后重试
            
            return False
                
        except Exception as e:
            error_msg = f"搜索专利时出错: {str(e)}"
            self.status_update.emit(error_msg)
            self.logger.error(error_msg)
            return False

    def download_pdf(self, pdf_url, patent_id):
        """下载PDF文件，支持断点续传"""
        file_path = os.path.join(self.config.get("download_dir"), f"{patent_id}.pdf")
        temp_file_path = f"{file_path}.tmp"
        
        # 检查是否已存在临时文件，用于断点续传
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 设置代理
        proxies = {}
        if self.config.get("proxy"):
            proxies = {
                "http": f"http://{self.config.get('proxy')}",
                "https": f"http://{self.config.get('proxy')}"
            }
        
        try:
            # 获取文件大小
            file_size = 0
            if os.path.exists(temp_file_path) and self.config.get("resume_download", True):
                file_size = os.path.getsize(temp_file_path)
                headers['Range'] = f'bytes={file_size}-'
                self.status_update.emit(f"断点续传: {patent_id} 从 {file_size} 字节开始")
            
            # 先发送HEAD请求获取文件总大小
            head_response = requests.head(pdf_url, headers=headers, proxies=proxies, timeout=self.config.get("timeout", 30))
            total_size = int(head_response.headers.get('content-length', 0))
            
            # 下载文件
            response = requests.get(
                pdf_url, 
                headers=headers, 
                proxies=proxies, 
                stream=True, 
                timeout=self.config.get("timeout", 30)
            )
            
            # 处理断点续传的响应
            if file_size > 0 and response.status_code == 206:  # 部分内容
                mode = 'ab'  # 追加二进制模式
                self.status_update.emit(f"断点续传中: {patent_id}")
            elif response.status_code == 200:  # 完整内容
                mode = 'wb'  # 写入二进制模式
                self.status_update.emit(f"开始下载: {patent_id}")
            else:
                self.status_update.emit(f"下载失败 HTTP {response.status_code}: {patent_id}")
                return False
            
            # 写入文件
            chunk_size = self.config.get("chunk_size", 8192)
            downloaded = file_size
            start_time = time.time()
            last_update_time = start_time
            
            with open(temp_file_path, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not self.is_running:
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 每秒更新一次下载进度
                        current_time = time.time()
                        if current_time - last_update_time > 1:
                            if total_size > 0:
                                progress = int(downloaded / total_size * 100)
                                speed = downloaded / (current_time - start_time) / 1024  # KB/s
                                self.status_update.emit(f"下载中: {patent_id} - {progress}% ({speed:.1f} KB/s)")
                            last_update_time = current_time
            
            # 下载完成后重命名文件
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_file_path, file_path)
            
            self.status_update.emit(f"已下载: {patent_id}")
            return True
            
        except requests.exceptions.Timeout:
            self.status_update.emit(f"下载超时: {patent_id}")
            self.logger.warning(f"下载超时: {patent_id}")
            return False
        except requests.exceptions.ConnectionError:
            self.status_update.emit(f"网络连接错误: {patent_id}")
            self.logger.warning(f"网络连接错误: {patent_id}")
            return False
        except Exception as e:
            self.status_update.emit(f"下载错误: {str(e)}")
            self.logger.error(f"下载错误: {str(e)}")
            return False

    def update_progress(self):
        progress = int((self.processed_patents / self.total_patents) * 100)
        self.progress_update.emit(progress)

    def stop(self):
        self.is_running = False
        if self.driver:
            self.driver.quit()
    
    # 以下是各种检索策略
    def test_strategy1(self, patent):
        """策略1：使用组合选择器定位"""
        try:
            search_url = f"https://patents.google.com/?q=({patent})"
            self.driver.get(search_url)
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(self.config.get("delay", 5))
            
            pdf_link = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "search-result-item a[href*='patentimages.storage.googleapis.com']"))
            )
            if pdf_link:
                pdf_url = pdf_link.get_attribute("href")
                if pdf_url:
                    return True, pdf_url
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略1失败: {str(e)}")
            return False, None

    def test_strategy2(self, patent):
        """策略2：从页面源码提取PDF链接"""
        try:
            search_url = f"https://patents.google.com/?q=({patent})"
            self.driver.get(search_url)
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(self.config.get("delay", 5))
            
            page_source = self.driver.page_source
            pdf_url_match = re.search(r'href="(https://patentimages\.storage\.googleapis\.com/[^"]+\.pdf)"', page_source)
            if pdf_url_match:
                return True, pdf_url_match.group(1)
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略2失败: {str(e)}")
            return False, None

    def test_strategy3(self, patent):
        """策略3：使用精确的CSS选择器定位PDF元素"""
        try:
            search_url = f"https://patents.google.com/?q=({patent})"
            self.driver.get(search_url)
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(self.config.get("delay", 5))
            
            pdf_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-proto='OPEN_PATENT_PDF']"))
            )
            if pdf_element:
                parent_element = pdf_element.find_element(By.XPATH, "./..")
                if parent_element:
                    pdf_url = parent_element.get_attribute("href")
                    if pdf_url:
                        return True, pdf_url
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略3失败: {str(e)}")
            return False, None

    def test_strategy4(self, patent):
        """策略4：使用XPath定位PDF元素"""
        try:
            search_url = f"https://patents.google.com/?q=({patent})"
            self.driver.get(search_url)
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(self.config.get("delay", 5))
            
            pdf_elements = self.driver.find_elements(By.XPATH, "//span[@data-proto='OPEN_PATENT_PDF']")
            if pdf_elements:
                parent_element = pdf_elements[0].find_element(By.XPATH, "./..")
                if parent_element:
                    pdf_url = parent_element.get_attribute("href")
                    if pdf_url:
                        return True, pdf_url
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略4失败: {str(e)}")
            return False, None

    def test_strategy5(self, patent):
        """策略5：直接访问专利页面"""
        try:
            patent_page_url = f"https://patents.google.com/patent/{patent}"
            self.driver.get(patent_page_url)
            time.sleep(self.config.get("delay", 5))
            
            pdf_link = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-tip='Download PDF']"))
            )
            if pdf_link:
                pdf_url = pdf_link.get_attribute("href")
                if pdf_url:
                    return True, pdf_url
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略5失败: {str(e)}")
            return False, None
    def test_strategy6(self, patent):
        """策略6：使用多种选择器组合尝试"""
        try:
            # 直接访问专利页面
            patent_page_url = f"https://patents.google.com/patent/{patent}/en"
            self.driver.get(patent_page_url)
            
            # 等待页面加载
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(self.config.get("delay", 5))
            
            # 尝试多种选择器
            selectors = [
                "a[data-tip='Download PDF']",
                "a[href*='patentimages.storage.googleapis.com']",
                "a.download-pdf",
                "//a[contains(@href, '.pdf')]",
                "//a[contains(text(), 'PDF')]"
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        # XPath选择器
                        pdf_link = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                    else:
                        # CSS选择器
                        pdf_link = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                    
                    if pdf_link:
                        pdf_url = pdf_link.get_attribute("href")
                        if pdf_url and ".pdf" in pdf_url:
                            self.logger.info(f"策略6成功 (选择器: {selector}): {patent}")
                            return True, pdf_url
                except Exception:
                    continue
            
            return False, None
        except Exception as e:
            self.logger.debug(f"策略6失败: {str(e)}")

def init_browser(self):
    """初始化浏览器"""
    try:
        # 设置Chrome选项
        chrome_options = Options()
        if not self.config.get("show_browser", False):
            chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        
        # 设置下载选项
        prefs = {
            "download.default_directory": self.config.get("download_dir"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 设置代理
        if self.config.get("proxy"):
            chrome_options.add_argument(f"--proxy-server={self.config.get('proxy')}")
        
        # 尝试使用绿色版ChromeDriver
        try:
            # 获取应用程序运行路径
            if getattr(sys, 'frozen', False):
                # 如果是打包后的应用
                application_path = os.path.dirname(sys.executable)
            else:
                # 如果是开发环境
                application_path = os.path.dirname(os.path.abspath(__file__))
            
            # 查找ChromeDriver路径
            chromedriver_path = None
            
            # 首先检查chromedriver-win32目录
            chrome_dir = os.path.join(application_path, "chromedriver")
            if os.path.exists(chrome_dir):
                for root, dirs, files in os.walk(chrome_dir):
                    for file in files:
                        if file.lower() == "chromedriver.exe":
                            chromedriver_path = os.path.join(root, file)
                            break
                    if chromedriver_path:
                        break
            
            # 如果没找到，检查应用程序根目录
            if not chromedriver_path:
                if os.path.exists(os.path.join(application_path, "chromedriver.exe")):
                    chromedriver_path = os.path.join(application_path, "chromedriver.exe")
            
            if chromedriver_path:
                self.status_update.emit(f"使用本地ChromeDriver: {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # 如果找不到本地ChromeDriver，尝试使用webdriver_manager
                self.status_update.emit("未找到本地ChromeDriver，尝试使用webdriver_manager")
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        except Exception as e:
            self.status_update.emit(f"ChromeDriver初始化失败: {str(e)}")
            # 最后尝试不指定路径，使用系统默认的ChromeDriver
            self.driver = webdriver.Chrome(options=chrome_options)
        
        # 设置超时
        self.driver.set_page_load_timeout(self.config.get("timeout", 30))
        self.driver.implicitly_wait(10)
        
        return True
    except Exception as e:
        error_msg = f"初始化浏览器失败: {str(e)}"
        self.status_update.emit(error_msg)
        self.logger.error(error_msg)
        return False

# ... 现有代码 ...