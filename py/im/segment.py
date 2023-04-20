#!/usr/bin/env python
'''Morphological operations applied to images'''

# external packages
import cv2 as cv
import numpy as np 
import os
import sys
import logging
from typing import List, Dict, Tuple, Union, Any, TextIO
import pandas as pd
import matplotlib.pyplot as plt

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(currentdir)
sys.path.append(os.path.dirname(currentdir))
from imshow import imshow
from morph import *
from m_tools import contourRoughness, getContours
from tools.timeCounter import timeObject

# logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
for s in ['matplotlib', 'imageio', 'IPython', 'PIL']:
    logging.getLogger(s).setLevel(logging.WARNING)



#----------------------------------------------

class fillMode:
    removeBorder = 0
    fillSimple = 1
    fillSimpleWithHoles = 2
    fillByContours = 3
    

class segmenter(timeObject):
    '''for thresholding and segmenting images'''
    
    def __init__(self, im:np.array, acrit:float=2500, diag:int=0
                 , fillMode:int=fillMode.removeBorder, eraseMaskSpill:bool=False, closeTop:bool=True
                 , closing:int=0, grayBlur:int=3, removeSharp:bool=False
                 , leaveHollows:bool=True, **kwargs):
        self.im = im
        self.w = self.im.shape[1]
        self.h = self.im.shape[0]
        self.acrit = acrit
        self.diag = diag
        self.fillMode = fillMode
        self.eraseMaskSpill = eraseMaskSpill
        self.closeTop = closeTop
        self.closing = closing
        self.kwargs = kwargs
        self.leaveHollows = leaveHollows
        self.removeSharp = removeSharp
        self.grayBlur = grayBlur
        if 'nozData' in kwargs:
            self.nd = kwargs['nozData']
        if 'crops' in kwargs:
            self.crops = kwargs['crops']
        self.segmentInterfaces(**kwargs)
        self.makeDF()
            
    def makeDF(self):
        if hasattr(self, 'filled'):
            self.sdf = segmenterDF(self.filled, self.acrit, diag=self.diag)
        
    def display(self):
        if self.diag>0:
            if hasattr(self, 'labeledIm'):
                imshow(self.im, self.gray, self.thresh, self.sdf.labeledIm, maxwidth=13, titles=['seg.im', 'gray', 'thresh', 'labeled'])
            else:
                imshow(self.im, self.gray, self.thresh, maxwidth=13, titles=['seg.im', 'gray', 'thresh']) 
        
    def getGray(self) -> None:
        '''convert the image to grayscale and store the grayscale image as self.thresh'''
        if len(self.im.shape)==3:
            gray = cv.cvtColor(self.im,cv.COLOR_BGR2GRAY)
        else:
            gray = self.im.copy()
        if self.grayBlur>0:
            self.gray = cv.medianBlur(gray, self.grayBlur)
        else:
            self.gray = gray
        
    def adaptiveThresh(self) -> np.array:
        '''adaptive threshold'''
        return cv.adaptiveThreshold(self.gray,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY_INV,11,6)
    
    def threshThresh(self, topthresh, whiteval) -> np.array:
        '''conventional threshold
        topthresh is the initial threshold value
        whiteval is the pixel intensity below which everything can be considered white'''
        crit = topthresh
        impx = np.product(self.gray.shape)
        allwhite = impx*whiteval
        prod = allwhite
        while prod>=allwhite and crit>50: # segmentation included too much
            ret, thresh = cv.threshold(self.gray,crit,255,cv.THRESH_BINARY_INV)
            prod = np.sum(np.sum(thresh))/impx
            crit = crit-10
        if self.diag>0:
            logging.info(f'Threshold: {crit+10}, product: {prod}, white:{whiteval}')
        return thresh
    
    def kmeansThresh(self) -> np.array:
        '''use kmeans clustering on the color image to segment interfaces'''
        twoDimage = self.im.reshape((-1,3))
        twoDimage = np.float32(twoDimage)
        attempts= 2
        epsilon = 0.5
        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, attempts, epsilon)
        K = 2
        h,w = self.im.shape[:2]
        
        ret,label,center=cv.kmeans(twoDimage,K,None,criteria,attempts,cv.KMEANS_PP_CENTERS)
        center = np.uint8(center)
        res = center[label.flatten()]
        result_image = res.reshape((self.im.shape))
        for i,c in enumerate(center):
            result_image[result_image==c]=int(i*255)

        result_image = cv.cvtColor(result_image, cv.COLOR_BGR2GRAY)
        if result_image.sum(axis=0).sum(axis=0)/255/(h*w)>0.5:
            result_image = cv.bitwise_not(result_image)
        return result_image

        
    def threshes(self, topthresh:int=200, whiteval:int=80, adaptive:int=0, **kwargs) -> None:
        '''threshold the grayscale image and store the resulting binary image as self.thresh
        topthresh is the initial threshold value
        whiteval is the pixel intensity below which everything can be considered white
        '''
        threshes = []
        if not type(adaptive) is list:
            adaptives = [adaptive]
        else:
            adaptives = adaptive
        for a in adaptives:
            if a==0:
                threshes.append(self.threshThresh(topthresh, whiteval))
            elif a==1:
                threshes.append(self.adaptiveThresh())
            elif a==2:
                # use k-means clstering
                threshes.append(self.kmeansThresh())
        thresh = threshes[0]
        for t in threshes[1:]:
            thresh = cv.add(thresh, t)
        self.thresh = thresh
        
        
    def closeHorizLine(self, im:np.array, imtop:int, close:bool) -> np.array:
        '''draw a black line across the y position imtop between the first and last black point'''

        if close:
            marks = np.where(im[imtop]==255) 
            if len(marks[0])==0:
                return
            val = 255
            first = marks[0][0] # first position in x in y row where black
            last = marks[0][-1]
        else:
            val = 255
            first = 0
            last = im.shape[1]
        if last-first<im.shape[1]*0.2:
            im[imtop:imtop+3, first:last] = val*np.ones(im[imtop:imtop+3, first:last].shape)
        return im

    def closeVerticalTop(self, im:np.array, close:bool=True, cutoffTop:float=0.01, closeBottom:bool=False, **kwargs) -> np.array:
        '''if the image is of a vertical line, close the top'''
        if im.shape[0]<im.shape[1]*2:
            return im

        # cut off top 3% of image
        if cutoffTop>0:
            if close:
                val = 255
            else:
                val = 0
            imtop = int(im.shape[0]*cutoffTop)  
            im[1:imtop, 1:-1] = np.ones(im[1:imtop, 1:-1].shape)*val

        # vertical line. close top to fix bubbles
        top = np.where(np.array([sum(x) for x in im])>0) 

        if len(top[0])==0:
            return im
        imtop = top[0][0] # first position in y where black
        im = self.closeHorizLine(im, imtop, close)
        if closeBottom:
            imbot = top[0][-1]-3
            im = self.closeHorizLine(im, imbot, close)
        return im 
    
    def closeFullBorder(self, im:np.array) -> np.array:
        '''put a white border around the whole image'''
        if len(im.shape)>2:
            zero = [0,0,0]
        else:
            zero = 255
        im2 = im.copy()
        im2[0, :] = zero
        im2[-1, :] = zero
        im2[:, 0] = zero
        im2[:,-1] = zero
        return im2
        
    def addNozzle(self, bottomOnly:bool=False) -> None:
        '''add the nozzle in black back in for filling'''
        if not (hasattr(self, 'nd') and hasattr(self, 'crops')):
            return
        thresh = self.nd.maskNozzle(self.thresh, ave=False, invert=False, crops=self.crops, bottomOnly=bottomOnly)   
        h,w = thresh.shape
        thresh[0, :] = 0   # clear out the top row
        thresh[:int(h/4), 0] = 0  # clear left and right edges at top half
        thresh[:int(h/4),-1] = 0
        self.thresh = thresh
        
    def removeLaplacian(self, sharpCrit:int=20, **kwargs) -> None:
        '''remove from thresh the edges with a sharp gradient from white to black'''
        self.laplacian = cv.Laplacian(self.gray,cv.CV_64F)
        # ret, thresh2 = cv.threshold(laplacian,10,255,cv.THRESH_BINARY)   # sharp transition from black to white
        ret, thresh3 = cv.threshold(self.laplacian,-sharpCrit,255,cv.THRESH_BINARY_INV)  # sharp transition from white to black
        thresh3 = erode(normalize(thresh3), 2)  # remove tiny boxes
        thresh3 = thresh3.astype(np.uint8)
        self.thresh = cv.subtract(self.thresh, thresh3)

    def fillParts(self, fillTop:bool=True, **kwargs) -> None:
        '''fill the components, and remove the border if needed'''
        if fillTop:
            self.thresh = self.closeVerticalTop(self.thresh, close=True)
        if self.closing>0:
            self.thresh = closeMorph(self.thresh, self.closing)
        elif self.closing<0:
            self.thresh = openMorph(self.thresh, -self.closing)
        if self.removeSharp:
            self.removeLaplacian(**self.kwargs)
        if self.fillMode == fillMode.removeBorder:
            self.filled = removeBorderAndFill(self.thresh, leaveHollows=True)    
        elif self.fillMode == fillMode.fillSimple:
            self.filled = fillComponents(self.thresh, diag=self.diag-2, leaveHollows=False)
        elif self.fillMode == fillMode.fillSimpleWithHoles:
            self.filled = fillComponents(self.thresh, diag=self.diag-2, leaveHollows=True)
        elif self.fillMode == fillMode.fillByContours:
            if hasattr(self, 'laplacian'):
                self.filled = fillByContours(self.thresh, self.im, diag=self.diag-2, laplacian=self.laplacian)
            else:
                self.filled = fillByContours(self.thresh, self.im, diag=self.diag-2)
        self.filled = self.closeVerticalTop(self.filled, close=False)
        if self.closing>0:
            self.filled = closeMorph(self.filled, self.closing)
        elif self.closing<0:
            self.filled = openMorph(self.filled, -self.closing)
            
    def emptyVertSpaces(self) -> None:
        '''empty the vertical spaces between printed vertical lines'''
        if not hasattr(self, 'filled'):
            return
        # Apply morphology operations
        thresh2 = self.nd.maskNozzle(self.thresh, dilate=5, crops=self.crops, invert=True)  # generously remove nozzle
        gX = openMorph(thresh2, 1, aspect=15)    # filter out horizontal lines
        tot1 = closeMorph(gX, 5, aspect=1/5)   # close sharp edges
        tot = emptySpaces(tot1)    # fill gaps
        tot = openMorph(tot, 3)    # remove debris
        er = cv.subtract(tot1, gX)              # get extra filled gaps
        tot = cv.add(tot, er)        # remove from image
        tot = openMorph(tot, 2)           # remove debris
        
        filled = cv.subtract(self.sdf.labelsBW, tot)   # remove from image

        if self.diag>1:
            imshow(gX, tot, filled, self.filled, title='emptyVertSpaces')
        self.filled = filled
        self.makeDF()
        
            
        
    def removeNozzle(self, s:str='filled') -> None:
        '''remove the black nozzle from the image'''
        if not (hasattr(self, 'nd') and hasattr(self, 'crops')):
            return
        setattr(self, s, self.nd.maskNozzle(getattr(self, s), ave=False, invert=True, crops=self.crops))  
        # remove the nozzle again
            
            
    def segmentInterfaces(self, addNozzle:bool=True, addNozzleBottom:bool=False, **kwargs) -> np.array:
        '''from a color image, segment out the ink, and label each distinct fluid segment. 
        acrit is the minimum component size for an ink segment
        removeVert=True to remove vertical lines from the thresholded image
        removeBorder=True to remove border components from the thresholded image'''
        self.getGray()
        self.threshes(**kwargs)  # threshold
        if addNozzle:
            self.addNozzle()    # add the nozzle to the thresholded image
        if addNozzleBottom:
            self.addNozzle(bottomOnly=True)
        self.fillParts(**kwargs)    # fill components
        self.removeNozzle() # remove the nozzle again
        
    def __getattr__(self, s):
        if s in ['success', 'df', 'labeledIm', 'numComponents', 'labelsBW']:
            return getattr(self.sdf, s)
        
    def eraseSmallComponents(self, **kwargs):
        '''erase small components from the labeled image and create a binary image'''
        return self.sdf.eraseSmallComponents(**kwargs)
        
    def eraseSmallestComponents(self, satelliteCrit:float=0.2, **kwargs) -> None:
        '''erase the smallest relative components from the labeled image'''
        return self.sdf.eraseSmallestComponents(satelliteCrit, **kwargs)
          
    def eraseBorderComponents(self, margin:int, **kwargs) -> None:
        '''remove any components that are too close to the edge'''
        return self.sdf.eraseBorderComponents(margin, **kwargs)
        
    def eraseFullWidthComponents(self, **kwargs) -> None:
        '''remove components that are the full width of the image'''
        return self.sdf.eraseFullWidthComponents(**kwargs)
        
    def eraseLeftRightBorder(self, **kwargs) -> None:
        '''remove components that are touching the left or right border'''
        return self.sdf.eraseLeftRightBorder(**kwargs)
        
    def eraseTopBottomBorder(self, **kwargs) -> None:
        '''remove components that are touching the top or bottom border'''
        return self.sdf.eraseTopBottomBorder(**kwargs)
     
    def removeScragglies(self, **kwargs) -> None:
        return self.sdf.removeScragglies(**kwargs)
        
    def largestObject(self) -> pd.Series:
        '''the largest object in the dataframe'''
        return self.sdf.largestObject()
     
    def reconstructMask(self, df:pd.DataFrame) -> np.array:
        '''construct a binary mask with all components labeled in the dataframe'''
        return self.sdf.reconstructMask(df)
    
    def noDF(self) -> bool:
        return self.sdf.noDF(df)

            
