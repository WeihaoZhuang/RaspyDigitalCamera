import sys
import os
import cv2
import re
import rawpy
import pilgram
import torch
import numpy as np
import picamera as picam
from sid_model import preprocessing, init_sid_model
from PIL import Image
from pathlib import Path
from glob import glob
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool, pyqtSlot, pyqtSignal
from pidng.core import RPICAM2DNG

from picamera import mmal, mmalobj, exc
from picamera.mmalobj import to_rational


MMAL_PARAMETER_ANALOG_GAIN = mmal.MMAL_PARAMETER_GROUP_CAMERA + 0x59
MMAL_PARAMETER_DIGITAL_GAIN = mmal.MMAL_PARAMETER_GROUP_CAMERA + 0x5A

us2s = 1000000
img_folder = "./images/"
def set_gain(camera, gain, value):
    """Set the analog gain of a PiCamera.
    
    camera: the picamera.PiCamera() instance you are configuring
    gain: either MMAL_PARAMETER_ANALOG_GAIN or MMAL_PARAMETER_DIGITAL_GAIN
    value: a numeric value that can be converted to a rational number.
    """
    if gain not in [MMAL_PARAMETER_ANALOG_GAIN, MMAL_PARAMETER_DIGITAL_GAIN]:
        raise ValueError("The gain parameter was not valid")
    ret = mmal.mmal_port_parameter_set_rational(camera._camera.control._port, 
                                                    gain,
                                                    to_rational(value))
    if ret == 4:
        raise exc.PiCameraMMALError(ret, "Are you running the latest version of the userland libraries? Gain setting was introduced in late 2017.")
    elif ret != 0:
        raise exc.PiCameraMMALError(ret)

def set_analog_gain(camera, value):
    """Set the gain of a PiCamera object to a given value."""
    set_gain(camera, MMAL_PARAMETER_ANALOG_GAIN, value)

def set_digital_gain(camera, value):
    """Set the digital gain of a PiCamera object to a given value."""
    set_gain(camera, MMAL_PARAMETER_DIGITAL_GAIN, value)
    
    
    

class ClickableImageLabelListener():
    def __init__(self, ):
        self.image_label = []
        
        self.current_label = None
        
    def add_image_label(self, image_label):
        image_label.set_motion(self.current_label)
        self.image_label.append(image_label)
    
    def set_main_viewer(self, main_label):
        for label in self.image_label:
            label.set_main_viewer(main_label)
    
    def set_text_label(self, text_label):
        for label in self.image_label:
            label.set_text_label(text_label)  
    
    def remove_image_labels(self,):
        for v in self.image_label:
            v.clear()
            
class ClickableImageLabel(QtWidgets.QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, pixmap, file_name, message=None):
        super(ClickableImageLabel, self).__init__()
        self.setPixmap(pixmap)
        self.file_name = file_name
        self.message = message
    
    def set_img(self, img):
        self.img = img
        
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        
        return QtWidgets.QLabel.mousePressEvent(self, event)
    
    def set_motion(self, self_slot):
        self.clicked.connect(lambda : self.sent_self(self_slot))

    def sent_self(self, self_slot):
        self_slot[0] = self
    
    def set_main_viewer(self, main_label):
        self.clicked.connect(lambda : self.show_image(main_label))
    
    def set_text_label(self, text_label):
        self.clicked.connect(lambda : self.show_text(text_label))
    
    def show_text(self, text_label):
        text_label.setText(self.message)
    
    def show_image(self,main_label):
        pixmap = QtGui.QPixmap.fromImage(self.img)
        main_label.setPixmap(pixmap)

