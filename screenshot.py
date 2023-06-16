from subprocess import Popen, signal, PIPE
from string import ascii_letters, digits
from os import makedirs, remove, chdir
from os.path import isdir, dirname
from threading import Thread
from requests import post
from random import choice
from sys import argv
from json import load

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from xnotipy.xnotipy import Notification

chdir(dirname := dirname(__file__))

capture_directory = "/home/ganer/Media/ScreenCapture/"
copy_mode = "url"

priv = load(open("config.json", 'r'))
uploader_url = priv["uploader_url"]
shorterner_url = priv["shorterner_url"]
uploader_access_code = priv["uploader_access_code"]

mode = "image" if len(argv) < 2 else argv[1]
upload = True if len(argv) < 3 else argv[2].lower() != "false"

characters = ascii_letters + digits
make_name = lambda: ''.join(map(lambda _: choice(characters), range(16)))

proc_list, file_loc = [], None

if not isdir(capture_directory):
    makedirs(capture_directory)

class CustomWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.loc1 = self.loc2 = None
        self.firstPaint = False
        self.coords = None
        self.disable_click = False
        self.disable_esc = False
    
    def finish(self):
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
        print(f"{e.pos()=}")
        if self.disable_click:
            return
        
        if e.button() == 1:
            self.loc1 = e.pos()
            self.loc2 = e.pos()
        elif e.button() == 2:
            self.loc1 = e.pos()
            self.loc2 = None
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
                self.disable_click = True
            elif mode == "image":
                file_loc = f"{capture_directory}/{make_name()}.png"
                proc_list.append(p := Popen([
                    "ffmpeg", "-y", "-video_size", f"{w}x{h}", "-f", "x11grab", "-i",
                    f":0.0+{x},{y}", "-frames:v", "1", file_loc
                ]))
                p.wait()
                self.showMinimized()
                self.keyPressEvent(None, force_esc = True)
            
            file_loc = file_loc.replace('//', '/')

        return super().mouseReleaseEvent(e)
    
    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        print(f"{e.pos()=}")
        if self.disable_click:
            return
        
        self.loc2 = e.pos()
        self.update()
        return super().mouseMoveEvent(e)
    
    def keyPressEvent(self, e: QtGui.QKeyEvent, force_esc=False):
        if not self.disable_esc and (force_esc or e.key() == Qt.Key.Key_Escape):
            self.disable_esc = True
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
                
                Notification(f"Copy OCR to clipboard", cmd=(
                    lambda: [
                        Popen(f"tesseract {file_loc} stdout | xclip -selection clipboard", shell=True),
                        Notification("Copied OCR!", time=1).run()]
                )).background_run()
                Notification(f"Copy image to clipboard", cmd=(
                    lambda: [
                        Popen(f"xclip -selection clipboard -t image/png -i {file_loc}", shell=True),
                        Notification("Copied image!", time=1).run()]
                )).background_run()
                Notification(f"Copy path to clipboard", cmd=(
                    lambda: [
                        Popen(f"echo {file_loc} | xclip -selection clipboard", shell=True),
                        Notification("Copied path!", time=1).run()]
                )).background_run()
                
                Popen(["paplay", f"{dirname}/bell.ogg"])
                Notification.exit(10)
                        
            self.finish()

app = QApplication([])
window = CustomWindow()
window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
window.setAttribute(Qt.WA_NoSystemBackground, True)
window.setAttribute(Qt.WA_TranslucentBackground, True)
window.setAttribute(Qt.WA_PaintOnScreen, True)
window.show()
app.exec_()