class segmenterDF(timeObject):
    '''holds labeled components for an image'''
    
    def __init__(self, filled:np.array, acrit:float=100, diag:int=0):
        self.acrit = acrit
        self.filled = filled
        self.trustLargest = 0
        self.success = False
        self.w = self.filled.shape[1]
        self.h = self.filled.shape[0]
        self.diag = diag
        self.getConnectedComponents()
        
    def display(self):
        if self.diag<1:
            return
        if not hasattr(self, 'imML'):
            return
        imdiag = cv.cvtColor(self.filled, cv.COLOR_GRAY2BGR)
        imdiag[(self.exc==255)] = [0,0,255]
        imshow(self.imML, self.imU, self.dif, imdiag, titles=['ML', 'Unsupervised', 'Difference'])
        return
    
    def getDataFrame(self):
        '''convert the labeled segments to a dataframe'''
        df = pd.DataFrame(self.stats, columns=['x0', 'y0', 'w', 'h','a'])
        df2 = pd.DataFrame(self.centroids, columns=['xc','yc'])
        df = pd.concat([df, df2], axis=1) 
            # combine markers into dataframe w/ label stats
        df = df[df.a<df.a.max()] 
            # remove largest element, which is background
        self.df = df
        
    def resetStats(self):
        '''reset the number of components and the filtered binary image'''
        self.numComponents = len(self.df)
        self.labelsBW = self.labeledIm.copy()
        self.labelsBW[self.labelsBW>0]=255
        self.labelsBW = self.labelsBW.astype(np.uint8)
        if self.diag>0 and self.labeledIm.max().max()>6:
            self.resetNumbering()
        if self.numComponents==0:
            self.success = False
        else:
            self.success = True
            
    def resetNumbering(self):
        '''reset the numbering of the components so the labeledIm is easier to read'''
        j = 1
        for i,row in self.df.iterrows():
            self.labeledIm[self.labeledIm == i] = j
            self.df.rename(index={i:j}, inplace=True)
            j = j+1
            
            
    def noDF(self) -> bool:
        return not hasattr(self, 'df') or len(self.df)==0
    
    def touchingBorder(self, row:pd.Series, margin:int=5):
        '''determine if the object is touching the border'''
        if row['x0']<margin:
            return True
        if row['x0']+row['w']>self.w-margin:
            return True
        if row['y0']<margin:
            return True
        if row['y0']+row['h']>self.h-margin:
            return True
    
    def mainComponent(self, margin:int=5, pcrit:int=20) -> int:
        '''the index of the largest, most centrally located component'''
        largest = self.largestObject()
        if type(largest) is int:
            return -1
        if self.trustLargest==1:
            return largest.name
        if self.trustLargest==-1:
            return -1
        if self.touchingBorder(largest):
            # this object is close to border
            mask = self.singleMask(largest.name)
            contours = getContours(mask, mode=cv.CHAIN_APPROX_NONE)
            if len(contours)>0:
                contours = contours[0][:,0]
                xmin = len(contours[contours[:,0]==min(contours[:,0])])
                xmax = len(contours[contours[:,0]==max(contours[:,0])])
                ymin = len(contours[contours[:,1]==min(contours[:,1])])
                ymax = len(contours[contours[:,1]==max(contours[:,1])])
                if xmin>pcrit or xmax>pcrit or ymin>pcrit or ymax>pcrit:
                    return -1
                else:
                    self.trustLargest = 1
                    return largest.name
            else:
                return -1
        else:
            return largest.name
            
    def selectComponents(self, goodpts:pd.Series, checks:bool=True, **kwargs) -> None:
        '''erase any components that don't fall under criterion'''
        if len(goodpts)==0:
            # don't empty the dataframe
            return
        for i in list(self.df[~goodpts].index):
            if not checks or not i==self.mainComponent():
                self.labeledIm[self.labeledIm==i] = 0
            else:
                # add this point back in
                goodpts = goodpts|(self.df.index==i)
        self.df = self.df[goodpts] 
        self.resetStats()
            
    def eraseSmallComponents(self, **kwargs):
        '''erase small components from the labeled image and create a binary image'''
        if self.noDF():
            return
        goodpts = (self.df.a>=self.acrit)
        self.selectComponents(goodpts, **kwargs)
        
    def eraseLargeComponents(self, acrit:int, **kwargs):
        '''erase large components from the labeled image'''
        if self.noDF():
            return
        goodpts = (self.df.a<=acrit)
        self.selectComponents(goodpts, **kwargs)
        
    def eraseSmallestComponents(self, satelliteCrit:float=0.2, **kwargs) -> None:
        '''erase the smallest relative components from the labeled image'''
        if self.noDF():
            return
        goodpts = (self.df.a>=satelliteCrit*self.df.a.max())
        self.selectComponents(goodpts, **kwargs)
          
    def eraseBorderComponents(self, margin:int, **kwargs) -> None:
        '''remove any components that are too close to the edge'''
        if self.noDF():
            return
        goodpts = (self.df.x0>margin)&(self.df.y0>margin)&(self.df.x0+self.df.w<self.w-margin)&(self.df.y0+self.df.h<self.h-margin)
        self.selectComponents(goodpts, **kwargs)
        
    def eraseFullWidthComponents(self, margin:int=0, **kwargs) -> None:
        '''remove components that are the full width of the image'''
        if self.noDF():
            return
        goodpts = (self.df.w<self.w-margin)
        self.selectComponents(goodpts, **kwargs)
        
    def eraseLeftRightBorder(self, margin:int=1, **kwargs) -> None:
        '''remove components that are touching the left or right border'''
        if self.noDF():
            return
        goodpts = ((self.df.x0>margin)&(self.df.x0+self.df.w<(self.w-margin)))
        self.selectComponents(goodpts, **kwargs)
        
    def eraseTopBottomBorder(self, margin:int=0, **kwargs) -> None:
        '''remove components that are touching the top or bottom border'''
        if self.noDF():
            return
        goodpts = (self.df.y0>margin)&(self.df.y0+self.df.h<self.h-margin)
        self.selectComponents(goodpts, **kwargs)
        
    def eraseTopBorder(self, margin:int=0, **kwargs) -> None:
        '''remove components that are touching the top or bottom border'''
        if self.noDF():
            return
        goodpts = (self.df.y0>margin)
        self.selectComponents(goodpts, **kwargs)
        
        
    def largestObject(self, **kwargs) -> pd.Series:
        '''the largest object in the dataframe'''
        if len(self.df)==0:
            return []
        return self.df[self.df.a==self.df.a.max()].iloc[0]
            
    def removeScragglies(self, **kwargs) -> None:
        '''if the largest object is smooth, remove anything with high roughness'''
        if self.numComponents<=1:
            return
        for i in self.df.index:
            mask = (self.labeledIm == i).astype("uint8") * 255 
            cnt = getContours(mask)[0]
            self.df.loc[i, 'roughness'] = contourRoughness(cnt)
        if not self.df.idxmin()['roughness']==self.df.idxmax()['a']:
            # smoothest object is not the largest object
            return
        if self.df.roughness.min()>0.5:
            # smoothest object is pretty rough
            return
        goodpts = self.df.roughness<(self.df.roughness.min()+0.5)
        self.selectComponents(goodpts, **kwargs)

    def getConnectedComponents(self) -> int:
        '''get connected components and filter by area, then create a new binary image without small components'''
        self.markers = cv.connectedComponentsWithStats(self.filled, 8, cv.CV_32S)
        self.numComponents = self.markers[0]
        if self.numComponents==1:
            # no components detected
            return 1
        
        self.labeledIm = self.markers[1]  # this image uses different numbers to label each component
        self.stats = self.markers[2]
        self.centroids = self.markers[3]
        self.getDataFrame()       # convert stats to dataframe
        self.eraseSmallComponents()
        self.resetStats()
        return 0  

    def singleMask(self, i:int) -> np.array:
        '''get a binary mask of a single component given as a row in df'''
        return (self.labeledIm == i).astype("uint8") * 255
            
    def reconstructMask(self, df:pd.DataFrame) -> np.array:
        '''construct a binary mask with all components labeled in the dataframe'''
        masks = [self.singleMask(i) for i in df.index]
        if len(masks)>0:
            componentMask = masks[0]
            if len(masks)>1:
                for mask in masks[1:]:
                    componentMask = cv.add(componentMask, mask)
            
        else:
            return np.zeros(self.filled.shape).astype(np.uint8)
        return componentMask
    
    def componentIsIn(self, mask:np.array) -> bool:
        '''determine if the component shown in the mask overlaps with the existing image'''
        both = cv.bitwise_and(mask, self.filled)
        return both.sum().sum()>0
    
    def commonMask(self, sdf, onlyOne:bool=False) -> np.array:
        '''get the mask of all components that overlap with the segments in sdf, another segmenterDF object'''
        mask = np.zeros(self.filled.shape).astype(np.uint8)
        if not hasattr(self, 'df'):
            return mask
        for i in self.df.index:
            m = self.singleMask(i)
            if sdf.componentIsIn(m):
                mask = cv.add(mask, m)
        return mask


