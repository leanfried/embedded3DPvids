#!/usr/bin/env python
'''Functions for handling files'''

# external packages
import os, sys
import re
import shutil
import time
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import pandas as pd
import subprocess

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(currentdir)
from tools.config import cfg


# logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)



#----------------------------------------------
def openExplorer(folder:str) -> None:
    '''open the folder in explorer'''
    subprocess.Popen(['explorer', folder.replace(r"/", "\\")], shell=True);

def twoBN(file:str) -> str:
    '''get the basename and folder it is in'''
    if len(file)==0:
        return ''
    return os.path.join(os.path.basename(os.path.dirname(file)), os.path.basename(file))

def numeric(s:str) -> bool:
    '''determine if the string is a number'''
    try:
        float(s)
    except ValueError:
        return False
    else:
        return True
    
def dateOrTime(s:str) -> bool:
    '''determine if the string starts with a date'''
    if len(s)<6:
        return False
    if not numeric(s[:6]):
        return False
    if int(s[0])>2:
        # let me just introduce a Y3K bug into my silly little program
        return False
    return True

def toInt(s:str) -> Union[str,int]:
    '''convert to int if possible'''
    try:
        return int(s)
    except ValueError:
        return s


def fileDateAndTime(file:str, out:str='str') -> Tuple[Union[str,int]]:
    '''get the date and time of the file'''
    errorRet = '','',''
    if len(file)==0:
        return errorRet
    split = re.split('_|\.', os.path.basename(file))
    i = len(split)-1
    while not dateOrTime(split[i]):
        i=i-1
        if i<0:
            levels = labelLevels(file)
            if not levels.currentLevel in ['printTypeFolder', 'sampleTypeFolder', 'sampleFolder']:
                return fileDateAndTime(os.path.dirname(file))
            else:
                return errorRet
    if len(split[i-1])==6:
        # valid time and date
        time = split[i][0:6]
        date = split[i-1][0:6]
        if len(split)>i+1:
            v = split[i+1]
            try:
                int(v)
            except ValueError:
                v = ''
        else:
            v = ''
    else:
        # only date
        date = split[i][0:6]
        time = ''
        v = ''
    
    if out=='int':
        date = toInt(date)
        time = toInt(time)
        v = toInt(v)
    return date,time, v

def fileTime(file:str, out:str='str') -> str:
    '''get the time from the file, where the time is in the filename'''    
    return fileDateAndTime(file, out=out)[1]


def fileTimeV(file:str) -> str:
    '''get the time and number from the file'''
    errorRet = ''
    _,t,v = fileDateAndTime(file)
    if not len(t)==6:
        return errorRet
    if len(v)==0:
        return t
    else:
        return f'{t}_{v}'

def fileDate(file:str, out:str='str') -> str:
    '''Get the creation date from the file'''
    date = fileDateAndTime(file, out=out)[0]
    if (type(date) is str and not len(date)==6):
        # if the date is not a valid date, get the date from the file modified time
        date = time.strftime("%y%m%d", time.gmtime(os.path.getctime(file)))

    return date


def fileScale(file:str) -> str:
    '''get the scale from the file name'''
    if 'vid' in os.path.basename(file):
        return '1'
    if 'stitch' in os.path.basename(file):
        spl = re.split('stitch', os.path.basename(file))[-1]
        scale = re.split('_', spl)[1]
        return str(float(scale))
    try:
        scale = re.split('_', os.path.basename(file))[-2]
        if len(scale)==6:
            # this is a date
            return 1
        else:
            try:
                s2 = float(scale)
            except:
                return 1
            else:
                return s2
    except:
        scale = 1
    return str(scale)

def formatSample(s:str) -> str:
    '''convert a string for use in I_#_S_# format'''
    while s[0]=='_':
        s = s[1:]
    while s[-1]=='_':
        s = s[0:-1]
    try:
        sf = float(s)
    except:
        pass
    else:
        s = "{:.2f}".format(sf)
    return s

def mlapSample(file:str, formatOutput:bool=True) -> str:
    '''determine the sample name, where the sample was named as M#_Lap# instead of IM#_S#'''
    parent = os.path.basename(file)
    split1 = re.split('M', parent)[1]
    split2 = re.split('Lap', split1)
    ink = split2[0]
    split3 = re.split('_', split2[1])
    if len(split3[0])==0:
        sup = '_'+split3[1]
    else:
        sup = split3[0]
    if formatOutput:
        sample = f'I_M{formatSample(ink)}_S_{formatSample(sup)}'
    else:
        sample = f'M{ink}Lap{sup}'
    return sample

def sampleRecursive(file:str) -> str:
    '''go up folders until you get a string that contains the sample name'''
    bn = os.path.basename(file)
    if 'I_' in bn and '_S' in bn:
        return bn
    else:
        parent = os.path.dirname(file)
        bn = os.path.basename(parent)
        if 'I_' in bn and '_S' in bn:
            return bn
        else:
            parent = os.path.dirname(parent)
            bn = os.path.basename(parent)
            if 'I_' in bn and '_S' in bn:
                return bn
            else:
                raise f'Could not determine sample name for {file}'

