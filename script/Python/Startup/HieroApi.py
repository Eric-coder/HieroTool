# -*- coding:utf-8 -*-
import sys
import os
import json
sys.path.append(r'C:\cgteamwork5\bin\base')

class CGTW(object):
    def __init__(self):
        import cgtw2
        self._t_tw = cgtw2.tw()
    def getAllProject(self):
        proj_data = []
        t_id_list = self._t_tw.info.get_id('public', 'project',
                                     [["project.status", "!=", "Lost"], "and", ["project.status", "!=", "Close"]])
        t_data = self._t_tw.info.get('public', 'project', t_id_list, ['project.database', 'project.code'])
        for data in t_data:
            proj_data.append(data['project.code'])
        proj_data.insert(0,'')
        return proj_data
    def getProjectDatabase(self,Pro_Name):
        if Pro_Name != '':
            t_id_list = self._t_tw.info.get_id('public', 'project',
                                         [['project.code','=',Pro_Name]])
            t_data = self._t_tw.info.get('public', 'project', t_id_list, ['project.database'])
            return t_data[0]['project.database']

    def getEps(self,Pro_Name):
        eps_data = []
        t_db = self.getProjectDatabase(Pro_Name)
        t_id_list = self._t_tw.info.get_id(t_db, 'eps', [["eps.eps_name", "has", "%"]])
        t_data = self._t_tw.info.get(t_db, "eps", t_id_list, ['eps.eps_name'])
        for data in t_data:
            eps_data.append(data['eps.eps_name'])
        eps_data.insert(0,'')
        return eps_data

    def getGroupName(self,Pro_Name,eps_name):
        group_name = []
        t_db = self.getProjectDatabase(Pro_Name)
        t_id_list = self._t_tw.task.get_id(t_db, 'shot', [["eps.eps_name", "=", eps_name],"and",['task.flow_name','has',u'合成']])
        t_data =  self._t_tw.task.get(t_db, "shot", t_id_list, ['task.flow_name'])
        for i in t_data:
            group_name.append(i['task.flow_name'])
        nameList=list(set(group_name))
        nameList.insert(0, '')
        return nameList

    def getPmdInfo(self,Pro_Name,eps_name,Group_name):
        infor_data = []
        t_db = self.getProjectDatabase(Pro_Name)

        t_id_list = self._t_tw.task.get_id(t_db, 'shot',
                                     [['shot.eps_name', '=', eps_name], 'and',
                                      ['task.task_name', '=', 'CMP'],'and', ['task.flow_name', '=', Group_name]])

        pipeline_id_list = self._t_tw.pipeline.get_id(t_db,
                                                [['entity_name', '=', 'CMP'], 'and', ['module', '=', 'shot'], 'and',
                                                 ['module_type', '=', 'task']])
        filebox_id = self._t_tw.filebox.get_id(t_db,
                                         [['title', '=', u'PMD'], 'and', ['#pipeline_id', '=', pipeline_id_list[0]]])
        for i in t_id_list:
            Plates = self._t_tw.task.get_filebox(t_db, "shot", i, filebox_id[0])['path']
            t_data = self._t_tw.task.get(t_db, "shot", [i], ['shot.shot','task.artist'])[0]
            tempFiles = []
            tempName = []
            for root,dirname,files in os.walk(Plates):
                if files!=[]:
                    for files_path in files:
                        fileFullPath = os.path.join(root,files_path).replace('\\','/')
                        fileType = os.path.splitext(fileFullPath)[-1]
                        if fileType == '.mov' or fileType == '.MOV':
                            tempName.append(files_path)
                            tempFiles.append(fileFullPath)
            t_data['pmdPath'] = tempFiles
            t_data['pmdName'] = tempName
            # print tempFiles
            infor_data.append(t_data)

        return infor_data


    def getTaskInfo(self,Pro_Name,eps_name,group_name,filter):
        result_data = []
        status =  u'Check'
        t_db = self.getProjectDatabase(Pro_Name)
        t_id_list = self._t_tw.task.get_id(t_db, 'shot',
                                           [["eps.eps_name", "=", eps_name], "and", ['task.flow_name', '=', group_name]])

        t_data = self._t_tw.task.get(t_db, "shot", t_id_list, ['shot.shot','task.leader_status','task.artist'])

        for data in  t_data :
            if data['task.leader_status'] == status:
                version_dict = self.getVersion(t_db,data['id'],filter)
                if version_dict !=None:
                    data['version_fileName'] = json.loads(version_dict['filename'])[0]
                    data['version_filePath'] = json.loads(version_dict['local_path'])[0]
                    data['version_time'] = version_dict['create_time']
                    result_data.append(data)
        return result_data

    def getVersion(self,t_database,t_id_list,filter):
        t_version_final_id_list = self._t_tw.version.get_id(t_database, [['#link_id', '=', t_id_list]])  # 查找提交信息中的final
        allFile_final = self._t_tw.version.get(t_database, t_version_final_id_list,
                                               ['#id', 'filename', 'create_time', 'local_path'])  # 查找之前提交的final
        if allFile_final !=[]:
            New_finalFiles = sorted(allFile_final, key=lambda data: (data['create_time']), reverse=True)
            if filter in  json.loads(New_finalFiles[0]['filename'])[0]:
                return New_finalFiles[0]
            else:
                return None
        else:
            return None
    def checkStatus(self,Pro_Name,eps_name,shotlist):
        t_db = self.getProjectDatabase(Pro_Name)
        for shot in shotlist:
            t_id_list = self._t_tw.task.get_id(t_db, 'shot',
                                         [['shot.eps_name', '=', eps_name], 'and',
                                          ['task.task_name', '=', 'CMP'],'and', ['shot.shot', '=', shot]])
            self._t_tw.task.update_flow(t_db,'shot',t_id_list[0],'task.leader_status','Approve')

