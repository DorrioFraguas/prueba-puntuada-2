#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE: CLEAN

@author: sm5911
@date: 09/08/2019

"""

# IMPORTS
import pandas as pd

#%% FUNCTIONS
def fillNaNgroupby(df, group_by, non_data_cols=None, method='mean', axis=0):
    """ A function to impute missing values in given dataframe by replacing
        with mean value by given grouping variable. """
    
    def groupMeanValue(group, axis=axis):
        group = group.fillna(group.mean(axis=axis))
        return group

    original_cols = list(df.columns)
    if isinstance(non_data_cols, pd.Index):
        non_data_cols = list(non_data_cols)
    if non_data_cols:
        if not isinstance(non_data_cols, list):
            print("Please provide non data columns as a list or 'pandas.Index' object")
        else:    
            if group_by in non_data_cols:
                #print("'%s' found in non-data columns" % group_by)
                non_data_cols_nogroupby = [col for col in non_data_cols if col != group_by]
                datacols = [col for col in df.columns if col not in non_data_cols_nogroupby]
            elif group_by not in non_data_cols:
                datacols = [col for col in df.columns if col not in non_data_cols]

            nondata = df[non_data_cols]
            data = df[datacols]
            
            n_nans = data.isna().sum(axis=axis).sum()
            if n_nans > 0:
                print("Imputing %d missing values using %s value for each '%s'" % (n_nans, method, group_by))
    
                data = data.groupby(group_by).transform(groupMeanValue)
                df = pd.concat([nondata, data], axis=1, sort=False)
            else:
                print("No NaN values found in data.")
    else:
        n_nans = df.isna().sum(axis=axis).sum()
        print("Imputing %d missing values using %s value for each '%s'" % (n_nans, method, group_by))
        df = df.groupby(group_by).transform(groupMeanValue)
    
    return df[original_cols]

#%%
def filterSummaryResults(full_results_df, impute_NaNs_by_group=False, preconditioned_from_L4='yes',\
                        featurecolnames=None, snippet=0, nan_threshold=0.75):
    """ 
    A function written to: 
    (1) clean feature summary results in the following ways: 
        (a) remove features with too many NaN values ('nan_threshold'=0-1)
        (b) remove features that are all zeroes, and (c) impute remaining missing 
            values (with global or group mean, 'impute_NaNs_by_group'=True/False)
    (2) filter feature summary results by the following treatments: 
        (a) whether worms have been exposed to the food prior to assay recording 
            ('preconditioned_from_L4'='yes'/'no')
        (b) the video snippet of interest ('snippet'=0-10)
    Feature column names should be provided
    """
    # Filter feature summary results to analyse the video snippet required
    snippet_df = full_results_df[full_results_df['filename'].str.contains('%.6d_featuresN.hdf5' % snippet)]
    
    # Filter feature summary results to look at L4-prefed worms (long food exposure) only
    precondition_snippet_df = snippet_df[snippet_df['preconditioned_from_L4'].str.lower() == preconditioned_from_L4.lower()]
    
    # Divide dataframe into 2 dataframes: data (feature summaries) and non-data (metadata)
    colnames_all = list(precondition_snippet_df.columns)
    if isinstance(featurecolnames, list):
        colnames_data = featurecolnames
        colnames_nondata = [col for col in colnames_all if col not in colnames_data]
    else:
        # Use defaults
        colnames_data = colnames_all[25:]
        colnames_nondata = colnames_all[:25]
        
    data_df = precondition_snippet_df[colnames_data]
    nondata_df = precondition_snippet_df[colnames_nondata]
    
    # Drop data columns with too many nan values
    colnamesBefore = data_df.columns
    data_df = data_df.dropna(axis=1, thresh=nan_threshold)
    colnamesAfter = data_df.columns
    nan_cols = len(colnamesBefore) - len(colnamesAfter)
    print("Dropped %d features with too many NaNs" % nan_cols)
    
    # All dropped features here have to do with the 'food_edge' (which is undefined, so NaNs are expected)
    droppedFeatsList_NaN = [col for col in colnamesBefore if col not in colnamesAfter]
    
    # Drop data columns that contain only zeros
    colnamesBefore = data_df.columns
    data_df = data_df.drop(columns=data_df.columns[(data_df == 0).all()])
    colnamesAfter = data_df.columns
    zero_cols = len(colnamesBefore) - len(colnamesAfter)
    print("Dropped %d features with all zeros" % zero_cols)
    
    # All dropped features here have to do with 'd_blob' (blob derivative calculations)
    droppedFeatsList_allZero = [col for col in colnamesBefore if col not in colnamesAfter]
    
    if not impute_NaNs_by_group:
        # Impute remaining NaN values (using global mean feature value for each food)
        n_nans = data_df.isna().sum(axis=1).sum()
        if n_nans > 0:
            print("Imputing %d missing values using global mean value for each feature" % n_nans)  
            data_df = data_df.fillna(data_df.mean(axis=1))
        else:
            print("No need to impute! No remaining NaN values found in feature summary results.")
    
    # Re-combine into full results dataframe
    precondition_snippet_df = pd.concat([nondata_df, data_df], axis=1, sort=False)
    
    if impute_NaNs_by_group:
        # Impute remaining NaN values (using mean feature value for each food)
        n_nans = data_df.isna().sum(axis=1).sum()
        if n_nans > 0:    
            precondition_snippet_df = fillNaNgroupby(df=precondition_snippet_df, group_by='food_type',\
                                                non_data_cols=colnames_nondata)
        else:
            print("No need to impute! No remaining NaN values found in feature summary results.") 
            
    return precondition_snippet_df, droppedFeatsList_NaN, droppedFeatsList_allZero