def sampleName(file:str, formatOutput:bool=True) -> str:
    '''Get the name of the sample from a file name or its parent folder'''

    parent = sampleRecursive(file)
    if '_I_' in parent:
        istr = '_I_'
    else:
        istr = 'I_'
    split1 = re.split(istr, parent)[1]
    split2 = re.split('_S_', split1)
    ink = split2[0]
    split3 = re.split('_', split2[1])
    if len(split3[0])==0:
        sup = f'_{split3[1]}'
    else:
        sup = split3[0]
    if formatOutput:
        sample = f'I_{formatSample(ink)}_S_{formatSample(sup)}'
    else:
        sample = f'I{ink}_S{sup}'
    return sample

    
#-----------------------------------------------------

def dateInName(file:str) -> bool:
    '''this file basename ends in a date'''
    entries = re.split('_', os.path.basename(file))
    date = entries[-1]
    if not len(date)>=6:
        return False
    yy = float(date[0:2])
    mm = float(date[2:4])
    dd = float(date[4:])
    if mm>12:
        # bad month
        return False
    if dd>31:
        # bad day
        return False
    
    # passed all tests
    return True

def sampleInName(file:str) -> bool:
    '''this file basename contains a sample name'''
    entries = re.split('_', os.path.basename(file))
    if entries[0]=='I' and entries[2]=='S':
        return True
    else:
        return False
    
def firstEntry(folder:str, directory:bool=True) -> str:
    '''find the first entry in the folder. directory=True to find directories, False to find files'''
    ld = os.listdir(folder)
    if len(ld)==0:
        return ''
    d1 = ''
    while len(ld)>0 and (((os.path.isdir(d1) and not directory) or (not os.path.isdir(d1) and directory)) or 'Thumbs' in d1 or not os.path.exists(d1)):
        # go through files in the directory until you find another directory
        d1 = os.path.join(folder, ld.pop(0))
    if (os.path.isdir(d1) and directory) or (not os.path.isdir(d1) and not directory):
        return d1
    else:
        return ''
    
def findBottom(bottom:str) -> str:
    '''find the bottom level file in the hierarchy'''
    # recurse until you hit the bottom level
    while os.path.isdir(bottom): # bottom is a directory
        newbot = firstEntry(bottom, directory=True) # find the first directory
        if os.path.exists(newbot):
            # this is a directory
            bottom = newbot
        else:
            # no directories in bottom. find first file
            bottom2 = firstEntry(bottom, directory=False) 
            if not os.path.exists(bottom2):
                return bottom
            else:
                return bottom2
    return bottom
    

class labelLevels:
    '''label the levels of the file hierarchy, with one characteristic file per level'''

    def __init__(self, file:str):
        
        if not os.path.exists(file):
            raise ValueError(f'File does not exist: {file}')
    
        levels = {}
        bottom = findBottom(file)

        # bottom is now a bottom level file
        if os.path.isdir(bottom):
            bfold = bottom
            bottom = ''
        else:
            bfold = os.path.dirname(bottom)
        if 'raw' in bfold or 'temp' in bfold:
            # raw image folder
            self.rawFile = bottom
            if os.path.basename(bfold)=='raw':
                self.rawFolder = bfold
                aboveRaw = os.path.dirname(self.rawFolder)
            elif os.path.basename(bfold)=='temp':
                self.tempFolder = bfold
                aboveRaw = os.path.dirname(self.tempFolder)
            else:
                self.rawLineFolder = bfold
                self.rawFolder = os.path.dirname(bfold)
                aboveRaw = os.path.dirname(self.rawFolder)

            if sampleInName(aboveRaw):
                self.file = os.path.join(aboveRaw, firstEntry(aboveRaw, directory=False)) # bottom level file inside sbpfolder
                if dateInName(aboveRaw):
                    # sample and date in name: this is a subfolder
                    self.subFolder = aboveRaw
                else:
                    # this is a sample folder. these files are misplaced
                    self.sampleFolder = aboveRaw
                    self.subFolder = 'generate' # need to generate a new subfolder
            else:
                # no sample in name: shopbot folder
                self.sbpFolder = aboveRaw
                self.subFolder = os.path.dirname(aboveRaw)
                self.file = os.path.join(aboveRaw, firstEntry(aboveRaw, directory=False)) # bottom level file inside sbpfolder
        else:
            # just a file. no raw folder, because we would have found it during recursion
            self.file = bottom
            if sampleInName(bfold):
                if dateInName(bfold):
                    # sample and date in name: this is a subfolder
                    self.subFolder = bfold
                else:
                    # this is a sample folder. these files are misplaced
                    self.sampleFolder = bfold
            else:
                # no sample in name: shopbot folder
                self.sbpFolder = bfold
                self.subFolder = os.path.dirname(bfold)           

        if not 'sampleFolder' in levels:
            sabove = os.path.dirname(self.subFolder)
            if not sampleInName(sabove):
                self.sampleFolder = 'generate' # need to generate a new sample folder
                self.sampleTypeFolder = sabove # the type is right above the subFolder
            else:
                self.sampleFolder = sabove
                self.sampleTypeFolder = os.path.dirname(sabove)
        else:
            self.sampleTypeFolder = os.path.dirname(self.sampleFolder)
        self.printTypeFolder = os.path.dirname(self.sampleTypeFolder)

        currentLevel = ''
        for key in self.__dict__:
            if getattr(self, key)==file:
                currentLevel = key
        self.currentLevel = currentLevel
        
    def printFolder(self) -> str:
        '''get the folder that the print files are in. note that this needed to be initialized at the printfolder or inside the print folder to get the right print folder, otherwise you'll get the first one in the subFolder or sampleFolder'''
        if hasattr(self, 'sbpFolder'):
            return self.sbpFolder
        else:
            return self.subFolder

    def printAll(self):
        spacer = '  '
        ii = 0
        for s in ['printTypeFolder', 'sampleTypeFolder', 'sampleFolder', 'subFolder']:
            if hasattr(self, s):
                if ii==0:
                    pout = getattr(self,s)
                else:
                    pout = os.path.basename(getattr(self,s))
                print(spacer*ii, s,': ', pout)
                ii+=1
        jj = 0
        for s in ['sbpFolder', 'file']:
            if hasattr(self, s):
                pout = os.path.basename(getattr(self,s))
                print(spacer*(ii+jj), s,': ', pout)
                jj+=1
        jj = 0
        for s in ['rawFolder', 'rawLineFolder', 'rawFile']:
            if hasattr(self, s):
                pout = os.path.basename(getattr(self,s))
                print(spacer*(ii+jj), s,': ', pout)
                jj+=1
                
    
        
        
