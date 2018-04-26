# -*- coding: utf-8 -*-
"""
Created on Wed Apr 25 21:56:46 2018

@author: fiorito_l
"""
import numpy as np
import pandas as pd

def split_zam(zam):
    Z = np.floor(np.array(zam)/10000)
    A = np.floor((np.array(zam) - Z*10000)/10)
    M = np.floor(np.array(zam) - Z*10000 - A*10)
    return pd.DataFrame.from_dict({"Z" : Z, "A" : A, "M" : M, "ZAM" : zam}, dtype=int)