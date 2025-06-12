import os
import json
import logging
from pathlib import Path

class Config:
    """配置管理类"""
    DEFAULT_CONFIG = {
        "download_dir": "",
        "proxy": "127.0.0.1:7890",
        "delay": 5,
        "timeout": 30,
        "retry_count": 3,
        "chunk_size": 8192,
        "log_level": "INFO"
    }
    
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        
    def load_config(self):
        """加载配置文件，如果不存在则创建默认配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 确保所有默认配置项都存在
                for key, value in self.DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
            else:
                # 创建默认配置
                config = self.DEFAULT_CONFIG.copy()
                config["download_dir"] = os.path.join(os.getcwd(), "downloads")
                self.save_config(config)
                return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config=None):
        """保存配置到文件"""
        if config is None:
            config = self.config
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置项并保存"""
        self.config[key] = value
        return self.save_config()