"""Document toolbar, searchable navigation and consistent editor presentation."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton, QFrame,
    QHBoxLayout, QVBoxLayout, QGridLayout, QTableWidget, QScrollArea,
    QSizePolicy, QComboBox)


class EditorUiMixin:
    def setup_editor_ui(self):
        self.nav_search = QLineEdit()
        self.nav_search.setPlaceholderText('搜索页面或字段')
        self.nav_search.setClearButtonEnabled(True)
        self.nav_search.textChanged.connect(self._filter_navigation)
        self._sb_layout.insertWidget(1, self.nav_search)
        self.sidebar.setMinimumWidth(190)
        self.sidebar.setMaximumWidth(250)
        toolbar = QFrame()
        toolbar.setObjectName('DocumentBar')
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)
        self.file_label = QLabel('未打开存档')
        self.file_label.setObjectName('CardTitle')
        self.file_label.setMinimumWidth(100)
        self.file_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.document_badge = QLabel('等待打开')
        self.document_badge.setObjectName('DocumentBadge')
        layout.addWidget(self.file_label, 1)
        layout.addWidget(self.document_badge)
        for attr, text, callback in [
                ('open_button', '打开', self.open_file),
                ('find_button', '查找存档', self.find_save_file),
                ('check_button', '检查修改', self.check_document),
                ('save_as_button', '另存为', self.save_file_as),
                ('save_button', '保存  Ctrl+S', self.save_file)]:
            button = QPushButton(text)
            if attr != 'save_button':
                button.setObjectName('Ghost')
            button.clicked.connect(callback)
            setattr(self, attr, button)
            layout.addWidget(button)
        self.stack.parentWidget().layout().insertWidget(0, toolbar)
        self.overview_values = {}
        overview = QWidget()
        overview_layout = QGridLayout(overview)
        overview_layout.setContentsMargins(0, 8, 0, 8)
        for i, (key, title) in enumerate([('Currency', '可用资金'), ('Day', '经营天数'),
                                         ('Workers', '在册工人'), ('PlaceItems', '已放置物品')]):
            card = QFrame()
            card.setObjectName('CardBox')
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 12, 16, 12)
            caption = QLabel(title)
            caption.setObjectName('Muted')
            value = QLabel('—')
            value.setObjectName('MetricValue')
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            box.addWidget(caption)
            box.addWidget(value)
            overview_layout.addWidget(card, 0, i)
            self.overview_values[key] = value
        self.tab_welcome.layout().insertWidget(2, overview)
        for page in (self.tab_welcome, self.tab_basic, self.tab_story):
            self._wrap_scroll_page(page)
        for table in self.findChildren(QTableWidget):
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.verticalHeader().setDefaultSectionSize(34)
            table.setWordWrap(False)
            table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
            table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
            table.horizontalHeader().setMinimumSectionSize(32 if table is self.mem_target_table else 72)
            if table is not self.mem_target_table:
                table.setMinimumHeight(140)
        # Normalize the repeated page primitives after every page has built its
        # own controls. This keeps legacy and newer pages visually consistent.
        for button in self.findChildren(QPushButton):
            if button.parentWidget() is not self.statusBar:
                button.setMinimumHeight(max(button.minimumHeight(), 24))
                if button.objectName() != "WelcomeCard":
                    button.setMaximumHeight(28)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(max(combo.minimumHeight(), 28))
        for label in self.findChildren(QLabel):
            if label.objectName() in ('Hint', 'PageSub'):
                label.setWordWrap(True)
        self._shortcuts = []
        for keys, callback in [('Ctrl+O', self.open_file), ('Ctrl+S', self.save_file),
                               ('Ctrl+Shift+S', self.save_file_as), ('Ctrl+K', self.nav_search.setFocus)]:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self._state_timer = QTimer(self)
        self._state_timer.setInterval(1000)
        self._state_timer.timeout.connect(self._refresh_document_state)
        self._state_timer.start()
        self._refresh_document_state()

    def _wrap_scroll_page(self, page):
        old_layout = page.layout()
        if old_layout is None:
            return
        content = QWidget()
        content.setLayout(old_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _filter_navigation(self, text):
        query = text.strip().casefold()
        aliases = {'basic': 'currency level exp day electricity shopname difficulty calldata',
                   'unlock': 'debt missionprogress tutorialsavedata',
                   'growth': 'progress easteregg', 'municipal': 'mayor npcrolefound',
                   'interior': 'dirt interior', 'purchase': 'npcpurchase',
                   'delivery': 'deliverylocation', 'airport': 'airportnpc',
                   'schedule': 'schedulecall', 'crypto': 'cryptodata', 'placed': 'placeitems'}
        for leaf in self._nav_leaves:
            row = leaf.data(0, Qt.UserRole)
            icon, label, key = self.nav_items[row]
            leaf.setHidden(query not in f'{label} {key} {aliases.get(key, "")}'.casefold())
        for group in self._nav_group_items:
            group.setHidden(all(group.child(i).isHidden() for i in range(group.childCount())))
            if query:
                group.setExpanded(True)
            self._nav_refresh_group_label(group)

    def _go_to_page(self, key):
        self.nav_search.clear()
        row = self._key_to_row[key]
        for leaf in self._nav_leaves:
            if leaf.data(0, Qt.UserRole) == row:
                if leaf.parent():
                    leaf.parent().setExpanded(True)
                self.nav_list.setCurrentItem(leaf)
                self.nav_list.scrollToItem(leaf)
                break
