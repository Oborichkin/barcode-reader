import copy
import datetime
import os
import sys
import time
import xlwt
from random import choice
from typing import List
from collections import Counter

import design
import serial
from errors import InvalidBarcode, UnsupportedBarcode, DatabaseException
from comport import ComPortManager
from config import AppConfig
from session import Session
from database import BarcodeDatabase, ProductInfo, Item
from PyQt5.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import QAction, QApplication, QFileDialog, QListWidgetItem, QMainWindow, QMessageBox


class ExampleApp(QMainWindow, design.Ui_MainWindow):
    def __init__(self, config_path=None):
        super().__init__()

        self.db = BarcodeDatabase()
        self.session = Session()

        self.comManager = ComPortManager()
        self.comThread = QThread()
        self.comManager.newCodeRead.connect(self.onNewCode)
        self.comManager.moveToThread(self.comThread)
        self.comThread.started.connect(self.comManager.ComReader)
        self.comThread.start()

        self.setupSound()
        self.setupUi(self)

        # Temp button actions assignment
        self.exitButton.clicked.connect(self.close)
        self.clearButton.clicked.connect(self.clearSessionData)
        self.openDbButton.clicked.connect(self.loadNewDatabase)
        self.saveButton.clicked.connect(self.onSave)

        self.menuCOM.aboutToShow.connect(self.loadComPortMenu)
        self.loadDb.triggered.connect(self.loadNewDatabase)
        self.openDb.triggered.connect(self.onEditDbFile)
        self.reloadDb.triggered.connect(self.onReloadDb)
        self.save.triggered.connect(self.onSave)
        self.clear.triggered.connect(self.clearSessionData)
        self.BarcodeHistory.itemClicked.connect(self.onItemClicked)
        self.BarcodeHistory.currentItemChanged.connect(self.onItemClicked)

        self.app_config = AppConfig(parent=self)
        self.session.sessionItemRestore.connect(self.onNewCode)
        self.comManager.newCodeRead.connect(self.session.new_item)

        self.session.init_session()

    def setupSound(self):
        print(os.getcwd())
        good = QSoundEffect(self)
        good.setSource(QUrl.fromLocalFile(os.path.join("sound", "good.wav")))
        good.setLoopCount(1)
        bad = QSoundEffect(self)
        bad.setSource(QUrl.fromLocalFile(os.path.join("sound", "bad.wav")))
        bad.setLoopCount(1)
        self.sounds = {
            'good': good,
            'bad': bad
        }

    def loadComPortMenu(self):
        self.menuCOM.clear()
        ports = self.comManager.GetPortsList()
        if ports:
            for port, enabled in ports.items():
                port_action = self.menuCOM.addAction(port)
                port_action.setCheckable(True)
                if enabled:
                    port_action.setChecked(True)
                else:
                    port_action.triggered.connect(lambda *args, portName=port: self.comManager.SwitchComPort(portName))
                self.menuCOM.addAction(port_action)
        else:
            self.menuCOM.addAction(self.no_ports)

    def onNewCode(self, code):
        try:
            product = self.dispatchBarcode(code)
            item = QListWidgetItem(product.name, self.BarcodeHistory)
            item.setData(32, product)
            self.BarcodeHistory.addItem(item)
            self.BarcodeHistory.setCurrentItem(item)
            self.sounds["good"].play()
        except Exception as e:
            self.sounds["bad"].play()
            print(e)

    def onItemClicked(self, item):
        if item:
            product = item.data(32)
            self.Name.setText(str(product.name))
            self.Packaging.setText(str(product.packaging))
            self.Weight.setText(str(product.weight))
            self.StorageType.setText(str(product.storage_type))

    def loadNewDatabase(self):
        fname = QFileDialog.getOpenFileName(self, "Open file", "c:\\", "Database files (*.xls)")
        if fname[0]:
            self.app_config.db_file = fname[0]

    def onDbFileChange(self, db_file: str):
        self.db.load(db_file)

    def onReloadDb(self):
        self.db.load(self.app_config.db_file)

    def onConfigInitialized(self, config):
        try:
            self.db.load(config.db_file)
            self.comManager.SwitchComPort(config.com_port)
        except Exception as e:
            self.onException(e)

    def onEditDbFile(self):
        os.system(self.app_config.db_file)
        self.db.load(self.app_config.db_file)

    def onSave(self):
        itemsList: List[Item] = [self.BarcodeHistory.item(i).data(32) for i in range(self.BarcodeHistory.count())]
        codeList = [item.code for item in itemsList]
        unique_codes = set(codeList)
        freq_list = Counter(codeList)
        fields = ("Код", "Название", "Тип", "Упаковка", "Вес")
        full_fields = ("Код", "Название", "Тип", "Упаковка", "Количество", "Вес")

        with open(self.app_config.full_report_file, "w+") as f:
            f.writelines([str(item.code) + "\n" for item in itemsList])

        with open(self.app_config.report_file, "w+") as f:
            f.writelines([f"{str(code)};{str(freq)}\n" for code, freq in freq_list.items()])

        workbook = xlwt.Workbook()

        worksheet = workbook.add_sheet('Полный Отчет')
        for i, fieldname in enumerate(fields):
            worksheet.write(0, i, fieldname)

        for row_index, item in enumerate(itemsList):
            worksheet.write(row_index + 1, 0, item.code)
            worksheet.write(row_index + 1, 1, item.name)
            worksheet.write(row_index + 1, 2, item.storage_type)
            worksheet.write(row_index + 1, 3, item.packaging)
            worksheet.write(row_index + 1, 4, item.weight)

        worksheet = workbook.add_sheet('Количественный Отчет')
        for i, fieldname in enumerate(full_fields):
            worksheet.write(0, i, fieldname)

        for row_index, code in enumerate(unique_codes):
            worksheet.write(row_index + 1, 0, code)
            worksheet.write(row_index + 1, 1, self.db[code].name)
            worksheet.write(row_index + 1, 2, self.db[code].storage_type)
            worksheet.write(row_index + 1, 3, self.db[code].packaging)
            worksheet.write(row_index + 1, 4, freq_list[code])
            worksheet.write(row_index + 1, 5, sum([int(item.weight) for item in itemsList if item.code == code]))

        workbook.save(self.app_config.report_xls)

    def dispatchBarcode(self, code: str) -> Item:
        try:
            if len(code) == 13:
                return Item(self.db[int(code)])
            elif len(code) == 32:
                code, weight, date = code[:13], code[13:19], code[19:25]
                product = Item(self.db[int(code)])
                product.weight = float(weight)
                product.date = datetime.datetime.strptime(date, "%d%m%Y").date()
                return product
            else:
                raise UnsupportedBarcode
        except Exception as e:
            self.onException(e)

    def clearSessionData(self):
        self.BarcodeHistory.clear()
        self.session.clear()

    def onException(self, e):
        print(e)


def main():
    app = QApplication(sys.argv)
    if os.path.isfile("style.css"):
        with open("style.css") as f:
            app.setStyleSheet(f.read())
    window = ExampleApp()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