class HieroApi(object):
    def __init__(self):
        import nuke
        import nuke.rotopaint
        import hiero.core as HieroCore
        self._HieroCore = HieroCore

    def setPmd(self,Paths,eps_name):
        MyProject = self._HieroCore.projects()[-1]
        AllBin = self.GetAllBins()
        eps_name = str(eps_name)
        if eps_name in AllBin.keys():
            PMDbin = AllBin[eps_name]
        else:
            PMDbin = self._HieroCore.Bin(eps_name)
            clipsBin = MyProject.clipsBin()
            clipsBin.addItem(PMDbin)
        for i in Paths:
            source = (i)
            clip = self._HieroCore.Clip(source)
            PMDbin.addItem(self._HieroCore.BinItem(clip))
    
    def setDailies(self,Paths):
        MyProject = self._HieroCore.projects()[-1]
        AllBin = self.GetAllBins()
        if "Dailies" in AllBin.keys():
            Dailiesbin = AllBin['Dailies']
        else:
            Dailiesbin = self._HieroCore.Bin("Dailies")
            clipsBin = MyProject.clipsBin()
            clipsBin.addItem(Dailiesbin)
        for i in Paths:
            source = (i)
            clip = self._HieroCore.Clip(source)
            Dailiesbin.addItem(self._HieroCore.BinItem(clip))
            
    def setFinal(self,Paths):
        MyProject = self._HieroCore.projects()[-1]
        AllBin = self.GetAllBins()
        if "Final" in AllBin.keys():
            Finalbin = AllBin['Final']
        else:
            Finalbin = self._HieroCore.Bin("Final")
            clipsBin = MyProject.clipsBin()
            clipsBin.addItem(Finalbin)
        for i in Paths:
            source = (i)
            clip = self._HieroCore.Clip(source)
            Finalbin.addItem(self._HieroCore.BinItem(clip))
            
    def GetAllBins(self):
        MyProject = self._HieroCore.projects()[-1]
        BinNames = {}
        AllBin = MyProject.bins()
        for i in AllBin:
            BinName = i.name()
            BinNames[BinName] = i
        return BinNames
    def getAllItems(self,filter):
        '''

        :param filter: 匹配工程BIN的文件名称 如Dailies
        :return:
        '''
        AllItems = {}
        AllBin = self.GetAllBins()
        if filter in AllBin.keys():
            filterbin = AllBin[filter]
            AllItem =  filterbin.items()
            for i in AllItem:
                ItemName = i.name()#.activeVersion()
                AllItems[ItemName] = i
            return AllItems
        else:
            return AllItems

    def getTrackVideo(self,filter):
        '''
        获取时间线上的对应filter的版本信息，查看是否匹配
        :param filter:
        :return:
        '''
        AllTimeEditData = {}
        MyProject = self._HieroCore.projects()[-1]
        MySeqs = MyProject.sequences()
        if MySeqs !=[]:
            MySeq = MySeqs[-1]
            TrackCount = MySeq.numVideoTracks()
            for count in range(TrackCount):
                Track_Pro = MySeq.videoTrack(count)
                Track_Item = Track_Pro.items()
                for items in Track_Item:
                    Source_name = items.source().name()
                    if filter in Source_name:
                        AllTimeEditData[Source_name] = items

        return AllTimeEditData

    def VersionUp(self,data):
        data.maxVersion()
    
    def VersionAllUp(self,data_list):
        for item in data_list:
            item.maxVersion()
