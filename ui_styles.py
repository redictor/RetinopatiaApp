from PyQt5 import QtWidgets, QtCore, QtGui


def window_button_style(kind):
    if kind == "close":
        border = "#fecaca"
        hover_bg = "#fee2e2"
        hover_border = "#fca5a5"
        icon_color = "#ef4444"
    else:
        border = "#e5e7eb"
        hover_bg = "#f3f4f6"
        hover_border = "#d1d5db"
        icon_color = "#6b7280"

    return f"""
    QPushButton {{
        background-color: white;
        border: 1px solid {border};
        border-radius: 8px;
        padding: 0px;
        color: {icon_color};
    }}
    QPushButton:hover {{
        background-color: {hover_bg};
        border: 1px solid {hover_border};
    }}
    QPushButton:pressed {{
        background-color: #e5e7eb;
    }}
    """


def set_icon(button, path):
    icon = QtGui.QIcon(path)
    button.setIcon(icon)
    button.setIconSize(QtCore.QSize(16, 16))
    button.setText("")


def create_window_buttons(parent):
    minimize_button = QtWidgets.QPushButton()
    minimize_button.setFixedSize(32, 32)
    minimize_button.setCursor(QtCore.Qt.PointingHandCursor)
    minimize_button.setStyleSheet(window_button_style("minimize"))
    set_icon(minimize_button, "assets/icons/minimize.svg")
    minimize_button.clicked.connect(parent.showMinimized)

    close_button = QtWidgets.QPushButton()
    close_button.setFixedSize(32, 32)
    close_button.setCursor(QtCore.Qt.PointingHandCursor)
    close_button.setStyleSheet(window_button_style("close"))
    set_icon(close_button, "assets/icons/close.svg")
    close_button.clicked.connect(parent.close)

    return minimize_button, close_button