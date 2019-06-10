# -*- coding:utf-8 -*-
# _Author_:@WangTianXiang

#------------导入环境所需要的库------------#
import os
import sys
import copy
import time
import traceback
import re
import webbrowser
from functools import partial
import hiero.ui
import hiero.core
from hiero.core.events import*
try:
    from PySide import QtGui as QtWidgets
    from PySide import QtCore
except:
    from PySide2 import QtWidgets
    from PySide2 import QtGui
    from PySide2 import QtCore
import HieroApi as api
from operator import itemgetter, attrgetter
Locator = []
GIF_FILE = os.path.join(os.path.expanduser('~'),'.nuke/Python/Startup/Loading.gif').replace('\\','/')
QtCore.QCoreApplication.addLibraryPath(os.path.join(os.path.dirname(QtCore.__file__), "plugins"))
MOVE_PNG = os.path.join(os.path.expanduser('~'),'.nuke/Python/Startup/move.png').replace('\\','/')
#-----------------------------------------------进度条函数---------------------------------#
def _showProgress(label = '' , waitSeconds = 0.01) :
    def call(func) :
        def handle(*args , **kwargs) :
            progress = TextProgressDialog(label , action = func , args = args , kwargs = kwargs ,
                                          waitSeconds = waitSeconds , parent = args[0])
            return progress.start()
        return handle
    return call
#----------------------------消除选择边框--------------------------#
class NoFocusDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, QPainter, QStyleOptionViewItem, QModelIndex):
        if (QStyleOptionViewItem.state & QtWidgets.QStyle.State_HasFocus):
            QStyleOptionViewItem.state = QStyleOptionViewItem.state^QtWidgets.QStyle.State_HasFocus
        QtWidgets.QStyledItemDelegate.paint(self,QPainter, QStyleOptionViewItem, QModelIndex)

#-----------------------------------------------Nuke拖拽接受函数---------------------------#
class BinViewDropHandler:
    kTextMimeType = "text/plain"
    def __init__(self,parent = None):
        self._HieroAPI = api.HieroApi()
        self._MainUI = parent
        # hiero doesn't deal with drag and drop for text/plain data, so tell it to allow it
        hiero.ui.registerBinViewCustomMimeDataType(BinViewDropHandler.kTextMimeType)
        # register interest in the drop event now
        hiero.core.events.registerInterest((EventType.kDrop, EventType.kBin), self.dropHandler)
    def dropHandler(self, event):
        # get the mime data
        # fast/easy way to get at text data
        if event.mimeData.hasText():
            print 'hasText'
            print event.mimeData.text()
        # more complicated way
        if event.mimeData.hasFormat(BinViewDropHandler.kTextMimeType):
            byteArray = event.mimeData.data(BinViewDropHandler.kTextMimeType)
            print 'hasFormat'
            print byteArray.data()
            if '[' in byteArray.data():
                DragData = eval(byteArray.data())
            else:
                DragData = byteArray.data()
            print 'DragData',DragData
            if 'Dailies' in DragData:
                DragData.pop(-1)
                self._HieroAPI.setDailies(DragData)
                self._MainUI.UpdataDailes()
            elif 'PMD' in DragData:
                eps_name = DragData[-1]
                print 'DragData',DragData
                DragData.pop(-1)
                DragData.pop(-1)
                # DragData = [(DragData[0])]
                self._HieroAPI.setPmd(DragData,eps_name)
                self._MainUI.UpdataPMD()
            elif 'Final' in DragData:
                DragData.pop(-1)
                self._HieroAPI.setFinal(DragData)
                self._MainUI.UpdataFinal()
            # signal that we've handled the event here
            event.dropEvent.accept()
        # get custom hiero objects if drag from one view to another (only present if the drop was from one hiero view to another)
        if hasattr(event, "items"):
            print "hasItems"
            print event.items
        # figure out which item it was dropped onto
        print "dropItem: ", event.dropItem

        # get the widget that the drop happened in
        print "dropWidget: ", event.dropWidget

        # get the higher level container widget (for the Bin View, this will be the Bin View widget)
        print "containerWidget: ", event.containerWidget

        # can also get the sender
        print "eventSender: ", event.sender
    # def unregister(self):
    # unregisterInterest((EventType.kDrop, EventType.kBin), self.dropHandler)
    # hiero.ui.unregisterBinViewCustomMimeDataType(BinViewDropHandler.kTextMimeType)