class segmentCombiner(timeObject):
    '''combine segmentation from ML model and unsupervised model'''
    
    def __init__(self, imML:np.array, imU:np.array, acrit:int, rErode:int=5, rDilate:int=10, diag:int=0):
        super().__init__()
        sML = segmenterDF(imML, acrit=acrit) # ML DF
        sU = segmenterDF(imU, acrit=acrit) # unsupervised DF
        sMLm = sML.commonMask(sU)         # parts from ML that are also in unsupervised
        sUm = sU.commonMask(sML)          # parts from unsupervised that are also in ML
        both = cv.bitwise_and(sMLm, sUm)  # parts that are in both
        tot = cv.add(sMLm, sUm)           # parts that are in either, but with overlapping components

        MLadd = cv.subtract(sMLm, sUm)   # parts that are in ML but not U
        if MLadd.sum().sum()>0:
            e2 = segmenterDF(MLadd, acrit=0)
            e2.eraseTopBorder(margin=5, checks=False)               # remove parts from the ML image that are touching the top edge
            if hasattr(e2, 'labelsBW'):       # ML model has tendency to add reflection at top
                MLadd = e2.labelsBW
        dif = cv.subtract(sUm, sMLm)
        Uadd = dilate(erode(dif, rErode),rDilate)   # parts that are in U but not ML, opened
        Uexc = cv.bitwise_and(tot, Uadd)
        if Uexc.sum().sum()>0:
            e1 = segmenterDF(Uexc, acrit=0)
            e1.eraseLargeComponents(1000, checks=False)
            if hasattr(e1, 'labelsBW'):
                Uexc = e1.labelsBW
        exc = cv.add(MLadd, Uexc)
        filled = cv.add(both, exc)
        filled = fillTiny(filled, acrit=50)
        segmenter = segmenterDF(filled, acrit=acrit, diag=diag)
        segmenter.imML = imML
        segmenter.imU = imU
        segmenter.exc = exc
        segmenter.dif = dif
        self.segmenter = segmenter
        
    
