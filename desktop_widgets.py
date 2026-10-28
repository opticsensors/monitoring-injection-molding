"""Shared desktop layout: embedded setup, editable History and plot tabs."""
from copy import deepcopy
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from config_window import DaqConfigWindow
from metadata_widgets import HistoryPanel, PartEditor, value_text
from cycle_metadata import optional_number, effective_settings

ICON_DIR = Path(__file__).parent / "assets" / "preview" / "lucide"


def configure_application(app):
    """Keep native metrics and DPI rendering consistent in every launcher."""
    app.setStyle("Fusion")
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        identifier = QtGui.QFontDatabase.addApplicationFont(str(font_path))
        families = QtGui.QFontDatabase.applicationFontFamilies(identifier)
        if families:
            app.setFont(QtGui.QFont(families[0], 10))


STYLE = """
QMainWindow, QWidget#previewRoot { background: #edf1f5; color: #243343; }
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #243343; }
QWidget#workspacePage, QStackedWidget, QScrollArea > QWidget > QWidget { background: #ffffff; }
QLabel, QCheckBox { background: transparent; }
QCheckBox::indicator { width: 14px; height: 14px; background: #ffffff; border: 1px solid #8a9bae; border-radius: 2px; }
QCheckBox::indicator:checked { image: url("$CHECK_ICON"); background: #edf5fc; border-color: #3975aa; }
QLabel:disabled { color: #637383; }
QLabel[role='muted'] { color: #5d6c7b; }
QGroupBox { background: #ffffff; border: 1px solid #d8e0e7; border-radius: 5px; margin-top: 12px; padding: 10px 10px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QPushButton, QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 6px; }
QPushButton:hover, QToolButton:hover { background: #eaf1f8; border-color: #b5cbe0; }
QPushButton#connectionButton { border-color: #cbd5df; background: #ffffff; }
QPushButton#connectionButton:hover { background: #eaf1f8; border-color: #8cacc9; }
QPushButton:checked, QToolButton:checked { background: #e2effa; border-color: #3975aa; color: #14588d; }
QPushButton:disabled, QToolButton:disabled { color: #87939f; background: transparent; border-color: transparent; }
QPushButton:focus, QToolButton:focus { border: 2px solid #3975aa; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #cbd5df; border-radius: 3px; padding: 5px 7px; selection-background-color: #d2e8fa; selection-color: #163c5d; }
QLineEdit:focus, QComboBox:focus { border-color: #3975aa; }
QLineEdit:disabled, QComboBox:disabled { background: #f0f3f6; color: #667685; }
QTabWidget { background: transparent; }
QTabWidget::pane { border: 1px solid #b9c7d6; background: #ffffff; top: -1px; }
QTabWidget#controllerWorkspaces::pane { border: none; top: 0px; }
QTabBar { background: transparent; font-weight: 600; }
QTabBar::tab { background: #e7ecf2; border: 1px solid #b9c7d6; border-top: 3px solid #b9c7d6; border-top-left-radius: 4px; border-top-right-radius: 4px; padding: 10px 20px; margin-right: 3px; color: #526274; }
QTabBar::tab:selected { background: #ffffff; color: #145e94; border-top-color: #2472aa; border-bottom-color: #ffffff; }
QTabBar::tab:!selected:hover { background: #f3f7fb; }
QTabBar::close-button { image: url("$CLOSE_ICON"); width: 14px; height: 14px; subcontrol-position: right; padding: 3px; }
QTabBar::close-button:hover { background: #e5edf5; border-radius: 3px; }
QPlainTextEdit { background: #ffffff; border: 1px solid #d8e0e7; padding: 5px; font-family: Consolas; font-size: 9pt; }
QTableWidget { background: #ffffff; alternate-background-color: #f5f8fb; border: 1px solid #d8e0e7; selection-background-color: #e1effa; selection-color: #183b58; }
QHeaderView::section { background: #eef2f6; color: #4a5c6d; border: 0; border-bottom: 1px solid #d8e0e7; padding: 7px; }
QMenuBar { background: #edf1f5; padding: 2px 10px; }
QMenuBar::item:selected, QMenu::item:selected { background: #e1effa; color: #183b58; }
QMenu { background: #ffffff; border: 1px solid #cbd5df; }
QMenu::item { padding: 7px 22px; }
QSplitter::handle { background: #e9eef3; }
QScrollArea { border: none; background: #ffffff; }
""".replace("$CLOSE_ICON", (ICON_DIR / "x.svg").as_posix()).replace("$CHECK_ICON", (ICON_DIR / "check.svg").as_posix())