# Instantiate the handler to get it to register itself.
# dropHandler = BinViewDropHandler()
#-----------------------------------------------PMD素材TableWid控件函数，重写Tablewidget--------------------#
class PmdTableWidget(QtWidgets.QTableWidget):
    def __init__(self,parent = None):
        super(PmdTableWidget,self).__init__(parent)
        self._HieroAPI = api.HieroApi()
        self._mianUI()
        self._parent = parent
    def _mianUI(self):
        '''
        实例化控件的属性，
        开启拖拽功能，但不开启接受拖拽，设置不可编辑，多选
        :return:
        '''
        self.setDragEnabled(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(60)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([u'镜头号',u'制作人',u'文件数量',u'文件名',u'文件路径',])
        self.setColumnWidth(0,120)
        self.setColumnWidth(1,70)
        self.setColumnWidth(2,50)
        self.setColumnWidth(3,230)
        self.setColumnWidth(4,370)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.doubleClicked.connect(self.OpenPath)
        self.initColorWidget()

    # -----------------------------------------------初始化颜色空间，用来标记状态--------------------#
    def initColorWidget(self):
        try:
            self.Red_Color = QtWidgets.QBrush(QtWidgets.QColor('red'))
            self.Green_Color = QtWidgets.QBrush(QtWidgets.QColor('green'))
            self.Blue_Color = QtWidgets.QBrush(QtWidgets.QColor('blue'))
        except:
            self.Red_Color = QtGui.QBrush(QtGui.QColor('red'))
            self.Green_Color = QtGui.QBrush(QtGui.QColor('green'))
            self.Blue_Color = QtGui.QBrush(QtGui.QColor('blue'))

    # -----------------------------------------------重写鼠标移动事件，将item中对应的路径信息携带到数据中Drag--------------------#
    def mouseMoveEvent(self,event):
        '''
        拖拽事件
        :param event:
        :return:
        '''
        
        super(PmdTableWidget, self).mouseMoveEvent(event)#继承原生态空间的属性
        DragPath = [] # 存储Table上的路径信息
        PathsIndex = self.selectedIndexes()#获取选择的列

        for model in xrange(3,len(PathsIndex),5):
            Nameitems = self.itemFromIndex(PathsIndex[model])#获取文件名Item
            PathsItems = self.itemFromIndex(PathsIndex[model+1])#获取文件路径Item
            AllPaths = eval(PathsItems.text())#将字符串路径转化成列表
            if Nameitems is None:#如果文件名对应的是combox，来获取combox控件中的信息
                RowCount = PathsIndex[model].row()
                FileName = self.cellWidget(RowCount, 3).currentText()
                FilePath = [x for x in AllPaths if FileName in x][0]#判断用户选择的文件名与路径进行匹配
                DragPath.append(FilePath)
            else:
                FileName = Nameitems.text()
                FilePath = AllPaths[0]
                DragPath.append(FilePath)
        DragPath.append('PMD')
        DragPath.append(self._parent._eps_name)
        data = str(DragPath)
        Data = QtCore.QMimeData()
        Data.setText(data)
        try:
            drag = QtWidgets.QDrag(self)
        except:
            drag = QtGui.QDrag(self)
        drag.setMimeData(Data)
        try:
            drag.setPixmap(QtGui.QPixmap(MOVE_PNG))
        except:
            drag.setPixmap(QtWidgets.QPixmap(MOVE_PNG))
        dropAction = drag.start(QtCore.Qt.MoveAction)
        

    #-------------------------------------------------Item双击打开视频------------------------#
    def OpenPath(self,index):
        modelIndex = self.selectedIndexes()[3]
        PathsIndex = self.selectedIndexes()[4]
        Nameitems = self.itemFromIndex(modelIndex)
        PathsItems = self.itemFromIndex(PathsIndex)
        AllPaths = eval(PathsItems.text())
        if Nameitems is None:
            RowCount = modelIndex.row()
            FileName = self.cellWidget(RowCount, 3).currentText()
            FilePath = [x for x in AllPaths if FileName in x][0]
            webbrowser.open(FilePath)
        else:
            FileName = Nameitems.text()
            FilePath = AllPaths[0]
            webbrowser.open(FilePath)

    def compareData(self,data,allData):
        #判断当前文件是否已经在项目中了
        for i in allData:
            if data in i:
                return True
        return False
        
    #----------------------------------------------------数据显示到界面上，并且判断文件的状态并且标记--------------------#
    def setTableData(self,pmd_dict):
        '''
        将数据显示到PMD环节下
        :param pmd_dict: 从Teamwork中获取到的素材信息
        :return:
        '''
        AllItem = self._HieroAPI.getAllItems(str(self._parent._eps_name))#获取工程文件中对应PMD夹子下面的item，返回的信息为字典
        AllItemKey = AllItem.keys()#提取字段中对应的键值
        # result_name = [result.split('_')[1] for result in AllItemKey]#进行切片操作，比对镜头号信息而不是全名称
        self.clearContents()
        self.setRowCount(0)
        information = pmd_dict
        if information != []:
            self.setRowCount(len(information))
        for index, data in enumerate(information):
            item_0 = QtWidgets.QTableWidgetItem(data['shot.shot'])
            self.setItem(index, 0, item_0)  # 镜头号
            item_0.setToolTip(data['shot.shot'])
            if AllItemKey == []:
                item_0.setBackground(self.Red_Color)
            else:
                # Shot_Name = data['shot.shot'].split('_')[0]
                full_name = os.path.splitext(data['pmdName'][0])[0]
                # print 'haha',Shot_Name,result_name
                if self.compareData(full_name,AllItemKey):
                # if Shot_Name in result_name:#首先判断文件是否在工程中已经完全匹配上
                    item_0.setBackground(self.Green_Color)
                else:
                    item_0.setBackground(self.Red_Color)

            item_1 = QtWidgets.QTableWidgetItem(data['task.artist'])
            self.setItem(index, 1, item_1)  # 制作人
            item_1.setToolTip(data['task.artist'])

            item_2 = QtWidgets.QTableWidgetItem(str(len(data['pmdPath'])))
            self.setItem(index, 2, item_2)  # 文件数量

            if len(data['pmdPath'])>1:
                PmdPathBox = QtWidgets.QComboBox()
                PmdPathBox.addItems(data['pmdName'])
                self.setCellWidget(index, 3, PmdPathBox)
            else:
                item_3 = QtWidgets.QTableWidgetItem((data['pmdName'][0]))
                self.setItem(index, 3, item_3)  # 文件名
                item_3.setToolTip(str(data['pmdName']))

            item_4 = QtWidgets.QTableWidgetItem(str(data['pmdPath']))
            self.setItem(index, 4, item_4)  # 文件路径
            item_4.setToolTip(str(data['pmdPath']))
#-----------------------------------------------Tabwidget下的PMD界面布局----------------------#
class PmdView(QtWidgets.QDialog):
    def __init__(self,parent = None):
        super(PmdView,self).__init__(parent)
        self._parent = parent
        self._HieroAPI = api.HieroApi()
        self._mianUI()
        
#----------------------------------PMD界面的布局----------------------------------------------#
    def _mianUI(self):
        self.PmdTableWd = PmdTableWidget(self)
        self.exprotPMD = QtWidgets.QPushButton('import PMD')
        self.exprotPMD.setFixedSize(80, 30)
        HLayout = QtWidgets.QHBoxLayout()
        HLayout.addStretch()
        HLayout.addWidget(self.exprotPMD)
        HLayout.addStretch()
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.PmdTableWd)
        mainLayout.addLayout(HLayout)
        self.setLayout(mainLayout)
        self.exprotPMD.clicked.connect(self.RunImport)
        
