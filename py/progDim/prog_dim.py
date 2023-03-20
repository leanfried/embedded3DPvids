#!/usr/bin/env python
'''Functions for handling tables of programmed timings'''

# external packages
import os, sys
import traceback
import logging
from typing import List, Dict, Tuple, Union, Any, TextIO
import re
import pandas as pd
import numpy as np
import csv

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(currentdir)
sys.path.append(os.path.dirname(currentdir))
from pg_singleLine import *
from pg_singleDisturb import *
from pg_SDT import *
from pg_triple import *

# logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
for s in ['matplotlib', 'imageio', 'IPython', 'PIL']:
    logging.getLogger(s).setLevel(logging.WARNING)



#----------------------------------------------

def getProgDims0(folder:str, pv:printVals) -> progDim:
    if pv.pfd.printType=='tripleLine':
        return progDimsTripleLine(folder, pv)
    elif pv.pfd.printType=='singleLine':
        return progDimsSingleLine(folder, pv)
    elif pv.pfd.printType=='singleDisturb':
        return progDimsSingleDisturb(folder, pv)  
    elif pv.pfd.printType=='SDT':
        return progDimsSDT(folder, pv)  
    else:
        raise ValueError(f'No print type detected in {folder}')

def getProgDimsPV(pv:printVals) -> progDim:
    return getProgDims0(pv.printFolder, pv)
            
def getProgDims(folder:str) -> progDim:
    pv = printVals(folder)
    return getProgDims0(folder, pv)
    
    
def exportProgDims(folder:str, overwrite:bool=False) -> list:
    '''export programmed dimensions. returns list of bad folders'''
    errorList = []
    if not os.path.isdir(folder):
        return errorList
    if not fh.isPrintFolder(folder):
        for f1 in os.listdir(folder):
            errorList = errorList + exportProgDims(os.path.join(folder, f1), overwrite=overwrite)
        return errorList

    pv = printVals(folder)
    if not overwrite:
        if len(pv.pfd.progDims)>0 and len(pv.pfd.progPos)>0:
            return errorList
        
    try:
        pdim = getProgDims(folder)
        pdim.exportProgDims(overwrite=overwrite)
    except ValueError as e:
        errorList.append(folder)
        print(e)
        traceback.print_exc()
        return errorList
    else:
        return errorList

def exportAllDims(folder:str, overwrite:bool=False) -> list:
    '''export programmed dimensions. returns list of bad folders'''
    errorList = []
    if not os.path.isdir(folder):
        return errorList
    if not fh.isPrintFolder(folder):
        for f1 in os.listdir(folder):
            errorList = errorList + exportProgDims(os.path.join(folder, f1), overwrite=overwrite)
        return errorList

    pv = printVals(folder)
    if not overwrite:
        if len(pv.pfd.progDims)>0 and len(pv.pfd.progPos)>0:
            return errorList
        
    try:
        pdim = getProgDims(folder)
        pdim.exportAll(overwrite=overwrite)
    except ValueError as e:
        errorList.append(folder)
        print(e)
        traceback.print_exc()
        return errorList
    else:
        return errorList

def progTableRecursive(topfolder:str, useDefault:bool=False, overwrite:bool=False, **kwargs) -> pd.DataFrame:
    '''go through all of the folders and summarize the programmed timings'''
    if isSubFolder(topfolder):
        try:
            pv = printVals(topfolder)
            if (not 'dates' in kwargs or pv.date in kwargs['dates']) and overwrite:
                pv.redoSpeedFile()
                pv.fluigent()
                pv.exportProgDims() # redo programmed dimensions
            if useDefault:
                pv.useDefaultTimings()
            t,u = pv.progDimsSummary()
        except:
            traceback.print_exc()
            logging.warning(f'failed to get programmed timings from {topfolder}')
            return {}, {}
        return t,u
    elif os.path.isdir(topfolder):
        tt = []
        u = {}
        for f in os.listdir(topfolder):
            f1f = os.path.join(topfolder, f)
            if os.path.isdir(f1f):
                t,u0=progTableRecursive(f1f, useDefault=useDefault, overwrite=overwrite, **kwargs)
                if len(t)>0:
                    if len(tt)>0:
                        tt = pd.concat([tt,t])
                    else:
                        tt = t
                    if len(u)==0:
                        u = u0
        return tt, u
    
def checkProgTableRecursive(topfolder:str, **kwargs) -> None:
    '''go through the folder recursively and check if the pressure calibration curves are correct, and overwrite if they're wrong'''
    if isSubFolder(topfolder):
        try:
            pv = printVals(topfolder)
            pv.importProgDims()
            if 0 in list(pv.progDims.a):
                pv.fluigent()
                pv.exportProgDims() # redo programmed dimensions
        except:
            traceback.print_exc()
            logging.warning(f'failed to get programmed timings from {topfolder}')
            return
        return 
    elif os.path.isdir(topfolder):
        for f in os.listdir(topfolder):
            f1f = os.path.join(topfolder, f)
            if os.path.isdir(f1f):
                checkProgTableRecursive(f1f, **kwargs)
        return

def progTable(topfolder:str, exportFolder:str, filename:str, **kwargs) -> pd.DataFrame:
    '''go through all the folders, get a table of the speeds and pressures, and export to filename'''
    tt,units = progTableRecursive(topfolder, **kwargs)
    tt = pd.DataFrame(tt)
    if os.path.exists(exportFolder):
        plainExp(os.path.join(exportFolder, filename), tt, units)
    return tt,units
    