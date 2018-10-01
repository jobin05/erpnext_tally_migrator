import sys
from PyQt5.QtWidgets import QMainWindow, QApplication, QLineEdit, QPushButton


class TallyMigratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()


    def init_ui(self):
        self.setup_window()
        self.setup_textboxes()
        self.setup_buttons()
        self.center()
        self.show()


    def setup_window(self):
        self.setGeometry(0, 0, 240, 260)
        self.setWindowTitle('Tally Migrator')


    def setup_textboxes(self):
        self.textbox_erpnext_subdomain = QLineEdit(self)
        self.textbox_erpnext_subdomain.move(20, 20)
        self.textbox_erpnext_subdomain.resize(200, 20)

        self.textbox_erpnext_username = QLineEdit(self)
        self.textbox_erpnext_username.move(20, 60)
        self.textbox_erpnext_username.resize(200, 20)

        self.textbox_erpnext_password = QLineEdit(self)
        self.textbox_erpnext_password.move(20, 100)
        self.textbox_erpnext_password.resize(200, 20)

        self.textbox_tally_ip = QLineEdit(self)
        self.textbox_tally_ip.move(20, 180)
        self.textbox_tally_ip.resize(200, 20)
        self.textbox_tally_ip.setText("localhost")

        self.textbox_tally_port = QLineEdit(self)
        self.textbox_tally_port.move(20, 220)
        self.textbox_tally_port.resize(200, 20)
        self.textbox_tally_port.setText("9000")


    def setup_buttons(self):
        self.button_connect = QPushButton('Connect', self)
        self.button_connect.move(20, 140)
        self.button_connect.resize(200, 20)
        self.button_connect.clicked.connect(self.on_click_connect)


    # Copied from StackOverflow
    # https://stackoverflow.com/questions/20243637/pyqt4-center-window-on-active-screen
    # Thanks to Andy
    def center(self):
        frame = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frame.moveCenter(centerPoint)
        self.move(frame.topLeft())


    def on_click_connect(self):
        print("Clicked Connect")


if __name__ == '__main__':
    tall_migrator_app = QApplication(sys.argv)
    tally_migrator_window = TallyMigratorWindow()
    tall_migrator_app.exec_()