def action_icon(name):
    return QtGui.QIcon(str(ICON_DIR / f"{name}.svg"))


def label(text, role=None):
    widget = QtWidgets.QLabel(text)
    widget.setTextFormat(QtCore.Qt.PlainText)
    if role:
        widget.setProperty("role", role)
    return widget


def group(title):
    widget = QtWidgets.QGroupBox(title)
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setSpacing(10)
    return widget, layout


def icon_button(button, name, icon=None):
    if icon is not None:
        button.setIcon(icon)
    button.setText("")
    button.setAccessibleName(name)
    button.setToolTip(name)
    button.setIconSize(QtCore.QSize(20, 20))
    button.setFixedSize(38, 36)
    if isinstance(button, QtWidgets.QToolButton):
        button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)


class AutoSavePartEditor(PartEditor):
    """Autosave to a fixed cycle identity; never move an active text edit."""

    def __init__(self, controller):
        self._saving = False
        super().__init__(controller)
        self.saveButton.hide()
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self.apply)
        for edit in (self.weight, self.length):
            edit.editingFinished.connect(self._finished)
            edit.returnPressed.connect(edit.clearFocus)
            edit.setToolTip("Saved automatically for the selected cycle. Blank clears the value.")

    def _edited(self):
        self.dirty = True
        self._save_timer.start()

    def editing(self):
        return self.weight.hasFocus() or self.length.hasFocus()

    def _finished(self):
        self.apply()
        QtCore.QTimer.singleShot(0, self.controller.resume_part_follow)

    def can_leave(self):
        return not self.dirty or self.apply()

    def set_entry(self, key):
        changed = key != self.key
        if changed:
            if self.controller._suppress_part_selection or not self.can_leave():
                return False
        self.key = key
        for edit in (self.weight, self.length):
            edit.setEnabled(key is not None)
        if not self.dirty and not self._saving:
            values = self.controller.part_measurements(key) if key else {}
            for field, edit in (("weight_g", self.weight), ("length_mm", self.length)):
                # Keep the caret and partially typed decimal during background saves.
                if changed or not edit.hasFocus():
                    edit.setText(value_text(values.get(field)))
                    edit.setStyleSheet("")
        self.context.setText(f"Cycle {key[2]}" if key else "No cycle selected")
        return True

    def apply(self):
        if not self.dirty:
            return True
        if self.key is None or self._saving:
            return False
        self._save_timer.stop()
        values = {}
        valid = True
        for field, edit in (("weight_g", self.weight), ("length_mm", self.length)):
            try:
                values[field] = optional_number(edit.text(), "Weight" if field == "weight_g" else "Spiral")
                edit.setStyleSheet("")
                edit.setToolTip("Saved automatically for the selected cycle. Blank clears the value.")
            except ValueError:
                edit.setStyleSheet("QLineEdit { border: 1px solid #be4444; }")
                edit.setToolTip("Enter a non-negative number, or leave blank.")
                valid = False
        if not valid:
            return False
        self._saving = True
        try:
            if not self.controller.save_part_measurements(self.key, **values):
                return False
            self.dirty = False
            return True
        finally:
            self._saving = False