#------------------------------------

def isSubFolder(folder:str) -> bool:
    '''determine if the folder is a subfolder'''
    levels = labelLevels(folder)
    if levels.currentLevel=='subFolder':
        return True
    else:
        return False
    
def subFolder(folder:str) -> str:
    '''name of the subfolder'''
    levels = labelLevels(folder)
    return levels.subFolder
    
def isSBPFolder(folder:str) -> bool:
    '''determine if the folder is a sbpfolder'''
    bn = os.path.basename(folder)
    if 'Pics' in bn:
        return False
    for s in list(tripleLineSBPfiles().keys()) + list(singleDisturbSBPfiles().keys()):
        if s in bn:
            return True
    
def isPrintFolder(folder:str) -> bool:
    '''determine if the folder is the print folder'''
    bn = os.path.basename(folder)
    # has tripleLines SBP name in basename
    if isSBPFolder(folder):
        return True
        
    if not ('I_' in bn and 'S_' in bn):
        return False
        
    # has singleLines SBP name in any file in the folder
    for s in singleLineSBPfiles():
        for f in os.listdir(folder):
            if s in f:
                return True
    return False
 
    
def listDirs(folder:str) -> List[str]:
    '''List of directories in the folder'''
    return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f)) ]

def anyIn(slist:List[str], s:str) -> bool:
    '''bool if any of the strings in slist are in s'''
    if len(slist)==0:
        return True
    for si in slist:
        if si in s:
            return True
    return False

def allIn(slist:List[str], s:str) -> bool:
    '''bool if all of the strings are in s'''
    if len(slist)==0:
        return True
    for si in slist:
        if not si in s:
            return False
    return True
    
def printFolders(topFolder:str, tags:List[str]=[''], someIn:List[str]=[], **kwargs) -> List[str]:
    '''Get a list of bottom level print folders in the top folder'''
    if isPrintFolder(topFolder):
        if len(someIn)>0:
            anyin = anyIn(someIn, topFolder)
        else:
            anyin = True
        if allIn(tags, topFolder) and anyin:
            folders = [topFolder]
        else:
            folders = []
    else:
        folders = []
        dirs = listDirs(topFolder)
        for d in dirs:
            folders = folders+printFolders(d, tags=tags, someIn=someIn)
    return folders
    
    
    
#------------

def singleDisturbSBPfiles() -> dict:
    '''get a dictionary of singleDisturb sbp file names and their shortcuts'''
    files = {'disturbHoriz':'DH', 'disturbVert':'DV', 'disturbXS':'DX'}
    return files

def singleDisturbSt() -> list:
    '''get a list of disturbed line object types'''
    return ['HIx', 'HOx', 'HOh', 'V']

def singleDisturb2FileDict() -> str:
    '''get the corresponding object name and sbp file'''
    d = {'HIx':'disturbXS_+y', 
        'HOx':'disturbXS_+z',
        'HOh':'disturbHoriz',
        'V':'disturbVert'}
    return d
    
