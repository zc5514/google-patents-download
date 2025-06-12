# 显式导入所有需要的模块，确保打包时包含它们
try:
    import sys
    import os
    import json
    import time
    import logging
    import requests

    # Selenium 相关导入
    import selenium
    import selenium.webdriver
    import selenium.webdriver.chrome
    import selenium.webdriver.chrome.service
    from selenium.webdriver.chrome.service import Service
    import selenium.webdriver.chrome.options
    from selenium.webdriver.chrome.options import Options
    import selenium.webdriver.common.by
    from selenium.webdriver.common.by import By
    import selenium.webdriver.support.ui
    from selenium.webdriver.support.ui import WebDriverWait
    import selenium.webdriver.support.expected_conditions
    from selenium.webdriver.support import expected_conditions as EC
    
    # webdriver_manager 相关导入
    import webdriver_manager
    import webdriver_manager.chrome
    from webdriver_manager.chrome import ChromeDriverManager

    # PyQt5 相关导入
    import PyQt5
    import PyQt5.QtWidgets
    import PyQt5.QtCore
    import PyQt5.QtGui
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *

    #print("所有模块导入成功！")
except ImportError as e:
    print(f"导入错误: {e}")