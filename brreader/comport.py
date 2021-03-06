import copy
import time
from typing import Dict

import serial
from PyQt5.QtCore import QMutex, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction

from errors import CouldNotInitPort

ports = [f"COM{i + 1}" for i in range(256)]


def get_available_ports():
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


class ComPortManager(QObject):
    newCodeRead = pyqtSignal(str)
    currentPort = None
    buffer = b""
    _mutex = QMutex()
    SEPARATOR = b"\r"

    # TODO: Добавить буфферизацию, а то иногда считывается только часть штрихкода
    def ComReader(self):
        while True:
            if self.currentPort:
                self._mutex.lock()
                self.buffer += self.currentPort.read_until(self.SEPARATOR)
                if b"\r" in self.buffer:
                    self.newCodeRead.emit(self.buffer.decode().strip())
                    self.buffer = b""
                self._mutex.unlock()
            else:
                time.sleep(1)

    @pyqtSlot()
    def SwitchComPort(self, port):
        print("Switch to " + port)
        self._mutex.lock()
        if self.currentPort:
            self.currentPort.close()
        try:
            self.currentPort = serial.Serial(port, timeout=1)
        except serial.serialutil.SerialException as e:
            self.currentPort = None
            raise e
        finally:
            self._mutex.unlock()

    def GetPortsList(self) -> Dict[str, bool]:
        ports = {port: False for port in get_available_ports()}
        if self.currentPort:
            ports[self.currentPort.name] = True
        return ports
