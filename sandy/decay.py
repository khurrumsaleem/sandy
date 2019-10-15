# -*- coding: utf-8 -*-
"""
Outline
=======
1. Summary_
2. Examples_
3. Routines_

.. _Summary:

Summary
=======
This module contains all classes and functions dedicated to the processing and 
analysis of a decay data.

.. _Examples:

Examples
========

Example 1
---------
To collect all decay data from a endf-6 file called `"rdd.dat"` into a `DecayData` object:

>>> import sandy
>>> tape = sandy.read_formatted_file("rdd.dat")
>>> rdd = sandy.decay.from_endf6(tape)

Example 2
---------
To save the data content of a `DecayData` object into a hdf5 file `"decay.hdf5"` in the 
group namespace `"jeff_33"`:

>>> rdd.to_hdf5("decay.hdf5", "jeff_33")

Example 3
---------
To collect all decay data from a hdf5 file called `"decay.hdf5"` into a `DecayData` object:

>>> import sandy
>>> rdd = sandy.decay.from_hdf5("decay.hdf5")

Example 4
---------
To produce a transition matrix (for depletion purposes) from a `DecayData` object `rdd`:

>>> tmatrix = rdd.get_transition_matrix()

.. _Routines:

Routines
========

"""

import logging
import pdb
import h5py
import os

import numpy as np
import pandas as pd

import sandy

__author__ = "Luca Fiorito"

__all__ = [
        "DecayData"
        ]



class DecayData():
    """Dataframe of decay chains for several isotopes.
    Each row contain a different decay chain.
    

    **Columns**:
        
        - PARENT : (`int`) `ID = ZZZ * 10000 + AAA * 10 + META` of parent nuclide
        - DAUGHTER : (`int`) `ID = ZZZ * 10000 + AAA * 10 + META` of daughter nuclide
        - YIELD : (`float`) branching ratio (between 0 and 1)
        - CONSTANT : (`float`) decay constant
    
    Methods
    -------
    get_bmatrix
        extract B-matrix inro dataframe
    get_decay_chains
        extract decay chains into dataframe
    get_qmatrix
        extract Q-matrix into dataframe
    get_transition_matrix
        extract transition matrix into dataframe
    """

    labels = ["PARENT", "DAUGHTER", "YIELD", "CONSTANT"]
    
    def to_hdf5(self, filename, lib):
        """
        ....
        """
        with h5py.File(filename, 'w') as h5file:
            sandy.tools.recursively_save_dict_contents_to_group(h5file, '/decay/{}/'.format(lib), self.data)
    
    def get_bmatrix(self):
        """
        Extract B-matrix into dataframe.
        
        Returns
        -------
        `pandas.DataFrame`
            B-matrix associated to the given decay chains
        """
        df = self.get_decay_chains()
        B = df.pivot_table(index="DAUGHTER", columns="PARENT", values="YIELD", aggfunc=np.sum, fill_value=0.0). \
                 astype(float). \
                 fillna(0)
        np.fill_diagonal(B.values, 0)
        return B.reindex(B.columns.values, fill_value=0.0)

    def get_qmatrix(self, keep_neutrons=False):
        """Extract Q-matrix dataframe.
        
        Returns
        -------
        `pandas.DataFrame`
            Q-matrix associated to the given decay chains
        """
        B = self.get_bmatrix()
        if not keep_neutrons:
            if 10 in B.index:
                B.drop(index=10, inplace=True)
            if 10 in B.columns:
                B.drop(columns=10, inplace=True)
        C = np.identity(len(B)) - B.values
        Q = np.linalg.pinv(C)
        return pd.DataFrame(Q, index=B.index, columns=B.columns)

    def get_decay_chains(self):
        """
        Extract decay chains into dataframe.
        
        Returns
        -------
        `pandas.DataFrame`
            decay chains dataframe
        
        Raises
        ------
        `AssertionError`
            when key `"decay_mode"` is not present but `"decay_constant"` is larger than 0
        `AssertionError`
            when key `"decay_products"` is not present and decay mode is not spontaneous fission
        """
        items = []
        for zam,v in sorted(self.data.items()):
            items.append((zam, zam, -1., 1., v["decay_constant"]))
            if "decay_mode" not in v:
                assert v["decay_constant"] == 0
                continue
            for km, vm in v["decay_mode"].items():
                if "decay_products" not in vm:
                    assert km == 60
                    continue
                for zap,yld in vm["decay_products"].items():
                    items.append((zam, zap, yld, vm["branching_ratio"], v["decay_constant"]))
        return pd.DataFrame(items, columns=["PARENT", "DAUGHTER", "YIELD", "BR", "LAMBDA"]).sort_values(by=["PARENT", "DAUGHTER"])
            
    def get_transition_matrix(self):
        """
        Extract transition matrix into dataframe.
        
        Returns
        -------
        `pandas.DataFrame`
            transition matrix associated to the given decay chains
        """
        df = self.get_decay_chains()
        df["YIELD"] *= df["LAMBDA"]*df["BR"]
        T = df.pivot_table(index="DAUGHTER", columns="PARENT", values="YIELD", aggfunc=np.sum). \
               astype(float). \
               fillna(0)
        return T.reindex(T.columns.values, fill_value=0.0)



