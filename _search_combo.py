"""Combo box with a search field inside its transient popup."""
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLineEdit, QListWidget, QVBoxLayout


class SearchComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.popup = QFrame(self, Qt.Popup)
        self.popup.setObjectName('ToolPanel')
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.search = QLineEdit(self.popup)
        self.search.setPlaceholderText('搜索名称或等级，例如：床、Lv 3')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('搜索可添加物品')
        self.results = QListWidget(self.popup)
        self.empty_label = QLabel('没有匹配的物品，请修改或清空搜索', self.popup)
        self.empty_label.setObjectName('Muted')
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.search)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.results, 1)
        for widget in (self.search, self.results):
            widget.installEventFilter(self)
        self.results.itemClicked.connect(self._choose)
        self.results.itemActivated.connect(self._choose)

    def sync_results(self):
        self.results.clear()
        self.results.addItems([self.itemText(i) for i in range(self.count())])
        self.results.setCurrentRow(self.currentIndex())
        self.empty_label.setVisible(self.count() == 0)
        self.results.setVisible(self.count() > 0)

    def showPopup(self):
        self.sync_results()
        screen = self.screen().availableGeometry()
        width = min(max(self.width(), 320), screen.width())
        height = min(360, screen.height())
        below = self.mapToGlobal(QPoint(0, self.height()))
        above = self.mapToGlobal(QPoint(0, 0)).y() - height
        x = max(screen.left(), min(below.x(), screen.right() - width + 1))
        y = below.y() if below.y() + height <= screen.bottom() + 1 else above
        y = max(screen.top(), min(y, screen.bottom() - height + 1))
        self.popup.setGeometry(x, y, width, height)
        self.popup.show()
        self.search.setFocus(Qt.PopupFocusReason)
        self.search.selectAll()

    def hidePopup(self):
        self.popup.hide()
        super().hidePopup()

    def _choose(self, item):
        if item is None:
            return
        row = self.results.row(item)
        if 0 <= row < self.count():
            self.setCurrentIndex(row)
            self.activated.emit(row)
            self.hidePopup()
            self.setFocus(Qt.PopupFocusReason)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hidePopup()
                self.setFocus(Qt.PopupFocusReason)
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._choose(self.results.currentItem())
                return True
            if watched is self.search and event.key() in (Qt.Key_Down, Qt.Key_Up):
                step = 1 if event.key() == Qt.Key_Down else -1
                row = max(0, min(self.count() - 1, self.results.currentRow() + step))
                self.results.setCurrentRow(row)
                return True
        return super().eventFilter(watched, event)
