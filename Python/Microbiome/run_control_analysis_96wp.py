#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OP50 Control across imaging days

Analyse control data: look for variation across experiment days (Kruskal-Wallis) 
and plot: (a) boxplots of the most important features that vary across days, (b)

@author: sm5911
@date: 23/10/2019

"""

#%% IMPORTS

# General imports
import os, sys, itertools, time#, umap
import pandas as pd
import seaborn as sns; sns.set(color_codes=True)
from matplotlib import pyplot as plt
from scipy.stats import zscore, kruskal#, f_oneway
from statsmodels.stats import multitest as smm#, AnovaRM
from statsmodels.stats.multicomp import MultiComparison, pairwise_tukeyhsd
from statsmodels.multivariate.manova import MANOVA
from sklearn.decomposition import PCA
from matplotlib.axes._axes import _log as mpl_axes_logger # Work-around for Axes3D plot colour warnings
from mpl_toolkits.mplot3d import Axes3D

# Path to GitHub functions
sys.path.insert(0, '/Users/sm5911/Documents/GitHub/PhD_Project/Python')

# Custom imports
from SM_plot import pcainfo
from SM_save import savefig

# TODO: Colour PCA plots: refeeding time to track (morn vs afternoon), and bleaching variation, temp + humidity

#%% MAIN
def control_variation(path_to_control_data, feature_colnames):
    """ A function written to analyse control data variation over time across
        different experiment days. """

#%%    
    DIRPATH = os.path.dirname(path_to_control_data)
                        
    # Statistics parameters
    test = kruskal # f_oneway
    TukeyHSD = False
    p_value_threshold = 0.05 # P-vlaue threshold for statistical analyses
    
    # Dimensionality reduction parameters
    useTop256 = True                # Restrict dimensionality reduction inputs to Avelino's top 256 feature list?
    n_top_feats_per_food = 10       # HCA - Number of top features to include in HCA (for union across foods HCA)
    PCs_to_keep = 10                # PCA - Number of principal components to record
    depthshade = False              # PCA - Shade colours on 3-D plots to show depth?
#    perplexity = [10,15,20,25,30]   # tSNE - Parameter range for t-SNE mapping
#    n_neighbours = [10,15,20,25,30] # UMAP - Number of neighbours parameter for UMAP projections
#    min_dist = 0.3                  # UMAP - Minimum distance parameter for UMAP projections
  
    #%% READ + FILTER + CLEAN SUMMARY RESULTS
    
    OP50_control_df = pd.read_csv(path_to_control_data, index_col=0)

    # Record non-data columns before dropping features for statistics    
    meta_colnames = [col for col in OP50_control_df.columns if col not in feature_colnames]
        
    # Drop columns that contain only zeros
    n_cols = len(OP50_control_df.columns)
    OP50_control_df = OP50_control_df.drop(columns=OP50_control_df.columns[(OP50_control_df == 0).all()])
    zero_cols = n_cols - len(OP50_control_df.columns)
    if zero_cols > 0:
        print("Dropped %d feature summaries for OP50 control (all zeros)" % zero_cols)
    
    # Record a list of feature column names
    feature_colnames = [col for col in OP50_control_df.columns if col not in meta_colnames]
    
    
    #%% OP50 CONTROL DATA ACROSS DAYS: STATS (ANOVAs)
    # - Does N2 worm behaviour on OP50 control vary across experiment days?
    # - Perform ANOVA to see if features vary across imaging days for OP50 control
    # - Perform Tukey HSD post-hoc analyses for pairwise differences between imaging days
    # - Highlight outlier imaging days and investigate reasons why
    # - Save list of top significant features for outlier days - are they size-related features?
    #   (worms are larger? pre-fed earlier? camera focus/FOV adjusted? skewed by non-worm tracked objects?
    #   Did not record time when worms were refed! Could be this. If so, worms will be bigger across all foods on that day) 
    
    # Plot OP50 control top10 size-skewed features for each food - do they all differ for outlier date? If so, worms are likely just bigger.
    # PCA: For just OP50 control - colour by imaging date - do they cluster visibly? If so, we have time-dependence = NOT GREAT 
    # => Consider excluding that date on the basis of un-standardised development times since refeeding?
    
    # One-way ANOVA with Bonferroni correction for repeated measures
    print("Performing `Kruskal-Wallis (non-para One-Way ANOVAs, for each feature)")
    print("to investigate whether control OP50 results vary across imaging dates:")
    OP50_over_time_results_df = pd.DataFrame(index=['stat','pval'], columns=feature_colnames)
    for feature in feature_colnames:
        test_stat, test_pvalue = test(*[OP50_control_df[OP50_control_df['date_recording_yyyymmdd']==date][feature]\
                                            for date in OP50_control_df['date_recording_yyyymmdd'].unique()])
        OP50_over_time_results_df.loc['stat',feature] = test_stat
        OP50_over_time_results_df.loc['pval',feature] = test_pvalue
    
    # Bonferroni correction for multiple comparisons
    _corrArray = smm.multipletests(OP50_over_time_results_df.loc['pval'], alpha=p_value_threshold,\
                                   method='fdr_bh', is_sorted=False, returnsorted=False)
    
    # Get pvalues for features that passed the Benjamini/Hochberg (non-negative) correlation test
    pvalues_corrected = _corrArray[1][_corrArray[0]]
    
    # Add pvalues to 1-way ANOVA results dataframe
    OP50_over_time_results_df = OP50_over_time_results_df.append(pd.Series(name='pval_corrected'))
    OP50_over_time_results_df.loc['pval_corrected', _corrArray[0]] = pvalues_corrected
    
    n_sigfeats = sum(OP50_over_time_results_df.loc['pval_corrected'] < p_value_threshold)
    
    print("%d / %d (%.1f%%) of features show significant variation across imaging dates for OP50 control (ANOVA/Kruskal)" % \
          (n_sigfeats, len(OP50_over_time_results_df.columns), n_sigfeats/len(OP50_over_time_results_df.columns)*100))
    
    # Record name of statistical test used (kruskal/f_oneway)
    test_name = str(test).split(' ')[1].split('.')[-1].split('(')[0].split('\'')[0]
    
    # Save test statistics to file
    stats_outpath = os.path.join(DIRPATH, 'OP50_control_across_days_' + test_name + '_stats.csv')
    OP50_over_time_results_df.to_csv(stats_outpath)
    
    # Compile list to store names of significant features
    sigfeats_out = OP50_over_time_results_df.loc['pval_corrected'].sort_values(ascending=True) # Rank pvalues by significance
    sigfeats_out = sigfeats_out[sigfeats_out < p_value_threshold]
    sigfeats_out.name = 'p_value_' + test_name
    
    # Save significant features list to CSV
    sigfeats_outpath = os.path.join(DIRPATH, 'OP50_control_across_days_' + test_name + '_sigfeats.csv')
    sigfeats_out.to_csv(sigfeats_outpath, header=False)
    
    if TukeyHSD:
        # Tally total number of significantly different pairwise comparisons
        n_sigdiff_pairwise_beforeBF = 0
        n_sigdiff_pairwise_afterBF = 0
        
        # Tukey HSD post-hoc pairwise differences between dates for each feature
        for feature in feature_colnames:
            # Tukey HSD post-hoc analysis (no Bonferroni correction!)
            tukeyHSD = pairwise_tukeyhsd(OP50_control_df[feature], OP50_control_df['date_recording_yyyymmdd'])
            n_sigdiff_pairwise_beforeBF += sum(tukeyHSD.reject)
            
            # Tukey HSD post-hoc analysis (Bonferroni correction)
            tukeyHSD_BF = MultiComparison(OP50_control_df[feature], OP50_control_df['date_recording_yyyymmdd'])
            n_sigdiff_pairwise_afterBF += sum(tukeyHSD_BF.tukeyhsd().reject)   
            
        total_comparisons = len(feature_colnames) * 6
        reject_H0_percentage = n_sigdiff_pairwise_afterBF / total_comparisons * 100
        
        print("""%d / %d (%.1f%%) of pairwise-comparisons of imaging dates (%d features) 
        show significant variation for OP50 control (TukeyHSD)""" %\
        (n_sigdiff_pairwise_afterBF, total_comparisons, reject_H0_percentage, len(feature_colnames)))
        
        # TODO: Reverse-engineer p-values using mean/std?
        #from statsmodels.stats.libqsturng import psturng
        ##studentized range statistic
        #rs = res2[1][2] / res2[1][3]
        #pvalues = psturng(np.abs(rs), 3, 27)
        
    #%% MANOVA (date, temp, humid, etc)

#    maov = MANOVA.from_formula('' + '' + '' ~ , data=OP50_control_df)
#    print(maov.mv_test())
    
    #%% Boxplots for most important features across days
    
    plotroot = os.path.join(DIRPATH, "Plots")
    if not os.path.exists(plotroot):
        os.makedirs(plotroot)

    pvals_corrected = OP50_over_time_results_df.loc['pval_corrected']
    n_sigfeats = sum(pvals_corrected < p_value_threshold)
    
    if pvals_corrected.isna().all():
        print("No signficant features found across days for OP50 control!")
    elif n_sigfeats > 0:
        # Rank p-values in ascending order
        ranked_pvals = pvals_corrected.sort_values(ascending=True)
         
        # Drop NaNs
        ranked_pvals = ranked_pvals.dropna(axis=0)
        
        # Drop non-sig feats
        ranked_pvals = ranked_pvals[ranked_pvals < p_value_threshold]

        # Select the first n pvalues for plotting
        topfeats = ranked_pvals[:n_top_feats_per_food]
                
        if n_sigfeats < n_top_feats_per_food:
            print("WARNING: Only %d features found to vary significantly across days" % n_sigfeats)
            
        print("\nTop %d features for OP50 that differ significantly across days:\n" % len(topfeats))
        print(*[feat + '\n' for feat in list(topfeats.index)])
    
        # for f, feature in enumerate(feature_colnames[0:25]):
        for feature in topfeats.index:
            print("P-value for '%s': %s" % (feature, str(topfeats[feature])))
            OP50_feat_df = OP50_control_df[['date_recording_yyyymmdd', feature]]
            
            # Plot boxplots of OP50 control across days for most significant features
            plt.close('all')
            fig = plt.figure(figsize=[10,6])
            ax = fig.add_subplot(1,1,1)
            sns.boxplot(x='date_recording_yyyymmdd', y=feature, data=OP50_feat_df)
            ax.set_xlabel('Imaging Date (YYYYMMDD)', fontsize=15, labelpad=12)
            ax.set_title(feature, fontsize=20, pad=20)
            
            # TODO: Add reverse-engineered pvalues to plot?
            
            # Save plot
            plots_outpath = os.path.join(plotroot, feature + '_across_days.eps')
            savefig(plots_outpath, tellme=True, saveFormat='eps')            
    
    #%% PCA of OP50 CONTROL DATA ACROSS DAYS
    
    PCAplotroot = os.path.join(plotroot, 'PCA')
    if not os.path.exists(PCAplotroot):
        os.makedirs(PCAplotroot)
    
    # Read list of important features (highlighted by previous research - see Javer, 2018 paper)
    if useTop256:
        featroot = DIRPATH.split("/Results/")[0]
        featslistpath = os.path.join(featroot,'AuxiliaryFiles','top256_tierpsy_no_blob_no_eigen_only_abs_no_norm.csv')
        top256features = pd.read_csv(featslistpath)
        
        # Take first set of 256 features (it does not matter which set is chosen)
        top256features = top256features[top256features.columns[0]]   
        top256features = [feat for feat in top256features if feat in OP50_control_df.columns]
        print("PCA: Using existing results for %d/256 features in Top256 list (Javer 2018)" % len(top256features))
    
        # Drop all but top256 columns for PCA
        data = OP50_control_df[top256features]
    else:
        data = OP50_control_df[feature_colnames]
    
    # Normalise the data before PCA
    zscores = data.apply(zscore, axis=0)
    
    # Drop features with NaN values after normalising
    zscores.dropna(axis=1, inplace=True)
    
    # Perform PCA on extracted features
    print("\nPerforming Principal Components Analysis (PCA)...")
    
    # Fit the PCA model with the normalised data
    pca = PCA()
    pca.fit(zscores)
    
    # Plot summary data from PCA: explained variance (most important features)
    important_feats, fig = pcainfo(pca, zscores, PC=1, n_feats2print=10)
    
    # Save plot of PCA explained variance
    PCAplotpath = os.path.join(PCAplotroot, 'PCA_explained.eps')
    savefig(PCAplotpath, tight_layout=True, tellme=True, saveFormat='eps')
    
    # Project data (zscores) onto PCs
    projected = pca.transform(zscores) # A matrix is produced
    # NB: Could also have used pca.fit_transform()
    
    # Store the results for first few PCs in dataframe
    projected_df = pd.DataFrame(projected[:,:PCs_to_keep],\
                                columns=['PC' + str(n+1) for n in range(PCs_to_keep)])
    
    # Add concatenate projected PC results to metadata
    projected_df.set_index(OP50_control_df.index, inplace=True) # Do not lose video snippet index position
    OP50_dates_projected_df = pd.concat([OP50_control_df[meta_colnames], projected_df], axis=1)
    
    #%% 2D Plot - first 2 PCs - OP50 Control (coloured by imaging date)
    
    # Plot first 2 principal components
    plt.close('all'); plt.ion()
    plt.rc('xtick',labelsize=15)
    plt.rc('ytick',labelsize=15)
    sns.set_style("whitegrid")
    fig, ax = plt.subplots(figsize=[10,10])
    
    # Create colour palette for plot loop
    imaging_dates = list(OP50_dates_projected_df['date_recording_yyyymmdd'].unique())
    palette = itertools.cycle(sns.color_palette("gist_rainbow", len(imaging_dates)))
    
    for date in imaging_dates:
        date_projected_df = OP50_dates_projected_df[OP50_dates_projected_df['date_recording_yyyymmdd']==int(date)]
        sns.scatterplot(date_projected_df['PC1'], date_projected_df['PC2'], color=next(palette), s=100)
    ax.set_xlabel('Principal Component 1', fontsize=15, labelpad=12)
    ax.set_ylabel('Principal Component 2', fontsize=15, labelpad=12)
    if useTop256:
        ax.set_title('Top256 features 2-Component PCA', fontsize=20)
    else: 
        ax.set_title('All features 2-Component PCA', fontsize=20)
    plt.tight_layout(rect=[0.04, 0, 0.84, 0.96])
    ax.legend(imaging_dates, frameon=False, loc=(1, 0.65), fontsize=15)
    ax.grid()
    
    # Save scatterplot of first 2 PCs
    PCAplotpath = PCAplotpath.replace('PCA_explained', '2_component_PCA')
    savefig(PCAplotpath, tight_layout=True, tellme=True, saveFormat='eps')
    
    plt.show(); plt.pause(2)


    #%% Plot 3 PCs - OP50 across imaging dates
    rotate = True
    
    # Work-around for 3D plot colour warnings
    mpl_axes_logger.setLevel('ERROR')

    # Plot first 3 principal components
    plt.close('all')
    fig = plt.figure(figsize=[10,10])
    ax = Axes3D(fig, rect=[0.04, 0, 0.8, 0.96]) # ax = fig.add_subplot(111, projection='3d')
    
    # Re-initialise colour palette for plot loop
    palette = itertools.cycle(sns.color_palette("gist_rainbow", len(imaging_dates)))
    
    for date in imaging_dates:
        date_projected_df = OP50_dates_projected_df[OP50_dates_projected_df['date_recording_yyyymmdd']==int(date)]
        ax.scatter(xs=date_projected_df['PC1'], ys=date_projected_df['PC2'], zs=date_projected_df['PC3'],\
                   zdir='z', color=next(palette), s=50, depthshade=depthshade)
    ax.set_xlabel('Principal Component 1', fontsize=15, labelpad=12)
    ax.set_ylabel('Principal Component 2', fontsize=15, labelpad=12)
    ax.set_zlabel('Principal Component 3', fontsize=15, labelpad=12)
    if useTop256:
        ax.set_title('Top256 features 2-Component PCA', fontsize=20, pad=20)
    else: 
        ax.set_title('All features 2-Component PCA', fontsize=20, pad=20)
    ax.legend(imaging_dates, frameon=False, loc=(0.97, 0.65), fontsize=15)
    ax.grid()
    
    # Save scatterplot of first 3 PCs
    PCAplotpath = PCAplotpath.replace('PCA_explained', '3_component_PCA')
    savefig(PCAplotpath, tight_layout=False, tellme=True, saveFormat='eps')
    
    # Rotate the axes and update
    if rotate:
        for angle in range(0, 360):
            ax.view_init(30, angle)
            plt.draw(); plt.pause(0.001)
    else:
        plt.show()

#%% INPUT HANDLING AND GLOBAL PARAMETERS
        
# TODO: Optional: call script from terminal command line as well as use as function

if __name__ == '__main__':
    tic = time.time()
    if len(sys.argv) >= 2:
        print("\nRunning script", os.path.basename(sys.argv[0]), "...")
        path_to_control_data = sys.argv[1]
        feature_colnames = list(sys.argv[2:])
        
        # Analyse control variation over time
        control_variation(path_to_control_data, feature_colnames)   
    else:
        print("""Please provide path to control data, followed by an unpacked list 
        of feature column names as inputs.""")
        
    toc = time.time()
    print("OP50 control analysis complete.\n(Time taken: %d seconds)" % (toc-tic))
