import json
import os
import configparser

from errors import ConfigError, UnsupportedConfig

from PyQt5.QtCore import QObject, pyqtSignal


class AppConfig(QObject):
    CONFIG_FILE_NAME = "config.ini"
    dbFileChanged = pyqtSignal(str)
    configInitialized = pyqtSignal(object)

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dbFileChanged.connect(parent.onDbFileChange)
        self.configInitialized.connect(parent.onConfigInitialized)
        self.config = self._init_config()
        self.configInitialized.emit(self)

    def _init_config(self):
        if os.path.isfile(self.CONFIG_FILE_NAME):
            config = configparser.ConfigParser()
            config.read(self.CONFIG_FILE_NAME)
            return config
        else:
            config = self.default_config
            with open(self.CONFIG_FILE_NAME, "w") as f:
                config.write(f)
            return config

    @property
    def default_config(self):
        config = configparser.ConfigParser()
        config["DB"] = {"Path": "DB_BarCode.xls"}
        config["Output"] = {
            "TextReport": "report.txt",
            "FullTextReport": "full-report.txt",
            "XlsReport": "report.xls",
            "FullXlsReport": "full-report.xls"
        }
        config["Input"] = {"Port": "COM1"}
        return config

    @property
    def db_file(self):
        return self.config["DB"]["Path"]

    @db_file.setter
    def db_file(self, value):
        self.self.config["DB"]["Path"] = value
        self.dbFileChanged.emit(self._db_file)