class EditableHistoryPanel(HistoryPanel):
    EDITABLE = {2: "machine_id", 4: "material", 5: "mold_temperature_c",
                6: "melt_temperature_c", 7: "injection_speed_mm_s",
                8: "weight_g", 9: "length_mm"}

    def __init__(self, controller):
        self._refreshing = False
        self._pending_cells = []
        self._refresh_queued = False
        super().__init__(controller)
        self.editSettingsButton.hide()
        self.moreButton.hide()
        self.loadButton.clicked.disconnect()
        self.loadButton.clicked.connect(controller.load_next_history)
        self.plotButton.clicked.disconnect()
        self.plotButton.clicked.connect(lambda: controller.plot_history_cycles(self.action_keys()))
        self.table.doubleClicked.disconnect()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked |
                                   QtWidgets.QAbstractItemView.EditKeyPressed |
                                   QtWidgets.QAbstractItemView.AnyKeyPressed)
        self.table.itemChanged.connect(self._cell_changed)
        self.table.itemDelegate().closeEditor.connect(lambda *_: QtCore.QTimer.singleShot(0, self._after_editor))
        # Clicking an action commits the current cell before using its value;
        # the queued itemChanged callback alone would run after clicked().
        for button, action in (
                (self.loadButton, controller.load_next_history),
                (self.plotButton, lambda: controller.plot_history_cycles(self.action_keys())),
                (self.excludeButton, lambda: controller.update_reviews(self.action_keys(), excluded=True)),
                (self.restoreButton, lambda: controller.update_reviews(self.action_keys(), excluded=False)),
                (self.sendEditsButton, lambda: controller.send_pending_edits(self.action_keys(), force=True))):
            button.clicked.disconnect()
            button.clicked.connect(lambda _=False, action=action: self._run_after_edit(action))
        self.search.setMinimumWidth(160)
        self.search.setMaximumWidth(280)
        self.table.verticalHeader().setDefaultSectionSize(36)
        icon_button(self.loadButton, "Load cycles", action_icon("refresh-cw"))
        icon_button(self.plotButton, "Plot selected cycles", action_icon("chart-no-axes-combined"))
        icon_button(self.excludeButton, "Exclude selected cycles", action_icon("ban"))
        icon_button(self.restoreButton, "Restore selected cycles", action_icon("undo-2"))
        icon_button(self.sendEditsButton, "Send edits", action_icon("cloud-upload"))
        self.showExcluded.setText("Excluded")
        self.showExcluded.setToolTip("Show excluded cycles")
        self.status.setText("")
        # Replace the inherited two action rows with one contextual toolbar.
        outer = self.layout()
        for _ in range(2):
            old = outer.takeAt(0).layout()
            while old.count():
                old.takeAt(0)
            old.deleteLater()
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(4)
        self.search.setFixedWidth(240)
        actions.addWidget(self.search)
        actions.addSpacing(12)
        for button in (self.loadButton, self.plotButton, self.excludeButton,
                       self.restoreButton, self.sendEditsButton):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(self.showExcluded)
        outer.insertLayout(0, actions)
        outer.setContentsMargins(0, 0, 0, 0)
        self.refresh()

    def _update_actions(self):
        super()._update_actions()
        self.plotButton.setEnabled(bool(self.action_keys()))
        self.plotButton.setText("")
        self.editSettingsButton.hide()

    def _checked(self, item):
        super()._checked(item)
        self.plotButton.setText("")

    def _cell_changed(self, item):
        if self._refreshing or item.column() not in self.EDITABLE:
            return
        key = item.data(QtCore.Qt.UserRole)
        if key:
            self._pending_cells.append((key, self.EDITABLE[item.column()], item.text()))
            QtCore.QTimer.singleShot(0, self._commit_cells)

    def _commit_cells(self):
        pending, self._pending_cells = self._pending_cells, []
        success = True
        for key, field, value in pending:
            success = bool(self.controller.edit_history_cell(key, field, value)) and success
        if pending:
            self.refresh()
        return success

    def flush_edits(self):
        editor = QtWidgets.QApplication.focusWidget()
        if self.table.state() == QtWidgets.QAbstractItemView.EditingState and editor and self.table.isAncestorOf(editor):
            delegate = self.table.itemDelegate()
            delegate.commitData.emit(editor)
            delegate.closeEditor.emit(editor, QtWidgets.QAbstractItemDelegate.NoHint)
        return self._commit_cells()

    def _run_after_edit(self, action):
        if self.flush_edits():
            action()

    def _after_editor(self):
        if self._refresh_queued:
            self.refresh()

    def refresh(self):
        # New cycles/server results must not destroy an unfinished cell editor.
        if hasattr(self, "table") and self.table.state() == QtWidgets.QAbstractItemView.EditingState:
            self._refresh_queued = True
            return
        self._refresh_queued = False
        self._refreshing = True
        query = self.search.text()
        self.search.blockSignals(True)
        self.search.setText("")
        super().refresh()
        self.search.setText(query)
        self.search.blockSignals(False)
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 0).data(QtCore.Qt.UserRole)
            entry = self.controller.cycle_history[key]
            machine = effective_settings(entry)["machine_id"]
            self.table.item(row, 2).setText(machine)
            self.table.item(row, 2).setToolTip(
                f"{machine}\nRecorded as: {key[0]}" if machine != key[0] else machine)
            for column in range(1, self.table.columnCount()):
                item = self.table.item(row, column)
                flags = item.flags() & ~QtCore.Qt.ItemIsEditable
                if column in self.EDITABLE:
                    flags |= QtCore.Qt.ItemIsEditable
                item.setFlags(flags)
            state = self.table.item(row, 13)
            full = state.text()
            compact = ("Excluded" if entry.get("review", {}).get("excluded") else
                       "Conflict" if entry.get("edit_conflict") else
                       "Incomplete" if entry["capture"]["status"] == "interrupted" else
                       "Pending" if entry.get("local_review_edit") or entry.get("local_measurement_edit") else
                       "Stored" if entry.get("waveform_status") == "stored" else "Local")
            state.setText(compact)
            state.setToolTip(full)
        if query:
            for row in reversed(range(self.table.rowCount())):
                key = self.table.item(row, 0).data(QtCore.Qt.UserRole)
                values = [self.table.item(row, column).text() for column in range(1, self.table.columnCount())]
                if query.lower() not in (" ".join(values) + " " + key[1]).lower():
                    self.table.removeRow(row)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(30)
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.Stretch)
        for column, width in ((0, 30), (1, 165), (3, 65)):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.blockSignals(False)
        self._refreshing = False
        self._update_actions()
        self.plotButton.setText("")
        self.loadButton.setToolTip("Load next 10 cycles" if self.controller._history_next_cursor is not None else "Load / refresh cycles")