def singleDisturbName(file:str) -> str:
    '''get the short name, given the sbp file name'''
    d = singleDisturb2FileDict()
    for key,val in d.items():
        if val in file:
            return key
    raise ValueError(f'Unexpected sbp file name: {file}')
    
#--------------

def SDTSBPfiles() -> dict:
    '''get a dictionary of singleDoubleTriple sbp file names and their shortcuts'''
    files = {'disturbHoriz':'DH', 'disturbVert':'DV', 'disturbXS':'DX'}
    return files

def SDTSt() -> list:
    '''get a list of disturbed line object types'''
    return [f'{s}{i}' for s in ['HIx', 'HOx', 'HOh', 'V'] for i in [1,2,3]]

def SDTSBPPicfiles() -> dict:
    '''get a dictionary of triple line pic file names and their shortcuts'''
    tls = SDTSBPfiles()
    files = dict([[f'{key}',f'{val}P'] for key,val in tls.items()])
    return files

def SDT2FileDict() -> str:
    '''get the corresponding object name and sbp file'''
    d = {}
    for i in [1,2,3]:
        d[f'HIx{i}'] = f'disturbXS2_{i}_+y'
        d[f'HOx{i}'] = f'disturbXS2_{i}_+z'
        d[f'HOh{i}'] = f'disturbHoriz3_{i}'
        d[f'V{i}'] = f'disturbVert2_{i}'
    return d
    
def SDTName(file:str) -> str:
    '''get the short name, given the sbp file name'''
    d = SDT2FileDict()
    for key,val in d.items():
        if val in file:
            return key
    raise ValueError(f'Unexpected sbp file name: {file}')
    
    
#---

def tripleLineSBPfiles() -> dict:
    '''get a dictionary of tripleLine sbp file names and their shortcuts'''
    
    # C = cross, D = double, H = horiz, V = vert, U = under, TL = triple line, X = cross-section
    files = {'crossDoubleHoriz':'CDH',
             'crossDoubleVert':'CDV',
             'crossUnder':'CU',
             'tripleLinesHoriz':'TLH',
             'tripleLinesXS':'TLX',
             'tripleLinesVert':'TLV',
             'tripleLinesUnder':'TLU'}
    return files

def tripleLineSBPPicfiles() -> dict:
    '''get a dictionary of triple line pic file names and their shortcuts'''
    tls = tripleLineSBPfiles()
    files = dict([[f'{key}Pics',f'{val}P'] for key,val in tls.items()])
    return files
    
def tripleLineSt() -> list:
    '''get a list of triple line object types'''
    # H = horiz, V = vertical
    # I = in layer, O = out of layer
    # P = parallel, B = bridge, C = cross
    return ['HIB', 'HIPh', 'HIPxs', 'HOB', 'HOC', 'HOPh', 'HOPxs', 'VB', 'VC', 'VP']

def tripleLine2FileDict() -> str:
    '''get the corresponding object name and sbp file'''
    d = {'HOB':'crossDoubleHoriz_0.5',
         'HOC':'crossDoubleHoriz_0',
         'VB':'crossDoubleVert_0.5',
         'VC':'crossDoubleVert_0',
         'HIC':'underCross_0.5',
         'HIB':'underCross_0',
         'HIPxs':'tripleLinesXS_+y',
         'HOPxs':'tripleLinesXS_+z',
         'HIPh':'tripleLinesUnder',
         'HOPh':'tripleLinesHoriz',
         'VP':'tripleLinesVert'}
    return d

def tripleLineName(file:str) -> str:
    '''get the short name, given the sbp file name'''
    d = tripleLine2FileDict()
    for key,val in d.items():
        if val in file:
            return key
    raise ValueError(f'Unexpected sbp file name: {file}')

#---
    
def singleLineSBPfiles() -> dict:
    '''get a dictionary of singleLine sbp file names and their shortcuts'''
    files = {'singleLinesNoZig':'SLNZ',
            'singleLines':'SL'}
    return files

def singleLineSBPPicfiles() -> dict:
    '''get a dictionary of singleLine pic sbp file names and their shortcuts'''
    files = dict([[f'singleLinesPics{i}',f'SLP{i}'] for i in range(10)])
    files['singleLinesPics'] = 'SLP'
    return files
    
def singleLineSt() -> list:
    '''get a list of single line object types'''
    return ['horiz', 'vert', 'xs']

def singleLineStN() -> list:
    '''get a list of single line stitch names'''
    return ['horizfull', 'vert1', 'vert2', 'vert3', 'vert4', 'xs1', 'xs2', 'xs3', 'xs4', 'xs5', 'horiz0', 'horiz1', 'horiz2']

def singleLineStPics(vertLines:int, xsLines:int) -> List[str]:
    '''get a list of strings that describe the stitched pics'''
    l = ['horizfull']
    l = l+[f'vert{c+1}' for c in range(vertLines)]
    l = l+[f'xs{c+1}' for c in range(xsLines)]
    return l

    