#--------------------------------主界面链接的PMD界面刷新函数------------------------------#
    def setTableData(self, pmd_dict):
        '''
        将数据写入PMD 表格中
        :param pmd_dict:
        :return:
        '''
        sort_pmd_dict = sorted(pmd_dict, key=itemgetter('shot.shot'))#根据镜头号排序
        
        self._eps_name = self._parent.Eps_Box.currentText()
        self.tempPmd = copy.deepcopy(sort_pmd_dict)
        self.PmdTableWd.setTableData(sort_pmd_dict)
        
#--------------------------------PMD界面信息全部导入Hiero中-------------------------------#
    def RunImport(self):
        '''
        进行PMD素材的导入功能
        :return:
        '''
        result_Pmd = []
        Count =  self.PmdTableWd.rowCount()
        for ii in xrange(Count):
            AllFilePath = eval(self.PmdTableWd.item(ii,4).text())
            if self.PmdTableWd.item(ii,3) is None:
                FileName = self.PmdTableWd.cellWidget(ii, 3).currentText()
                FilePath = [x for x in AllFilePath if FileName in x][0]
                result_Pmd.append(FilePath)
            else:
                for FilePath in AllFilePath:
                    result_Pmd.append(FilePath)
        result_Pmd = sorted(result_Pmd)
        self.importHiero(result_Pmd)
        self.PmdTableWd.setTableData(self.tempPmd)
        
        
#--------------------------------调用API导入函数----------------------------------------#
    def importHiero(self,Paths):
        
        self._HieroAPI.setPmd(Paths,self._eps_name)