#----------------------------------------------------------
    
class segmenterSingle(segmenter):
    
    def __init__(self, im:np.array, acrit:float=2500, diag:int=0, removeVert:bool=False, removeBorder:bool=True, **kwargs):
        self.removeVert = removeVert
        super().__init__(im, acrit=acrit, diag=diag, removeBorder=removeBorder, **kwargs)
 
        
    def threshes(self, attempt:int, topthresh:int=200, whiteval:int=80, **kwargs) -> None:
        '''threshold the grayscale image
        attempt number chooses different strategies for thresholding ink
        topthresh is the initial threshold value
        whiteval is the pixel intensity below which everything can be considered white
        increase diag to see more diagnostic messages
        '''
        if attempt==0:
    #         ret, thresh = cv.threshold(self.gray,180,255,cv.THRESH_BINARY_INV)
            # just threshold on intensity
            crit = topthresh
            impx = np.product(self.gray.shape)
            allwhite = impx*whiteval
            prod = allwhite
            while prod>=allwhite and crit>100: # segmentation included too much
                ret, thresh1 = cv.threshold(self.gray,crit,255,cv.THRESH_BINARY_INV)
                ret, thresh2 = cv.threshold(self.gray,crit+10,255,cv.THRESH_BINARY_INV)
                thresh = np.ones(shape=thresh2.shape, dtype=np.uint8)
                thresh[:600,:] = thresh2[:600,:] # use higher threshold for top 2 lines
                thresh[600:,:] = thresh1[600:,:] # use lower threshold for bottom line
                prod = np.sum(np.sum(thresh))
                crit = crit-10
    #         ret, thresh = cv.threshold(self.gray,0,255,cv.THRESH_BINARY_INV+cv.THRESH_OTSU)
            if diag>0:
                logging.info(f'Threshold: {crit+10}, product: {prod/impx}, white:{whiteval}')
        elif attempt==1:
            # adaptive threshold, for local contrast points
            thresh = cv.adaptiveThreshold(self.gray,255,cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY,11,2)
            filled = fillComponents(thresh)
            thresh = cv.add(255-thresh,filled)
        elif attempt==2:
            # threshold based on difference between red and blue channel
            b = self.im[:,:,2]
            g = self.im[:,:,1]
            r = self.im[:,:,0]
            self.gray2 = cv.subtract(r,b)
            self.gray2 = cv.medianBlur(self.gray2, 5)
            ret, thresh = cv.threshold(self.gray2,0,255,cv.THRESH_BINARY_INV+cv.THRESH_OTSU)
            ret, background = cv.threshold(r,0,255, cv.THRESH_BINARY_INV+cv.THRESH_OTSU)
            background = 255-background
            thresh = cv.subtract(background, thresh)
        elif attempt==3:
            # adaptive threshold, for local contrast points
            thresh = cv.adaptiveThreshold(self.gray,255,cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY,21,2)
            filled = fillComponents(thresh)
            thresh2 = cv.add(255-thresh,filled)

            # remove verticals
            if self.removeVert:
                # removeVert=True to remove vertical lines from the thresholding. useful for horizontal images where stitching leaves edges
                thresh = cv.subtract(thresh, verticalFilter(self.gray))
                ret, topbot = cv.threshold(self.gray,0,255,cv.THRESH_BINARY_INV+cv.THRESH_OTSU) 
                thresh = cv.subtract(thresh,topbot)
        elif attempt==4:
            thresh0 = threshes(self.im, self.gray, self.removeVert, 0)
            thresh2 = threshes(self.im, self.gray, self.removeVert, 2)
            thresh = cv.bitwise_or(thresh0, thresh2)
            thresh = cv.medianBlur(thresh,3)
        self.thresh = closeVerticalTop(thresh)
    
    def segmentInterfaces(self) -> np.array:
        '''from a color image, segment out the ink, and label each distinct fluid segment. '''
        self.getGray()
        attempt = 0
        self.finalAt = attempt
        while attempt<1:
            self.finalAt = attempt
            self.threshes(attempt, **self.kwargs)
            if self.removeBorder:
                self.filled = fillComponents(self.thresh)    
            else:
                self.filled = self.thresh.copy()
            self.markers = cv.connectedComponentsWithStats(self.filled, 8, cv.CV_32S)

            if self.self.diag>0:
                imshow(self.im, self.gray, self.thresh, self.filled)
                plt.title(f'attempt:{attempt}')
            if self.markers[0]>1:
                self.df = pd.DataFrame(self.markers[2], columns=['x0', 'y0', 'w', 'h', 'area'])
                if max(self.df.loc[1:,'area'])<self.acrit:
                    # poor segmentation. redo with adaptive thresholding.
                    attempt=attempt+1
                else:
                    attempt = 6
            else:
                attempt = attempt+1
        return self.filled, self.markers, self.finalAt
    
    

        
    