#------------

def isStitch(file:str) ->bool:
    '''determine if the file is a stitched image'''
    if not '.png' in file:
        return False
    if '_vid_' in file or '_vstill_' in file:
        return False
    for st in (singleLineStN()+tripleLineSt()+singleDisturbSt()+SDTSt()):
        if f'_{st}_' in file:
            return True
    
def isVidStill(file:str) ->bool:
    '''determine if the file is a video still'''
    if not '.png' in file:
        return False
    if '_vstill_' in file:
        return True
    for st in singleLineStN():
        if f'_vid_{st}' in file:
            return True
    return False

def splitName(fname:str) -> List[str]:
    '''drop the version number from sbp name in files'''
    spl = re.split('_', fname)
    while spl[0][-1].isnumeric():
        spl[0] = spl[0][:-1]
    return spl

def splitFileName(file:str) -> str:
    exspl = os.path.splitext(os.path.basename(file))
    ext = exspl[-1]
    fname = exspl[0]
    spl = splitName(fname)
    return spl

def isTripleLineStill(file):
    spl = splitFileName(file)
    return spl[0] in tripleLineSBPPicfiles()
    
def isSingleLineStill(file):
    spl = splitFileName(file)
    return spl[0] in singleLineSBPPicfiles()

def isSDTStill(file):
    spl = splitFileName(file)
    return spl[0] in SDTSBPPicfiles()

def isStill(file:str) -> bool:
    '''determine if the file is an unstitched image'''
    return isTripleLineStill(file) or isSingleLineStill(file) or isSDTStill(file)
    
#------------    

def sbpPath(topFolder:str, name:str) -> str:
    '''find the full path of the sbp file, where name is just the file name, no extension'''
    if '.sbp' in name:
        name = re.split('.sbp', name)[0]
    fn = os.path.join(topFolder, f'{name}.sbp')
    if os.path.exists(fn):
        # found the file in this folder
        return fn
    else:
        # go through subfolders and look for the file
        for d in os.listdir(topFolder):
            dfull = os.path.join(topFolder, d)
            if os.path.isdir(dfull):
                s = sbpPath(dfull, name)
                if len(s)>0:
                    return s
    # didn't find any file
    return ''

