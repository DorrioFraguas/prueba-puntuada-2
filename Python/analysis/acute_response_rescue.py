#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse Keio Follow-up Acute Effect Antioxidant Rescue experiment
- window feature summaries for Ziwei's optimal windows around each bluelight stimulus
- Bluelight delivered for 10 seconds every 5 minutes, for a total of 45 minutes

When do we start to see an effect on worm behaviour? At which timepoint/window? 
Do we still see arousal of worms on siderophore mutants, even after a short period of time?

@author: sm5911
@date: 20/01/2022

"""

#%% Imports

import argparse
import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path
from matplotlib import transforms
from matplotlib import pyplot as plt
from scipy.stats import zscore

from read_data.read import load_json
from read_data.paths import get_save_dir
from preprocessing.compile_hydra_data import process_metadata, process_feature_summaries
from filter_data.clean_feature_summaries import clean_summary_results
from statistical_testing.stats_helper import pairwise_ttest
from statistical_testing.perform_keio_stats import df_summary_stats
from visualisation.plotting_helper import sig_asterix

# from tierpsytools.preprocessing.filter_data import select_feat_set
from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes

#%% Globals

JSON_PARAMETERS_PATH = 'analysis/20220111_parameters_keio_acute_rescue.json'

FEATURE = 'motion_mode_paused_fraction'

scale_outliers_box = True

ALL_WINDOWS = False
WINDOW_LIST = [2,5,8,11,14,17,20,23] # if ALL_WINDOWS is False

# mapping dictionary - windows summary window number to corresponding timestamp (seconds)
WINDOW_FRAME_DICT = {0:(290,300), 1:(305,315), 2:(315,325), 
                     3:(590,600), 4:(605,615), 5:(615,625), 
                     6:(890,900), 7:(905,915), 8:(915,925), 
                     9:(1190,1200), 10:(1205,1215), 11:(1215,1225), 
                     12:(1490,1500), 13:(1505,1515), 14:(1515,1525), 
                     15:(1790,1800), 16:(1805,1815), 17:(1815,1825), 
                     18:(2090,2100), 19:(2105,2115), 20:(2115,2125), 
                     21:(2390,2400), 22:(2405,2415), 23:(2415,2425)}

#%% Functions

def acute_rescue_stats(features, 
                       metadata, 
                       save_dir, 
                       control_strain, 
                       control_antioxidant, 
                       control_window,
                       fdr_method='fdr_by',
                       pval_threshold=0.05):
    """ Pairwise t-tests for each window comparing worm 'motion mode paused fraction' on 
        Keio mutants vs BW control 
        
        # One could fit a multiple linear regression model: to account for strain*antioxidant in a 
        # single model: Y (motion_mode) = b0 + b1*X1 (strain) + b2*X2 (antiox) + e (error)
        # But this is a different type of question: we care about difference in means between 
        # fepD vs BW (albeit under different antioxidant treatments), and not about modelling their 
        # relationship, therefore individual t-tests (multiple-test-corrected) should suffice
        
        1. For each treatment condition, t-tests comparing fepD vs BW for motion_mode
        
        2. For fepD and BW separately, f-tests for equal variance among antioxidant treatment groups,
        then ANOVA tests for significant differences between antioxidants, then individual t-tests
        comparing each treatment to control
        
        Inputs
        ------
        features, metadata : pandas.DataFrame
        
        window_list : list
            List of windows (int) to perform statistics (separately for each window provided, 
            p-values are adjusted for multiple test correction)
        
        save_dir : str
            Directory to save statistics results
            
        control_strain
        control_antioxidant
        fdr_method
        
    """

    stats_dir =  Path(save_dir) / "Stats" / args.fdr_method
    stats_dir.mkdir(parents=True, exist_ok=True)

    strain_list = [control_strain] + [s for s in set(metadata['gene_name'].unique()) if s != control_strain]  
    antiox_list = [control_antioxidant] + [a for a in set(metadata['antioxidant'].unique()) if 
                                           a != control_antioxidant]
    window_list = [control_window] + [w for w in set(metadata['window'].unique()) if w != control_window]

    # categorical variables to investigate: 'gene_name', 'antioxidant' and 'window'
    print("\nInvestigating difference in fraction of worms paused between hit strain and control " +
          "(for each window), in the presence/absence of antioxidants:\n")    

    # print mean sample size
    sample_size = df_summary_stats(metadata, columns=['gene_name', 'antioxidant', 'window'])
    print("Mean sample size of strain/antioxidant for each window: %d" %\
          (int(sample_size['n_samples'].mean())))
      
    # For each strain separately...
    for strain in strain_list:
        strain_meta = metadata[metadata['gene_name']==strain]
        strain_feat = features.reindex(strain_meta.index)

        # 1. Is there any variation in fraction paused wtr antioxidant treatment?
        #    - ANOVA on pooled window data, then pairwise t-tests for each antioxidant
        
        print("Performing ANOVA on pooled window data for significant variation in fraction " +
              "of worms paused among different antioxidant treatments for %s..." % strain)
        
        # perform ANOVA (correct for multiple comparisons)             
        stats, pvals, reject = univariate_tests(X=strain_feat[[FEATURE]], 
                                                y=strain_meta['antioxidant'], 
                                                test='ANOVA',
                                                control=control_antioxidant,
                                                comparison_type='multiclass',
                                                multitest_correction=fdr_method,
                                                alpha=pval_threshold,
                                                n_permutation_test=None) # 'all'
    
        # get effect sizes
        effect_sizes = get_effect_sizes(X=strain_feat[[FEATURE]], 
                                        y=strain_meta['antioxidant'],
                                        control=control_antioxidant,
                                        effect_type=None,
                                        linked_test='ANOVA')
    
        # compile
        test_results = pd.concat([stats, effect_sizes, pvals, reject], axis=1)
        test_results.columns = ['stats','effect_size','pvals','reject']     
        test_results['significance'] = sig_asterix(test_results['pvals'])
        test_results = test_results.sort_values(by=['pvals'], ascending=True) # rank pvals
        
        # save results
        anova_path = Path(stats_dir) / 'ANOVA_{}_variation_across_antioxidants.csv'.format(strain)
        test_results.to_csv(anova_path, header=True, index=True)
              
        print("Performing t-tests comparing each antioxidant treatment to None (pooled window data)")
        
        stats_t, pvals_t, reject_t = univariate_tests(X=strain_feat[[FEATURE]],
                                                      y=strain_meta['antioxidant'],
                                                      test='t-test',
                                                      control=control_antioxidant,
                                                      comparison_type='binary_each_group',
                                                      multitest_correction=fdr_method,
                                                      alpha=pval_threshold)
        effect_sizes_t =  get_effect_sizes(X=strain_feat[[FEATURE]], 
                                           y=strain_meta['antioxidant'], 
                                           control=control_antioxidant,
                                           effect_type=None,
                                           linked_test='t-test')
            
        # compile + save t-test results
        stats_t.columns = ['stats_' + str(c) for c in stats_t.columns]
        pvals_t.columns = ['pvals_' + str(c) for c in pvals_t.columns]
        reject_t.columns = ['reject_' + str(c) for c in reject_t.columns]
        effect_sizes_t.columns = ['effect_size_' + str(c) for c in effect_sizes_t.columns]
        ttest_results = pd.concat([stats_t, effect_sizes_t, pvals_t, reject_t], axis=1)
        ttest_save_path = stats_dir / 't-test_{}_antioxidant_results.csv'.format(strain)
        ttest_save_path.parent.mkdir(exist_ok=True, parents=True)
        ttest_results.to_csv(ttest_save_path, header=True, index=True)
    
        # 2. Is there any variation in fraction paused wrt window (time) across the videos?
        #    - ANOVA on pooled antioxidant data, then pairwise for each window
        
        print("Performing ANOVA on pooled antioxidant data for significant variation in fraction " +
              "of worms paused across (bluelight) window summaries for %s..." % strain)
        
        # perform ANOVA (correct for multiple comparisons)
        stats, pvals, reject = univariate_tests(X=strain_feat[[FEATURE]],
                                                y=strain_meta['window'],
                                                test='ANOVA',
                                                control=control_window,
                                                comparison_type='multiclass',
                                                multitest_correction=fdr_method,
                                                alpha=pval_threshold,
                                                n_permutation_test=None)
        
        # get effect sizes
        effect_sizes = get_effect_sizes(X=strain_feat[[FEATURE]],
                                        y=strain_meta['window'],
                                        control=control_window,
                                        effect_type=None,
                                        linked_test='ANOVA')

        # compile
        test_results = pd.concat([stats, effect_sizes, pvals, reject], axis=1)
        test_results.columns = ['stats','effect_size','pvals','reject']     
        test_results['significance'] = sig_asterix(test_results['pvals'])
        test_results = test_results.sort_values(by=['pvals'], ascending=True) # rank pvals
        
        # save results
        anova_path = Path(stats_dir) / 'ANOVA_{}_variation_across_windows.csv'.format(strain)
        test_results.to_csv(anova_path, header=True, index=True)

        print("Performing t-tests comparing each window with the first (pooled antioxidant data)")
        
        stats_t, pvals_t, reject_t = univariate_tests(X=strain_feat[[FEATURE]],
                                                      y=strain_meta['window'],
                                                      test='t-test',
                                                      control=control_window,
                                                      comparison_type='binary_each_group',
                                                      multitest_correction=fdr_method,
                                                      alpha=pval_threshold)
        effect_sizes_t =  get_effect_sizes(X=strain_feat[[FEATURE]], 
                                           y=strain_meta['window'], 
                                           control=control_window,
                                           effect_type=None,
                                           linked_test='t-test')
            
        # compile + save t-test results
        stats_t.columns = ['stats_' + str(c) for c in stats_t.columns]
        pvals_t.columns = ['pvals_' + str(c) for c in pvals_t.columns]
        reject_t.columns = ['reject_' + str(c) for c in reject_t.columns]
        effect_sizes_t.columns = ['effect_size_' + str(c) for c in effect_sizes_t.columns]
        ttest_results = pd.concat([stats_t, effect_sizes_t, pvals_t, reject_t], axis=1)
        ttest_save_path = stats_dir / 't-test_{}_window_results.csv'.format(strain)
        ttest_save_path.parent.mkdir(exist_ok=True, parents=True)
        ttest_results.to_csv(ttest_save_path, header=True, index=True)   
         
    # Pairwise t-tests - is there a difference between strain vs control?

    control_meta = metadata[metadata['gene_name']==control_strain]
    control_feat = features.reindex(control_meta.index)
    control_df = control_meta.join(control_feat[[FEATURE]])

    for strain in strain_list[1:]: # skip control_strain at first index postion         
        strain_meta = metadata[metadata['gene_name']==strain]
        strain_feat = features.reindex(strain_meta.index)
        strain_df = strain_meta.join(strain_feat[[FEATURE]])

        # 3. Is there a difference between strain vs control at any window?
        
        print("\nPairwise t-tests for each window (pooled antioxidants) comparing fraction of " + 
              "worms paused on %s vs control:" % strain)

        stats, pvals, reject = pairwise_ttest(control_df, 
                                              strain_df, 
                                              feature_list=[FEATURE], 
                                              group_by='window', 
                                              fdr_method=fdr_method,
                                              fdr=0.05)
 
        # compile table of results
        stats.columns = ['stats_' + str(c) for c in stats.columns]
        pvals.columns = ['pvals_' + str(c) for c in pvals.columns]
        reject.columns = ['reject_' + str(c) for c in reject.columns]
        test_results = pd.concat([stats, pvals, reject], axis=1)
        
        # save results
        ttest_strain_path = stats_dir / 'pairwise_ttests' / 'window' /\
                            '{}_window_results.csv'.format(strain)
        ttest_strain_path.parent.mkdir(parents=True, exist_ok=True)
        test_results.to_csv(ttest_strain_path, header=True, index=True)
                             
        # for each antioxidant treatment condition...
        for antiox in antiox_list:
            print("Pairwise t-tests for each window comparing fraction of " + 
                  "worms paused on %s vs control with '%s'" % (strain, antiox))

            antiox_control_df = control_df[control_df['antioxidant']==antiox]
            antiox_strain_df = strain_df[strain_df['antioxidant']==antiox]
            
            stats, pvals, reject = pairwise_ttest(antiox_control_df,
                                                  antiox_strain_df,
                                                  feature_list=[FEATURE],
                                                  group_by='window',
                                                  fdr_method=fdr_method,
                                                  fdr=0.05)
        
            # compile table of results
            stats.columns = ['stats_' + str(c) for c in stats.columns]
            pvals.columns = ['pvals_' + str(c) for c in pvals.columns]
            reject.columns = ['reject_' + str(c) for c in reject.columns]
            test_results = pd.concat([stats, pvals, reject], axis=1)
            
            # save results
            ttest_strain_path = stats_dir / 'pairwise_ttests' / 'window' /\
                                '{0}_{1}_window_results.csv'.format(strain, antiox)
            ttest_strain_path.parent.mkdir(parents=True, exist_ok=True)
            test_results.to_csv(ttest_strain_path, header=True, index=True)

        # 4. Is there a difference between strain vs control for any antioxidant?

        print("\nPairwise t-tests for each antioxidant (pooled windows) comparing fraction of " + 
              "worms paused on %s vs control:" % strain)

        stats, pvals, reject = pairwise_ttest(control_df, 
                                              strain_df, 
                                              feature_list=[FEATURE], 
                                              group_by='antioxidant', 
                                              fdr_method=fdr_method,
                                              fdr=0.05)
 
        # compile table of results
        stats.columns = ['stats_' + str(c) for c in stats.columns]
        pvals.columns = ['pvals_' + str(c) for c in pvals.columns]
        reject.columns = ['reject_' + str(c) for c in reject.columns]
        test_results = pd.concat([stats, pvals, reject], axis=1)
        
        # save results
        ttest_strain_path = stats_dir / 'pairwise_ttests' / 'antioxidant' /\
                            '{}_antioxidant_results.csv'.format(strain)
        ttest_strain_path.parent.mkdir(parents=True, exist_ok=True)
        test_results.to_csv(ttest_strain_path, header=True, index=True)
                             
        # For each window...
        for window in window_list:
            print("Pairwise t-tests for each antioxidant comparing fraction of " + 
                  "worms paused on %s vs control at window %d" % (strain, window))

            window_control_df = control_df[control_df['window']==window]
            window_strain_df = strain_df[strain_df['window']==window]
            
            stats, pvals, reject = pairwise_ttest(window_control_df,
                                                  window_strain_df,
                                                  feature_list=[FEATURE],
                                                  group_by='antioxidant',
                                                  fdr_method=fdr_method,
                                                  fdr=0.05)
        
            # compile table of results
            stats.columns = ['stats_' + str(c) for c in stats.columns]
            pvals.columns = ['pvals_' + str(c) for c in pvals.columns]
            reject.columns = ['reject_' + str(c) for c in reject.columns]
            test_results = pd.concat([stats, pvals, reject], axis=1)
            
            # save results
            ttest_strain_path = stats_dir / 'pairwise_ttests' / 'antioxidant' /\
                                '{0}_window{1}_antioxidant_results.csv'.format(strain, window)
            ttest_strain_path.parent.mkdir(parents=True, exist_ok=True)
            test_results.to_csv(ttest_strain_path, header=True, index=True)
               
    return

def analyse_acute_rescue(features, 
                         metadata,
                         save_dir,
                         control_strain, 
                         control_antioxidant, 
                         control_window,
                         fdr_method='fdr_by',
                         pval_threshold=0.05):
 
    stats_dir =  Path(save_dir) / "Stats" / fdr_method
    plot_dir = Path(save_dir) / "Plots" / fdr_method

    strain_list = [control_strain] + [s for s in metadata['gene_name'].unique() if s != control_strain]  
    antiox_list = [control_antioxidant] + [a for a in metadata['antioxidant'].unique() if 
                                           a != control_antioxidant]
    window_list = [control_window] + [w for w in metadata['window'].unique() if w != control_window]

    # categorical variables to investigate: 'gene_name', 'antioxidant' and 'window'
    print("\nInvestigating difference in fraction of worms paused between hit strain and control " +
          "(for each window), in the presence/absence of antioxidants:\n")    

    # print mean sample size
    sample_size = df_summary_stats(metadata, columns=['gene_name', 'antioxidant', 'window'])
    print("Mean sample size of strain/antioxidant for each window: %d" %\
          (int(sample_size['n_samples'].mean())))
            
    # plot dates as different colours (in loop)
    date_lut = dict(zip(list(metadata['date_yyyymmdd'].unique()), 
                        sns.color_palette('Set1', n_colors=len(metadata['date_yyyymmdd'].unique()))))
        
    for strain in strain_list[1:]: # skip control_strain at first index postion        
        plot_meta = metadata[np.logical_or(metadata['gene_name']==strain, 
                                           metadata['gene_name']==control_strain)]
        plot_feat = features.reindex(plot_meta.index)
        plot_df = plot_meta.join(plot_feat[[FEATURE]])
        
        # Is there a difference between strain vs control at any window? (pooled antioxidant data)
        print("Plotting windows for %s vs control" % strain)
        plt.close('all')
        fig, ax = plt.subplots(figsize=((len(window_list) if len(window_list) >= 20 else 12),8))
        ax = sns.boxplot(x='window', y=FEATURE, hue='gene_name', hue_order=strain_list, order=window_list,
                         data=plot_df, palette='Set3', dodge=True, ax=ax)
        for date in date_lut.keys():
            date_df = plot_df[plot_df['date_yyyymmdd']==date]   
            ax = sns.stripplot(x='window', y=FEATURE, hue='gene_name', order=window_list,
                               hue_order=strain_list, data=date_df, 
                               palette={control_strain:date_lut[date], strain:date_lut[date]}, 
                               alpha=0.7, size=4, dodge=True, ax=ax)
        n_labs = len(plot_df['gene_name'].unique())
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles[:n_labs], labels[:n_labs], fontsize=15, frameon=False, loc='upper right')
                
        # scale plot to omit outliers (>2.5*IQR from mean)
        if scale_outliers_box:
            grouped_strain = plot_df.groupby('window')
            y_bar = grouped_strain[FEATURE].median() # median is less skewed by outliers
            # Computing IQR
            Q1 = grouped_strain[FEATURE].quantile(0.25)
            Q3 = grouped_strain[FEATURE].quantile(0.75)
            IQR = Q3 - Q1
            plt.ylim(-0.02, max(y_bar) + 3 * max(IQR))
            
        # load t-test results + annotate p-values on plot
        for ii, window in enumerate(window_list):
            ttest_strain_path = stats_dir / 'pairwise_ttests' / 'window' /\
                                '{}_window_results.csv'.format(strain)
            ttest_strain_table = pd.read_csv(ttest_strain_path, index_col=0, header=0)
            strain_pvals_t = ttest_strain_table[[c for c in ttest_strain_table if "pvals_" in c]] 
            strain_pvals_t.columns = [c.split('pvals_')[-1] for c in strain_pvals_t.columns] 
            p = strain_pvals_t.loc[FEATURE, str(window)]
            text = ax.get_xticklabels()[ii]
            assert text.get_text() == str(window)
            p_text = 'P<0.001' if p < 0.001 else 'P=%.3f' % p
            #y = (y_bar[antiox] + 2 * IQR[antiox]) if scale_outliers_box else plot_df[feature].max()
            #h = (max(IQR) / 10) if scale_outliers_box else (y - plot_df[feature].min()) / 50
            trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
            plt.plot([ii-.3, ii-.3, ii+.3, ii+.3], 
                     [0.98, 0.99, 0.99, 0.98], #[y+h, y+2*h, y+2*h, y+h], 
                     lw=1.5, c='k', transform=trans)
            ax.text(ii, 1.01, p_text, fontsize=9, ha='center', va='bottom', transform=trans,
                    rotation=(0 if len(window_list) <= 20 else 90))
            
        ax.set_xticks(range(len(window_list)+1))
        xlabels = [str(int(WINDOW_FRAME_DICT[w][0]/60)) for w in window_list]
        ax.set_xticklabels(xlabels)
        x_text = 'Time (minutes)' if ALL_WINDOWS else 'Time of bluelight 10-second burst (minutes)'
        ax.set_xlabel(x_text, fontsize=15, labelpad=10)
        ax.set_ylabel(FEATURE.replace('_',' '), fontsize=15, labelpad=10)
        
        fig_savepath = plot_dir / 'window_boxplots' / strain / (FEATURE + '.png')
        fig_savepath.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fig_savepath)
    
    
        # Is there a difference between strain vs control for any antioxidant? (pooled window data)
        plt.close('all')
        fig, ax = plt.subplots(figsize=(10,8))
        ax = sns.boxplot(x='antioxidant', y=FEATURE, hue='gene_name', hue_order=strain_list, data=plot_df,
                          palette='Set3', dodge=True, order=antiox_list)
        ax = sns.swarmplot(x='antioxidant', y=FEATURE, hue='gene_name', hue_order=strain_list, data=plot_df,
                          color='k', alpha=0.7, size=4, dodge=True, order=antiox_list)
        n_labs = len(plot_df['gene_name'].unique())
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles[:n_labs], labels[:n_labs], fontsize=15, frameon=False, loc='upper right')
        ax.set_xlabel('antioxidant', fontsize=15, labelpad=10)
        ax.set_ylabel(FEATURE.replace('_',' '), fontsize=15, labelpad=10)
        
        # scale plot to omit outliers (>2.5*IQR from mean)
        if scale_outliers_box:
            grouped_strain = plot_df.groupby('antioxidant')
            y_bar = grouped_strain[FEATURE].median() # median is less skewed by outliers
            # Computing IQR
            Q1 = grouped_strain[FEATURE].quantile(0.25)
            Q3 = grouped_strain[FEATURE].quantile(0.75)
            IQR = Q3 - Q1
            plt.ylim(min(y_bar) - 2.5 * max(IQR), max(y_bar) + 2.5 * max(IQR))
            
        # annotate p-values
        for ii, antiox in enumerate(antiox_list):
            ttest_strain_path = stats_dir / 'pairwise_ttests' / 'antioxidant' /\
                                '{}_antioxidant_results.csv'.format(strain)
            ttest_strain_table = pd.read_csv(ttest_strain_path, index_col=0, header=0)
            strain_pvals_t = ttest_strain_table[[c for c in ttest_strain_table if "pvals_" in c]] 
            strain_pvals_t.columns = [c.split('pvals_')[-1] for c in strain_pvals_t.columns] 
            p = strain_pvals_t.loc[FEATURE, antiox]
            text = ax.get_xticklabels()[ii]
            assert text.get_text() == antiox
            p_text = 'P < 0.001' if p < 0.001 else 'P = %.3f' % p
            #y = (y_bar[antiox] + 2 * IQR[antiox]) if scale_outliers_box else plot_df[feature].max()
            #h = (max(IQR) / 10) if scale_outliers_box else (y - plot_df[feature].min()) / 50
            trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
            plt.plot([ii-.2, ii-.2, ii+.2, ii+.2], 
                      [0.8, 0.81, 0.81, 0.8], #[y+h, y+2*h, y+2*h, y+h], 
                      lw=1.5, c='k', transform=trans)
            ax.text(ii, 0.82, p_text, fontsize=9, ha='center', va='bottom', transform=trans)
                
        fig_savepath = plot_dir / 'antioxidant_boxplots' / strain / (FEATURE + '.png')
        fig_savepath.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fig_savepath)
        
    # Plot for each strain separately to see whether antioxidants had an effect at all
    for strain in strain_list:
            
        plt.close('all')
        fig, ax = plt.subplots(figsize=(10,8))
        ax = sns.boxplot(x='antioxidant', y=FEATURE, order=antiox_list, 
                         dodge=True, data=plot_df[plot_df['gene_name']==strain])
        ax = sns.swarmplot(x='antioxidant', y=FEATURE, order=antiox_list, 
                           dodge=True, data=plot_df[plot_df['gene_name']==strain],
                           alpha=0.7, size=4, color='k')        
        n_labs = len(plot_df['antioxidant'].unique())
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles[:n_labs], labels[:n_labs], fontsize=15, frameon=False, loc='upper right')
        ax.set_xlabel('antioxidant', fontsize=15, labelpad=10)
        ax.set_ylabel(FEATURE.replace('_',' '), fontsize=15, labelpad=10)
        
        # scale plot to omit outliers (>2.5*IQR from mean)
        if scale_outliers_box:
            grouped_strain = plot_df.groupby('antioxidant')
            y_bar = grouped_strain[FEATURE].median() # median is less skewed by outliers
            # Computing IQR
            Q1 = grouped_strain[FEATURE].quantile(0.25)
            Q3 = grouped_strain[FEATURE].quantile(0.75)
            IQR = Q3 - Q1
            plt.ylim(min(y_bar) - 1 * max(IQR), max(y_bar) + 2.5 * max(IQR))
            
        # annotate p-values
        for ii, antiox in enumerate(antiox_list):
            if antiox == control_antioxidant:
                continue
            # load antioxidant results for strain
            ttest_strain_path = stats_dir / 't-test_{}_antioxidant_results.csv'.format(strain)
            ttest_strain_table = pd.read_csv(ttest_strain_path, index_col=0, header=0)
            strain_pvals_t = ttest_strain_table[[c for c in ttest_strain_table if "pvals_" in c]] 
            strain_pvals_t.columns = [c.split('pvals_')[-1] for c in strain_pvals_t.columns] 
            p = strain_pvals_t.loc[FEATURE, antiox]
            text = ax.get_xticklabels()[ii]
            assert text.get_text() == antiox
            p_text = 'P < 0.001' if p < 0.001 else 'P = %.3f' % p
            trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
            #plt.plot([ii-.2, ii-.2, ii+.2, ii+.2], [0.98, 0.99, 0.98, 0.99], lw=1.5, c='k', transform=trans)
            ax.text(ii, 1.01, p_text, fontsize=9, ha='center', va='bottom', transform=trans)
                
        plt.title(strain, fontsize=18, pad=30)
        fig_savepath = plot_dir / 'antioxidant_boxplots' / strain / (FEATURE + '.png')
        fig_savepath.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(fig_savepath)
        
        
        # Hierarchical Clustering Analysis
        #   - Clustermap of features by strain, to see if data cluster into groups
        #   - Control data is clustered first, feature order is stored and ordering applied to 
        #     full data for comparison
        
        heatmap_saveFormat = 'pdf'
        
        # Extract data for control
        control_feat_df = features[metadata['gene_name']==control_strain]
        control_meta_df = metadata.reindex(control_feat_df.index)
        
        control_feat_df, control_meta_df = clean_summary_results(features=control_feat_df,
                                                                 metadata=control_meta_df,
                                                                 imputeNaN=False)
        
        # Ensure no NaNs or features with zero standard deviation before normalisation
        assert not control_feat_df.isna().sum(axis=0).any()
        assert not (control_feat_df.std(axis=0) == 0).any()

        #zscores = (df-df.mean())/df.std() # minus mean, divide by std
        controlZ_feat_df = control_feat_df.apply(zscore, axis=0)

        # Drop features with NaN values after normalising
        n_cols = len(controlZ_feat_df.columns)
        controlZ_feat_df.dropna(axis=1, inplace=True)
        n_dropped = n_cols - len(controlZ_feat_df.columns)
        if n_dropped > 0:
            print("Dropped %d features after normalisation (NaN)" % n_dropped)

        # plot clustermap for control        
        if len(control_meta_df[args.lmm_random_effect].unique()) > 1:
            control_clustermap_path = plot_dir / 'HCA' / ('{}_clustermap'.format(CONTROL) + 
                                                          '.{}'.format(heatmap_saveFormat))
            cg = plot_clustermap(featZ=controlZ_feat_df,
                                 meta=control_meta_df,
                                 group_by=[GROUPING_VAR,'date_yyyymmdd'],
                                 col_linkage=None,
                                 method='complete',#[linkage, complete, average, weighted, centroid]
                                 figsize=[18,6],
                                 saveto=control_clustermap_path)
    
            # Extract linkage + clustered features
            col_linkage = cg.dendrogram_col.calculated_linkage
            clustered_features = np.array(controlZ_feat_df.columns)[cg.dendrogram_col.reordered_ind]
        else:
            clustered_features = None
        
        assert not feat_df.isna().sum(axis=0).any()
        assert not (feat_df.std(axis=0) == 0).any()
        
        featZ_df = feat_df.apply(zscore, axis=0)
        
        # Drop features with NaN values after normalising
        # TODO: Do we need these checks?
        #assert not any(featZ_df.isna(axis=1))
        n_cols = len(featZ_df.columns)
        featZ_df.dropna(axis=1, inplace=True)
        n_dropped = n_cols - len(featZ_df.columns)
        if n_dropped > 0:
            print("Dropped %d features after normalisation (NaN)" % n_dropped)

        # Save stats table to CSV
        stats_table_path = stats_dir / 'stats_summary_table.csv'
        if not stats_path.exists():
            # Add z-normalised values
            z_stats = featZ_df.join(meta_df[GROUPING_VAR]).groupby(by=GROUPING_VAR).mean().T
            z_mean_cols = ['z-mean ' + v for v in z_stats.columns.to_list()]
            z_stats.columns = z_mean_cols
            stats_table = stats_table.join(z_stats)
            first_cols = [m for m in stats_table.columns if 'mean' in m]
            last_cols = [c for c in stats_table.columns if c not in first_cols]
            first_cols.extend(last_cols)
            stats_table = stats_table[first_cols].reset_index()
            first_cols.insert(0, 'feature')
            stats_table.columns = first_cols
            stats_table['feature'] = [' '.join(f.split('_')) for f in stats_table['feature']]
            stats_table = stats_table.sort_values(by='{} p-value'.format((T_TEST_NAME if 
                                         len(run_strain_list) == 2 else TEST_NAME)), ascending=True)
            stats_table.to_csv(stats_table_path, header=True, index=None)
        
        # Clustermap of full data       
        full_clustermap_path = plot_dir / 'HCA' / ('{}_full_clustermap'.format(GROUPING_VAR) + 
                                                   '.{}'.format(heatmap_saveFormat))
        fg = plot_clustermap(featZ=featZ_df, 
                             meta=meta_df, 
                             group_by=GROUPING_VAR,
                             col_linkage=None,
                             method='complete',
                             figsize=[20, (len(run_strain_list) / 4 if 
                                           len(run_strain_list) > 10 else 6)],
                             saveto=full_clustermap_path)
        if not clustered_features:
            # If no control clustering (due to no day variation) then use clustered features for 
            # all strains to order barcode heatmaps
            clustered_features = np.array(featZ_df.columns)[fg.dendrogram_col.reordered_ind]
        
        if len(run_strain_list) > 2:
            pvalues_heatmap = pvals.loc[clustered_features, TEST_NAME]
        elif len(run_strain_list) == 2:
            pvalues_heatmap = pvals_t.loc[pvals_t.index[0], clustered_features]
        pvalues_heatmap.name = 'P < {}'.format(args.pval_threshold)

        assert all(f in featZ_df.columns for f in pvalues_heatmap.index)

        # Heatmap barcode with selected features, ordered by control clustered feature order
        #   - Read in selected features list  
        if args.selected_features_path is not None and run == 3 and GROUPING_VAR == 'worm_strain':
            fset = pd.read_csv(Path(args.selected_features_path), index_col=None)
            fset = [s for s in fset['feature'] if s in featZ_df.columns] 
            # TODO: assert all(s in featZ_df.columns for s in fset['feature'])
            
        # Plot barcode heatmap (grouping by date)
        if len(control_meta_df[args.lmm_random_effect].unique()) > 1:
            heatmap_date_path = plot_dir / 'HCA' / ('{}_date_heatmap'.format(GROUPING_VAR) + 
                                                    '.{}'.format(heatmap_saveFormat))
            plot_barcode_heatmap(featZ=featZ_df[clustered_features], 
                                 meta=meta_df, 
                                 group_by=['date_yyyymmdd',GROUPING_VAR], 
                                 pvalues_series=pvalues_heatmap,
                                 p_value_threshold=args.pval_threshold,
                                 selected_feats=fset if len(fset) > 0 else None,
                                 saveto=heatmap_date_path,
                                 figsize=[20, (len(run_strain_list) / 4 if 
                                               len(run_strain_list) > 10 else 6)],
                                 sns_colour_palette="Pastel1")
        
        # Plot group-mean heatmap (averaged across days)
        heatmap_path = plot_dir / 'HCA' / ('{}_heatmap'.format(GROUPING_VAR) + 
                                           '.{}'.format(heatmap_saveFormat))
        plot_barcode_heatmap(featZ=featZ_df[clustered_features], 
                             meta=meta_df, 
                             group_by=[GROUPING_VAR], 
                             pvalues_series=pvalues_heatmap,
                             p_value_threshold=args.pval_threshold,
                             selected_feats=fset if len(fset) > 0 else None,
                             saveto=heatmap_path,
                             figsize=[20, (len(run_strain_list) / 4 if 
                                           len(run_strain_list) > 10 else 6)],
                             sns_colour_palette="Pastel1")        
                        
        #%% Principal Components Analysis (PCA)

        if args.remove_outliers:
            outlier_path = plot_dir / 'mahalanobis_outliers.pdf'
            feat_df, inds = remove_outliers_pca(df=feat_df, 
                                                features_to_analyse=None, 
                                                saveto=outlier_path)
            meta_df = meta_df.reindex(feat_df.index)
            featZ_df = feat_df.apply(zscore, axis=0)
  
        # plot PCA
        #from tierpsytools.analysis.decomposition import plot_pca
        pca_dir = plot_dir / 'PCA'
        projected_df = plot_pca(featZ=featZ_df, 
                                meta=meta_df, 
                                group_by=GROUPING_VAR, 
                                n_dims=2,
                                control=CONTROL,
                                var_subset=None, 
                                saveDir=pca_dir,
                                PCs_to_keep=10,
                                n_feats2print=10,
                                sns_colour_palette="tab10",
                                hypercolor=False) 
        # TODO: Ensure sns colour palette doees not plot white points
         
        #%%     t-distributed Stochastic Neighbour Embedding (tSNE)

        tsne_dir = plot_dir / 'tSNE'
        perplexities = [5,15,30]
        
        tSNE_df = plot_tSNE(featZ=featZ_df,
                            meta=meta_df,
                            group_by=GROUPING_VAR,
                            var_subset=None,
                            saveDir=tsne_dir,
                            perplexities=perplexities,
                             # NB: perplexity parameter should be roughly equal to group size
                            sns_colour_palette="plasma")
       
        #%%     Uniform Manifold Projection (UMAP)

        umap_dir = plot_dir / 'UMAP'
        n_neighbours = [5,15,30]
        min_dist = 0.1 # Minimum distance parameter
        
        umap_df = plot_umap(featZ=featZ_df,
                            meta=meta_df,
                            group_by=GROUPING_VAR,
                            var_subset=None,
                            saveDir=umap_dir,
                            n_neighbours=n_neighbours,
                            # NB: n_neighbours parameter should be roughly equal to group size
                            min_dist=min_dist,
                            sns_colour_palette="tab10")


    return
    
#%% Main

if __name__ == '__main__':   
    parser = argparse.ArgumentParser(description="Analyse acute response videos to investigate how \
    fast the food takes to influence worm behaviour")
    parser.add_argument('-j','--json', help="Path to JSON parameters file", default=JSON_PARAMETERS_PATH)
    args = parser.parse_args()
    args = load_json(args.json)

    aux_dir = Path(args.project_dir) / 'AuxiliaryFiles'
    results_dir =  Path(args.project_dir) / 'Results'
    
    # load metadata    
    metadata, metadata_path = process_metadata(aux_dir, 
                                               imaging_dates=args.dates, 
                                               add_well_annotations=args.add_well_annotations, 
                                               n_wells=6)
    
    features, metadata = process_feature_summaries(metadata_path, 
                                                   results_dir, 
                                                   compile_day_summaries=args.compile_day_summaries, 
                                                   imaging_dates=args.dates, 
                                                   align_bluelight=args.align_bluelight, 
                                                   window_summaries=True,
                                                   n_wells=6)
 
    # Subset results (rows) to remove entries for wells with unknown strain data for 'gene_name'
    n = metadata.shape[0]
    metadata = metadata.loc[~metadata['gene_name'].isna(),:]
    features = features.reindex(metadata.index)
    print("%d entries removed with no gene name metadata" % (n - metadata.shape[0]))
 
    # update gene names for mutant strains
    metadata['gene_name'] = [args.control_dict['gene_name'] if s == 'BW' else s 
                             for s in metadata['gene_name']]
    #['BW\u0394'+g if not g == 'BW' else 'wild_type' for g in metadata['gene_name']]

    # Create is_bad_well column - refer to manual metadata for bad 35mm petri plates
    metadata['is_bad_well'] = False

    # Clean results - Remove bad well data + features with too many NaNs/zero std + impute
    features, metadata = clean_summary_results(features, 
                                               metadata,
                                               feature_columns=None,
                                               nan_threshold_row=args.nan_threshold_row,
                                               nan_threshold_col=args.nan_threshold_col,
                                               max_value_cap=args.max_value_cap,
                                               imputeNaN=args.impute_nans,
                                               min_nskel_per_video=args.min_nskel_per_video,
                                               min_nskel_sum=args.min_nskel_sum,
                                               drop_size_related_feats=args.drop_size_features,
                                               norm_feats_only=args.norm_features_only,
                                               percentile_to_use=args.percentile_to_use)

    assert not features.isna().sum(axis=1).any()
    assert not (features.std(axis=1) == 0).any()
    
    # assert there will be no errors due to case-sensitivity
    assert len(metadata['gene_name'].unique()) == len(metadata['gene_name'].str.upper().unique())
    assert len(metadata['antioxidant'].unique()) == len(metadata['antioxidant'].str.upper().unique())

    if ALL_WINDOWS:
        WINDOW_LIST = list(WINDOW_FRAME_DICT.keys())
        args.save_dir = Path(args.save_dir) / 'all_windows'
     
    # subset for windows in window_frame_dict
    assert all(w in metadata['window'] for w in WINDOW_LIST)
    metadata = metadata[metadata['window'].isin(WINDOW_LIST)]
    features = features.reindex(metadata.index)

    # # subset for Tierpsy features only
    # if args.n_top_feats is not None:
    #     features = select_feat_set(features, 
    #                                tierpsy_set_name='tierpsy_{}'.format(args.n_top_feats),
    #                                append_bluelight=True)

    # statistics save path
    save_dir = get_save_dir(args)
    
    acute_rescue_stats(features, 
                       metadata, 
                       save_dir=save_dir, 
                       control_strain=args.control_dict['gene_name'],
                       control_antioxidant=args.control_dict['antioxidant'],
                       control_window=args.control_dict['window'],
                       fdr_method='fdr_by',
                       pval_threshold=args.pval_threshold)
    
    analyse_acute_rescue(features, 
                         metadata, 
                         save_dir=save_dir,
                         control_strain=args.control_dict['gene_name'],
                         control_antioxidant=args.control_dict['antioxidant'],
                         control_window=args.control_dict['window'],
                         fdr_method='fdr_by',
                         pval_threshold=args.pval_threshold)
    
    
    