#-----------------------------------------------DailiesTableWidget控件函数--------------------#
class DailiesTableWidget(QtWidgets.QTableWidget):
    def __init__(self,parent = None):
        super(DailiesTableWidget,self).__init__(parent)
        self._HieroAPI = api.HieroApi()

        self._mianUI()

    def _mianUI(self):
        '''
        实例化控件的属性，
        开启拖拽功能，但不开启接受拖拽，设置不可编辑，多选
        :return:
        '''
        self.setDragEnabled(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(60)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([u'镜头号',u'制作人',u'提交时间',u'组长状态',u'文件名',u'升级版本',u'文件路径'])
        self.setItemDelegate(NoFocusDelegate())
        self.setColumnWidth(0,110)
        self.setColumnWidth(1,60)
        self.setColumnWidth(2,130)
        self.setColumnWidth(3,60)
        self.setColumnWidth(4,270)
        self.setColumnWidth(5,60)
        self.setColumnWidth(6,320)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.initColorWidget()
    # -----------------------------------------------初始化颜色空间，用来标记状态--------------------#
    def initColorWidget(self):
        try:
            self.Red_Color = QtWidgets.QBrush(QtWidgets.QColor('red'))
            self.Green_Color = QtWidgets.QBrush(QtWidgets.QColor('green'))
            self.Blue_Color = QtWidgets.QBrush(QtWidgets.QColor('blue'))
        except:
            self.Red_Color = QtGui.QBrush(QtGui.QColor('red'))
            self.Green_Color = QtGui.QBrush(QtGui.QColor('green'))
            self.Blue_Color = QtGui.QBrush(QtGui.QColor('blue'))
    # -----------------------------------------------重写鼠标移动事件，将item中对应的路径信息携带到数据中Drag--------------------#
    def mouseMoveEvent(self,event):
        '''
        拖拽事件
        :param event:
        :return:
        '''
        if event.buttons() == QtCore.Qt.LeftButton:
            DragPath = []#存储路径信息
            PathsIndex = self.selectedIndexes()#获取选择的列
            for i in xrange(6,len(PathsIndex),7):
                DragPath.append(self.itemFromIndex(PathsIndex[i]).text())
            DragPath.append('Dailies')#标记为Dailies，方便Hiero识别是那个页面拖拽进来的
            data = str(DragPath)
            Data = QtCore.QMimeData()
            Data.setText(data)
            try:
                drag = QtWidgets.QDrag(self)
            except:
                drag = QtGui.QDrag(self)
            drag.setMimeData(Data)
            try:
                drag.setPixmap(QtGui.QPixmap(MOVE_PNG))
            except:
                drag.setPixmap(QtWidgets.QPixmap(MOVE_PNG))
            dropAction = drag.start(QtCore.Qt.MoveAction)

    #-----------------------------------------------将数据显示到Dailies页面上，同时进行文件是否存在，版本是否对应进行处理提示----------------#
    def setDailiesData(self,dailies_dict):
        self.All_waitVersion = []
        self._Version_Updata = copy.deepcopy(dailies_dict)#拷贝一份信息用于刷新界面
        AllItem = self._HieroAPI.getAllItems('Dailies')#获取工程中对应Dailis夹子下面所有item
        AllItemKey = AllItem.keys()
        TrackItem = self._HieroAPI.getTrackVideo('dailies')#获取工程文件中，时间线上的Video，筛选文件名中函数dailies的文件item
        TrackItemKey = TrackItem.keys()

        self.clearContents()
        self.setRowCount(0)
        information = dailies_dict
        if information != []:
            self.setRowCount(len(information))
        for index, data in enumerate(information):
            item_0 = QtWidgets.QTableWidgetItem(data['shot.shot'])
            self.setItem(index, 0, item_0)  # 镜头号
            item_0.setToolTip(data['shot.shot'])

            item_1 = QtWidgets.QTableWidgetItem(data['task.artist'])
            self.setItem(index, 1, item_1)  # 制作人
            item_1.setToolTip(data['task.artist'])

            item_2 = QtWidgets.QTableWidgetItem(data['version_time'])
            self.setItem(index, 2, item_2)  # 提交时间

            item_3 = QtWidgets.QTableWidgetItem((data['task.leader_status']))
            self.setItem(index, 3, item_3)  # 组长状态
            item_3.setToolTip(data['task.leader_status'])

            item_4 = QtWidgets.QTableWidgetItem((data['version_fileName']))
            self.setItem(index, 4, item_4)  # 文件名
            item_4.setToolTip(str(data['version_fileName']))
            if AllItemKey == []:
                item_4.setBackground(self.Red_Color)
            else:
                File_Name = os.path.splitext(data['version_fileName'])[0]
                Version_File =re.findall('_v+\d+',File_Name)[0]#获取文件当前版本号
                Match_File = File_Name.split(Version_File)[0] #获取文件不带版本号的名字
                if [x for x in AllItemKey if x in File_Name]:#首先判断文件是否存在HieroBin中，存在为绿色不存在为红色
                    item_4.setBackground(self.Green_Color)
                else:
                    item_4.setBackground(self.Red_Color)
                waitVersion =  [y for y in TrackItemKey if Match_File in y and File_Name not in y]#判断文件版本信息是否与提交的文件版本一致，首先判断不带版本的文件是否存在，
                # 同时带版本号的相同文件不存在则说明版本号不对应
                print 'print',TrackItemKey,Match_File
                if waitVersion:#如果成立则增加升级按钮控件
                    self.All_waitVersion.append(TrackItem[waitVersion[0]])#存储版本不对应的item
                    item_4.setBackground(self.Blue_Color)
                    VersionUp_button = QtWidgets.QPushButton(u'升级')
                    self.setCellWidget(index, 5, VersionUp_button)
                    VersionUp_button.clicked.connect(partial(self.SetVersion_api,TrackItem[waitVersion[0]]))

            item_5 = QtWidgets.QTableWidgetItem((data['version_filePath']))
            self.setItem(index, 6, item_5)  # 文件路径
            item_5.setToolTip(str(data['version_filePath']))
#----------------------------------------------单独升级版本函数-----------------------------#
    def SetVersion_api(self,Data):
        self._HieroAPI.VersionUp(Data)
        self.setDailiesData(self._Version_Updata)

#---------------------------------------------同步所有版本函数------------------------------#
    def AllVersion_api(self):
        if self.All_waitVersion!=[]:
            self._HieroAPI.VersionAllUp(self.All_waitVersion)
            self.setDailiesData(self._Version_Updata)
            
            

        
#----------------------------------------------dailies页面的布局-----------------------------#
class DailiesView(QtWidgets.QDialog):
    def __init__(self,parent = None):
        super(DailiesView,self).__init__(parent)
        self._HieroAPI = api.HieroApi()
        self._CGTW = api.CGTW()
        self._parent = parent
        self._mianUI()
    def _mianUI(self):
        self.DailiesTableWd = DailiesTableWidget()
        self.exprotDailies = QtWidgets.QPushButton(u'导入全部dailies')
        self.exprotDailies.setFixedSize(90, 30)
        self.Updata_All = QtWidgets.QPushButton(u'同步所有版本')
        self.Updata_All.setFixedSize(90,30)
        HLayout = QtWidgets.QHBoxLayout()
        HLayout.addStretch()
        HLayout.addWidget(self.exprotDailies)
        HLayout.addStretch()
        HLayout.addWidget(self.Updata_All)
        HLayout.addStretch()
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.DailiesTableWd)
        mainLayout.addLayout(HLayout)
        self.setLayout(mainLayout)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        
        self.exprotDailies.clicked.connect(self.RunImport)
        self.Updata_All.clicked.connect(self.synchronizationVerAll)
         
    def setDaiUI(self, dailies_dict):
        '''
        将数据写入dailies 表格中
        :param pmd_dict:
        :return:
        '''
        self.tempDailies = copy.deepcopy(dailies_dict)
        self.DailiesTableWd.setDailiesData(dailies_dict)
    def RunImport(self):
        '''
        进行dailies素材的导入功能
        :return:
        '''
        result_Dailies = []
        Count = self.DailiesTableWd.rowCount()
        for ii in xrange(Count):
            FilePath = self.DailiesTableWd.item(ii, 6).text()
            result_Dailies.append(FilePath)
        result_Dailies = sorted(result_Dailies)
        self.importHiero(result_Dailies)
        self.DailiesTableWd.setDailiesData(self.tempDailies)
        
