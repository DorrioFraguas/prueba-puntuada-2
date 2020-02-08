#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@date:   18/12/2019 (modified: 5/2/2020)
@author: Saul Moore (sm5911)

COMPARE MUTANT STRAINS TO N2 CONTROL & PLOT SIGNIFICANT FEATURES

This example script loads feature summaries generated by Tierpsy and uses the 
data to compare N2 behaviour on twelve bacterial strains to the control, OP50. 
It performs PCA to visualise the differences in  the different strains, and 
then performs feature-by-feature tests to identify those that are significantly 
different between the mutants and the wild type after controlling for multiple 
comparisons.

Specifically, this script does the following:
a) Reads in: (1) a metadata file, (2) Tierpsy feature summary files (features 
   and filenames), (3) a set of top256 features to investigate
b) Matches strain names with results and combines metadata with feature summary results
c) Cleans data by dropping features with too many NaN values and replacing 
   remaining NaNs with global means
d) PCA on normalised feature summary matrix before and after removing outliers
e) Performs a test to find significantly different features from performance on
   the control strain
f) Saves PCA + box plots showing all significant differences

"""

#%% Imports

import os
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches
from matplotlib import transforms
from scipy.stats import ttest_ind, ranksums, zscore
from sklearn.decomposition import PCA
from sklearn.covariance import MinCovDet
from statsmodels.stats import multitest as smm


#%% Paths

# Path to example metadata
PATH_metadata = '/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/AuxiliaryFiles/20191003/example_metadata.csv'

# Path to associated Tierpsy feature summary files
PATH_featsums = '/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/features_summary_tierpsy_plate_20191008_105943_window_0.csv'
PATH_filesums = '/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/filenames_summary_tierpsy_plate_20191008_105943_window_0.csv'

# Path to Tierpsy 256 feature list (CSV)
PATH_top256 = '/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/AuxiliaryFiles/top256_tierpsy_no_blob_no_eigen_only_abs_no_norm.csv'


#%% Set parameters (user-defined)

nanThresh = 0.8                                                                # Threshold proportion of NaN values above which features are dropped from analysis
pvalThresh = 0.05
strainsToCompare = ['MYB71','JUB19','CENZENT1']                                # List of bacterial strains to compare N2 performance on
controlStrain = 'OP50'                                                         # Control bacterial strain
testType = 't-test'                                                            # Choice of statistical test: 't-test' or 'ranksum'

strainsToCompare.insert(0, controlStrain)


#%% Functions

def pcainfo(pca, zscores, PC=1, n_feats2print=10):
    """ A function to plot PCA explained variance, and print the most 
        important features in the given principal component (P.C.) """
    
    # Input error handling
    PC = int(PC)
    if PC == 0:
        PC += 1
    elif PC < 1:
        PC = abs(PC)
        
    cum_expl_var_frac = np.cumsum(pca.explained_variance_ratio_)

    # Plot explained variance
    fig, ax = plt.subplots()
    plt.plot(range(1,len(cum_expl_var_frac)+1),
             cum_expl_var_frac,
             marker='o')
    ax.set_xlabel('Number of Principal Components')
    ax.set_ylabel('explained $\sigma^2$')
    ax.set_ylim((0,1.05))
    fig.tight_layout()
    
    # Print important features
    important_feats = zscores.columns[np.argsort(pca.components_[PC-1]**2)[-n_feats2print:][::-1]]
    
    print("\nTop %d features in Principal Component %d:\n" % (n_feats2print, PC))
    for feat in important_feats:
        print(feat)

    return important_feats, fig

def MahalanobisOutliers(featMatProjected, extremeness=2., showplot=True):
    """ A function to determine to return a list of outlier indices using the
        Mahalanobis distance. 
        Outlier threshold = std(Mahalanobis distance) * extremeness degree 
        [extreme_values=2, very_extreme_values=3 --> according to 68-95-99.7 rule]
    """
    # NB: Euclidean distance puts more weight than it should on correlated variables
    # Chicken and egg situation, we can’t know they are outliers until we calculate 
    # the stats of the distribution, but the stats of the distribution are skewed outliers!
    # Mahalanobis gets around this by weighting by robust estimation of covariance matrix
    
    # Fit a Minimum Covariance Determinant (MCD) robust estimator to data 
    robust_cov = MinCovDet().fit(featMatProjected[:,:10]) # Use the first 10 principal components
    
    # Get the Mahalanobis distance
    MahalanobisDist = robust_cov.mahalanobis(featMatProjected[:,:10])
    
    # Colour PCA by Mahalanobis distance
    if showplot:
        plt.close('all')
        plt.rc('xtick',labelsize=15)
        plt.rc('ytick',labelsize=15)
        fig, ax = plt.subplots(figsize=[10,10])
        ax.set_facecolor('white')
        plt.scatter(np.array(projectedTable['PC1']), np.array(projectedTable['PC2']), c=MahalanobisDist)
        plt.title('Mahalanobis Distance for Outlier Detection', fontsize=20)
        plt.colorbar()

    k = np.std(MahalanobisDist) * extremeness
    upper_t = np.mean(MahalanobisDist) + k
    lower_t = np.mean(MahalanobisDist) - k
    outliers = []
    for i in range(len(MahalanobisDist)):
        if (MahalanobisDist[i] >= upper_t) or (MahalanobisDist[i] <= lower_t):
            outliers.append(i)
    print("Outliers found: %d" % len(outliers))
            
    return np.array(outliers)

def ranksumtest(test_data, control_data):
    """ A function to perform a series of Wilcoxon rank sum tests 
        (column-wise between 2 dataframes of equal dimensions)
    
    Returns
    -------
    2 lists: a list of test statistics, and a list of associated p-values
    """
    
    colnames = list(test_data.columns)
    J = len(colnames)
    statistics = np.zeros(J)
    pvalues = np.zeros(J)
    
    for j in range(J):
        test_feat_data = test_data[colnames[j]]
        control_feat_data = control_data[colnames[j]]
        statistic, pval = ranksums(test_feat_data, control_feat_data)
        pvalues[j] = pval
        statistics[j] = statistic
        
    return statistics, pvalues


#%% Import data, combine with metadata, and select feature subset

# Load the feature matrix, corresponding filenames, and metadata
tierpsyFeatureTable = pd.read_csv(PATH_featsums, skiprows=0)
tierpsyFileTable = pd.read_csv(PATH_filesums, skiprows=0)
metadataTable = pd.read_csv(PATH_metadata, dtype={"comments":str})

# Join Tierpsy results tables to match filenames with file_id (Required in case
# features were not extracted for any files)
combinedTierpsyTable = pd.merge(left=tierpsyFileTable, right=tierpsyFeatureTable,\
                                on='file_id')

# Get just the filenames from the full path in the tables
fileNamesTierpsy = combinedTierpsyTable['file_name']

# Rename Tierpsy output to match metadata output
combinedTierpsyTable['file_name'] = [file.split('/metadata_featuresN.hdf5')[0].replace('Results','MaskedVideos')\
                                     for file in fileNamesTierpsy]

# Merge metadata and results to match strain names with feature summaries
#(using uniqueID column created using filename and well number)

metadataTable['uniqueID'] = metadataTable['filename'] + '__' + metadataTable['well_number']
combinedTierpsyTable['uniqueID'] = combinedTierpsyTable['file_name'] + '__' + combinedTierpsyTable['well_name']

# Merge on uniqueID, keeping metadata entries where results are missing
featureTable = pd.merge(left=metadataTable, right=combinedTierpsyTable, how='left',\
                        left_on='uniqueID', right_on='uniqueID')

# Drop unnecessary columns
featureTable.drop(columns=['file_id','file_name','is_good','well_name'], inplace=True)
    
# Save combined results to file (CSV)
featureTable.to_csv('/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/CombinedResults.csv', index=False)

# Load the set of 256 features selected basexd on classification accuracy on a 
# set of mutant worm strains
top256_all = pd.read_csv(PATH_top256, header=0)
top256 = top256_all['1'] # Take just one set of 256


#%% Pre-process data (impute NaNs, normalise)

featNames = list(top256.values)
featMat = featureTable[featNames]

# Drop row entries that have no results (empty wells?)
rows2keep = featMat[featNames].sum(axis=1) != 0
inds = featMat.index[rows2keep]
if len(inds) < len(rows2keep):
    print("Dropping %d row entries with missing results" % (len(rows2keep) - len(inds))) # No worms in these wells? (see comments in metadata)
    featMat = featMat[rows2keep]

# Drop features that contain above threshold number of NaN values
n_feats = len(featMat.columns)
featMat = featMat.dropna(axis=1, thresh=nanThresh)
n_dropped_feats = n_feats - len(featMat.columns)
if n_dropped_feats > 0:
    print("Dropping %d features with no summary results" % n_dropped_feats)
    featNames = list(featMat.columns)
    
# Impute remaining NaN values (with global mean)
n_nans = featMat.isna().sum(axis=0).sum()
if n_nans > 0:
    print("Imputing %d missing values using global mean value for feature" % n_nans)  
    featMeans = featMat.mean(axis=0, skipna=True)
    featMat = featMat.fillna(featMeans)

# Re-combine into clean feature table
cols2keep = metadataTable.columns
featureTableClean = pd.concat([featureTable[rows2keep][cols2keep], featMat], axis=1, sort=False)

# Get names/indices of bacterial strains to analyse
bacteriaNames = featureTableClean['food_type']
uniqueNames = bacteriaNames.unique()
inds = featureTableClean['food_type'].isin(strainsToCompare)

featureTableStrains = featureTableClean[inds]
featMat = featMat[inds]

# Normalise the feature matrix (z-scores)
featMatNorm = featMat.apply(zscore, axis=0)


#%% Visualise strain differences using clustering and PCA

# Make a heatmap to check inter vs. intra strain phenotypic differences
colour_dictionary = dict(zip(strainsToCompare, sns.color_palette("bright", len(strainsToCompare))))

# Heatmap (clustergram) of Top256 features coloured by strain
plt.close('all')
row_colours = featureTableStrains['food_type'].map(colour_dictionary)
sns.set(font_scale=0.6)
g = sns.clustermap(featMatNorm, row_colors=row_colours, standard_scale=1,\
                   metric='correlation', figsize=[18,15], xticklabels=3)
plt.setp(g.ax_heatmap.xaxis.get_majorticklabels(), rotation=90)

# Save clustermap
plt.pause(5)
plt.savefig('/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/Clustergram.eps', dpi=300, format='eps')
plt.close()

# Plot summary data from PCA: explained variance (most important features)
pca = PCA()
pca.fit(featMatNorm)
featMatProjected = pca.transform(featMatNorm) # project data (zscores) onto PCs
important_feats, fig = pcainfo(pca=pca, zscores=featMatNorm, PC=1, n_feats2print=10)
plt.pause(5); plt.close()

# Store the results for first few PCs
projectedTable = pd.DataFrame(featMatProjected[:,:10],\
                              columns=['PC' + str(n+1) for n in range(10)])
projectedTable.set_index(featureTableStrains.index, inplace=True) # Do not lose index position
projectedTable = pd.concat([featureTableStrains[metadataTable.columns], projectedTable], axis=1)

# Plot data along first two principal components
title = """2-Component PCA (Top256 features)"""

plt.rc('xtick',labelsize=15)
plt.rc('ytick',labelsize=15)
sns.set_style("whitegrid")
fig, ax = plt.subplots(figsize=[10,10])

# Colour PCA by strain
for strain in strainsToCompare:
    strainProjected = projectedTable[projectedTable['food_type']==strain]
    sns.scatterplot(strainProjected['PC1'], strainProjected['PC2'], color=colour_dictionary[strain], s=50)
ax.set_xlabel('Principal Component 1', fontsize=20, labelpad=12)
ax.set_ylabel('Principal Component 2', fontsize=20, labelpad=12)
ax.set_title(title, fontsize=20)
plt.tight_layout(rect=[0.04, 0, 0.84, 0.96])
ax.legend(strainsToCompare, frameon=False, loc=(1, 0.1), fontsize=15)
ax.grid()

# Save 2-component PCA
plt.savefig('/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/2-Component_PCA', dpi=300, format='eps')
plt.show(); plt.pause(5)


#%% Remove outliers: Use Mahalanobis distance to exclude outliers from PCA
indsOutliers = MahalanobisOutliers(featMatProjected)
plt.pause(5); plt.close()

# Drop outlier observation(s) and re-normalise data
print("Dropping %d outliers from analysis" % len(indsOutliers))
indsOutliers = featMat.index[indsOutliers]
featMat = featMat.drop(index=indsOutliers)
featureTableStrains = featureTableStrains.drop(index=indsOutliers)

featMatNorm = featMat.apply(zscore, axis=0)

# Project data on PCA axes again
pca = PCA()
pca.fit(featMatNorm)
featMatProjected = pca.transform(featMatNorm) # project data (zscores) onto PCs
important_feats, fig = pcainfo(pca=pca, zscores=featMatNorm, PC=1, n_feats2print=10)
plt.pause(5); plt.close()

# Store the results for first few PCs
projectedTable = pd.DataFrame(featMatProjected[:,:10],\
                              columns=['PC' + str(n+1) for n in range(10)])
projectedTable.set_index(featureTableStrains.index, inplace=True) # Do not lose index position
projectedTable = pd.concat([featureTableStrains[metadataTable.columns], projectedTable], axis=1)

# Plot data along first two principal components
title = """2-Component PCA (Top256 features)
        (No outliers)"""

plt.rc('xtick',labelsize=15)
plt.rc('ytick',labelsize=15)
sns.set_style("whitegrid")
fig, ax = plt.subplots(figsize=[10,10])

# Colour PCA by strain
for strain in strainsToCompare:
    strainProjected = projectedTable[projectedTable['food_type']==strain]
    sns.scatterplot(strainProjected['PC1'], strainProjected['PC2'], color=colour_dictionary[strain], s=50)
ax.set_xlabel('Principal Component 1', fontsize=20, labelpad=12)
ax.set_ylabel('Principal Component 2', fontsize=20, labelpad=12)
ax.set_title(title, fontsize=20)
plt.tight_layout(rect=[0.04, 0, 0.84, 0.96])
ax.legend(strainsToCompare, frameon=False, loc=(1, 0.1), fontsize=15)
ax.grid()

# Save 2-component PCA
plt.savefig('/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003/2-Component_PCA_No_Outliers', dpi=300, format='eps')
plt.show(); plt.pause(5)


#%% Find significantly different features

if testType == 't-test':
    statTest = ttest_ind
elif testType == 'ranksum':
    statTest = ranksumtest
    
# Compare each of the test strains to N2 for each feature
# Pre-allocate dataframes for storing test statistics and p-values
testStrains = [strain for strain in strainsToCompare if strain != 'OP50']
testStats = pd.DataFrame(index=testStrains, columns=featNames)
testPvals = pd.DataFrame(index=testStrains, columns=featNames)
sigFeats = pd.DataFrame(index=testPvals.index, columns=['N_sigdiff_beforeBF','N_sigdiff_afterBF'])

# Compare each strain to OP50: compute test statistics for each feature
for t, strain in enumerate(strainsToCompare):
    if strain == controlStrain:
        continue
    print("Computing %s tests for %s vs %s..." % (testType, controlStrain, strain))
        
    # Grab feature summary results for that food
    testData = featureTableStrains[featureTableStrains['food_type'] == strain]
    
    # Drop non-data columns
    testData = testData.drop(columns=metadataTable.columns)
    controlData = featureTableStrains[featureTableStrains['food_type']==controlStrain].drop(columns=metadataTable.columns)
               
    # Perform tests to compare between foods for each feature
    test_stats, test_pvalues = statTest(testData, controlData)

    # Add test results to out-dataframe
    testStats.loc[strain] = test_stats
    testPvals.loc[strain] = test_pvalues
    
    # Record the names and number of significant features 
    sigFeatsList = testPvals.columns[np.where(test_pvalues < pvalThresh)]
    sigFeats.loc[strain,'N_sigdiff_beforeBF'] = len(sigFeatsList)
            
# Bonferroni correction for multiple comparisons
sigFeatsList = []
testPvalsBF = pd.DataFrame(index=testPvals.index, columns=testPvals.columns)
for strain in testPvals.index:
    # Locate pvalue results (row) for strain
    pvals = testPvals.loc[strain]
    
    # Perform Benjamini/Hochberg correction for multiple comparisons on test p-values
    _corrArray = smm.multipletests(pvals.values, alpha=pvalThresh, method='fdr_bh',\
                                   is_sorted=False, returnsorted=False)
    
    # Get pvalues for features that passed the Benjamini/Hochberg (non-negative) correlation test
    pvalsCorrected = _corrArray[1][_corrArray[0]]
    
    # Add pvalues to dataframe of corrected test pvalues
    testPvalsBF.loc[strain, _corrArray[0]] = pvalsCorrected
    
    # Record the names and number of significant features (after Bonferroni correction)
    sigdiff_feats = pd.Series(testPvalsBF.columns[np.where(_corrArray[1] < pvalThresh)])
    sigdiff_feats.name = strain
    sigFeatsList.append(sigdiff_feats)
    sigFeats.loc[strain,'N_sigdiff_afterBF'] = len(sigdiff_feats)

# Concatenate table of features for each strain that differ significantly from behaviour on OP50
sigFeatsStrain = pd.concat(sigFeatsList, axis=1, ignore_index=True, sort=False)
sigFeatsStrain.columns = testPvalsBF.index


#%% Export boxplots showing all significant differences
# - Rank features by p-value significance (lowest first)
# - Plot boxplots of all significant features for each strain vs control

for i, strain in enumerate(testPvalsBF.index):
    pvals = testPvalsBF.loc[strain]
    n_sigfeats = sum(pvals < pvalThresh)
    n_nonnanfeats = np.logical_not(pvals.isna()).sum()
    if pvals.isna().all():
        print("No signficant features found for %s" % strain)
    elif n_sigfeats > 0:       
        # Rank p-values in ascending order
        ranked_pvals = pvals.sort_values(ascending=True)
        # Drop NaNs
        ranked_pvals = ranked_pvals.dropna(axis=0)
        #topfeats = ranked_pvals[:n_top_features] # Optional: select n top ranked p-values
        
        # Drop non-significant features
        topfeats = ranked_pvals[ranked_pvals < pvalThresh]   
        #topfeats = pd.Series(index=['curvature_midbody_abs_90th']) # Optional: cherry-pick features
        
        # Subset for control + test strain feature summary results
        plot_df = featureTableStrains[np.logical_or(featureTableStrains['food_type']==controlStrain,\
                                                    featureTableStrains['food_type']==strain)] 
    
        # Colour dictionary subset for strains of interest
        labels = list(plot_df['food_type'].unique())
        colour_dict = {k: colour_dictionary[k] for k in (controlStrain, strain)}
        
        # Boxplots of control vs test strain for each significant feature
        for f, feature in enumerate(topfeats.index):
            plt.close()
            sns.set_style('darkgrid')
            fig = plt.figure(figsize=[10,8])
            ax = fig.add_subplot(1,1,1)
            sns.boxplot(x="food_type", y=feature, data=plot_df, palette=colour_dict,\
                        showfliers=False, showmeans=True,\
                        meanprops={"marker":"x", "markersize":5, "markeredgecolor":"k"},\
                        flierprops={"marker":"x", "markersize":15, "markeredgecolor":"r"})
            sns.swarmplot(x="food_type", y=feature, data=plot_df, s=10, marker=".", color='k')
            ax.set_xlabel('Bacterial Strain (Food)', fontsize=15, labelpad=12)
            ax.set_ylabel(feature, fontsize=15, labelpad=12)
            ax.set_title(feature, fontsize=20, pad=40)

            # Add plot legend
            patches = []
            for l, key in enumerate(colour_dict.keys()):
                patch = mpatches.Patch(color=colour_dict[key], label=key)
                patches.append(patch)
                if key == strain:
                    ylim = plot_df[plot_df['food_type']==key][feature].max()
                    pval = testPvalsBF.loc[key, feature]
                    if isinstance(pval, float) and pval < pvalThresh:
                        trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
                        pval2plt = testPvals.loc[key, feature]
                        ax.text(l - 0.1, 1, 'p={:g}'.format(float('{:.2g}'.format(pval2plt))),\
                        fontsize=13, color='k', verticalalignment='bottom', transform=trans)
            plt.tight_layout(rect=[0.04, 0, 0.8, 0.96])
            plt.legend(handles=patches, labels=colour_dict.keys(), loc=(1.02, 0.8),\
                      borderaxespad=0.4, frameon=False, fontsize=15)

            # Save box plot
            plots_outpath = os.path.join('/Volumes/behavgenom$/Saul/MicrobiomeAssay96WP/Results/20191003',\
                                         strain, '{0}_'.format(f + 1) + feature + '.eps')
            directory = os.path.dirname(plots_outpath)
            if not os.path.exists(directory):
                os.makedirs(directory)
            print("[%d] Saving figure: %s" % (i, os.path.basename(plots_outpath)))
            plt.savefig(plots_outpath, dpi=300, format='eps')

