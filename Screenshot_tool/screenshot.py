from subprocess import Popen, signal, PIPE
from string import ascii_letters, digits
from os import makedirs, remove
from os.path import isdir, dirname
from threading import Thread
from requests import post
from random import choice
from sys import argv

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

capture_directory = "/home/ganer/Documents/ScreenCapture/"
copy_mode = "url"

uploader_url = "http://192.168.1.44/upload"
shorterner_url = "http://192.168.1.44/shortenURL"
uploader_access_code = "bruh"

mode = "image" if len(argv) < 2 else argv[1]
upload = True if len(argv) < 3 else argv[2].lower() != "false"

characters = ascii_letters + digits
make_name = lambda: ''.join(map(lambda x: choice(characters), range(16)))

proc_list, file_loc = [], None

if not isdir(capture_directory):
    makedirs(capture_directory)

check_comp = lambda: Popen(["qdbus", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.active"], stdout = PIPE).communicate()[0].decode().strip() != "false"
toggle_comp = lambda: Popen(["qdbus", "org.kde.kglobalaccel", "/component/kwin", "invokeShortcut", "Suspend Compositing"]).wait()
(inital_comp := check_comp()) or toggle_comp()

class CustomWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.loc1 = self.loc2 = None
        self.firstPaint = False
        self.coords = None
    
    def finish(self):
        not inital_comp and check_comp() and toggle_comp()
        
        # clipboard = QGuiApplication.clipboard()
        # event = QtCore.QEvent(QEvent.Clipboard)
        # QApplication.sendEvent(clipboard, event)
        
        # Pain
        with open(fName := f"/tmp/{make_name()}", 'w') as f:
            f.write(QGuiApplication.clipboard().text())
        Popen(["xclip", "-selection", "clipboard", fName]).wait()
        remove(fName)
        self.close()
    
    def paintEvent(self, event = None):
        painter = QPainter(self)
        pen = QPen(Qt.red)
        pen.setWidth(2)
        painter.setPen(pen)
        if not self.firstPaint:
            virtualScreen = self.screen().virtualGeometry()
            w, h = virtualScreen.width(), virtualScreen.height()
            print(w, h)
            self.setGeometry(0, 0, w, h)
            self.firstPaint = True
        
        if not (self.loc1 and self.loc2): return
        
        self.coords = [
            min(self.loc1.x(), self.loc2.x()),
            min(self.loc1.y(), self.loc2.y()),
        ]
        self.coords[2:] = [
            max(self.loc1.x(), self.loc2.x()) - self.coords[0],
            max(self.loc1.y(), self.loc2.y()) - self.coords[1]
        ]
        painter.drawRect(*self.coords)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == 1:
            self.loc1 = e.pos()
            self.loc2 = e.pos()
        elif e.button() == 2:
            self.loc1 = self.loc2 = None
        self.update()

        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        global file_loc
        if e.button() == 1:
            window = self.window()
            if g := self.loc1 and self.loc2:
                x, y = window.x() + self.coords[0] + 2, window.y() + self.coords[1] + 2
                w, h = self.coords[2] - 4, self.coords[3] - 4
            if not g or w < 0 or h < 0:
                target_desktop = qApp.desktop().screen(qApp.desktop().screenNumber(e.pos())).geometry()
                x, y, w, h = target_desktop.x(), target_desktop.y(), target_desktop.width(), target_desktop.height()
                
            self.update()
            if mode == "video":
                file_loc = f"{capture_directory}/{make_name()}.mp4"
                proc_list.append(Popen([
                    "ffmpeg", "-y", "-video_size", f"{w}x{h}", "-framerate", "60",
                    "-f","x11grab", "-i", f":0.0+{x},{y}", "-c:v", "h264",
                    "-preset", "fast", file_loc
                ]))
            elif mode == "image":
                file_loc = f"{capture_directory}/{make_name()}.png"
                proc_list.append(p := Popen([
                    "ffmpeg", "-y", "-video_size", f"{w}x{h}", "-f", "x11grab", "-i",
                    f":0.0+{x},{y}", "-frames:v", "1", file_loc
                ]))
                p.wait()
                self.showMinimized()
                self.keyPressEvent(None, force_esc = True)

        return super().mouseReleaseEvent(e)
    
    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        self.loc2 = e.pos()
        self.update()
        return super().mouseMoveEvent(e)
    
    def keyPressEvent(self, e: QtGui.QKeyEvent, force_esc = False):
        if force_esc or e.key() == Qt.Key.Key_Escape:
            self.showMinimized()
            for i in proc_list: # Why is this a loop?
                i.send_signal(signal.SIGINT)
                i.wait()
                
                if copy_mode == "file":
                    # TODO: check if it's an image
                    QGuiApplication.clipboard().setImage(QImage(file_loc))
                
                if upload:
                    url = post(uploader_url,
                        headers = {
                            "access": uploader_access_code,
                            "filename": file_loc
                        },
                        data = open(file_loc, 'rb')
                    ).content.decode()
                    
                    if copy_mode == "url":
                        print(url)
                        short_url = post(shorterner_url, headers = {
                            "access": uploader_access_code,
                            "url": url
                        }).content.decode()
                        print(short_url)
                        
                        QGuiApplication.clipboard().setText(short_url)
                
                Popen(["paplay", dirname(__file__) + "/bell.ogg"])
                        
            self.finish()

app = QApplication([])
window = CustomWindow()
window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
window.setAttribute(Qt.WA_NoSystemBackground, True)
window.setAttribute(Qt.WA_TranslucentBackground, True)
window.show()
app.exec_()