#-----------------------------------调用API函数---------------------#
    def importHiero(self, Paths):
        self._HieroAPI.setDailies(Paths)
    def synchronizationVerAll(self):
        self.DailiesTableWd.AllVersion_api()
    def showContextMenu(self, pos=None):
        """
        显示上下文文件夹按钮
        :type pos: None or QtCore.QPoint
        :rtype: QtWidgets.QAction
        """
        PathsIndex = self.DailiesTableWd.selectedIndexes()#获取选择的列
        if PathsIndex:
            menu = self.createMenu()
            try:
                point = QtWidgets.QCursor.pos()
            except:
                point = QtGui.QCursor.pos()
            point.setX(point.x() + 3)
            point.setY(point.y() + 3)
            action = menu.exec_(point)

            menu.close()
            return action
            
    def createMenu(self):
        contextMenu = QtWidgets.QMenu(self)  # 创建QMenu
        self.approveAction = contextMenu.addAction('Approve')
        self.approveAction.triggered.connect(self.approveFunc)

        return contextMenu
        
    def approveFunc(self):
        shotlist = []
        Pro_name = self._parent.Pro_Box.currentText()
        Eps_name = self._parent.Eps_Box.currentText()
        PathsIndex = self.DailiesTableWd.selectedIndexes()#获取选择的列
        for i in xrange(0,len(PathsIndex),7):
            shotlist.append(self.DailiesTableWd.itemFromIndex(PathsIndex[i]).text())
        self._CGTW.checkStatus(Pro_name,Eps_name,shotlist)
        self._parent.Updata()

        