class printFileDict:
    '''get a dictionary of the paths for each file inside of the print folder'''
    
    def __init__(self, printFolder:str):
        self.levels = labelLevels(printFolder)
        if not self.levels.currentLevel in ['subFolder', 'sbpFolder']:
            raise ValueError(f'Input to labelPrintFiles must be subfolder or sbp folder. Given {printFolder}')

        printFolder = self.levels.currentLevel
        self.printFolder=self.levels.printFolder()
        self.sort()
        self.getDate()
            
    def newFileName(self, s:str, ext:str) -> str:
        '''generate a new file name'''
        if ext[0]=='.':
            ext = ext[1:]  # remove . from beginning
        if len(self.vid)>0:
            file = self.vid[0].replace('avi', ext)
            file = file.replace('Basler camera', s)
        elif len(self.still)>0:
            file = self.still[0].replace('png', ext)
            file = file.replace('Basler camera', s)
        else:
            file = os.path.join(self.printFolder, f'{s}.{ext}')
            if os.path.exists(file):
                ii = 0
                while os.path.exists(file):
                    file = os.path.join(self.printFolder, f'{s}_{ii}.{ext}')
                    ii+=1
        return file
    
    def deconstructFileName(self, file:str) -> str:
        '''get the original string that went into the file name'''
        if len(self.vid)>0:
            spl2 = re.split('_', os.path.basename(self.vid[0]))
        elif len(self.still)>0:
            spl2 = re.split('_', os.path.basename(self.still[0]))
        else:
            return os.path.basename(os.path.splitext(file)[0])
        if 'Basler camera' in spl2:
            i = spl2.index('Basler camera')
            ir = len(spl2)-i-1
        else:
            raise ValueError('Failed to find original value')
        spl1 = re.split('_',os.path.basename(file))
        return '_'.join(spl1[i:-ir])
    
    def sbpName(self) -> str:
        '''gets the name of the shopbot file'''
        if self.levels.currentLevel=='sbpFolder':
            self.sbp = os.path.basename(self.levels.sbpFolder)
            return self.sbp
        if len(self.vid)>0:
            file = self.vid[0]
            if '_Basler' in file:
                spl = re.split('_Basler', os.path.basename(file))
                self.sbp = spl[0]
                return self.sbp
            else:
                raise ValueError(f'Unexpected video file {file}')
                
    def sbpFile(self) -> str:
        '''find the full path name of the sbp file'''
        self.sbpName()
        return sbpPath(cfg.path.pyqtFolder, self.sbp)
    
    def sbpPointsFile(self) -> str:
        '''get the full path name of the sbp points csv'''
        file = self.sbpFile()
        return file.replace('.sbp', '.csv')

            
    def getDate(self):
        '''get the date of the folder'''
        if len(self.vid)>0:
            self.date = fileDate(self.vid[0], out='int')
        elif len(self.still)>0:
            self.date = fileDate(self.still[0], out='int')
        else:
            self.date = fileDate(self.levels.subFolder, out='int')
        return self.date
    
    def first(self, s:str) -> str:
        '''return first entry in the list'''
        if not hasattr(self, s):
            return ''
        l = getattr(self, s)
        if type(l) is list:
            if len(l)==0:
                return ''
            return l[0]
        else:
            return l
    
    def vidFile(self):
        '''get the primary video file'''
        return self.first('vid')
    
    def timeFile(self):
        '''get the primary time file'''
        return self.first('timeSeries')
    
    def metaFile(self):
        '''get the primary time file'''
        return self.first('meta')
    
    def resetList(self):
        '''reset the lists of files'''
        self.vid_unknown=[]
        self.csv_unknown=[]
        self.csv_delete=[]
        self.still=[]
        self.stitch=[]
        self.vstill=[]
        self.vid = []
        self.still_unknown=[]
        self.unknown=[]
        self.phoneCam = []
        self.timeSeries = []
        self.timeRewrite = []
        self.meta = []
        self.progDims = []
        self.progPos = []
        self.printType = ''
        
    def getPrintType(self) -> None:
        '''get the print type from the folder hierarchy'''
        f = os.path.basename(self.levels.printTypeFolder)
        if f=='singleDisturb':
            self.printType='singleDisturb'
        elif f=='singleLines':
            self.printType='singleLine'
        elif f=='tripleLines':
            self.printType='tripleLine'
        elif f=='singleDoubleTriple':
            self.printType='SDT'
        else:
            logging.error('Could not determine print type from file hierarchy')
            bn = re.split('_',os.path.basename(self.printFolder))[0]
            if bn in tripleLineSBPfiles():
                self.printType='tripleLine'
            elif bn in singleLineSBPfiles():
                self.printType='singleLine'
            elif bn in SDTSBPfiles():
                self.printType = 'SDT'
            elif bn in singleDisturbSBPfiles():
                self.printType = 'singleDisturb'
            
            
        
    def sortFiles(self, folder:str):
        '''sort and label files in the given folder'''
        
        tls = tripleLineSBPfiles()
        sls = singleLineSBPfiles()
        sds = singleDisturbSBPfiles()
        sdt = SDTSBPfiles()
        self.getPrintType()
        

        for f1 in os.listdir(folder):
            ffull = os.path.join(folder, f1)
            if os.path.isdir(ffull):
                # recurse
                self.sortFiles(ffull)
            elif not 'Thumbs' in f1:
                exspl = os.path.splitext(f1)
                ext = exspl[-1]
                fname = exspl[0]
                spl = splitName(fname)
                if ext=='.avi':
                    if 'Basler camera' in fname:
                        if spl[0] in sdt:
                            self.vid.append(ffull)
                        elif spl[0] in tls:
                            self.vid.append(ffull)
                        elif spl[0] in sls:
                            self.vid.append(ffull)
                        elif spl[0] in sds:
                            self.vid.append(ffull)                            
                        else:
                            self.vid_unknown.append(ffull)
                    else:
                        self.vid_unknown.append(ffull)
                elif ext=='.csv':
                    if spl[0] in tls or spl[0] in sls or spl[0] in sds:
                        if 'timeRewrite' in fname:
                            self.timeRewrite.append(ffull)
                        elif 'Fluigent' in fname or 'time' in fname:
                            self.timeSeries.append(ffull)
                        elif 'speeds' in fname or 'meta' in fname:
                            self.meta.append(ffull)
                        elif 'progDims' in fname:
                            self.progDims.append(ffull)
                        elif 'progPos' in fname:
                            self.progPos.append(ffull)
                        else:
                            setattr(self, self.deconstructFileName(ffull), ffull)
                    elif spl[0] in singleLineSBPPicfiles():
                        # extraneous fluigent or speed file from pic
                        self.csv_delete.append(ffull)
                    else:
                        # summary or analysis file
                        if hasattr(self, spl[-1]):
                            lprev = getattr(self, spl[-1])
                            if len(lprev)>0 and type(lprev) is str:
                                l = [lprev]
                            else:
                                l = []
                            l.append(ffull)
                            setattr(self, spl[-1], l)
                        else:
                            setattr(self, spl[-1], ffull)
                elif ext=='.png':
                    if 'background' in fname:
                        self.background = ffull
                    elif isStill(f1):
                        if 'Basler camera' in fname:
                            # raw still
                            self.still.append(ffull)
                        else: 
                            self.still_unknown.append(ffull)
                    elif isStitch(f1):
                        # stitched image
                        self.stitch.append(ffull)
                    elif isVidStill(f1):
                        self.vstill.append(ffull)
                    else:
                        self.still_unknown.append(ffull)
                elif ext=='.jpg':
                    self.phoneCam.append(ffull)
                else:
                    self.unknown.append(ffull) 
                    
                    
    def sort(self) -> None:
        '''sort and label files in the print folder'''
        self.resetList()
        self.sortFiles(self.printFolder)
        
    def printAll(self) -> None:
        '''print all values'''
        for key,value in self.__dict__.items():
            if key in ['levels', 'printFolder']:
                pass
            elif type(value) is list:
                if len(value)>0:
                    if os.path.exists(value[0]):
                        print(f'\n{key}:\t{[os.path.basename(file) for file in value]}\n')
                    else:
                        print(f'{key}:\t{value}')
            else:
                if os.path.exists(value):
                    print(f'{key}:\t{os.path.basename(value)}')
                else:
                    print(f'{key}:\t{value}')
                    
    def check(self) -> list:
        '''check that the sample names match and that there is only one video per print folder'''
        self.mismatch=[]
        self.tooMany=[]
        bn = twoBN(self.printFolder)
        sname = sampleName(self.printFolder)
        for l in [self.vid, self.still, self.stitch, self.timeSeries, self.meta]:
            for file in l:
                if os.path.exists(file):
                    try:
                        s2 = sampleName(file)
                    except IndexError:
                        print(file)
                        raise IndexError
                    if not sname==s2:
                        logging.warning(f'Mismatched sample in {bn}: {os.path.basename(file)}')
                        self.mismatch.append(file)
        if len(self.vid)>1:
            logging.warning(f'Too many videos in {bn}: {len(self.vid)}')
            self.tooMany = self.vid