class CameraMenu(object):
    def __init__(self,):
        self.widget = QtWidgets.QWidget()
        self.widget_filter = QtWidgets.QWidget(self.widget)
        self.image_listener = ClickableImageLabelListener()
        self.image_listener_main = ClickableImageLabelListener()
        self.option_menu = QtWidgets.QMenu(self.widget)
        self.filter_names = ["_1977","aden","brannan","brooklyn","clarendon","earlybird","gingham", "hudson", 
                            "inkwell","kelvin","lark","lofi","maven","mayfair","moon","nashville","perpetua",
                            "reyes","rise","slumber","stinson","toaster","valencia","walden","willow","xpro2"]
        
        
        
        self.old_img_paths = glob(f"{img_folder}/*")
        self.old_img_paths.sort(key=lambda x: int(re.sub("\D", '', x)))
        
        self.image_label = []
        self.filter_label = []
        self.tex_label = []
        self.filter_text_label = []
        self.current_label = [None]
        
        self.sid_model = init_sid_model("/home/pi/workspace/digtial_camera/pth.txt")
        
    def set_main_viewer(self, main_label):
        for label in self.image_label:
            label.set_main_viewer(main_label)

    def set_main_viewer_filters(self, main_label):
        for label in self.filter_label:
            label.set_main_viewer(main_label)
            
    def set_text_label(self, text_label):
        for label in self.image_label:
            label.set_text_label(text_label)
            
    def set_text_label_filters(self, text_label):
        for label in self.filter_label:
            label.set_text_label(text_label)
    
    def remove_image_labels(self,):
        for v in self.image_label:
            v.clear()
        for v in self.tex_label:
            v.clear()
    def remove_filter_labels(self,):
        for v in self.filter_text_label:
            v.clear()
        for v in self.filter_label:
            v.clear()
        
    def set_main_image(self,):
        file = self.image_listener.current_label.file_name
        img = QtGui.QImage(file)
   
    def set_widget_motion(self,):
        self.backButton.clicked.connect(self.hide_window)
        
        self.pushButton_2.clicked.connect(self.hide_filter_window)
        self.pushButton.clicked.connect(self.save_filter)
     
    def hide_filter_window(self,):
        self.widget_filter.hide()
        self.scrollAreaWidgetContents.show()
        self.scrollArea.show()
    def hide_window(self,):
        self.widget.hide()
        
    def show_window(self,):
        self.load_images(False)
        self.widget.show()
    
    def set_option_menu(self,):
        self.delete_act = QtWidgets.QAction("Delete", self.widget)
        self.vis_dng_act = QtWidgets.QAction("Visual DNG", self.widget)
        self.vis_filters_act = QtWidgets.QAction("Filters", self.widget)
        self.super_night_act = QtWidgets.QAction("Super Night", self.widget)
        
        
        self.delete_act.triggered.connect(self.option_menu_motion)
        self.vis_dng_act.triggered.connect(self.option_menu_motion)
        self.vis_filters_act.triggered.connect(self.option_menu_motion)
        self.super_night_act.triggered.connect(self.option_menu_motion)
        
        
        self.option_menu.addAction(self.delete_act)
        self.option_menu.addAction(self.vis_dng_act)
        self.option_menu.addAction(self.vis_filters_act)
        self.option_menu.addAction(self.super_night_act)
        
        self.toolButton.setMenu(self.option_menu)
 

    def option_menu_motion(self,):
        if self.widget.sender() == self.delete_act:
            os.remove(f"{img_folder}/{self.toolButton.text()}")
            self.load_images(init=True)
            
        if self.widget.sender() == self.vis_dng_act:
            self.visual_dng()
            
        if self.widget.sender() == self.vis_filters_act:
            self.scrollAreaWidgetContents.hide()
            self.scrollArea.hide()
            self.widget_filter.show()
            self.visual_filters()
            
        if self.widget.sender() == self.super_night_act:
            self.super_night()
            
    @torch.no_grad()
    def super_night(self, ):
        file_name = self.toolButton.text()
        file_stem = file_name.split(".")[0]
        file_type = file_name.split(".")[1]
        file_path = f"{img_folder}/{file_name}"
        
        if file_type == 'dng':
            inp = preprocessing(file_path)
            out = self.sid_model(torch.tensor(inp[:, :, :2016])[None])[0]
            out = torch.clip(out, 0, 1)
            out = out.permute(1,2,0).numpy()[:,:,::-1] * 255.
            out = out.astype("uint8")
            cv2.imwrite(f"{img_folder}/{file_stem}_SN.jpeg", out)
            self.load_images(init=True)  
            
            
    def visual_dng(self,):
        file_name = self.toolButton.text()
        file_stem = file_name.split(".")[0]
        file_type = file_name.split(".")[1]
        file_path = f"{img_folder}/{file_name}"
        
        if file_type == "dng":
            raw = rawpy.imread(file_path).postprocess(use_camera_wb=True, half_size=True)[:,:,::-1]
            cv2.imwrite(f"{img_folder}/{file_stem}_VIS.jpeg", raw)
            self.load_images(init=True)            
    
    def visual_filters(self, ):
        self.remove_filter_labels()
            
        for i,name in enumerate(self.filter_names):
            filter_func = getattr(pilgram, name) 
            file_name = self.toolButton.text()
            file_path = f"{img_folder}/{file_name}"
        
            img = cv2.imread(file_path)
            img = cv2.resize(img, (320, 240))
            img = Image.fromarray(img)
            img = filter_func(img)
            img = np.ascontiguousarray(np.array(img)[:,:,::-1])
     
            img = QtGui.QImage(img, 320, 240, 3*320, QtGui.QImage.Format_RGB888)
            img_resized = img.scaled(75, 75, aspectRatioMode=QtCore.Qt.KeepAspectRatio, 
                                  transformMode = QtCore.Qt.FastTransformation)
            
            
            image_label = ClickableImageLabel(QtGui.QPixmap.fromImage(img_resized), self.toolButton.text(), name)
            image_label.set_img(img)
            image_label.set_motion(self.current_label)
            self.filter_label.append(image_label)
            

        
            text_label = QtWidgets.QLabel(name)
            text_label.setAlignment(QtCore.Qt.AlignCenter)
            self.filter_text_label.append(text_label)

            self.gridLayout_2.addWidget(image_label, 0, i)
            self.gridLayout_2.addWidget(text_label,1,i)    
        
        self.set_main_viewer_filters(self.MainImagelabel)
        self.set_text_label_filters(self.toolButton)
        self.load_images(init=True)
        
    def load_images(self, init=True):
        if init:
            st = 0
            self.remove_image_labels()
            img_paths = glob(f"{img_folder}/*")
            img_paths.sort(key=lambda x: int(re.sub("\D", '', x)))
            
            self.old_img_paths = img_paths
            print(f"load_images init=True:{len(self.image_listener.image_label)}, ")
        else:
            st = len(self.old_img_paths)
            
            new_img_paths = glob(f"{img_folder}/*")
            new_img_paths = set(new_img_paths)
            
            img_paths = list(new_img_paths - set(self.old_img_paths))
            img_paths.sort(key=lambda x: int(re.sub("\D", '', x)))
        
        
            self.old_img_paths = new_img_paths

        for i, file in enumerate(img_paths, st):

            img = QtGui.QImage(file)
            img_large = img.scaled(320, 240,aspectRatioMode=QtCore.Qt.KeepAspectRatio, transformMode = QtCore.Qt.FastTransformation)
            img_resized = img.scaled(75,75,aspectRatioMode=QtCore.Qt.KeepAspectRatio, transformMode = QtCore.Qt.FastTransformation)

            image_label = ClickableImageLabel(QtGui.QPixmap.fromImage(img_resized), Path(file).name, Path(file).name)
            image_label.set_img(img_large)
            

            self.image_label.append(image_label)
            tex_label = QtWidgets.QLabel(self.scrollAreaWidgetContents)
            tex_label.setText(Path(file).name)
            tex_label.setAlignment(QtCore.Qt.AlignCenter)

            
            self.tex_label.append(tex_label)
            
            self.gridLayout.addWidget(image_label, 0, i)
            self.gridLayout.addWidget(tex_label, 1, i)    
        
        self.set_main_viewer(self.MainImagelabel)
        self.set_text_label(self.toolButton)
    
    def save_filter(self,):
        file_name = self.current_label[0].file_name
        filter_name = self.current_label[0].message
        filter_func = getattr(pilgram, filter_name) 
        file_stem = file_name.split(".")[0]
        file_path = f"{img_folder}/{file_name}"

        img = cv2.imread(file_path)
        img = Image.fromarray(img)
        img = filter_func(img)
        img = np.array(img)
        cv2.imwrite(f"{img_folder}/{file_stem}.JPG", img)
        self.load_images(init=True)
    
    def init_sid_model(self,):
        pth = open("./pth.txt", 'rb')
        pth.seek(0)
        model = SeeInDark()
        model = model.eval()
        model = quantize_fx.prepare_fx(model, {'': torch.quantization.default_qconfig})
        model = quantize_fx.convert_fx(model)
        model.load_state_dict(torch.load(pth))
        self.sid_model = model
       
    def init_ui(self,):
        self.setupUi()
        self.retranslateUi()
        self.load_images(True)
        self.set_option_menu()
        
        
    def setupUi(self,):
        Form = self.widget
        Form.setObjectName("Form")
        Form.resize(600, 400)
        self.scrollArea = QtWidgets.QScrollArea(Form)
        self.scrollArea.setEnabled(True)
        self.scrollArea.setGeometry(QtCore.QRect(10, 250, 580, 101))
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 459, 99))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.gridLayoutWidget = QtWidgets.QWidget(self.scrollAreaWidgetContents)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(10, 10, 441, 71))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.backButton = QtWidgets.QPushButton(Form)
        self.backButton.setGeometry(QtCore.QRect(349, 10, 221, 30))
        self.backButton.setObjectName("backButton")
        self.toolButton = QtWidgets.QToolButton(Form)
        self.toolButton.setGeometry(QtCore.QRect(350, 50, 221, 29))
        self.toolButton.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.toolButton.setObjectName("toolButton")
        self.MainImagelabel = QtWidgets.QLabel(Form)
        self.MainImagelabel.setGeometry(QtCore.QRect(5, 5, 320, 240))
        self.MainImagelabel.setText("")
        self.MainImagelabel.setObjectName("MainImagelabel")
        
        
        
        
        self.widget_filter.setGeometry(QtCore.QRect(10, 250, 580, 101))
        self.widget_filter.setObjectName("widget")
        self.widget_filter.hide()

        self.scrollArea_2 = QtWidgets.QScrollArea(self.widget_filter)
        self.scrollArea_2.setWidgetResizable(True)
        self.scrollArea_2.setObjectName("scrollArea_2")
        self.scrollAreaWidgetContents_2 = QtWidgets.QWidget()
        self.scrollAreaWidgetContents_2.setGeometry(QtCore.QRect(10, 250, 580, 101))
        self.scrollAreaWidgetContents_2.setObjectName("scrollAreaWidgetContents_2")
        self.gridLayoutWidget_2 = QtWidgets.QWidget(self.scrollAreaWidgetContents_2)
        self.gridLayoutWidget_2.setGeometry(QtCore.QRect(10, 250, 580, 101))
        self.gridLayoutWidget_2.setObjectName("gridLayoutWidget_2")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.scrollAreaWidgetContents_2)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.scrollArea_2.setWidget(self.scrollAreaWidgetContents_2)
        
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.pushButton = QtWidgets.QPushButton(self.widget_filter)
        self.pushButton.setMaximumSize(QtCore.QSize(30, 50))
        self.pushButton.setObjectName("pushButton")
        self.pushButton.setText("OK")
        self.verticalLayout.addWidget(self.pushButton)
        self.pushButton_2 = QtWidgets.QPushButton(self.widget_filter)
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_2.setText("Return")
        self.verticalLayout.addWidget(self.pushButton_2)
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.widget_filter)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.addWidget(self.scrollArea_2)
        self.horizontalLayout.addLayout(self.verticalLayout)
        
        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self,):
        Form = self.widget
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.backButton.setText(_translate("Form", "Back"))
        
        self.toolButton.setText(_translate("Form", "..."))
        self.MainImagelabel.setText(_translate("Form", " "))



