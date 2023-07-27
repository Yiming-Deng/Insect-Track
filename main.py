import sys
import os
import onnxruntime

from PyCameraList.camera_device import list_video_devices

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QSize, QUrl, QTime, QSizeF
from PyQt5.QtGui import QPixmap, QCursor, QMouseEvent, QPen, QColor
from PyQt5.QtWidgets import QApplication, QFrame, QSlider, QGraphicsScene, QHeaderView, QTableWidgetItem, QTableWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem

from qfluentwidgets import (NavigationItemPosition, MessageBox, isDarkTheme, setTheme, Theme, setThemeColor,
                            StateToolTip, InfoBar, InfoBarPosition, MessageBox)
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar

from Insect import Ui_MainWindow
from track import OpenCamera, VideoProcess

import frozen_dir

base = frozen_dir.app_path()

HEIGHT = 601
WIDTH = 801
QCOLOR_LIST = [
    QColor(255, 0, 0),
    QColor(0, 255, 0),
    QColor(0, 0, 255),
    QColor(255, 175, 0),
    QColor(255, 0, 255),
    QColor(0, 255, 255)
]


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow, FramelessWindow):
    view_signal = QtCore.pyqtSignal(QPixmap)
    camera_opened_signal = QtCore.pyqtSignal(int)
    video_frame_signal = QtCore.pyqtSignal(int, int)
    finish_video_signal = QtCore.pyqtSignal(dict, dict)
    finish_camera_signal = QtCore.pyqtSignal(dict, dict)

    def __init__(self):
        super().__init__()
        '''
        the part of mainwindow
        '''
        self.setupUi(self)
        self.setTitleBar(StandardTitleBar(self))
        # use dark theme mode
        # setTheme(Theme.DARK)
        # change the theme color
        setThemeColor('#0078d4')
        # initialize layout
        self.initLayout()
        # add items to navigation interface
        self.initNavigation()
        # init mainwindow (position, title and so on)
        self.initWindow()
        '''
        the part of camera and video
        '''
        self.cameraInit()
        self.videoInit()
        self.cameraLabel.setScaledContents(True)
        '''
        the part of track
        '''
        self.trackSettingInit()

    def cameraInit(self):
        # tip
        self.cameraStateTip = None

        # connect function
        self.cameraOpenButton.clicked.connect(self.openAndCloseCamera)
        self.view_signal.connect(self.viewCamera)
        self.camera_opened_signal.connect(self.cameraOpened)

        # multithreading to open camera
        self.camera_thread = OpenCamera(self.view_signal, self.camera_opened_signal, self.finish_camera_signal)

        # choose camera
        cameras = list(dict(list_video_devices()).values())
        self.cameraChooseBox.addItems(cameras)
        self.cameraChooseBox.setCurrentIndex(0)

        # choose insect
        insect = ['cockroach', 'ant']
        self.insectChooseBox.addItems(insect)
        self.insectChooseBox.setCurrentIndex(0)

        # style of camera window
        self.cameraLabel.setFrameShape(QtWidgets.QFrame.Box)
        self.cameraLabel.setFrameShadow(QtWidgets.QFrame.Raised)
        self.cameraLabel.setFrameShape(QFrame.Box)
        self.cameraLabel.setStyleSheet(
            'border-width: 1px;border-style: solid;border-color: rgb(0, 0, 0);background-color: rgb(255, 255, 255);')

    def trackSettingInit(self):
        # track switch setting
        self.trackSwitchButton.checkedChanged.connect(self.trackSwitchChanged)
        self.trackSwitchButton.setEnabled(False)

        # model path setting
        self.modelLineEdit.setClearButtonEnabled(True)
        self.modelLineEdit.setPlaceholderText("Choose insect then press \"Default Path\"")
        self.modelDefaultPathButton.clicked.connect(self.setModelDefaultPath)
        self.modelPathButton.clicked.connect(self.loadModel)

        # save setting
        self.videoSaveLineEdit.setClearButtonEnabled(True)
        self.videoSaveLineEdit.setPlaceholderText("Select video save path (folder)")
        self.videoSavePathButton.clicked.connect(self.setVideoSavePath)
        self.saveSwitchButton.checkedChanged.connect(self.saveSwitchchanged)

        # count setting
        self.areaTableWidget.setWordWrap(False)
        self.areaTableWidget.setRowCount(0)
        self.areaTableWidget.setColumnCount(3)
        self.areaTableWidget.verticalHeader().hide()
        self.areaTableWidget.setHorizontalHeaderLabels(['Area', 'num', 'time(s)'])
        self.areaTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.areaTableWidget.setEditTriggers(QTableWidget.NoEditTriggers)

        self.minCameraSpinBox.setValue(5)
        self.minCameraSpinBox.setSingleStep(0.5)
        self.maxCameraSpinBox.setValue(3)
        self.maxCameraSpinBox.setSingleStep(0.5)

        self.add_camera_event = False
        self.show_camera_rect = True
        self.camera_temp_rect = None
        self.camera_area_dict = {}

        self.cameraLabel.installEventFilter(self)

        self.addAreaButton.clicked.connect(self.addCameraArea)
        self.deleteAreaButton.clicked.connect(self.deleteCameraArea)
        self.showAreaButton.clicked.connect(self.showCameraArea)

        self.finish_camera_signal.connect(self.finishCameraTrack)

    def videoInit(self):
        # choose video setting
        self.videoChoosePathEdit.setClearButtonEnabled(True)
        self.videoChoosePathEdit.setPlaceholderText("Select video to detect and track")
        self.videoChooseButton.clicked.connect(self.setVideoChoosePath)

        # choose insect
        insect = ['cockroach', 'ant']
        self.videoInsectChooseBox.addItems(insect)
        self.videoInsectChooseBox.setCurrentIndex(0)

        # model setting
        self.videoModelLineEdit.setClearButtonEnabled(True)
        self.videoModelLineEdit.setPlaceholderText("Choose insect then press \"Default Path\"")
        self.videoModelDefaultPathButton.clicked.connect(self.setVideoModelDefaultPath)
        self.videoModelPathButton.clicked.connect(self.loadModel)

        # open video and process
        self.player = QMediaPlayer()
        video_widget = QGraphicsVideoItem()
        video_widget.setSize(QSizeF(796, 597))
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 796, 597)
        self.graphicsView.setScene(self.scene)

        self.scene.addItem(video_widget)

        self.player.setVideoOutput(video_widget)
        self.scene.installEventFilter(self)

        # video slider
        self.videoSlider.setValue(0)
        self.videoSlider.setMinimum(0)
        self.player.positionChanged.connect(self.getVideoTime)
        self.videoSlider.sliderPressed.connect(self.player.pause)
        self.videoSlider.sliderReleased.connect(self.player.play)
        self.videoSlider.sliderMoved.connect(self.videoChangetime)

        # video volume
        volume_icon = QApplication.style().standardIcon(68)
        self.volumeLabel.setPixmap(volume_icon.pixmap(volume_icon.actualSize(QSize(64, 64))))
        self.volumeSlider.setValue(50)
        self.volumeSlider.setTickInterval(10)
        self.volumeSlider.setTickPosition(QSlider.TicksBelow)
        self.volumeSlider.valueChanged.connect(self.videoChangeVolume)

        # open video
        self.videoOpenButton.clicked.connect(self.openVideoFile)
        self.video_thread = VideoProcess(self.video_frame_signal, self.finish_video_signal)

        # adjust video progress
        self.advanceButton.clicked.connect(self.advanceVideo)
        self.backButton.clicked.connect(self.backVideo)

        # play and pause
        self.videoControlButton.setEnabled(False)
        self.advanceButton.setEnabled(False)
        self.backButton.setEnabled(False)
        self.videoSlider.setEnabled(False)
        self.video_play = False
        self.videoControlButton.setIcon(self.style().standardIcon(61))
        self.videoControlButton.clicked.connect(self.controlVideo)

        # video track
        self.videoTrackSwitchButton.checkedChanged.connect(self.videoTrack)
        self.video_frame_signal.connect(self.updateProgress)
        self.finish_video_signal.connect(self.finishVideoTrack)

        # count setting
        self.areaVideoTableWidget.setWordWrap(False)
        self.areaVideoTableWidget.setRowCount(0)
        self.areaVideoTableWidget.setColumnCount(3)
        self.areaVideoTableWidget.verticalHeader().hide()
        self.areaVideoTableWidget.setHorizontalHeaderLabels(['Area', 'num', 'time(s)'])
        self.areaVideoTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.areaVideoTableWidget.setEditTriggers(QTableWidget.NoEditTriggers)

        self.minSpinBox.setValue(5)
        self.minSpinBox.setSingleStep(0.5)
        self.maxSpinBox.setValue(3)
        self.maxSpinBox.setSingleStep(0.5)

        self.temp_rect = None
        self.add_event = False
        self.show_rect = True
        self.video_area_dict = {}

        self.addVideoAreaButton.clicked.connect(self.addVideoArea)
        self.deleteVideoAreaButton.clicked.connect(self.deleteVideoArea)
        self.showVideoAreaButton.clicked.connect(self.showVideoArea)

    def addCameraArea(self):
        self.cameraLabel.setCursor(QCursor(Qt.CrossCursor))
        self.camera_area = []
        self.add_camera_event = True
        self.cameraLabel.add_camera_event = True

        self.deleteAreaButton.setEnabled(False)
        self.showAreaButton.setEnabled(False)

    def deleteCameraArea(self):
        index = len(self.camera_area_dict)
        if index > 0:
            self.areaTableWidget.removeRow(index - 1)
            item = self.camera_area_dict.popitem()
            self.cameraLabel.removeItem(item[-1][-1])

    def showCameraArea(self):
        if self.show_camera_rect:
            self.show_camera_rect = False
            self.showAreaButton.setText("Show")
            for values in self.camera_area_dict.values():
                self.cameraLabel.removeItem(values[-1])
        else:
            self.show_camera_rect = True
            self.showAreaButton.setText("Hide")
            for values in self.camera_area_dict.values():
                self.cameraLabel.addRect(values[-1][0], values[-1][1], values[-1][2], values[-1][3], values[-1][4])

    def addVideoArea(self):
        self.graphicsView.setCursor(QCursor(Qt.CrossCursor))
        self.area = []
        self.add_event = True

        self.deleteVideoAreaButton.setEnabled(False)
        self.showVideoAreaButton.setEnabled(False)

    def deleteVideoArea(self):
        index = len(self.video_area_dict)
        if index > 0:
            self.areaVideoTableWidget.removeRow(index - 1)
            item = self.video_area_dict.popitem()
            self.scene.removeItem(item[-1][-1])

    def showVideoArea(self):
        if self.show_rect:
            self.show_rect = False
            self.showVideoAreaButton.setText("Show")
            for values in self.video_area_dict.values():
                self.scene.removeItem(values[-1])
        else:
            self.show_rect = True
            self.showVideoAreaButton.setText("Hide")
            for values in self.video_area_dict.values():
                self.scene.addItem(values[-1])

    def eventFilter(self, obj, event):
        '''
        camera
        '''
        # click event
        if obj == self.cameraLabel and event.type() == QMouseEvent.MouseButtonPress and self.add_camera_event:
            mouse_event = event
            if mouse_event.button() == Qt.LeftButton:
                label_pos = self.cameraLabel.mapFromGlobal(mouse_event.globalPos())
                self.camera_area.append(label_pos)
        # click release
        if obj == self.cameraLabel and event.type() == QMouseEvent.MouseButtonRelease and self.add_camera_event:
            mouse_event = event
            if mouse_event.button() == Qt.LeftButton:
                label_pos = self.cameraLabel.mapFromGlobal(mouse_event.globalPos())
                self.camera_area.append(label_pos)
                self.cameraLabel.removeItem(self.camera_temp_rect)
                rect_item = self.cameraLabel.addRect(min(self.camera_area[0].x(), self.camera_area[1].x()),
                                                     min(self.camera_area[0].y(), self.camera_area[1].y()),
                                                     abs(self.camera_area[0].x() - self.camera_area[1].x()),
                                                     abs(self.camera_area[0].y() - self.camera_area[1].y()),
                                                     QPen(QCOLOR_LIST[(len(self.camera_area_dict)) % 6]))
                self.camera_area_dict['Area_' + str(len(self.camera_area_dict) + 1)] = [
                    min(self.camera_area[0].x(), self.camera_area[1].x()),
                    min(self.camera_area[0].y(), self.camera_area[1].y()),
                    abs(self.camera_area[0].x() - self.camera_area[1].x()),
                    abs(self.camera_area[0].y() - self.camera_area[1].y()), rect_item
                ]
                self.areaTableWidget.setRowCount(self.areaTableWidget.rowCount() + 1)
                self.areaTableWidget.setItem(
                    len(self.camera_area_dict) - 1, 0, QTableWidgetItem(list(self.camera_area_dict.keys())[-1]))
                # for i in range(2):
                #     self.areaTableWidget.setItem(
                #         len(self.camera_area_dict) - 1, i + 1,
                #         QTableWidgetItem(str(list(self.camera_area_dict.values())[-1][i])))

                self.camera_area.clear()
                self.camera_temp_rect = None
                self.add_camera_event = False
                self.graphicsView.setCursor(QCursor(Qt.ArrowCursor))

                self.deleteAreaButton.setEnabled(True)
                self.showAreaButton.setEnabled(True)
                self.areaTableWidget.selectRow(-1)

        # move event
        if obj == self.cameraLabel and event.type() == QMouseEvent.MouseMove and self.add_camera_event and len(
                self.camera_area) == 1:
            if self.camera_temp_rect != None:
                self.cameraLabel.removeItem(self.camera_temp_rect)
            mouse_event = event
            label_pos = self.cameraLabel.mapFromGlobal(mouse_event.globalPos())
            self.camera_temp_rect = self.cameraLabel.addRect(min(self.camera_area[0].x(), label_pos.x()),
                                                             min(self.camera_area[0].y(), label_pos.y()),
                                                             abs(self.camera_area[0].x() - label_pos.x()),
                                                             abs(self.camera_area[0].y() - label_pos.y()),
                                                             QPen(QCOLOR_LIST[(len(self.camera_area_dict)) % 6]))
        '''
        video
        '''
        # click event
        if obj == self.scene and event.type() == QMouseEvent.GraphicsSceneMousePress and self.add_event:
            mouse_event = event
            if mouse_event.button() == Qt.LeftButton:
                scene_pos = mouse_event.scenePos()
                self.area.append(scene_pos)
        # click release
        if obj == self.scene and event.type() == QMouseEvent.GraphicsSceneMouseRelease and self.add_event:
            mouse_event = event
            if mouse_event.button() == Qt.LeftButton:
                scene_pos = mouse_event.scenePos()
                self.area.append(scene_pos)
                self.scene.removeItem(self.temp_rect)
                rect_item = self.scene.addRect(min(self.area[0].x(), self.area[1].x()),
                                               min(self.area[0].y(), self.area[1].y()),
                                               abs(self.area[0].x() - self.area[1].x()),
                                               abs(self.area[0].y() - self.area[1].y()),
                                               QPen(QCOLOR_LIST[(len(self.video_area_dict)) % 6]))
                self.video_area_dict['Area_' + str(len(self.video_area_dict) + 1)] = [
                    min(self.area[0].x(), self.area[1].x()),
                    min(self.area[0].y(), self.area[1].y()),
                    abs(self.area[0].x() - self.area[1].x()),
                    abs(self.area[0].y() - self.area[1].y()), rect_item
                ]
                self.areaVideoTableWidget.setRowCount(self.areaVideoTableWidget.rowCount() + 1)
                self.areaVideoTableWidget.setItem(
                    len(self.video_area_dict) - 1, 0, QTableWidgetItem(list(self.video_area_dict.keys())[-1]))
                # for i in range(2):
                #     self.areaVideoTableWidget.setItem(
                #         len(self.video_area_dict) - 1, i + 1,
                #         QTableWidgetItem(str(list(self.video_area_dict.values())[-1][i])))

                self.area.clear()
                self.temp_rect = None
                self.add_event = False
                self.graphicsView.setCursor(QCursor(Qt.ArrowCursor))

                self.deleteVideoAreaButton.setEnabled(True)
                self.showVideoAreaButton.setEnabled(True)
                self.areaVideoTableWidget.selectRow(-1)
        # move event
        if obj == self.scene and event.type() == QMouseEvent.GraphicsSceneMouseMove and self.add_event and len(
                self.area) == 1:
            if self.temp_rect != None:
                self.scene.removeItem(self.temp_rect)
            mouse_event = event
            scene_pos = mouse_event.scenePos()
            self.temp_rect = self.scene.addRect(min(self.area[0].x(), scene_pos.x()),
                                                min(self.area[0].y(), scene_pos.y()),
                                                abs(self.area[0].x() - scene_pos.x()),
                                                abs(self.area[0].y() - scene_pos.y()),
                                                QPen(QCOLOR_LIST[(len(self.video_area_dict)) % 6]))

        return super().eventFilter(obj, event)

    def saveSwitchchanged(self, ischecked: bool):
        if ischecked:
            self.videosavePath = self.videoSaveLineEdit.text()
            if not os.path.exists(self.videosavePath):
                self.saveSwitchButton.setChecked(False)
                title = "Invalid Path"
                content = "The Video Save Path is not found, press check."
                w = MessageBox(title, content, self)
                w.yesButton.setText("Create")
                w.yesButton.clicked.connect(self.createSavePath)
                if w.exec():
                    pass

    def createSavePath(self):
        try:
            os.makedirs(self.videosavePath)
            InfoBar.success(title="Create successfully!",
                            content="The path has been created!",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=2000,
                            parent=self)
        except Exception as e:
            InfoBar.error(title="Create Failed!",
                          content="The path is not founded.",
                          orient=Qt.Horizontal,
                          isClosable=True,
                          position=InfoBarPosition.TOP_RIGHT,
                          duration=2000,
                          parent=self)

    def setVideoSavePath(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(None, "Choose folder", "./")
        self.videoSaveLineEdit.setText(folder_path)

    def setVideoChoosePath(self):
        video_path, video_type = QtWidgets.QFileDialog.getOpenFileName(None, "Choose video", "./")
        self.videoChoosePathEdit.setText(video_path)

    def openVideoFile(self):
        try:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.videoChoosePathEdit.text())))
            self.player.play()
            self.videoControlButton.setEnabled(True)
            self.advanceButton.setEnabled(True)
            self.backButton.setEnabled(True)
            self.videoSlider.setEnabled(True)
            self.video_play = True
            self.videoControlButton.setIcon(self.style().standardIcon(63))
        except Exception as e:
            print(e)
            InfoBar.error(title="Open Video Failed!",
                          content="The video path is not founded.",
                          orient=Qt.Horizontal,
                          isClosable=True,
                          position=InfoBarPosition.TOP_RIGHT,
                          duration=2000,
                          parent=self)

    def updateProgress(self, frame, tot_frame):
        self.trackProgressRing.setValue(int(100 * (frame / tot_frame)))
        self.displayProgressLabel.setText('%.2f%%' % (100 * (frame / tot_frame)))
        self.trackProgressLabel.setText(str(frame) + '/' + str(tot_frame))

    def finishCameraTrack(self, num, time):
        for index in range(len(num)):
            self.areaTableWidget.setItem(index, 1, QTableWidgetItem(str(list(num.values())[index])))
        for index in range(len(time)):
            self.areaTableWidget.setItem(index, 2, QTableWidgetItem(str(list(time.values())[index])))

    def finishVideoTrack(self, num, time):
        for index in range(len(num)):
            self.areaVideoTableWidget.setItem(index, 1, QTableWidgetItem(str(list(num.values())[index])))
        for index in range(len(time)):
            self.areaVideoTableWidget.setItem(index, 2, QTableWidgetItem(str(list(time.values())[index])))

        self.videoTrackSwitchButton.blockSignals(True)
        self.videoTrackSwitchButton.setChecked(False)
        self.videoTrackSwitchButton.blockSignals(False)
        InfoBar.success(title="Track successfully!",
                        content="The track result has been created!",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self)

    def getVideoTime(self, num):
        self.videoSlider.setMaximum(self.player.duration())
        self.videoSlider.setValue(num)
        current_time = QTime.fromMSecsSinceStartOfDay(num).toString("hh:mm:ss")
        tot_num = self.player.duration()
        tot_time = QTime.fromMSecsSinceStartOfDay(tot_num).toString("hh:mm:ss")
        self.videoTimeLabel.setText(current_time + '/' + tot_time)

    def videoChangetime(self, num):
        self.player.setPosition(num)

    def videoChangeVolume(self, num):
        self.volumeNumLabel.setText(str(num))
        self.player.setVolume(num)

    def advanceVideo(self):
        num = self.player.position() + 15000  # ms
        if num > self.player.duration():
            num = self.player.duration()
        self.player.setPosition(num)

    def backVideo(self):
        num = self.player.position() - 15000  # ms
        if num < 0:
            num = 0
        self.player.setPosition(num)

    def controlVideo(self):
        if self.video_play:
            self.video_play = False
            self.videoControlButton.setIcon(self.style().standardIcon(61))
            self.player.pause()
        else:
            self.video_play = True
            self.videoControlButton.setIcon(self.style().standardIcon(63))
            self.player.play()

    def videoTrack(self, ischecked: bool):
        if os.path.exists(self.videoModelLineEdit.text()) and os.path.exists(self.videoChoosePathEdit.text()):
            if ischecked:
                model = onnxruntime.InferenceSession(self.videoModelLineEdit.text())
                self.video_thread.track_signal.emit(model, self.videoChoosePathEdit.text(), self.video_area_dict,
                                                    self.maxSpinBox.value(), self.minSpinBox.value())
                self.video_thread.start()
            else:
                title = "Warning"
                content = "Are you sure to end the tracking?"
                w = MessageBox(title, content, self)
                w.yesButton.clicked.connect(self.stopVideoTrack)
                w.cancelButton.clicked.connect(self.continueVideoTrack)
                if w.exec():
                    pass
        else:
            self.videoTrackSwitchButton.blockSignals(True)
            self.videoTrackSwitchButton.setChecked(False)
            self.videoTrackSwitchButton.blockSignals(False)
            InfoBar.warning(title="WARNING!",
                            content="The Model/Video Path is not found, please check.",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=2000,
                            parent=self)

    def setModelDefaultPath(self):
        if self.insectChooseBox.currentIndex() == 0:
            self.modelLineEdit.setText(r"models\cockroach\best.onnx".format(base))
        elif self.insectChooseBox.currentIndex() == 1:
            self.modelLineEdit.setText(r"models\cockroach\best.onnx".format(base))

    def setVideoModelDefaultPath(self):
        if self.videoInsectChooseBox.currentIndex() == 0:
            self.videoModelLineEdit.setText(r"models\cockroach\best.onnx".format(base))
        elif self.videoInsectChooseBox.currentIndex() == 1:
            self.videoModelLineEdit.setText(r"models\cockroach\best.onnx".format(base))

    def videoSavePathButtonChanged(self):
        if self.cameraOpenButton.text() == "Close Camera":
            self.trackSwitchButton.setEnabled(True)

    def stopVideoTrack(self):
        self.video_thread.stop_signal.emit(1)

    def continueVideoTrack(self):
        self.videoTrackSwitchButton.blockSignals(True)
        self.videoTrackSwitchButton.setChecked(True)
        self.videoTrackSwitchButton.blockSignals(False)

    def setModelPath(self):
        self.modelLineEdit.setText()

    def loadModel(self):
        file_path, filetype = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Onnx Model", "./", "*.onnx")
        self.modelLineEdit.setText(file_path)

    def loadVideoModel(self):
        file_path, filetype = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Onnx Model", "./", "*.onnx")
        self.videoModelLineEdit.setText(file_path)

    def trackSwitchChanged(self, ischecked: bool):
        if os.path.exists(self.modelLineEdit.text()):
            model = onnxruntime.InferenceSession(self.modelLineEdit.text())
            self.camera_thread.track_signal.emit(ischecked, model, self.videoSaveLineEdit.text(),
                                                 self.saveSwitchButton.isChecked(), self.camera_area_dict,
                                                 self.maxCameraSpinBox.value(), self.minCameraSpinBox.value())
            if ischecked:
                self.cameraOpenButton.setEnabled(False)
                self.saveSwitchButton.setEnabled(False)
            else:
                self.cameraOpenButton.setEnabled(True)
                self.saveSwitchButton.setEnabled(True)
                self.saveSwitchButton.setChecked(False)
        else:
            self.trackSwitchButton.blockSignals(True)
            self.trackSwitchButton.setChecked(False)
            self.trackSwitchButton.blockSignals(False)
            InfoBar.warning(title="WARNING!",
                            content="The Model Path is not found, please check.",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=2000,
                            parent=self)

    def openAndCloseCamera(self):
        if self.cameraOpenButton.text() == "Close Camera":
            self.cameraStateTip = None
            self.cameraOpenButton.setText(self.tr("Open Camera"))
            self.camera_thread.close_camera_signal.emit(1)
            self.cameraLabel.clear()
            self.cameraLabel.setText("Camera")
            self.trackSwitchButton.setEnabled(False)
        else:
            self.camera_thread.camer_num = self.cameraChooseBox.currentIndex()
            self.camera_thread.start()
            self.cameraStateTip = StateToolTip(self.tr("Opening camera"), self.tr("Please wait patiently"),
                                               self.window())
            self.cameraOpenButton.setText(self.tr("Close Camera"))
            self.cameraOpenButton.setEnabled(False)
            self.cameraStateTip.move(self.cameraStateTip.getSuitablePos())
            self.cameraStateTip.show()

    def cameraOpened(self):
        self.cameraOpenButton.setEnabled(True)
        self.cameraStateTip.setContent(self.tr("The camera is opened!"))
        self.cameraStateTip.setState(True)
        self.trackSwitchButton.setEnabled(True)

    def viewCamera(self, camera_pixmap):
        self.cameraLabel.setPixmap(camera_pixmap)

    def initLayout(self):
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        self.horizontalLayout.addWidget(self.NavigationInterface)
        self.horizontalLayout.addWidget(self.stackedWidget)
        self.horizontalLayout.setStretchFactor(self.stackedWidget, 1)

    def initNavigation(self):
        self.addSubInterface(self.page_1, FIF.CAMERA, 'Camera')
        self.addSubInterface(self.page_3, FIF.VIDEO, 'Video')

        #!IMPORTANT: don't forget to set the default route key if you enable the return button
        # qrouter.setDefaultRouteKey(self.stackWidget, self.videoInterface.objectName())

        # set the maximum width
        self.NavigationInterface.setExpandWidth(300)

        self.stackedWidget.currentChanged.connect(self.onCurrentInterfaceChanged)
        self.stackedWidget.setCurrentIndex(0)

    def initWindow(self):
        self.setWindowTitle('Insects')
        self.titleBar.setAttribute(Qt.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def addSubInterface(self, interface, icon, text: str, position=NavigationItemPosition.TOP):
        """ add sub interface """
        self.NavigationInterface.addItem(routeKey=interface.objectName(),
                                         icon=icon,
                                         text=text,
                                         onClick=lambda: self.switchTo(interface),
                                         position=position,
                                         tooltip=text)

    def switchTo(self, widget):
        self.stackedWidget.setCurrentWidget(widget)

    def onCurrentInterfaceChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.NavigationInterface.setCurrentItem(widget.objectName())

        #!IMPORTANT: This line of code needs to be uncommented if the return button is enabled
        # qrouter.push(self.stackWidget, widget.objectName())

    # def showMessageBox(self):
    #     w = MessageBox(
    #         'This is a help message',
    #         'You clicked a customized navigation widget. You can add more custom widgets by calling `NavigationInterface.addWidget()` 😉',
    #         self)
    #     w.exec()


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    app.exec_()