class InspectorLayout(QtCore.QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = w = window
        self.mode = "monitor"
        self._legacy = w.takeCentralWidget()
        self._legacy.hide()
        root = QtWidgets.QWidget()
        root.setObjectName("previewRoot")
        body = QtWidgets.QVBoxLayout(root)
        body.setContentsMargins(12, 8, 12, 12)
        body.setSpacing(0)
        w.setCentralWidget(root)
        w.setMinimumSize(1000, 700)
        w.setWindowTitle("Injection monitoring — Preview" if w.preview_mode else "Injection monitoring")

        self.workspaces = QtWidgets.QTabWidget()
        self.workspaces.setObjectName("workspaceBook")
        self.workspaces.setTabsClosable(True)
        self.workspaces.setUsesScrollButtons(True)
        self.tabs = self.workspaces.tabBar()
        self.tabs.setExpanding(False)
        self.tabs.setAccessibleName("Workspaces")
        for title in ("Setup", "Monitor", "History"):
            index = self.workspaces.addTab(self._workspace_page(), title)
            for side in (QtWidgets.QTabBar.LeftSide, QtWidgets.QTabBar.RightSide):
                self.tabs.setTabButton(index, side, None)
        body.addWidget(self.workspaces, 1)

        self.side_toggle = QtWidgets.QToolButton()
        self.side_toggle.setCheckable(True)
        icon_button(self.side_toggle, "Hide inspector", action_icon("panel-right-close"))
        self.side_toggle.toggled.connect(self._sidebar_visibility)

        self.vertical = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.vertical.setChildrenCollapsible(False)
        upper = QtWidgets.QWidget()
        upper_layout = QtWidgets.QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(10)
        self.split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        main_area = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._setup_page())
        work = QtWidgets.QWidget()
        work_layout = QtWidgets.QVBoxLayout(work)
        work_layout.setContentsMargins(0, 0, 0, 0)
        w.workspaceTabs.setCornerWidget(None)
        w.parametersButton.hide()
        w.parametersButton.setShortcut(QtGui.QKeySequence())
        self.side_toggle.setShortcut("Ctrl+Alt+B")
        w.workspaceTabs.tabBar().hide()
        w.workspaceTabs.setObjectName("controllerWorkspaces")
        work_layout.addWidget(w.workspaceTabs, 1)
        self.pages.addWidget(work)
        main_layout.addWidget(self.pages)
        self.split.addWidget(main_area)

        sidebar_content = QtWidgets.QWidget()
        side_layout = QtWidgets.QVBoxLayout(sidebar_content)
        side_layout.setContentsMargins(12, 0, 0, 0)
        self.session_group, session_layout = group("Session settings")
        session_layout.addWidget(w.runSetup)
        w.runSetup.hint.hide()
        self.part_group, part_layout = group("Part measurements")
        self.cycle_selector = QtWidgets.QComboBox()
        self.cycle_selector.setAccessibleName("Selected cycle")
        self.cycle_selector.currentIndexChanged.connect(self._select_part)
        part_layout.addWidget(self.cycle_selector)
        part_layout.addWidget(w.partEditor)
        w.partEditor.context.hide()
        w.partEditor.saveButton.hide()
        side_layout.addWidget(self.session_group)
        side_layout.addWidget(self.part_group)
        side_layout.addStretch()
        self.sidebar = QtWidgets.QScrollArea()
        self.sidebar.setWidgetResizable(True)
        self.sidebar.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.sidebar.setWidget(sidebar_content)
        self.sidebar.setMinimumWidth(240)
        self.sidebar.setMaximumWidth(300)
        self.split.addWidget(self.sidebar)
        self.split.setStretchFactor(0, 1)
        self._toolbar()
        upper_layout.addWidget(self.toolbar)
        upper_layout.addWidget(self.split, 1)
        self.vertical.addWidget(upper)
        log_container = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 8, 0, 0)
        w.messagesBox.setMinimumHeight(45)
        w.messagesBox.setMaximumHeight(16777215)
        w.messagesBox.setReadOnly(True)
        w.messagesBox.setMaximumBlockCount(500)
        log_layout.addWidget(w.messagesBox)
        log_container.setMinimumHeight(65)
        self.vertical.addWidget(log_container)
        self.vertical.setStretchFactor(0, 1)
        self.vertical.setSizes([750, 80])
        self._expand_forms()
        self.split.setSizes([1200, 250])
        self._menus()
        self.workspaces.currentChanged.connect(self._tab_changed)
        self.workspaces.tabCloseRequested.connect(self.close_tab)
        w.workspaceTabs.currentChanged.connect(self._workspace_changed)
        w.historyPanel.table.itemSelectionChanged.connect(self.refresh_selection)
        self.navigate("monitor")

    def _workspace_page(self):
        page = QtWidgets.QWidget()
        page.setObjectName("workspacePage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        return page

    def _toolbar(self):
        w = self.window
        self.toolbar = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.setup_actions)
        self.monitor_actions = QtWidgets.QWidget()
        commands = QtWidgets.QHBoxLayout(self.monitor_actions)
        commands.setContentsMargins(0, 0, 0, 0)
        commands.setSpacing(4)
        for button, name, glyph in (
                (w.startButton, "Start recording", "play"),
                (w.stopButton, "Stop recording", "square"),
                (w.nextButton, "New session", "skip-forward"),
                (w.saveSessionButton, "Save session", "save"),
                (w.sendSessionButton, "Send session", "cloud-upload")):
            icon_button(button, name, action_icon(glyph))
            commands.addWidget(button)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFixedHeight(24)
        commands.addSpacing(8)
        commands.addWidget(separator)
        row.addWidget(self.monitor_actions)
        self.plot_tools = QtWidgets.QWidget()
        plot_row = QtWidgets.QHBoxLayout(self.plot_tools)
        plot_row.setContentsMargins(0, 0, 0, 0)
        plot_row.setSpacing(4)
        for button, name, glyph in (
                (w.homeButton, "Fit plot", "house"),
                (w.zoomButton, "Zoom", "zoom-in"),
                (w.panButton, "Pan", "move"),
                (w.cursorButton, "Cursors", None),
                (w.hideGhostsButton, "Hide previous cycles", "eye")):
            icon_button(button, name, action_icon(glyph) if glyph else None)
            plot_row.addWidget(button)
        w.readoutBox.setFixedHeight(36)
        plot_row.addWidget(w.readoutBox)
        row.addWidget(self.plot_tools)
        row.addStretch()
        row.addWidget(self.side_toggle)

    def _setup_page(self):
        w = self.window
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setup_actions = QtWidgets.QWidget()
        actions = QtWidgets.QHBoxLayout(self.setup_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        self.connection_button = QtWidgets.QPushButton()
        self.connection_button.setObjectName("connectionButton")
        self.connection_button.setFixedSize(112, 36)
        self.connection_button.clicked.connect(self._toggle_connection)
        actions.addWidget(self.connection_button)
        actions.addSpacing(12)
        w.findDeviceButton.hide()
        w.removeDeviceButton.hide()
        editor = DaqConfigWindow(w, initial_config=w.active_configuration())
        editor.setModal(False)
        w.ModuleSelectWin = self.config_editor = editor
        self.config_tabs = editor.tabs
        layout.addWidget(self.config_tabs, 1)
        # Reuse the validated configuration controls, grouped by working area.
        editor._source_pages = [self.config_tabs.widget(i) for i in range(self.config_tabs.count())]
        self.config_tabs.clear()
        sections = (
            ("DAQ", (editor.timeEdit, editor.triggerModeCombo, editor.channelTable, editor.digitalTable)),
            ("Mold sensors", (editor.moldAxesCombo, editor.tempDegPerVoltEdit, editor.kistlerS0Edit)),
            ("Machine data", (editor.machineLayoutCombo, editor.machineTable)),
            ("Display", (editor.pointsEdit,)),
        )
        for title, controls in sections:
            content = QtWidgets.QWidget()
            content_layout = QtWidgets.QVBoxLayout(content)
            content_layout.setSpacing(12)
            for control in controls:
                section = control.parentWidget()
                section.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
                content_layout.addWidget(section)
                section.show()
            content_layout.addStretch()
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            self.config_tabs.addTab(scroll, title)
        self.config_tabs.setCurrentIndex(0)
        # Upload is a real configuration option; machine belongs to Monitor.
        cloud_group = editor.mqttCheckBox.parentWidget()
        for child in cloud_group.findChildren(QtWidgets.QWidget):
            if child is not editor.mqttCheckBox:
                child.hide()
        editor.mqttCheckBox.setText("Automatic upload")
        if w.preview_mode:
            editor.mqttCheckBox.setChecked(False)
            editor.mqttCheckBox.setEnabled(False)
            cloud_group.hide()
        else:
            display_layout = self.config_tabs.widget(3).widget().layout()
            display_layout.insertWidget(display_layout.count() - 1, cloud_group)
            cloud_group.show()
        icon_button(editor.okButton, "Save configuration", action_icon("save"))
        icon_button(editor.cancelButton, "Discard configuration changes", action_icon("undo-2"))
        editor.cancelButton.clicked.disconnect()
        editor.cancelButton.clicked.connect(self.reset_configuration)
        editor.configSignal.connect(w._stage_configuration)
        actions.addWidget(editor.okButton)
        actions.addWidget(editor.cancelButton)
        editor.ensurePolished()
        self._fit_configuration_tables()
        self.config_tabs.currentChanged.connect(
            lambda _: QtCore.QTimer.singleShot(0, self._fit_configuration_tables))
        w.configurationButton.hide()
        self.refresh_device_control()
        return page

    def _fit_configuration_tables(self):
        editor = self.config_editor
        combos = list(editor.channel_type_combos.values()) + list(editor.digital_combos.values())
        for combo in combos:
            combo.ensurePolished()
        channel_width = max(max(combo.minimumWidth(), combo.sizeHint().width()) for combo in combos) + 2
        for table in (editor.channelTable, editor.digitalTable, editor.machineTable):
            table.ensurePolished()
            header = table.horizontalHeader()
            header.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
            header.setMinimumSectionSize(80 if table is editor.machineTable else 115)
            if table is not editor.machineTable:
                for column in range(table.columnCount()):
                    table.setColumnWidth(column, channel_width)
            table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            table.resizeRowsToContents()
            for row in range(table.rowCount()):
                table.setRowHeight(row, max(36, table.rowHeight(row)))
            # Fit only the headers, data rows and frame. Reserving space for a
            # hidden scrollbar produced the apparent extra bottom row.
            table.setFixedHeight(max(header.height(), header.sizeHint().height()) +
                                 sum(table.rowHeight(i) for i in range(table.rowCount())) +
                                 2 * table.frameWidth())
            table.setFixedWidth(table.verticalHeader().width() +
                                sum(table.columnWidth(i) for i in range(table.columnCount())) +
                                2 * table.frameWidth())

    def _toggle_connection(self):
        if self.window.daq_connected:
            self.window.rem_devs()
        else:
            self.window.find_device()

    def refresh_device_control(self):
        connected = self.window.daq_connected
        self.connection_button.setText("Disconnect" if connected else "Connect")
        self.connection_button.setAccessibleName("Disconnect DAQ" if connected else "Connect DAQ")
        self.connection_button.setToolTip("Disconnect DAQ" if connected else "Connect DAQ")
        self.connection_button.setEnabled(not self.window.desktop_busy())

    def reset_configuration(self):
        self.config_editor.initial_config = deepcopy(self.window._configuration_draft or self.window.active_configuration())
        self.config_editor.loadDefaults()
        self.refresh_configuration()

    def _expand_forms(self):
        w = self.window
        for form in w.runSetup.findChildren(QtWidgets.QFormLayout) + w.partEditor.findChildren(QtWidgets.QFormLayout):
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            form.setVerticalSpacing(10)
        for editor in (w.runSetup.machine, w.runSetup.material, w.runSetup.temperature,
                       w.runSetup.melt, w.runSetup.speed, w.partEditor.weight, w.partEditor.length):
            editor.setMinimumSize(80, 34)
            editor.setMaximumSize(16777215, 38)
            editor.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        for item in w.runSetup.findChildren(QtWidgets.QLabel) + w.partEditor.findChildren(QtWidgets.QLabel):
            if item.minimumWidth() == item.maximumWidth():
                item.setMinimumWidth(90)
                item.setMaximumWidth(16777215)
        self._detail_columns(False)

    def _menus(self):
        w = self.window
        w.menubar.clear()
        w.menubar.show()
        file_menu = w.menubar.addMenu("File")
        self.save_action = file_menu.addAction("Save session…", w.save_Session, QtGui.QKeySequence.Save)
        self.send_action = file_menu.addAction("Send session", w.send_Session_to_cloud)
        file_menu.addSeparator()
        file_menu.addAction("Close", w.close, QtGui.QKeySequence("Ctrl+Q"))
        view = w.menubar.addMenu("View")
        columns = view.addAction("Duration and peaks")
        columns.setCheckable(True)
        columns.toggled.connect(self._detail_columns)

    def _detail_columns(self, visible):
        for column in (10, 11, 12):
            self.window.historyPanel.table.setColumnHidden(column, not visible)

    def _sync_tabs(self):
        self.workspaces.blockSignals(True)
        source = self.window.workspaceTabs
        desired = ["Setup", "Monitor", "History"] + [source.tabText(i) for i in range(2, source.count())]
        while self.workspaces.count() > len(desired):
            index = self.workspaces.count() - 1
            removed = self.workspaces.widget(index)
            if removed.isAncestorOf(self.vertical):
                self.vertical.setParent(self.workspaces)
                self.vertical.hide()
            self.workspaces.removeTab(index)
            removed.deleteLater()
        for index, title in enumerate(desired):
            if index >= self.workspaces.count():
                self.workspaces.addTab(self._workspace_page(), title)
            else:
                self.workspaces.setTabText(index, title)
        self.workspaces.blockSignals(False)

    def navigate(self, mode):
        index = {"setup": 0, "monitor": 1, "history": 2}[mode]
        if self.workspaces.currentIndex() == index:
            self._tab_changed(index)
        else:
            self.workspaces.setCurrentIndex(index)

    def _tab_changed(self, index):
        # Preserve the controller's Monitor=0 / History=1 indices. The native
        # outer tab owns a full white pane, including its toolbar and inspector.
        self.workspaces.widget(index).layout().addWidget(self.vertical)
        self.vertical.show()
        self.mode = "setup" if index == 0 else "history" if index == 2 else "monitor" if index == 1 else "comparison"
        self.pages.setCurrentIndex(0 if index == 0 else 1)
        if index == 0:
            QtCore.QTimer.singleShot(0, self._fit_configuration_tables)
        self.toolbar.setVisible(index != 2)
        self.setup_actions.setVisible(index == 0)
        self.monitor_actions.setVisible(index == 1)
        self.plot_tools.setVisible(index != 0 and index != 2)
        if index:
            self.window.workspaceTabs.setCurrentIndex(index - 1)
        if index >= 3:
            view = self.window.workspaceTabs.widget(index - 1)
            if hasattr(view, "cycle_keys"):
                self.window.select_comparison_part(view)
        elif index == 1:
            self.window.follow_current_part()
        elif index == 2:
            key = self.window.historyPanel.selected_key()
            if key:
                self.window.partEditor.set_entry(key)
        self._sidebar_visibility()

    def _workspace_changed(self, index):
        self._sync_tabs()
        self.workspaces.blockSignals(True)
        self.workspaces.setCurrentIndex(index + 1)
        self.workspaces.blockSignals(False)
        self._tab_changed(index + 1)

    def close_tab(self, index):
        if index < 3:
            return
        self.window.close_workspace_tab(index - 1)
        self._sync_tabs()
        self._workspace_changed(self.window.workspaceTabs.currentIndex())

    def _sidebar_visibility(self, *_):
        available = self.mode in ("monitor", "comparison")
        self.side_toggle.setVisible(available)
        self.side_toggle.setEnabled(available)
        hidden = self.side_toggle.isChecked()
        self.sidebar.setVisible(available and not hidden)
        self.side_toggle.setToolTip("Show inspector" if hidden else "Hide inspector")
        self.side_toggle.setIcon(action_icon("panel-right-open" if hidden else "panel-right-close"))
        self.session_group.setVisible(self.mode == "monitor")
        self.part_group.setVisible(available)

    def _select_part(self, _):
        key = self.cycle_selector.currentData()
        self.window._pending_follow_key = None
        if key and self.window.partEditor.set_entry(key):
            self.window.historyPanel.select_key(key)
        self.refresh_selection()

    def refresh_selection(self):
        w = self.window
        self.cycle_selector.blockSignals(True)
        self.cycle_selector.clear()
        for key in reversed(w._part_drafts):
            if key not in w.cycle_history:
                self.cycle_selector.addItem(f"{key[2]} · {key[0]}", key)
        entries = sorted(w.cycle_history.items(), key=lambda item: int(item[1]["capture"]["first_time_ns"]), reverse=True)
        for key, entry in entries:
            if entry["capture"]["mode"] == "cycle" and not entry.get("review", {}).get("excluded"):
                self.cycle_selector.addItem(f"{key[2]} · {effective_settings(entry)['machine_id']}", key)
        # QVariant compares Python tuple wrappers by object identity. A live
        # draft and its completed record have equal keys but different tuples.
        selected = next((i for i in range(self.cycle_selector.count())
                         if self.cycle_selector.itemData(i) == w.partEditor.key), -1)
        self.cycle_selector.setCurrentIndex(selected)
        self.cycle_selector.blockSignals(False)

    def refresh_configuration(self):
        self.config_tabs.setEnabled(not self.window.desktop_busy())
        self.config_editor.okButton.setEnabled(not self.window.desktop_busy())
        self.config_editor.cancelButton.setEnabled(not self.window.desktop_busy())

    def refresh_summary(self):
        self.session_group.setTitle("Session settings")
