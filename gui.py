from __future__ import annotations

import sys
import os
import webbrowser
import multiprocessing as mp

from PySide6 import QtCore, QtGui, QtWidgets

from chatmock.app import create_app
from chatmock.cli import cmd_login
from chatmock.utils import load_chatgpt_tokens, parse_jwt_claims


def run_server(host: str, port: int, reasoning_effort: str = "medium", reasoning_summary: str = "auto") -> None:
    app = create_app(reasoning_effort=reasoning_effort, reasoning_summary=reasoning_summary)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


class ServerProcess(QtCore.QObject):
    state_changed = QtCore.Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._proc: QtCore.QProcess | None = None
        self._host = "127.0.0.1"
        self._port = 8000
        self._effort = "medium"
        self._summary = "auto"

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.state() != QtCore.QProcess.NotRunning

    def start(self, host: str, port: int, effort: str, summary: str) -> None:
        if self.is_running():
            return
        self._host, self._port = host, port
        self._effort, self._summary = effort, summary
        self._proc = QtCore.QProcess()
        self._proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        args = [
            "--run-server",
            "--host", host,
            "--port", str(port),
            "--effort", effort,
            "--summary", summary,
        ]
        self._proc.start(sys.executable, args)
        self._proc.started.connect(lambda: self.state_changed.emit(True))

        def _on_finished(code: int, status: QtCore.QProcess.ExitStatus) -> None:
            self.state_changed.emit(False)
            self._proc = None

        self._proc.finished.connect(_on_finished)

    def stop(self) -> None:
        if not self.is_running():
            return
        try:
            self._proc.kill()
            self._proc.waitForFinished(3000)
        except Exception:
            pass
        self._proc = None
        self.state_changed.emit(False)

    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}/v1"


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel)


def find_app_icon() -> QtGui.QIcon:
    candidates = [
        "appicon.icns",
        "appicon.ico",
        "appicon.png",
        "icon.icns",
        "icon.ico",
        "icon.png",
        "ChatMock.icns",
        "ChatMock.png",
    ]
    for name in candidates:
        p = resource_path(name)
        if os.path.exists(p):
            icon = QtGui.QIcon(p)
            if not icon.isNull():
                return icon
    return QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DesktopIcon)


def is_dark_mode() -> bool:
    app = QtWidgets.QApplication.instance()
    pal = app.palette() if app else QtGui.QPalette()
    bg = pal.window().color()
    return bg.lightness() < 128


def apply_theme() -> None:
    dark = is_dark_mode()
    if dark:
        bg = "#111827"  # slate-900
        text = "#e5e7eb"  # gray-200
        subtext = "#9ca3af"  # gray-400
        border = "#374151"  # slate-700
        primary = "#3b82f6"  # blue-500
        primary_hover = "#2563eb"
        danger = "#ef4444"  # red-500
        field_bg = "#0f172a"  # slightly lighter (inputs)
    else:
        bg = "#ffffff"
        text = "#0f172a"
        subtext = "#64748b"
        border = "#e5e7eb"
        primary = "#2563eb"
        primary_hover = "#1d4ed8"
        danger = "#ef4444"
        field_bg = "#ffffff"

    css = f"""
    QWidget {{ background: {bg}; color: {text}; }}
    QGroupBox {{
        background: {bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 12px;
        margin-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 6px;
        color: {text};
        font-weight: 600;
        background: transparent;
    }}
    QLabel#subtitle {{ color: {subtext}; }}
    QLabel {{ background: transparent; }}
    QLineEdit, QComboBox {{
        background: {field_bg};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    QPushButton {{
        border: 1px solid {border};
        border-radius: 6px;
        padding: 6px 12px;
        background: {bg};
        color: {text};
    }}
    QPushButton:hover {{
        border-color: {primary};
    }}
    QPushButton[muted="true"] {{
        background: transparent;
        color: {subtext};
        border-color: {border};
    }}
    QPushButton[muted="true"]:hover {{
        border-color: {primary};
        color: {text};
    }}
    QPushButton[primary="true"] {{
        background: {primary};
        color: #ffffff;
        border: 1px solid {primary};
    }}
    QPushButton[primary="true"]:hover {{
        background: {primary_hover};
        border-color: {primary_hover};
    }}
    QPushButton[danger="true"] {{
        background: transparent;
        color: {danger};
        border: 1px solid {danger};
    }}
    QPushButton[danger="true"]:hover {{
        background: {danger};
        color: #ffffff;
    }}
    QMenu {{
        background: {bg};
        border: 1px solid {border};
    }}
    QMenu::item:selected {{ background: {primary}; color: #ffffff; }}
    """

    app = QtWidgets.QApplication.instance()
    if app:
        app.setStyleSheet(css)


