import sys
import os
import import_modules  # 导入所有必要的模块
from PyQt5.QtWidgets import QApplication
from main import PatentBrowser

if __name__ == '__main__':
    # 确保工作目录正确
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    window = PatentBrowser()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())