def expand_decay_type(zam, dectyp):
    """
    Expand a decay type into decay products
    
    Parameters
    ----------
    zam : `int`
        ZAM identifier
    dectyp : `int`
        decay mode where:
            1. Beta decay
            2. Electron capture and/or positron emission
            3. Isomeric transition
            4. Alpha decay
            5. Neutron emission (not delayed neutron decay)
            6. Spontaneous fission
            7. Proton emission
    
    Returns
    -------
    `int`
        decay daughter product ZAM identifier
    `float`
        number of emitted neutrons
    `float`
        number of emitted protons
    `float`
        number of emitted alphas
    """
    daughter = zam//10
    neutrons = 0.
    protons = 0.
    alphas = 0.
    if dectyp == 1: # Beta decay
        daughter += 1001 - 1
    elif dectyp == 2: # Electron capture and/or positron emission
        daughter += 1 - 1001
    elif dectyp == 3: # Isomeric transition
        pass
    elif dectyp == 4: # Alpha decay
        daughter -= 2004
        alphas += 1.
    elif dectyp == 5: # Neutron emission
        daughter -= 1
        neutrons += 1.
    elif dectyp == 6: # Spontaneous fission
        pass
    elif dectyp == 7: # Proton emission
        daughter -= 1001
        protons += 1.
    elif dectyp == 0: # Gamma emission (not used in MT457)
        pass
    else: # Unknown decay mode
        raise sandy.SandyError("unknown decay mode {} for ZAM={}...".format(dectyp, zam))
    return daughter*10, neutrons, protons, alphas



def get_decay_products(rtyp, zam, rfs):
    """
    For a given isotope and decay mode, extract a dictionary of decay products.

    Parameters
    ----------
    rtyp : `str`
        string of decay modes where:
            1. Beta decay
            2. Electron capture and/or positron emission
            3. Isomeric transition
            4. Alpha decay
            5. Neutron emission (not delayed neutron decay)
            6. Spontaneous fission
            7. Proton emission
        
        Decay mode combinations are allowed, e.g. "15" means Beta decay 
        followed by neutron emission (delayed neutron decay).
    zam : `int`
        ZAM identifier of the nuclide undergoing decay (parent)
    rfs : `int`
        Isomeric state flag for daughter nuclide, e.g. `rfs=0` is ground state, 
        `rfs=1` is first isomeric state, etc.
    
    Returns
    -------
    `dict`
        dictionary of decay products where the keys are the ZAM identifiers for the products
        and the values are the corresponding yield.       
    """
    daughter = zam + 0
    neutrons = 0.
    protons = 0.
    alphas = 0.
    for dectyp in map(int, rtyp):
        daughter, n, h, a = expand_decay_type(daughter, dectyp)
        neutrons += n
        protons += h
        alphas += a
    daughter = int(daughter + rfs)
    products = {}
    if daughter != zam:
        products[daughter] = 1.0
    if neutrons != 0:
        products[10] = neutrons 
    if protons != 0:
        products[10010] = protons
    if alphas != 0:
        products[20040] = alphas
    return products


def from_endf6(endf6):
    """
    Extract hierarchical structure of decay data from `sandy.Endf6` instance.
    
    Parameters
    ----------
    tape : `sandy.Endf6`
        instance containing decay data
    
    Returns
    -------
    `DecayData`
        decay data object
    
    Raises
    ------
    `sandy.SandyError`
        if no decay data is found
    """
    tape = endf6.filter_by(listmf=[8], listmt=[457])
    if tape.empty:
        raise sandy.SandyError("no decay data found in file")
    groups = {} 
    for ix,text in tape.TEXT.iteritems():
        X = endf6.read_section(*ix)
        zam = int(X["ZA"]*10 + X["LISO"])
        groups[zam] = {"decay_constant" : X["LAMBDA"], "decay_mode" : {}}
        if "DK" not in X: # Stable isotope
            continue
        for rtyp, dk in X["DK"].items():
            decay_mode_data = {
                    "decay_products" : get_decay_products(rtyp, zam, dk["RFS"]),
                    "branching_ratio" : dk["BR"],
                    }
            groups[zam]["decay_mode"][rtyp] = decay_mode_data
    out = DecayData()
    out.data = groups
    return out



def from_hdf5(filename, lib):
    """
    Extract hierarchical structure of decay data from hdf5 file.
    
    Parameters
    ----------
    filename : `str`
        hdf5 filename (absolute or relative)
    lib : `str`
        library ID contained in the hdf5 file
    
    Returns
    -------
    `DecayData`
        decay data object
    """
    out = DecayData()
    with h5py.File(filename, 'r') as h5file:
        out.data = sandy.tools.recursively_load_dict_contents_from_group(h5file, '/decay/{}/'.format(lib))
    return out