class FinalTableWidget(QtWidgets.QTableWidget):
    def __init__(self,parent = None):
        super(FinalTableWidget,self).__init__(parent)
        self._mianUI()
        self._HieroAPI = api.HieroApi()
    def _mianUI(self):
        '''
        实例化控件的属性，
        开启拖拽功能，但不开启接受拖拽，设置不可编辑，多选
        :return:
        '''
        self.setDragEnabled(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(60)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([u'镜头号',u'制作人',u'提交时间',u'组长状态',u'文件名',u'升级版本',u'文件路径'])
        self.setItemDelegate(NoFocusDelegate())
        self.setColumnWidth(0,110)
        self.setColumnWidth(1,60)
        self.setColumnWidth(2,130)
        self.setColumnWidth(3,60)
        self.setColumnWidth(4,270)
        self.setColumnWidth(5,60)
        self.setColumnWidth(6,320)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.initColorWidget()
    # -----------------------------------------------初始化颜色空间，用来标记状态--------------------#
    def initColorWidget(self):
        try:
            self.Red_Color = QtWidgets.QBrush(QtWidgets.QColor('red'))
            self.Green_Color = QtWidgets.QBrush(QtWidgets.QColor('green'))
            self.Blue_Color = QtWidgets.QBrush(QtWidgets.QColor('blue'))
        except:
            self.Red_Color = QtGui.QBrush(QtGui.QColor('red'))
            self.Green_Color = QtGui.QBrush(QtGui.QColor('green'))
            self.Blue_Color = QtGui.QBrush(QtGui.QColor('blue'))
    # -----------------------------------------------重写鼠标移动事件，将item中对应的路径信息携带到数据中Drag--------------------#
    def mouseMoveEvent(self,event):
        '''
        拖拽事件
        :param event:
        :return:
        '''
        DragPath = []#存储路径信息
        PathsIndex = self.selectedIndexes()#获取选择的列
        for i in xrange(6,len(PathsIndex),7):
            DragPath.append(self.itemFromIndex(PathsIndex[i]).text())
        DragPath.append('Final')#标记为Dailies，方便Hiero识别是那个页面拖拽进来的
        
        data = str(DragPath)
        Data = QtCore.QMimeData()
        Data.setText(data)
        try:
            drag = QtWidgets.QDrag(self)
        except:
            drag = QtGui.QDrag(self)
        drag.setMimeData(Data)
        try:
            drag.setPixmap(QtGui.QPixmap(MOVE_PNG))
        except:
            drag.setPixmap(QtWidgets.QPixmap(MOVE_PNG))
        dropAction = drag.start(QtCore.Qt.MoveAction)
#------------------------------Final检测版本号需要找到Clip对其进行reconnectMedia--------------------------------#
    def setFinalData(self,final_dict):
        self.All_waitVersion = []
        self._Version_Updata = copy.deepcopy(final_dict)#拷贝一份信息用于刷新界面
        AllItem = self._HieroAPI.getAllItems('Final')#获取工程中对应Dailis夹子下面所有item
        AllItemKey = AllItem.keys()
        TrackItem = self._HieroAPI.getTrackVideo('final')#获取工程文件中，时间线上的Video，筛选文件名中函数dailies的文件item
        TrackItemKey = TrackItem.keys()
        self.clearContents()
        self.setRowCount(0)
        information = final_dict
        if information != []:
            self.setRowCount(len(information))
        for index, data in enumerate(information):
            item_0 = QtWidgets.QTableWidgetItem(data['shot.shot'])
            self.setItem(index, 0, item_0)  # 镜头号
            item_0.setToolTip(data['shot.shot'])

            item_1 = QtWidgets.QTableWidgetItem(data['task.artist'])
            self.setItem(index, 1, item_1)  # 制作人
            item_1.setToolTip(data['task.artist'])

            item_2 = QtWidgets.QTableWidgetItem(data['version_time'])
            self.setItem(index, 2, item_2)  # 提交时间

            item_3 = QtWidgets.QTableWidgetItem((data['task.leader_status']))
            self.setItem(index, 3, item_3)  # 组长状态
            item_3.setToolTip(data['task.leader_status'])

            item_4 = QtWidgets.QTableWidgetItem((data['version_fileName']))
            self.setItem(index, 4, item_4)  # 文件名
            item_4.setToolTip(str(data['version_fileName']))
            if AllItemKey == []:
                item_4.setBackground(self.Red_Color)
            else:
                File_Name = os.path.splitext(data['version_fileName'])[0]
                Version_File =re.findall('_v+\d+',File_Name)[0]#获取文件当前版本号
                Match_File = File_Name.split(Version_File)[0] #获取文件不带版本号的名字
                if [x for x in AllItemKey if x in File_Name]:#首先判断文件是否存在HieroBin中，存在为绿色不存在为红色
                    item_4.setBackground(self.Green_Color)
                else:
                    item_4.setBackground(self.Red_Color)
                waitVersion =  [y for y in TrackItemKey if Match_File in y and File_Name not in y]#判断文件版本信息是否与提交的文件版本一致，首先判断不带版本的文件是否存在，
                # 同时带版本号的相同文件不存在则说明版本号不对应
                if waitVersion:#如果成立则增加升级按钮控件
                    self.All_waitVersion.append(TrackItem[waitVersion[0]])#存储版本不对应的item
                    item_4.setBackground(self.Blue_Color)
                    VersionUp_button = QtWidgets.QPushButton(u'升级')
                    self.setCellWidget(index, 5, VersionUp_button)
                    VersionUp_button.clicked.connect(partial(self.SetVersion_api,TrackItem[waitVersion[0]]))

            item_5 = QtWidgets.QTableWidgetItem((data['version_filePath']))
            self.setItem(index, 6, item_5)  # 文件路径
            item_5.setToolTip(str(data['version_filePath']))

    # ----------------------------------------------单独升级版本函数-----------------------------#
    def SetVersion_api(self, Data):
        self._HieroAPI.VersionUp(Data)
        self.setDailiesData(self._Version_Updata)

        
    # ---------------------------------------------同步所有版本函数------------------------------#
    def AllVersion_api(self):
        if self.All_waitVersion != []:
            self._HieroAPI.VersionAllUp(self.All_waitVersion)
            self.setDailiesData(self._Version_Updata)

class FinalView(QtWidgets.QDialog):
    def __init__(self,parent = None):
        super(FinalView,self).__init__(parent)
        self._HieroAPI = api.HieroApi()
        self._mianUI()

    def _mianUI(self):
        self.FinalTableWd = FinalTableWidget()
        self.exprotFinal = QtWidgets.QPushButton('import Final')
        self.exprotFinal.setFixedSize(90, 30)
        self.Updata_All = QtWidgets.QPushButton(u'同步所有版本')
        self.Updata_All.setFixedSize(90,30)
        
        HLayout = QtWidgets.QHBoxLayout()
        HLayout.addStretch()
        HLayout.addWidget(self.exprotFinal)
        HLayout.addStretch()
        HLayout.addWidget(self.Updata_All)
        HLayout.addStretch()
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(self.FinalTableWd)
        mainLayout.addLayout(HLayout)
        self.setLayout(mainLayout)
        self.exprotFinal.clicked.connect(self.RunImport)
    def setFinUI(self, final_dict):
        '''
        将数据写入Final表格中
        :param pmd_dict:
        :return:
        '''
        self.tempFinal = copy.deepcopy(final_dict)
        self.FinalTableWd.setFinalData(final_dict)
        
    def RunImport(self):
        '''
        进行dailies素材的导入功能
        :return:
        '''
        result_Finals = []
        Count = self.FinalTableWd.rowCount()
        for ii in xrange(Count):
            FilePath = self.FinalTableWd.item(ii, 6).text()
            result_Finals.append(FilePath)
        result_Finals = sorted(result_Finals)
        self.importHiero(result_Finals)
        self.FinalTableWd.setFinalData(self.tempFinal)

#--------------------------------调用API导入函数----------------------------------------#
    def importHiero(self,Paths):
        self._HieroAPI.setFinal(Paths)

class HieroMainUI(QtWidgets.QDialog):
    def __init__(self,parent = None):
        super(HieroMainUI,self).__init__(parent)
        self.setWindowTitle( "PipelineTool" )
        try:
            self.setWindowIcon(QtWidgets.QIcon("icons:FBGridView.png"))
        except:
            self.setWindowIcon(QtGui.QIcon("icons:FBGridView.png"))
        self._cgtw = api.CGTW()
        self._initUI()
        dropHandler = BinViewDropHandler(self)
    def _initUI(self):
        self.resize(1220,610)
        self.setWindowFlags(QtCore.Qt.WindowMinMaxButtonsHint)
        Pro_Label = QtWidgets.QLabel(u'项目名')
        self.Pro_Box = QtWidgets.QComboBox()
        self.Pro_Box.setFixedSize(80,20)
        self.Pro_Box.addItems(self._cgtw.getAllProject())
        self.Pro_Box.currentIndexChanged.connect(self.setEpsComBox)

        Eps_Label = QtWidgets.QLabel(u'集数')
        self.Eps_Box = QtWidgets.QComboBox()
        self.Eps_Box.setFixedSize(100,20)
        
        self.Eps_Box.currentIndexChanged.connect(self.setGroupComBox)

        Group_Label = QtWidgets.QLabel(u'组名')
        self.Group_Box = QtWidgets.QComboBox()
        self.Group_Box.setFixedSize(80, 20)
        self.Group_Box.currentIndexChanged.connect(self.runSetData)
        
        self.updata_button = QtWidgets.QPushButton(u'刷新')
        self.updata_button.setFixedSize(80, 20)
        
        
        self.TableLayout = QtWidgets.QTabWidget()
        self.PmdWidget = PmdView(self)
        self.dailiesWidget = DailiesView(self)
        self.finalWidget = FinalView(self)

        self.TableLayout.addTab(self.PmdWidget,'PMD')
        self.TableLayout.addTab(self.dailiesWidget,'Dailies')
        self.TableLayout.addTab(self.finalWidget, 'Final')

        self.TableLayout.currentChanged.connect(self.ChangeTab)
        Hlayout1 = QtWidgets.QHBoxLayout()
        Hlayout1.setContentsMargins(8, 0, 8, 0)
        Hlayout1.addWidget(Pro_Label)
        Hlayout1.addWidget(self.Pro_Box)
        Hlayout1.addStretch()
        Hlayout1.addWidget(Eps_Label)
        Hlayout1.addWidget(self.Eps_Box)
        Hlayout1.addStretch()
        Hlayout1.addWidget(Group_Label)
        Hlayout1.addWidget(self.Group_Box)
        Hlayout1.addStretch()
        Hlayout1.addWidget(self.updata_button)
        # Hlayout1.addStretch()

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addLayout(Hlayout1)
        mainLayout.addWidget(self.TableLayout)

        self.setLayout(mainLayout)
        
        self.updata_button.clicked.connect(self.Updata)
        
    def ChangeTab(self,index):
        if index == 0:
            print 'PMD'
        elif index == 1:
            print 'dailies'
            self.setDailiesView('dailies')
        elif index == 2:
            print 'final'
            self.setFinalView('final')

    def Updata(self):
        Pro_name = self.Pro_Box.currentText()
        Eps_name = self.Eps_Box.currentText()
        Group_name = self.Group_Box.currentText()
        if Pro_name != '' and Eps_name != '' and Group_name != '':
            currentTab = self.TableLayout.currentIndex()
            print type(currentTab)
            if currentTab == 0: #如果当前Tab为0的话,则当前激活的是PMD面板
                PmdData = self.setMainData(Pro_name,Eps_name,Group_name)
                self.PmdWidget.setTableData(PmdData)
            elif currentTab == 1: #如果当前Tab为1的话,则当前激活的是Dailies面板
                self.setDailiesView('dailies')
            elif currentTab == 2: #否则为Final面板
                self.setFinalView('final')
            

    def moveEvent(self, event):
        Locator.append(self.frameGeometry())    # 获取主窗体的位置及大小信息
    
    def setEpsComBox(self):
        self.Eps_Box.clear()
        self.Group_Box.clear()
        if self.Pro_Box.currentText() != '':
            self.Eps_Box.addItems(self._cgtw.getEps(self.Pro_Box.currentText()))
            
            
            
    def setGroupComBox(self):
        
        currentGroup = self.Group_Box.currentText()
        # self.Group_Box.clear()
        if self.Pro_Box.currentText() != '' and self.Eps_Box.currentText()!='':
            Name = self._cgtw.getGroupName(self.Pro_Box.currentText(),self.Eps_Box.currentText())
            self.Group_Name = copy.deepcopy(Name)
            if currentGroup in Name and currentGroup != '':
                groupIndex = Name.index(currentGroup)
                self.Group_Box.clear()
                self.Group_Box.addItems(Name)
                self.Group_Box.setCurrentIndex(groupIndex)
            else:
                self.Group_Box.clear()
                self.Group_Box.addItems(Name)
            
    def runSetData(self):
        pass
        # Pro_name = self.Pro_Box.currentText()
        # Eps_name = self.Eps_Box.currentText()
        # Group_name = self.Group_Box.currentText()
        # if Pro_name != '' and Eps_name != '' and Group_name != '':
            # PmdData = self.setMainData(Pro_name,Eps_name,Group_name)
            # self.PmdWidget.setTableData(PmdData)
            
    @_showProgress(label='Getting global Information')
    def setMainData(self,Pro_name,Eps_name,Group_name):
        PmdData =  self._cgtw.getPmdInfo(Pro_name,Eps_name,Group_name)
        self.TempPMDdata = copy.deepcopy(PmdData)
        return PmdData

    def setDailiesView(self,filter):
        DailiesData =self.getPublishInfo(filter)
        self.TempDailiesData = copy.deepcopy(DailiesData)
        self.dailiesWidget.setDaiUI(DailiesData)

    def setFinalView(self,filter):
        FinalData = self.getPublishInfo(filter)
        self.TempFinalData = copy.deepcopy(FinalData)
        self.finalWidget.setFinUI(FinalData)

    @_showProgress(label='Getting global Information')
    def getPublishInfo(self,filter):
        Pro_name = self.Pro_Box.currentText()
        Eps_name = self.Eps_Box.currentText()
        Group_name = self.Group_Box.currentText()
        PublishData = self._cgtw.getTaskInfo(Pro_name,Eps_name,Group_name,filter)
        return PublishData

    def UpdataDailes(self):
        self.dailiesWidget.setDaiUI(self.TempDailiesData)

    def UpdataPMD(self):
        self.PmdWidget.setTableData(self.TempPMDdata)
    def UpdataFinal(self):
        self.finalWidget.setFinUI(self.TempFinalData)

class TextProgressDialog(QtWidgets.QLabel):
    '''A dialog to show the progress of the process.'''
    def __init__(self, text, action, args=[], kwargs={}, waitSeconds=1, parent=None):
        '''If the passed time is greater then waitSeconds, the dialog will pop up.'''

        self._text = text + ' '
        self._action = action
        self._args = args
        self._kwargs = kwargs
        self._actionReturned = None
        self._actionFinished = False
        self._actionFailed = False
        self._actionException = ''
        self._thread = None
        self.pointMove = QtCore.QPoint()
        self._waitSeconds = waitSeconds
        self._sleepSecond = 0.13
        self._go = True
        self._app = QtWidgets.QApplication.instance()
        QtWidgets.QLabel.__init__(self, parent)
        self._parent = parent
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    def closeEvent(self, event):
        self._go = False
        QtWidgets.QLabel.closeEvent(self, event)

    def _run(self):
        self._thread = QtCore.QThread(self)
        def run():
            try:
                self._actionReturned = self._action(*self._args, **self._kwargs)
                self._actionFailed = False
            except:
                self._actionFailed = True
                self._actionException = traceback.format_exc()

            self._actionFinished = True
            self._go = False
        self._thread.run = run
        self._thread.start()

    def raiseExceptionDialog(self,error=''):
        import traceback
        if not error:
            error = traceback.format_exc()
        title = 'Error Warning'
        content = 'There is an error!\n'
        content += error
        typ = QtWidgets.QMessageBox.Critical
        print content
        content = unicode(content)
        QtWidgets.QMessageBox(typ, title, content, parent=None).exec_()
    def start(self):
        if self._action:
            self._run()
        start = time.time()
        try:
            self.movie = QtWidgets.QMovie(GIF_FILE)
            # 设置cacheMode为CacheAll时表示gif无限循环，注意此时loopCount()返回-1
            self.movie.setCacheMode(QtWidgets.QMovie.CacheAll)
        except:
            self.movie = QtGui.QMovie(GIF_FILE)
            # 设置cacheMode为CacheAll时表示gif无限循环，注意此时loopCount()返回-1
            self.movie.setCacheMode(QtGui.QMovie.CacheAll)
        # 播放速度
        self.movie.setSpeed(100)
        self.setMovie(self.movie)
        while self._go:
            passedTime = time.time() - start
            if passedTime >= self._waitSeconds:
                if self.isVisible() == False:
                    self.movie.start()
                    self.show()
            self._app.processEvents()
            time.sleep(self._sleepSecond)
        else:
            self._thread.quit()
            self.close()
            if self._actionFailed:
                self.raiseExceptionDialog(error = self._actionException)
            return self._actionReturned

    # 触发重定义大小来获取中心位置，并移动
    def resizeEvent(self, event):
        # 获取parent，即SearchView窗口的宽高。
        self.width = self._parent.frameGeometry().width()
        self.height = self._parent.frameGeometry().height()
        self.x = Locator[-1].x() + self.width/2
        self.y = Locator[-1].y() + self.height/2
        self.pointMove.setX(self.x)
        self.pointMove.setY(self.y)
        self.move(self.pointMove)



hiero.ui.PipelineTool = HieroMainUI()
hiero.ui.PipelineTool.__doc__ = "The File PipelineTool panel object."
hiero.ui.registerPanel( "uk.co.thefoundry.PipelineTool", hiero.ui.PipelineTool )
wm = hiero.ui.windowManager()
wm.addWindow( hiero.ui.PipelineTool)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    WindowsView = HieroMainUI()
    WindowsView.show()
    app.exec_()