class LoginWorker(QtCore.QThread):
    finished_with_code = QtCore.Signal(int)

    def run(self) -> None:
        try:
            code = cmd_login(no_browser=False, verbose=False)
        except Exception:
            code = 1
        self.finished_with_code.emit(code)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChatMock")
        self.setMinimumSize(620, 420)
        self._logged_in = False
        self._server = ServerProcess()
        self._server.state_changed.connect(self._on_server_state_changed)

        # Central widget
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        # Header
        header = QtWidgets.QVBoxLayout()
        self.title = QtWidgets.QLabel("ChatMock")
        font = self.title.font()
        font.setPointSize(20)
        font.setBold(True)
        self.title.setFont(font)
        self.status = QtWidgets.QLabel("Welcome to ChatMock")
        self.status.setObjectName("subtitle")
        header.addWidget(self.title)
        header.addWidget(self.status)
        root.addLayout(header)

        # Account card
        acc_box = QtWidgets.QGroupBox("Account")
        acc_box.setStyleSheet("QGroupBox{font-weight:600;}")
        acc_layout = QtWidgets.QFormLayout(acc_box)
        acc_layout.setLabelAlignment(QtCore.Qt.AlignLeft)
        acc_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        acc_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.email_value = QtWidgets.QLabel("Not signed in")
        self.email_value.setWordWrap(True)
        self.plan_value = QtWidgets.QLabel("-")
        self.accid_value = QtWidgets.QLabel("-")
        self.accid_value.setWordWrap(True)
        acc_layout.addRow("Email", self.email_value)
        acc_layout.addRow("Plan", self.plan_value)
        acc_layout.addRow("Account ID", self.accid_value)
        acc_btns = QtWidgets.QHBoxLayout()
        self.btn_login = QtWidgets.QPushButton("Log in")
        self.btn_login.clicked.connect(self._on_login)
        acc_btns.addWidget(self.btn_login)
        acc_btns.addStretch(1)
        acc_layout.addRow(acc_btns)
        root.addWidget(acc_box)

        # Server card
        srv_box = QtWidgets.QGroupBox("Server")
        srv_layout = QtWidgets.QVBoxLayout(srv_box)
        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.addWidget(QtWidgets.QLabel("Host"), 0, 0)
        self.host_edit = QtWidgets.QLineEdit("127.0.0.1")
        self.host_edit.setClearButtonEnabled(True)
        self.host_edit.setMinimumWidth(220)
        self.host_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        form.addWidget(self.host_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Port"), 0, 2)
        self.port_edit = QtWidgets.QLineEdit("8000")
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535, self))
        self.port_edit.setMaximumWidth(100)
        form.addWidget(self.port_edit, 0, 3)
        form.setColumnStretch(1, 1)
        srv_layout.addLayout(form)

        actions = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton("Start in Background")
        self.btn_start.setDefault(True)
        self.btn_start.setProperty("primary", True)
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.setProperty("danger", True)
        self.btn_open = QtWidgets.QPushButton("Open Base URL")
        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_stop)
        actions.addWidget(self.btn_open)
        actions.addStretch(1)
        srv_layout.addLayout(actions)

        # Reasoning controls
        opts = QtWidgets.QGridLayout()
        opts.setHorizontalSpacing(12)
        opts.setVerticalSpacing(8)
        opts.addWidget(QtWidgets.QLabel("Reasoning Effort"), 0, 0)
        self.effort = QtWidgets.QComboBox()
        self.effort.addItems(["minimal", "low", "medium", "high"])  # default medium
        self.effort.setCurrentText("medium")
        self.effort.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.effort.setMinimumContentsLength(7)
        opts.addWidget(self.effort, 0, 1)
        opts.addWidget(QtWidgets.QLabel("Reasoning Summary"), 0, 2)
        self.summary = QtWidgets.QComboBox()
        self.summary.addItems(["auto", "concise", "detailed", "none"])  # default auto
        self.summary.setCurrentText("auto")
        self.summary.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.summary.setMinimumContentsLength(8)
        opts.addWidget(self.summary, 0, 3)
        opts.setColumnStretch(1, 1)
        opts.setColumnStretch(3, 1)
        srv_layout.addLayout(opts)

        url_row = QtWidgets.QHBoxLayout()
        url_row.addWidget(QtWidgets.QLabel("Base URL:"))
        self.baseurl = QtWidgets.QLabel("(server not running)")
        self.baseurl.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
        )
        self.baseurl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        url_row.addWidget(self.baseurl, 1)
        self.btn_copy = QtWidgets.QPushButton("Copy")
        url_row.addWidget(self.btn_copy)
        srv_layout.addLayout(url_row)
        root.addWidget(srv_box)

        self.btn_start.clicked.connect(self._start_server)
        self.btn_stop.clicked.connect(self._stop_server)
        self.btn_copy.clicked.connect(self._copy_url)
        self.btn_open.clicked.connect(self._open_base_url)

        # Tray
        self.tray = QtWidgets.QSystemTrayIcon(self)
        icon = find_app_icon()
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)
        tray_menu = QtWidgets.QMenu()
        act_show = tray_menu.addAction("Show Window")
        tray_menu.addSeparator()
        act_quit = tray_menu.addAction("Quit")
        act_show.triggered.connect(self._show_window)
        act_quit.triggered.connect(QtWidgets.QApplication.quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

        self._refresh_login_state()
        self._on_server_state_changed(False)

        QtWidgets.QApplication.instance().aboutToQuit.connect(self._server.stop)

    def _refresh_login_state(self) -> None:
        access_token, account_id, id_token = load_chatgpt_tokens()
        if access_token and id_token:
            self.status.setText("Signed in • Ready to serve")
            self._logged_in = True
            self.btn_login.setEnabled(True)
            self.btn_login.setProperty("muted", True)
            try:
                self.btn_login.style().unpolish(self.btn_login)
                self.btn_login.style().polish(self.btn_login)
            except Exception:
                pass
            self.btn_login.setToolTip("You are logged in. Click to re-authenticate.")
            id_claims = parse_jwt_claims(id_token) or {}
            access_claims = parse_jwt_claims(access_token) or {}
            email = id_claims.get("email") or id_claims.get("preferred_username") or "<unknown>"
            plan_raw = (access_claims.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type") or "unknown"
            plan_map = {"plus": "Plus", "pro": "Pro", "free": "Free", "team": "Team", "enterprise": "Enterprise"}
            plan = plan_map.get(
                str(plan_raw).lower(), str(plan_raw).title() if isinstance(plan_raw, str) else "Unknown"
            )
            self.email_value.setText(email)
            self.plan_value.setText(plan)
            self.accid_value.setText(account_id or "-")
        else:
            self.status.setText("Not signed in • Click Log in")
            self._logged_in = False
            self.btn_login.setEnabled(True)
            self.btn_login.setProperty("muted", False)
            try:
                self.btn_login.style().unpolish(self.btn_login)
                self.btn_login.style().polish(self.btn_login)
            except Exception:
                pass
            self.btn_login.setToolTip("Log in to ChatGPT")
            self.email_value.setText("Not signed in")
            self.plan_value.setText("-")
            self.accid_value.setText("-")
        self.btn_start.setEnabled(not self._server.is_running() and self._logged_in)

    def _on_login(self) -> None:
        self.status.setText("Launching login flow…")
        self.btn_login.setEnabled(False)
        self._login_worker = LoginWorker()
        self._login_worker.finished_with_code.connect(self._after_login)
        self._login_worker.start()

    def _after_login(self, code: int) -> None:
        if code == 0:
            QtWidgets.QMessageBox.information(self, "Login", "Login successful. You can now start the server.")
        elif code == 13:
            QtWidgets.QMessageBox.warning(
                self, "Login", "Login helper port is in use. Close other instances and try again."
            )
        else:
            QtWidgets.QMessageBox.critical(self, "Login", "Login failed. Please try again.")
        self._refresh_login_state()

    def _start_server(self) -> None:
        try:
            host = self.host_edit.text().strip() or "127.0.0.1"
            port = int(self.port_edit.text().strip() or "8000")
        except ValueError:
            QtWidgets.QMessageBox.critical(self, "Port", "Invalid port number.")
            return
        effort = self.effort.currentText().strip()
        summary = self.summary.currentText().strip()
        self.status.setText(f"Starting server at http://{host}:{port} …")
        self.btn_start.setEnabled(False)
        self._server.start(host, port, effort, summary)

    def _stop_server(self) -> None:
        self._server.stop()

    def _on_server_state_changed(self, running: bool) -> None:
        self.btn_start.setEnabled((not running) and self._logged_in)
        self.btn_stop.setEnabled(running)
        self.btn_open.setEnabled(running)
        self.btn_copy.setEnabled(running)
        if running:
            self.status.setText("Serving • Running in background")
            self.baseurl.setText(self._server.base_url())
            self.hide()
            self.tray.showMessage(
                "ChatMock", "Server is running in the background", QtWidgets.QSystemTrayIcon.Information, 1500
            )
        else:
            self.status.setText("Server stopped")
            self.baseurl.setText("(server not running)")

    def _copy_url(self) -> None:
        url = self.baseurl.text().strip()
        if url and not url.startswith("("):
            QtWidgets.QApplication.clipboard().setText(url)

    def _open_base_url(self) -> None:
        url = self.baseurl.text().strip()
        if url and not url.startswith("("):
            webbrowser.open(url)

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()


def main() -> None:
    mp.freeze_support()
    if "--run-server" in sys.argv:
        import argparse

        p = argparse.ArgumentParser(add_help=False)
        p.add_argument("--run-server", action="store_true")
        p.add_argument("--host", default="127.0.0.1")
        p.add_argument("--port", type=int, default=8000)
        p.add_argument("--effort", default="medium")
        p.add_argument("--summary", default="auto")
        args, _ = p.parse_known_args()
        run_server(args.host, args.port, args.effort, args.summary)
        return

    app = QtWidgets.QApplication(sys.argv)
    apply_theme()
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
