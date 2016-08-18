# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2015, Vispy Development Team. All Rights Reserved.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.
# -----------------------------------------------------------------------------
# vispy: gallery 2
#
# Adapted for use as a widget by Ron Pandolfi
# volumeViewer.getHistogram method borrowed from PyQtGraph

"""
Example volume rendering

Controls:

* 1  - toggle camera between first person (fly), regular 3D (turntable) and
       arcball
* 2  - toggle between volume rendering methods
* 3  - toggle between stent-CT / brain-MRI image
* 4  - toggle between colormaps
* 0  - reset cameras
* [] - decrease/increase isosurface threshold

With fly camera:

* WASD or arrow keys - move around
* SPACE - brake
* FC - move up-down
* IJKL or mouse - look around
"""

from itertools import cycle

import numpy as np

from PySide import QtGui,QtCore
from vispy import app, scene, io
from vispy.color import Colormap, BaseColormap,ColorArray
from pipeline import loader, msg
import pyqtgraph as pg
import imageio
import os

# TODO refactor general widgets to be part of plugins.widgets to be shared in a more organized fashion
from ..tomography.widgets import StackViewer


class ThreeDViewer(QtGui.QWidget, ):
    def __init__(self, paths, parent=None):
        super(ThreeDViewer, self).__init__(parent=parent)

        self.combo_box = QtGui.QComboBox(self)
        self.combo_box.addItems(['Image Stack', '3D Volume'])
        self.stack_viewer = StackViewer()
        self.volume_viewer = VolumeViewer()

        self.view_stack = QtGui.QStackedWidget(self)
        self.view_stack.addWidget(self.stack_viewer)
        self.view_stack.addWidget(self.volume_viewer)

        hlayout = QtGui.QHBoxLayout()
        self.subsample_spinbox = QtGui.QSpinBox()
        self.subsample_label = QtGui.QLabel('Subsample Level:')
        self.loadVolumeButton = QtGui.QToolButton()
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("gui/icons_45.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.loadVolumeButton.setIcon(icon)
        self.loadVolumeButton.setToolTip('Generate Volume')
        hlayout.addWidget(self.combo_box)
        hlayout.addSpacing(2)
        hlayout.addWidget(self.subsample_label)
        hlayout.addWidget(self.subsample_spinbox)
        hlayout.addWidget(self.loadVolumeButton)
        hlayout.addStretch()
        layout = QtGui.QVBoxLayout(self)
        layout.addLayout(hlayout)
        layout.addWidget(self.view_stack)

        self.subsample_spinbox.hide()
        self.subsample_spinbox.setValue(8)
        self.subsample_label.hide()
        self.loadVolumeButton.hide()

        self.stack_image = loader.StackImage(paths)
        self.volume = None
        self.stack_viewer.setData(self.stack_image)
        self.combo_box.activated.connect(self.view_stack.setCurrentIndex)
        self.view_stack.currentChanged.connect(self.toggleInputs)
        self.loadVolumeButton.clicked.connect(self.loadVolume)

    def toggleInputs(self, index):
        if self.view_stack.currentWidget() is self.volume_viewer:
            self.subsample_label.show()
            self.subsample_spinbox.show()
            self.loadVolumeButton.show()
        else:
            self.subsample_label.hide()
            self.subsample_spinbox.hide()
            self.loadVolumeButton.hide()

    def loadVolume(self):
        msg.showMessage('Generating volume...', timeout=5)
        level = self.subsample_spinbox.value()
        self.volume = self.stack_image.asVolume(level=level)
        self.volume_viewer.setVolume(vol=self.volume, slicevol=False)
        msg.clearMessage()


class VolumeViewer(QtGui.QWidget):

    sigImageChanged=QtCore.Signal()

    def __init__(self,path=None,data=None,*args,**kwargs):
        super(VolumeViewer, self).__init__()

        self.levels = [0, 1]

        ly = QtGui.QHBoxLayout()
        ly.setContentsMargins(0,0,0,0)
        ly.setSpacing(0)

        self.volumeRenderWidget=VolumeRenderWidget()
        ly.addWidget(self.volumeRenderWidget.native)

        self.HistogramLUTWidget = pg.HistogramLUTWidget(image=self, parent=self)
        self.HistogramLUTWidget.setMaximumWidth(self.HistogramLUTWidget.minimumWidth()+15)# Keep static width
        self.HistogramLUTWidget.setMinimumWidth(self.HistogramLUTWidget.minimumWidth()+15)

        ly.addWidget(self.HistogramLUTWidget)

        self.xregion = SliceWidget(parent=self)
        self.yregion = SliceWidget(parent=self)
        self.zregion = SliceWidget(parent=self)
        self.xregion.item.region.setRegion([0, 1000])
        self.yregion.item.region.setRegion([0, 1000])
        self.zregion.item.region.setRegion([0, 1000])
        self.xregion.sigSliceChanged.connect(self.setVolume) #change to setVolume
        self.yregion.sigSliceChanged.connect(self.setVolume)
        self.zregion.sigSliceChanged.connect(self.setVolume)
        ly.addWidget(self.xregion)
        ly.addWidget(self.yregion)
        ly.addWidget(self.zregion)

        self.setLayout(ly)

        # self.setVolume(vol=data,path=path)

        # self.volumeRenderWidget.export('video.mp4',fps=25,duration=10.)
        # self.writevideo()


    @property
    def vol(self):
        return self.volumeRenderWidget.vol

    def getSlice(self):
        xslice=self.xregion.getSlice()
        yslice=self.yregion.getSlice()
        zslice=self.zregion.getSlice()
        return xslice,yslice,zslice

    def setVolume(self, vol=None, path=None, slicevol=True):
        if slicevol:
            sliceobj = self.getSlice()
            msg.logMessage(('Got slice', sliceobj),msg.DEBUG)
        else:
            sliceobj = 3*(slice(0, None),)

        self.volumeRenderWidget.setVolume(vol, path, sliceobj)
        self.volumeRenderWidget.update()
        if vol is not None or path is not None:
            self.sigImageChanged.emit()
            for i, region in enumerate([self.xregion, self.yregion, self.zregion]):
                try:
                    region.item.region.setRegion([0, vol.shape[i]])
                except RuntimeError as e:
                    msg.logMessage(e.message,msg.ERROR)

    def moveGradientTick(self, idx, pos):
        tick = self.HistogramLUTWidget.item.gradient.listTicks()[idx][0]
        tick.setPos(pos, 0)
        tick.view().tickMoved(tick, QtCore.QPoint(pos*self.HistogramLUTWidget.item.gradient.length, 0))
        tick.sigMoving.emit(tick)
        tick.sigMoved.emit(tick)
        tick.view().tickMoveFinished(tick)

    def setLevels(self, levels, update=True):
        self.levels = levels
        self.setLookupTable()
        self.HistogramLUTWidget.region.setRegion(levels)
        if update:
            self.volumeRenderWidget.update()

    def setLookupTable(self, lut=None, update=True):
        try:
            table = self.HistogramLUTWidget.item.gradient.colorMap().color/256.
            pos = self.HistogramLUTWidget.item.gradient.colorMap().pos
            #table=np.clip(table*(self.levels[1]-self.levels[0])+self.levels[0],0.,1.)
            table[:, 3] = pos
            table = np.vstack([np.array([[0,0,0,0]]),table,np.array([[1,1,1,1]])])
            pos = np.hstack([[0], pos*(self.levels[1] - self.levels[0]) + self.levels[0], [1]])
            self.volumeRenderWidget.volume.cmap = Colormap(table, controls=pos)
        except AttributeError as ex:
            msg.logMessage(ex,msg.ERROR)


    def getHistogram(self, bins='auto', step='auto', targetImageSize=100, targetHistogramSize=500, **kwds):
        """Returns x and y arrays containing the histogram values for the current image.
        For an explanation of the return format, see numpy.histogram().

        The *step* argument causes pixels to be skipped when computing the histogram to save time.
        If *step* is 'auto', then a step is chosen such that the analyzed data has
        dimensions roughly *targetImageSize* for each axis.

        The *bins* argument and any extra keyword arguments are passed to
        np.histogram(). If *bins* is 'auto', then a bin number is automatically
        chosen based on the image characteristics:

        * Integer images will have approximately *targetHistogramSize* bins,
          with each bin having an integer width.
        * All other types will have *targetHistogramSize* bins.

        This method is also used when automatically computing levels.
        """
        if self.vol is None:
            return None,None
        if step == 'auto':
            step = (np.ceil(float(self.vol.shape[0]) / targetImageSize),
                    np.ceil(float(self.vol.shape[1]) / targetImageSize))
        if np.isscalar(step):
            step = (step, step)
        stepData = self.vol[::step[0], ::step[1]]

        if bins == 'auto':
            if stepData.dtype.kind in "ui":
                mn = stepData.min()
                mx = stepData.max()
                step = np.ceil((mx-mn) / 500.)
                bins = np.arange(mn, mx+1.01*step, step, dtype=np.int)
                if len(bins) == 0:
                    bins = [mn, mx]
            else:
                bins = 500

        kwds['bins'] = bins
        hist = np.histogram(stepData, **kwds)

        return hist[1][:-1], hist[0]

    # @volumeRenderWidget.connect
    # def on_frame(self,event):
    #     self.volumeRenderWidget.cam1.auto_roll

    def writevideo(self,fps=25):
        writer = imageio.save('foo.mp4', fps=25)
        self.volumeRenderWidget.events.draw.connect(lambda e: writer.append_data(self.render()))
        self.volumeRenderWidget.events.close.connect(lambda e: writer.close())


class VolumeRenderWidget(scene.SceneCanvas):

    def __init__(self,vol=None, path=None, size=(800,600), show=False):
        super(VolumeRenderWidget, self).__init__(keys='interactive', size=size, show=show)

        # Prepare canvas
        self.measure_fps()

        #self.unfreeze()

        # Set up a viewbox to display the image with interactive pan/zoom
        self.view = self.central_widget.add_view()

        self.vol=None
        self.setVolume(vol,path)
        self.volume=None

        # Create three cameras (Fly, Turntable and Arcball)
        fov = 60.
        self.cam1 = scene.cameras.FlyCamera(parent=self.view.scene, fov=fov, name='Fly')
        self.cam2 = scene.cameras.TurntableCamera(parent=self.view.scene, fov=fov, name='Turntable')
        self.cam3 = scene.cameras.ArcballCamera(parent=self.view.scene, fov=fov, name='Arcball')
        self.view.camera = self.cam2  # Select turntable at first


    def setVolume(self, vol=None, path=None, sliceobj=None):

        if path is not None and vol is None:
            if '*' in path:
                vol = loader.loadimageseries(path)
            elif os.path.splitext(path)[-1]=='.npy':
                vol = loader.loadimage(path)
            else:
                vol = loader.loadtiffstack(path)
        elif vol is None:
            vol = self.vol

        if vol is None:
            return

        self.vol = vol

        if slice is not None:
            slicevol = self.vol[sliceobj]
        else:
            slicevol = self.vol

        # Set whether we are emulating a 3D texture
        emulate_texture = False

        # Create the volume visuals
        if self.volume is None:
            self.volume = scene.visuals.Volume(slicevol, parent=self.view.scene, emulate_texture=emulate_texture)
            self.volume.method = 'translucent'
        else:
            self.volume.set_data(slicevol)
            self.volume._create_vertex_data() #TODO: Try using this instead of slicing array?

        # Translate the volume into the center of the view (axes are in strange order for unkown )
        scale = 3*(2.0/self.vol.shape[1],)
        translate = map(lambda x: -scale[0]*x/2, reversed(vol.shape))
        self.volume.transform = scene.STTransform(translate=translate, scale=scale)

    # Implement key presses
    def on_key_press(self, event):
        if event.text == '1':
            cam_toggle = {self.cam1: self.cam2, self.cam2: self.cam3, self.cam3: self.cam1}
            self.view.camera = cam_toggle.get(self.view.camera, self.cam2)
            msg.logMessage(self.view.camera.name + ' camera',msg.DEBUG)
        elif event.text == '2':
            pass
        elif event.text == '3':
            pass
        elif event.text == '4':
            pass
        elif event.text == '0':
            self.cam1.set_range()
            self.cam3.set_range()
        elif event.text != '' and event.text in '[]':
            s = -0.025 if event.text == '[' else 0.025
            self.volume.threshold += s
            th = self.volume.threshold
            msg.logMessage("Isosurface threshold: %0.3f" % th,msg.DEBUG)


class SliceWidget(pg.HistogramLUTWidget):
    sigSliceChanged = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(SliceWidget, self).__init__(*args, **kwargs)
        self.item.paint = lambda *x: None
        self.item.vb.deleteLater()
        self.item.gradient.gradRect.hide()
        self.item.gradient.allowAdd = False
        self.setMinimumWidth(70)
        self.setMaximumWidth(70)
        self.item.sigLookupTableChanged.connect(self.ticksChanged)
        self.setSizePolicy(QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)

    def sizeHint(self):
        return QtCore.QSize(70, 200)

    def ticksChanged(self,LUT):
        self.sigSliceChanged.emit()
        #tuple(sorted(LUT.gradient.ticks.values()))

    def getSlice(self):
        bounds = sorted(self.item.gradient.ticks.values())
        bounds = (bounds[0]*self.item.region.getRegion()[1],bounds[1]*self.item.region.getRegion()[1])
        return slice(*bounds)


class VolumeVisual(scene.visuals.Volume):
    def set_data(self, vol, clim=None):
        """ Set the volume data.

        Parameters
        ----------
        vol : ndarray
            The 3D volume.
        clim : tuple | None
            Colormap limits to use. None will use the min and max values.
        """
        # Check volume
        if not isinstance(vol, np.ndarray):
            raise ValueError('Volume visual needs a numpy array.')
        if not ((vol.ndim == 3) or (vol.ndim == 4 and vol.shape[-1] <= 4)):
            raise ValueError('Volume visual needs a 3D image.')

        # Handle clim
        if clim is not None:
            clim = np.array(clim, float)
            if not (clim.ndim == 1 and clim.size == 2):
                raise ValueError('clim must be a 2-element array-like')
            self._clim = tuple(clim)
        self._clim = vol.min(), vol.max()   #NOTE: THIS IS MODIFIED BY RP TO RESET MIN/MAX EACH TIME

        # Apply clim
        vol = np.array(vol, dtype='float32', copy=False)
        vol -= self._clim[0]
        vol *= 1./(self._clim[1] - self._clim[0])

        # Apply to texture
        self._tex.set_data(vol)  # will be efficient if vol is same shape
        self._program['u_shape'] = vol.shape[2], vol.shape[1], vol.shape[0]
        self._vol_shape = vol.shape[:3]

        # Create vertices?
        if self._index_buffer is None:
            self._create_vertex_data()

scene.visuals.Volume = VolumeVisual