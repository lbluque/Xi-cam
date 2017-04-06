import os

from xicam.plugins import base
from PySide import QtGui, QtCore, QtUiTools

from xicam import config
from xicam import xglobals
from pipeline import msg
from slacx.slacxui import slacxuiman
from slacx.slacxcore import slacximgman
from slacx.slacxcore.operations import slacxopman
from slacx.slacxcore.workflow import slacxwfman

class SlacxPlugin(base.plugin):
    # The display name in the xi-cam plugin bar
    name = 'Slacx'

    def __init__(self, *args, **kwargs):

        # start slacx core objects    
        imgman = slacximgman.ImgManager()
        opman = slacxopman.OpManager()
        wfman = slacxwfman.WfManager(imgman=imgman)

        # start slacx ui objects
        root_qdir = QtCore.QDir(__file__)
        rootdir = os.path.split( root_qdir.absolutePath() )[0]+'/slacx'
        uiman = slacxuiman.UiManager(rootdir)

        # set up ui-core refs    
        uiman.imgman = imgman
        uiman.opman = opman
        uiman.wfman = wfman

        # Make the slacx title box
        uiman.make_title()    

        # Connect the menu actions to UiManager functions
        uiman.connect_actions()

        # Take care of remaining details
        uiman.final_setup()

        # Set the widgets in base.plugin containers
        self.centerwidget = uiman.ui.center_frame
        self.leftwidget = uiman.ui.left_frame
        self.rightwidget = uiman.ui.right_frame

        super(SlacxPlugin, self).__init__(*args, **kwargs)


