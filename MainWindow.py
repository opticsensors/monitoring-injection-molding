# -*- coding: utf-8 -*-
# Created by: PyQt5 UI code generator 5.9.2


from PyQt5 import QtCore, QtGui, QtWidgets

from graphswidget import GraphsWidget
from plot_icons import home_icon, zoom_icon, pan_icon, measure_icon

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(621, 399)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/icons/eurecat.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.frame_4 = QtWidgets.QFrame(self.centralwidget)
        self.frame_4.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_4.setObjectName("frame_4")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.frame_4)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.frame = QtWidgets.QFrame(self.frame_4)
        self.frame.setMaximumSize(QtCore.QSize(16777215, 60))
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.gridLayout = QtWidgets.QGridLayout(self.frame)
        self.gridLayout.setObjectName("gridLayout")

        # Built-in theme icons for the session-control buttons (no image files needed)
        style = MainWindow.style()

        # ---- Single row: setup/device buttons then square session controls ----
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")

        # Setup / device buttons: same 40 px height as the square buttons
        self.configurationButton = QtWidgets.QPushButton(self.frame)
        self.configurationButton.setMinimumSize(QtCore.QSize(115, 40))
        self.configurationButton.setMaximumSize(QtCore.QSize(115, 40))
        self.configurationButton.setObjectName("configurationButton")
        self.horizontalLayout_3.addWidget(self.configurationButton)
        self.findDeviceButton = QtWidgets.QPushButton(self.frame)
        self.findDeviceButton.setEnabled(False)
        self.findDeviceButton.setMinimumSize(QtCore.QSize(115, 40))
        self.findDeviceButton.setMaximumSize(QtCore.QSize(115, 40))
        self.findDeviceButton.setObjectName("findDeviceButton")
        self.horizontalLayout_3.addWidget(self.findDeviceButton)
        self.removeDeviceButton = QtWidgets.QPushButton(self.frame)
        self.removeDeviceButton.setEnabled(False)
        self.removeDeviceButton.setMinimumSize(QtCore.QSize(115, 40))
        self.removeDeviceButton.setMaximumSize(QtCore.QSize(115, 40))
        self.removeDeviceButton.setObjectName("removeDeviceButton")
        self.horizontalLayout_3.addWidget(self.removeDeviceButton)

        # Session controls: square, icon-only buttons
        self.startButton = QtWidgets.QPushButton(self.frame)
        self.startButton.setEnabled(False)
        self.startButton.setMinimumSize(QtCore.QSize(40, 40))
        self.startButton.setMaximumSize(QtCore.QSize(40, 40))
        self.startButton.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self.startButton.setIconSize(QtCore.QSize(22, 22))
        self.startButton.setObjectName("startButton")
        self.horizontalLayout_3.addWidget(self.startButton)
        self.nextButton = QtWidgets.QPushButton(self.frame)
        self.nextButton.setEnabled(False)
        self.nextButton.setMinimumSize(QtCore.QSize(40, 40))
        self.nextButton.setMaximumSize(QtCore.QSize(40, 40))
        self.nextButton.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaSkipForward))
        self.nextButton.setIconSize(QtCore.QSize(22, 22))
        self.nextButton.setObjectName("nextButton")
        self.horizontalLayout_3.addWidget(self.nextButton)
        self.stopButton = QtWidgets.QPushButton(self.frame)
        self.stopButton.setEnabled(False)
        self.stopButton.setMinimumSize(QtCore.QSize(40, 40))
        self.stopButton.setMaximumSize(QtCore.QSize(40, 40))
        self.stopButton.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaStop))
        self.stopButton.setIconSize(QtCore.QSize(22, 22))
        self.stopButton.setObjectName("stopButton")
        self.horizontalLayout_3.addWidget(self.stopButton)
        self.saveSessionButton = QtWidgets.QPushButton(self.frame)
        self.saveSessionButton.setEnabled(False)
        self.saveSessionButton.setMinimumSize(QtCore.QSize(40, 40))
        self.saveSessionButton.setMaximumSize(QtCore.QSize(40, 40))
        self.saveSessionButton.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.saveSessionButton.setIconSize(QtCore.QSize(22, 22))
        self.saveSessionButton.setObjectName("saveSessionButton")
        self.horizontalLayout_3.addWidget(self.saveSessionButton)

        # Plot tools (matplotlib-style): Home / Zoom / Pan / Time cursors + readout.
        # Wider gap so they read as a separate group. All start disabled; they are
        # only usable while the plot is still (not following live data). The icons
        # are drawn as black line art (see plot_icons.py) to match matplotlib's
        # navigation toolbar; Qt greys them out automatically when disabled.
        self.horizontalLayout_3.addSpacing(30)
        toolIconSize = QtCore.QSize(22, 22)
        self.homeButton = QtWidgets.QPushButton(self.frame)
        self.homeButton.setEnabled(False)
        self.homeButton.setMinimumSize(QtCore.QSize(40, 40))
        self.homeButton.setMaximumSize(QtCore.QSize(40, 40))
        self.homeButton.setIcon(home_icon())
        self.homeButton.setIconSize(toolIconSize)
        self.homeButton.setObjectName("homeButton")
        self.horizontalLayout_3.addWidget(self.homeButton)
        self.zoomButton = QtWidgets.QPushButton(self.frame)
        self.zoomButton.setEnabled(False)
        self.zoomButton.setCheckable(True)
        self.zoomButton.setMinimumSize(QtCore.QSize(40, 40))
        self.zoomButton.setMaximumSize(QtCore.QSize(40, 40))
        self.zoomButton.setIcon(zoom_icon())
        self.zoomButton.setIconSize(toolIconSize)
        self.zoomButton.setObjectName("zoomButton")
        self.horizontalLayout_3.addWidget(self.zoomButton)
        self.panButton = QtWidgets.QPushButton(self.frame)
        self.panButton.setEnabled(False)
        self.panButton.setCheckable(True)
        self.panButton.setMinimumSize(QtCore.QSize(40, 40))
        self.panButton.setMaximumSize(QtCore.QSize(40, 40))
        self.panButton.setIcon(pan_icon())
        self.panButton.setIconSize(toolIconSize)
        self.panButton.setObjectName("panButton")
        self.horizontalLayout_3.addWidget(self.panButton)
        self.cursorButton = QtWidgets.QPushButton(self.frame)
        self.cursorButton.setEnabled(False)
        self.cursorButton.setCheckable(True)
        self.cursorButton.setMinimumSize(QtCore.QSize(40, 40))
        self.cursorButton.setMaximumSize(QtCore.QSize(40, 40))
        self.cursorButton.setIcon(measure_icon())
        self.cursorButton.setIconSize(toolIconSize)
        self.cursorButton.setObjectName("cursorButton")
        self.horizontalLayout_3.addWidget(self.cursorButton)
        # Blank space (as between the Save and Home icons) separating the tools
        # from the computed Δt / ΔP readout.
        self.horizontalLayout_3.addSpacing(30)
        # Readout box: cycle number + Δt / ΔP cursor measurements. A bordered
        # frame that hugs its content - only as wide as the three readings need,
        # with a small fixed gap between them and no blank filler. A trailing
        # stretch in the toolbar keeps it left-placed.
        self.readoutBox = QtWidgets.QFrame(self.frame)
        self.readoutBox.setObjectName("readoutBox")
        self.readoutBox.setFixedHeight(40)
        self.readoutBox.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                      QtWidgets.QSizePolicy.Fixed)
        self.readoutBox.setStyleSheet(
            "QFrame#readoutBox {"
            " border: 1px solid #9a9a9a;"
            " border-radius: 4px;"
            " background-color: palette(button);"
            "}")
        readoutFont = QtGui.QFont()
        readoutFont.setPointSize(10)
        readoutLayout = QtWidgets.QHBoxLayout(self.readoutBox)
        readoutLayout.setContentsMargins(12, 0, 12, 0)
        readoutLayout.setSpacing(22)  # gap between the three readings
        # Cycle number, then Δt, then ΔP - laid out left to right, tight.
        self.cycleReadoutLabel = QtWidgets.QLabel(self.readoutBox)
        self.cycleReadoutLabel.setFont(readoutFont)
        self.cycleReadoutLabel.setObjectName("cycleReadoutLabel")
        self.deltaTLabel = QtWidgets.QLabel(self.readoutBox)
        self.deltaTLabel.setFont(readoutFont)
        self.deltaTLabel.setObjectName("deltaTLabel")
        self.deltaPLabel = QtWidgets.QLabel(self.readoutBox)
        self.deltaPLabel.setFont(readoutFont)
        self.deltaPLabel.setObjectName("deltaPLabel")
        readoutLayout.addWidget(self.cycleReadoutLabel)
        readoutLayout.addWidget(self.deltaTLabel)
        readoutLayout.addWidget(self.deltaPLabel)
        self.horizontalLayout_3.addWidget(self.readoutBox)
        self.horizontalLayout_3.addStretch(1)

        self.gridLayout.addLayout(self.horizontalLayout_3, 0, 0, 1, 1)
        self.gridLayout_5.addWidget(self.frame, 0, 0, 1, 1)
        self.frame_3 = QtWidgets.QFrame(self.frame_4)
        self.frame_3.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_3.setObjectName("frame_3")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.frame_3)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.plotTabs = QtWidgets.QTabWidget(self.frame_3)
        self.plotTabs.setObjectName("plotTabs")
        self.GraphArea = GraphsWidget()
        self.GraphArea.setEnabled(True)
        self.GraphArea.setObjectName("GraphArea")
        self.GraphAreaMachine = GraphsWidget()
        self.GraphAreaMachine.setEnabled(True)
        self.GraphAreaMachine.setObjectName("GraphAreaMachine")
        self.plotTabs.addTab(self.GraphArea, "Mold sensors")
        self.plotTabs.addTab(self.GraphAreaMachine, "Machine data")
        self.gridLayout_3.addWidget(self.plotTabs, 0, 0, 1, 1)
        # Let the plot area expand to fill any spare vertical space
        sizePolicy_plots = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                                 QtWidgets.QSizePolicy.Expanding)
        self.frame_3.setSizePolicy(sizePolicy_plots)
        self.gridLayout_5.addWidget(self.frame_3, 1, 0, 1, 1)
        self.frame_2 = QtWidgets.QFrame(self.frame_4)
        self.frame_2.setMaximumSize(QtCore.QSize(16777215, 110))
        self.frame_2.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_2.setObjectName("frame_2")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.frame_2)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.messagesBox = QtWidgets.QPlainTextEdit(self.frame_2)
        self.messagesBox.setMinimumSize(QtCore.QSize(0, 90))
        self.messagesBox.setMaximumSize(QtCore.QSize(16777215, 100))
        self.messagesBox.setObjectName("messagesBox")
        self.gridLayout_2.addWidget(self.messagesBox, 0, 0, 1, 1)
        self.gridLayout_5.addWidget(self.frame_2, 2, 0, 1, 1)
        # Give all spare vertical height to the plot row (row 1), not the
        # fixed-height button (row 0) / messages (row 2) rows
        self.gridLayout_5.setRowStretch(0, 0)
        self.gridLayout_5.setRowStretch(1, 1)
        self.gridLayout_5.setRowStretch(2, 0)
        self.gridLayout_4.addWidget(self.frame_4, 0, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 621, 18))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Monitoring Sensor System"))
        self.configurationButton.setText(_translate("MainWindow", "Configuration"))
        self.findDeviceButton.setText(_translate("MainWindow", "Find Device"))
        self.removeDeviceButton.setText(_translate("MainWindow", "Remove Devices"))
        # Session-control buttons are icon-only (square) - name them via tooltips
        self.startButton.setToolTip(_translate("MainWindow", "Start"))
        self.nextButton.setToolTip(_translate("MainWindow", "Next"))
        self.stopButton.setToolTip(_translate("MainWindow", "Stop"))
        self.saveSessionButton.setToolTip(_translate("MainWindow", "Save Session"))
        # Plot-tool buttons are icon-only (matplotlib-style, see plot_icons.py);
        # they are enabled only while the plot is still. Name them via tooltips.
        self.homeButton.setToolTip(_translate("MainWindow", "Home - reset the view to the automatic range"))
        self.zoomButton.setToolTip(_translate("MainWindow", "Zoom - drag a rectangle to zoom in (available when the plot is not updating)"))
        self.panButton.setToolTip(_translate("MainWindow", "Pan - drag the plot to move around (available when the plot is not updating)"))
        self.cursorButton.setToolTip(_translate("MainWindow", "Time cursors - left-click: t1 line, right-click: t2 line, middle-click: clear. Drag a line to fine-tune."))
        self.cycleReadoutLabel.setText(_translate("MainWindow", "Cycle: --"))
        self.deltaTLabel.setText(_translate("MainWindow", "Δt: --"))
        self.deltaPLabel.setText(_translate("MainWindow", "ΔP: --"))
        self.readoutBox.setToolTip(_translate("MainWindow",
            "Cycle = current injection-cycle number.\n"
            "Δt = time between the two cursor lines.\n"
            "ΔP = difference between the two plotted cavity-pressure curves where the later line crosses them (always positive).\n"
            "Requires both lines and at least two pressure curves on screen."))