#         self.diagnoseMismatch()     # diagnose problems
#         self.fixMismatch()          # fix problems
        return 
    
    def datesAndTimes(self, s:str) -> List[str]:
        '''get a list of dates and times for the given list'''
        dates = []
        times = []
        if hasattr(self, s):
            sl = getattr(self, s)
            for si in sl:
                d,t = fileDateAndTime(si)
                dates.append(d)
                times.append(t)
        dates = [int(d) for d in list(set(dates))]
        times = [int(d) for d in list(set(times))]
        return dates,times
    
    def diagnoseMismatch(self):
        '''diagnose why there is a sample mismatch in the folder, and fix it'''
        self.newFolderFiles = []        # files to move to a new folder
        self.renameFiles = []          # files to rename
        if len(self.mismatch)==0:
            return
        stitchDates, stitchTimes = self.datesAndTimes('stitch')  # times and dates of stitches
        if len(stitchDates)==0:
            logging.info(f'Could not diagnose mismatch in {twoBN(self.printFolder)}: no stitches')
            return
        if len(stitchDates)>1:
            logging.info(f'Could not diagnose mismatch in {twoBN(self.printFolder)}: too many stitches')
        stitchDate = stitchDates[0]
        for m in self.mismatch:
            d,t = fileDateAndTime(m, out='int')
            if (not d==stitchDate) or t>max(stitchTimes):
                # different date from stitch, or vid taken after the stitch
                self.newFolderFiles.append(m)
            else:
                self.renameFiles.append(m)
        return
    
    def fixMismatch(self):
        '''fix mismatched files'''
        sname = sampleName(self.printFolder)
        for file in self.renameFiles:
            # rename file
            s = sampleName(file)
            newname = file.replace(s, sname)
            os.rename(file, newname)
            
            # remove from bad lists
            self.renameFiles.remove(file)
            self.mismatch.remove(file)
            
            # print status
            logging.info(f'Renamed {os.path.basename(file)} to {os.path.basename(newname)}')
            
        self.sort()
        
    def pxpmm(self):
        '''get pixels per mm'''
        if len(self.meta)==0:
            meta = {}
        else:
            df = pd.read_csv(self.meta[0], header=0, names=['var', 'units', 'val'])
            meta = dict(zip(df['var'], df['val']))
        if 'camera_magnification' in meta:
            cm = float(meta['camera_magnification'])
        else:
            cm = 1
        d = {0.5:71, 1:139}
        if cm in d:
            pxpmm = d[cm]
            return pxpmm
        else:
            raise ValueError(f'Unexpected camera magnification in {self.folder}: {cm}')
        

    
def checkFolders(topFolder:str) -> Tuple[list, list]:
    '''check the print folders in the top folder for extra files, mis-sorted files'''
    mismatch = []
    tooMany = []
    for f in printFolders(topFolder):
        pfd = printFileDict(f)
        pfd.check()               # check files
        if len(pfd.mismatch)>0:
            mismatch.append(f)
        if len(pfd.tooMany)>0:
            tooMany.append(f)
    return mismatch, tooMany

    
        
    

#------------------------------------------------------------

