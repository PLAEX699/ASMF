import sys
import os
import time
import threading
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit,
    QPushButton, QHBoxLayout, QLabel, QSystemTrayIcon, QMenu
)
from PyQt6.QtGui import QAction

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QIcon
import pyautogui
import psutil

INTERVAL = 30
MAX_LOG_LINES = 500

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.parent = parent
        self.drag_pos = None
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        self.title_label = QLabel("🖼️ Screenshot USB Style")
        self.title_label.setStyleSheet("color: #ff69b4; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        self.min_btn = QPushButton("–")
        self.max_btn = QPushButton("□")
        self.close_btn = QPushButton("✕")
        for btn in [self.min_btn, self.max_btn, self.close_btn]:
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a1a1a;
                    color: #ff69b4;
                    border: none;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                }
            """)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)
        self.setLayout(layout)
        self.close_btn.clicked.connect(parent.close)
        self.min_btn.clicked.connect(parent.showMinimized)
        self.max_btn.clicked.connect(self.toggle_max_restore)

    def toggle_max_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.parent.move(self.parent.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()

class USBScreenshotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(900, 500)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.setWindowIcon(QIcon())
        self.running = True
        self.active_folders = {}
        self.threads = []
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar = CustomTitleBar(self)
        layout.addWidget(self.title_bar)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ff69b4;
                border: none;
                padding: 10px;
            }
        """)
        self.text_log.setFont(QFont("Comic Sans MS", 11, QFont.Weight.Bold))
        layout.addWidget(self.text_log)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        threading.Thread(target=self.usb_detection_loop).start()

    def log(self, message: str):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.text_log.append(f"{timestamp} {message}")
        if self.text_log.document().blockCount() > MAX_LOG_LINES:
            cursor = self.text_log.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def take_screenshots_per_usb(self, folder, stop_event):
        while not stop_event.is_set():
            try:
                filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
                screenshot = pyautogui.screenshot()
                screenshot.save(os.path.join(folder, filename))
                self.log(f"💾 Screenshot saved: {filename}")
            except Exception as e:
                self.log(f"❌ Error saving screenshot: {e}")
                break
            for _ in range(INTERVAL):
                if stop_event.is_set():
                    break
                time.sleep(1)
        try:
            filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
            screenshot = pyautogui.screenshot()
            screenshot.save(os.path.join(folder, filename))
            self.log(f"📸 Final screenshot saved: {filename}")
        except Exception as e:
            self.log(f"❌ Error saving final screenshot: {e}")

    def detect_usb(self):
        return {disk.device for disk in psutil.disk_partitions() if 'removable' in disk.opts}

    def usb_detection_loop(self):
        waiting_printed = False
        while self.running:
            current_drives = self.detect_usb()
            for usb_drive in current_drives:
                if usb_drive not in self.active_folders:
                    self.log(f"🌸 USB detected at {usb_drive}. Waiting 5 seconds...")
                    time.sleep(5)
                    timestamp = datetime.now().strftime("Date %Y-%m-%d %I-%M-%S%p")
                    folder_name = f"{timestamp}_{uuid.uuid4().hex[:6]}"
                    folder_path = os.path.join(usb_drive, folder_name)
                    os.makedirs(folder_path, exist_ok=True)
                    self.log(f"🎀 Folder created: {folder_path}")
                    self.log("💖 Starting screenshots every 30 seconds...")
                    stop_event = threading.Event()
                    self.active_folders[usb_drive] = (folder_path, stop_event)
                    thread = threading.Thread(target=self.take_screenshots_per_usb, args=(folder_path, stop_event))
                    thread.start()
                    self.threads.append(thread)
            removed_drives = set(self.active_folders.keys()) - current_drives
            for removed in removed_drives:
                folder_path, stop_event = self.active_folders.pop(removed)
                self.log(f"⚠️ USB {removed} removed. Stopping capture.")
                stop_event.set()
            if not current_drives and not waiting_printed:
                self.log("🔌 Waiting for USB drive...")
                waiting_printed = True
            elif current_drives:
                waiting_printed = False
            time.sleep(1)

    def closeEvent(self, event):
        self.running = False
        for folder_path, stop_event in self.active_folders.values():
            stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = USBScreenshotApp()
    window.show()
    sys.exit(app.exec())