class PreviewWindow(object):
    def __init__(self,):
        self.window = QtWidgets.QMainWindow()
        self.camera = picam.PiCamera()
        set_digital_gain(self.camera, 1)
        self.iso_step = 10
        self.shutter_step = [10,13,15,20,25,30,40,50,60,80,100,125,160,200,250,320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000]
        self.dng_convert = RPICAM2DNG()
        
    
    def init_widget_status(self,):
        self.disable_iso_shutter()
        self.AutoModeBox.setCheckState(2)
        self.set_iso_shutter_text()
        
    def set_widget_event(self,):
        self.captureButton.clicked.connect(self.capture_raw)
        self.MenuButton.clicked.connect(self.stop_camera)
        self.MenuButton.clicked.connect(self.hiden_window)
        self.AutoModeBox.stateChanged.connect(self.camera_preview)
        self.ISOverticalScrollBar.valueChanged.connect(lambda : self.camera_preview(state=0, preview=False))
        self.ShutterverticalScrollBar.valueChanged.connect(lambda : self.camera_preview(state=0, preview=False))
        
    def camera_preview(self, state=0, preview=False):
        if state > 0:
            self.disable_iso_shutter()
            self.camera.exposure_mode = 'auto'
            self.camera.iso = 0
            self.camera.shutter_speed = 0
            
        else:
            self.enable_iso_shutter()
            self.camera.iso = self.ISOverticalScrollBar.value() * self.iso_step
            self.camera.shutter_speed = self.set_shutter(self.shutter_step[self.ShutterverticalScrollBar.value()])  
            self.set_iso_shutter_text()
        if preview:
            self.camera.start_preview(fullscreen=False, window=(5,40,500,int(500/4*3)))   
            
            
    def disable_iso_shutter(self,):
        self.ISOverticalScrollBar.setEnabled(False)
        self.ShutterverticalScrollBar.setEnabled(False)
        
    def enable_iso_shutter(self,):
        self.ISOverticalScrollBar.setEnabled(True)
        self.ShutterverticalScrollBar.setEnabled(True)
        
    def set_shutter(self, shutter):
        return int((1/(shutter))*us2s)  
    
    def set_iso_shutter_text(self, ):
        self.ISOlabel.setText(str(self.ISOverticalScrollBar.value() * self.iso_step))
        self.Shutterlabel.setText(f"1/{str(self.shutter_step[self.ShutterverticalScrollBar.value()])} (s)")
        
    def stop_camera(self,):
        self.camera.stop_preview()

    def capture_raw(self, ):
        idx = self.get_file_idx(img_folder)
        self.camera.capture(output=f"{img_folder}/{idx}.jpg", format='jpeg', bayer=True, use_video_port=False)
        self.dng_convert.convert(f"{img_folder}/{idx}.jpg")
        self.camera_preview(self.AutoModeBox.checkState())
        
    def get_file_idx(self, img_folder = "./images/"):
        if len(os.listdir(img_folder)) == 0:
            img_idx = 0
        else:
            img_idx = max([int(x.split(".")[0].split("_")[0]) for x in os.listdir(img_folder)]) + 1
        return img_idx   

    
    def show_main_window(self,):
        self.window.show() 
        self.camera_preview(self.AutoModeBox.checkState(), preview=True)
       
        
    def hiden_window(self):
        self.window.hide()
        
    def init_ui(self,):
        self.set_ui()
        self.retranslateUi()
        self.init_widget_status()
        self.set_widget_event()
        self.camera_preview(state=2, preview=True)
        
    def set_ui(self,):
        MainWindow = self.window
        MainWindow.setObjectName("MainWindow")
        MainWindow.setEnabled(True)
        MainWindow.resize(600, 400)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.widget = QtWidgets.QWidget(self.centralwidget)
        self.widget.setGeometry(QtCore.QRect(505, 10, 85, 206))
        self.widget.setObjectName("widget")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.widget)
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.captureButton = QtWidgets.QPushButton(self.widget)
        self.captureButton.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.captureButton.setObjectName("captureButton")
        self.verticalLayout_3.addWidget(self.captureButton)
        self.AutoModeBox = QtWidgets.QCheckBox(self.widget)
        self.AutoModeBox.setObjectName("AutoModeBox")
        self.verticalLayout_3.addWidget(self.AutoModeBox)
        self.MenuButton = QtWidgets.QPushButton(self.widget)
        self.MenuButton.setMinimumSize(QtCore.QSize(100, 0))
        self.MenuButton.setIconSize(QtCore.QSize(16, 16))
        self.MenuButton.setObjectName("MenuButton")
        self.verticalLayout_3.addWidget(self.MenuButton)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label = QtWidgets.QLabel(self.widget)
        self.label.setObjectName("label")
        self.horizontalLayout_2.addWidget(self.label)
        self.ISOlabel = QtWidgets.QLabel(self.widget)
        self.ISOlabel.setObjectName("ISOlabel")
        self.horizontalLayout_2.addWidget(self.ISOlabel)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.ISOverticalScrollBar = QtWidgets.QScrollBar(self.widget)
        self.ISOverticalScrollBar.setEnabled(False)
        self.ISOverticalScrollBar.setMinimum(1)
        self.ISOverticalScrollBar.setMaximum(80)
        self.ISOverticalScrollBar.setSingleStep(1)
        self.ISOverticalScrollBar.setPageStep(1)
        self.ISOverticalScrollBar.setProperty("value", 1)
        self.ISOverticalScrollBar.setOrientation(QtCore.Qt.Horizontal)
        self.ISOverticalScrollBar.setInvertedAppearance(False)
        self.ISOverticalScrollBar.setInvertedControls(False)
        self.ISOverticalScrollBar.setObjectName("ISOverticalScrollBar")
        self.verticalLayout.addWidget(self.ISOverticalScrollBar)
        self.verticalLayout_3.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_2 = QtWidgets.QLabel(self.widget)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.Shutterlabel = QtWidgets.QLabel(self.widget)
        self.Shutterlabel.setObjectName("Shutterlabel")
        self.horizontalLayout.addWidget(self.Shutterlabel)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.ShutterverticalScrollBar = QtWidgets.QScrollBar(self.widget)
        self.ShutterverticalScrollBar.setEnabled(False)
        self.ShutterverticalScrollBar.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.ShutterverticalScrollBar.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.ShutterverticalScrollBar.setMinimum(0)
        self.ShutterverticalScrollBar.setMaximum(26)
        self.ShutterverticalScrollBar.setSingleStep(1)
        self.ShutterverticalScrollBar.setPageStep(1)
        self.ShutterverticalScrollBar.setProperty("value", 0)
        self.ShutterverticalScrollBar.setOrientation(QtCore.Qt.Horizontal)
        self.ShutterverticalScrollBar.setInvertedAppearance(False)
        self.ShutterverticalScrollBar.setInvertedControls(False)
        self.ShutterverticalScrollBar.setObjectName("ShutterverticalScrollBar")
        self.verticalLayout_2.addWidget(self.ShutterverticalScrollBar)
        self.verticalLayout_3.addLayout(self.verticalLayout_2)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 480, 27))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        
        
    def retranslateUi(self,):
        MainWindow = self.window
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.captureButton.setText(_translate("MainWindow", "Capture"))
        self.AutoModeBox.setText(_translate("MainWindow", "Auto Mode"))
        self.MenuButton.setText(_translate("MainWindow", "Menu"))
        self.label.setText(_translate("MainWindow", "ISO"))
        self.ISOlabel.setText(_translate("MainWindow", "TextLabel"))
        self.label_2.setText(_translate("MainWindow", "S"))
        self.Shutterlabel.setText(_translate("MainWindow", "TextLabel"))



class CameraApp(object):
    def __init__(self,):
        self.app = QtWidgets.QApplication(sys.argv)
        self.preview_window = PreviewWindow()
        self.menu_window = CameraMenu()
        
        
    def run_app(self,):
        
        self.preview_window.init_ui()
        self.menu_window.init_ui()
        
        self.preview_window.MenuButton.clicked.connect(self.menu_window.show_window)

        self.preview_window.window.show()
        
        self.menu_window.set_widget_motion()
        self.menu_window.backButton.clicked.connect(self.preview_window.show_main_window)
    
    
        
        sys.exit(self.app.exec_())

app = CameraApp()

app.run_app()