def labelAndSort(folder:str, debug:bool=False) -> None:
    '''label the levels and create folders where needed'''
    levels = labelLevels(folder)
    if levels.sampleFolder =='generate':
        # generate a sample folder
        sample = sampleName(levels.subFolder, formatOutput=True)
        sampleFolder = os.path.join(levels.sampleTypeFolder, sample)
        if not os.path.exists(sampleFolder):
            if debug:
                logging.debug(f'Create {sampleFolder}')
            else:
                os.mkdir(sampleFolder)
        levels.sampleFolder = sampleFolder
        file = levels.subFolder
        newname = os.path.join(levels.sampleFolder, os.path.basename(file))
        if debug:
            logging.info(f'Move {file} to {newname}')
        else:
            os.rename(file, newname)
            logging.info(f'Moved {file} to {newname}')
    if levels.subFolder=='generate':
        # generate a subfolder
        fd = fileDate(levels.file)
        sample = os.path.basename(levels.sampleFolder) 
        bn = f'{sample}_{fd}'
        subfolder = os.path.join(levels.sampleFolder, bn)


def sortRecursive(folder:str, debug:bool=False) -> None:
    '''given any folder or file, sort and rename all the files inside'''
    if not os.path.exists(folder):
        return
    if "Thumbs" in folder or "DS_Store" in folder or 'README' in folder:
        return
    levels = labelLevels(folder)
    if levels.currentLevel =='sampleTypeFolder':
        for f in os.listdir(levels.sampleTypeFolder):
            labelAndSort(os.path.join(levels.sampleTypeFolder, f), debug=debug) # sort the folders inside sampleTypeFolder
    elif levels.currentLevel=='printTypeFolder':
        for f in os.listdir(levels.printTypeFolder):
            sortRecursive(os.path.join(levels.printTypeFolder, f), debug=debug)
    elif levels.currentLevel in ['sampleFolder', 'subFolder', 'sbpFolder']:
        labelAndSort(folder, debug=debug)
        
def putStillsAway(folder:str, debug:bool=False) -> None:
    '''identify the stills and put them in a folder'''
    if not os.path.exists(folder):
        return
    if "Thumbs" in folder or "DS_Store" in folder or 'README' in folder:
        return
    levels = labelLevels(folder)
    if levels.currentLevel in ['sampleTypeFolder', 'printTypeFolder', 'sampleFolder', 'subFolder']:
        for f in os.listdir(folder):
            putStillsAway(os.path.join(folder, f), debug=debug) # sort the folders inside sampleTypeFolder
    elif levels.currentLevel in ['sbpFolder']:    
        pfd = printFileDict(folder)
        snap = os.path.join(folder, 'raw')
        if not os.path.exists(snap):
            os.mkdir(snap)
        if debug:
            print('old names: ')
            print(pfd.still_unknown)
            print('new names: ')
            print([os.path.join(snap, os.path.basename(file)) for file in pfd.still_unknown])
        else:
            for file in pfd.still_unknown:
                os.rename(file, os.path.join(snap, os.path.basename(file)))

            
#------------------------------------------------------
      
def mkdirif(folder:str) -> None:
    if not os.path.exists(folder):
        os.mkdir(folder)

def fillDirsTriple(topFolder:str) -> None:
    '''make missing folders'''
    for s in ['0.500', '0.625', '0.750', '0.875', '1.000', '1.250']:
        for f in ['tripleLinesHoriz', 'tripleLinesVert']:
            mkdirif(os.path.join(topFolder, f'{f}_{s}'))
        for z in ['0', '0.5']:
            for f in ['crossDoubleHoriz', 'crossDoubleVert']:
                mkdirif(os.path.join(topFolder, f'{f}_{z}_{s}'))
        for z in ['+y', '+z']:
            for f in ['tripleLinesXS']:
                mkdirif(os.path.join(topFolder, f'{f}_{z}_{s}'))

            

            
    
#-------------------------------
# singleLines
def countFiles(topFolder:str, diag:bool=True) -> pd.DataFrame:
    '''Identify which print folders in the top folder are missing data'''
    folders = printFolders(topFolder)
    outlist = []
    for folder in folders:
        d = {'Folder':os.path.basename(folder), 'BasVideo':0, 'BasStills':0, 'PhoneCam':0, 'Fluigent':0}
        for f in os.listdir(folder):
            if ('Basler camera' in f or 'horiz' in f or 'xs' in f or 'vert' in f) and '.png' in f:
                d['BasStills']+=1
            elif 'Basler camera' in f and '.avi' in f:
                d['BasVideo']+=1
            elif 'phoneCam' in f:
                d['PhoneCam']+=1
            elif 'Fluigent' in f:
                d['Fluigent']+=1
        outlist.append(d)        
    df = pd.DataFrame(outlist)
    if diag:
        display(df[df['PhoneCam']==0])
        display(df[df['BasVideo']==0])
        display(df[df['BasStills']==0])
    return df



        
    