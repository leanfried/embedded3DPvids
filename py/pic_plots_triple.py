#!/usr/bin/env python
'''Functions for plotting video and image data for tripleLines'''

# external packages
import os, sys
import traceback
import logging
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib
from typing import List, Dict, Tuple, Union, Any, TextIO
import re
import numpy as np
import cv2 as cv
import matplotlib.ticker as mticker

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(currentdir)
from pic_plots import *

# logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
for s in ['matplotlib', 'imageio', 'IPython', 'PIL']:
    logging.getLogger(s).setLevel(logging.WARNING)
    
# plotting
matplotlib.rcParams['svg.fonttype'] = 'none'
matplotlib.rc('font', family='Arial')
matplotlib.rc('font', size='10.0')


#-----------------------------------------------

class multiPlots:
    '''given a sample type folder, plot values'''
    
    def __init__(self, folder:str, exportFolder:str, dates:List[str], **kwargs):
        self.folder = folder
        self.exportFolder = exportFolder
        self.dates = dates
        self.kwargs = kwargs
        self.inkvList = []
        self.supvList = []
        self.inkList = []
        self.supList = []
        self.spacingList = ['0.500', '0.625', '0.750', '0.875', '1.000', '1.250']
        for subfolder in os.listdir(self.folder):
            spl = re.split('_', subfolder)
            for i,s in enumerate(spl):
                if s=='I' and not spl[i+1] in self.inkList:
                    self.inkList.append(spl[i+1])
                elif s=='S' and not spl[i+1] in self.supList:
                    self.supList.append(spl[i+1])
                elif s=='VI' and not spl[i+1] in self.inkvList:
                    self.inkvList.append(spl[i+1])
                elif s=='VS' and not spl[i+1] in self.supvList:
                    self.supvList.append(spl[i+1])
                    
        # determine how many variables must be defined for a 2d plot
        self.freevars = 1
        self.freevarList = ['spacing']
        for s in ['ink', 'sup', 'inkv', 'supv']:
            l = getattr(self, f'{s}List')
            if len(l)>1:
                self.freevars+=1
                self.freevarList.append(s)

        if 'visc' in os.path.basename(folder):
            self.xvar = 'ink.var'
            self.yvar = 'sup.var'
        elif 'vels' in os.path.basename(folder):
            self.xvar = 'ink.v'
            self.yvar = 'sup.v'
            
    def keyPlots(self, **kwargs):
        '''most important plots'''
        for s in ['HIPxs', 'HOPxs', 'HOPh']:
            self.plot(s, spacing=0.875, index=[0,1,2,3], **kwargs)
            self.plot(s, ink=self.inkList[-1], index=[1], **kwargs)
        for s in ['VP']:
            self.plot(s, spacing=0.875, index=[0,1,2,3], **kwargs)
            self.plot(s, ink=self.inkList[-1], index=[2], **kwargs)
        for s in ['HOB', 'HOC', 'VB', 'VC']:
            self.plot(s, spacing=0.875, index=[0], **kwargs)
            self.plot(s, ink=self.inkList[-1], index=[0], **kwargs)
        
            
        
    def spacingPlots(self, name:str, showFig:bool=False, export:bool=True):
        '''run all plots for object name (e.g. HOB, HIPxs)'''
        for spacing in self.spacingList:
            self.plot(spacing=spacing, showFig=showFig, export=export)
            
    def plot(self, name:str, showFig:bool=False, export:bool=True, index:List[int]=[0], **kwargs):
        '''plot the values for object name (e.g. HOB, HIPxs)'''
        yvar = self.yvar
        xvar = 'self.spacing'
        kwargs2 = {**self.kwargs.copy(), **kwargs.copy()}
        obj2file = fh.tripleLine2FileDict()
        if not name in obj2file:
            raise ValueError(f'Unknown object requested: {name}')
        file = obj2file[name]
        allIn = [file]
        dates = self.dates
        tag = [f'{name}_{i}' for i in index]
        freevars = 0
        if 'spacing' in kwargs:
            spacing = kwargs['spacing']
            if not type(spacing) is str:
                spacing = '{:.3f}'.format(spacing)
            allIn.append(f'{file}_{spacing}')
            tag = [f'{spacing}_{name}_{i}' for i in index]
            xvar = self.xvar
            freevars+=1
        if 'ink' in kwargs:
            ink = kwargs['ink']
            allIn.append(f'I_{ink}')
            kwargs2['I'] = ink
            freevars+=1
        if 'sup' in kwargs:
            sup = kwargs['sup']
            allIn.append(f'S_{sup}')
            kwargs2['S'] = sup
            xvar = self.yvar
            freevars+=1
        if 'inkv' in kwargs:
            inkv = kwargs['inkv']
            allIn.append(f'VI_{inkv}')
            kwargs2['VI']=inkv
            freevars+=1
        if 'supv' in kwargs:
            supv = kwargs['supv']
            allIn.append(f'VS_{supv}')
            kwargs2['VS']=supv
            freevars+=1
        if freevars+2<self.freevars:
            raise ValueError(f'Too many variables to plot. Designate {self.freevarList} where needed')
            
        if 'crops' in kwargs:
            kwargs2['crops'] = kwargs['crops']
        else:
            crops = {'HOC':{'y0':0, 'yf':600, 'x0':0, 'xf':750},
                    'HOB':{'y0':0, 'yf':750, 'x0':0, 'xf':750},
                    'HIPxs':{'y0':0, 'yf':250, 'x0':50, 'xf':300},
                    'HOPxs':{'y0':0, 'yf':300, 'x0':50, 'xf':200},
                    'VB':{'y0':0, 'yf':800, 'x0':100, 'xf':700},
                    'VC':{'y0':0, 'yf':800, 'x0':100, 'xf':700},
                    'HOPh':{'y0':50, 'yf':350, 'x0':50, 'xf':750},
                    'VP':{'y0':0, 'yf':800, 'x0':0, 'xf':284}}
            if name in crops:
                kwargs2['crops'] = crops[name]
        if name in ['HIPh', 'HOPh', 'HOPxs']:
            concat = 'v'
        else:
            concat = 'h'
            
        exportFolder =  os.path.join(self.exportFolder, name)
        if not os.path.exists(exportFolder):
            os.mkdir(exportFolder)

        fig = picPlots0(self.folder, exportFolder
                        , allIn, dates, tag, showFig=showFig, export=export
                        , overlay={'shape':'3circles', 'dx':-0.8, 'dy':-0.8}
                        , xvar=xvar, yvar=yvar, concat=concat
                        , **kwargs2)
   