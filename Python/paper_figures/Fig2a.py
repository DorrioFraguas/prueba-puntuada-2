#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figure 2a and 2b - (a) boxplots and (b) timeseries of fepD, BW, BW+paraquat

@author: sm5911
@date: 10/06/2023

"""

#%% Imports 

import pandas as pd
import seaborn as sns
from pathlib import Path
from matplotlib import pyplot as plt
from matplotlib import transforms

from visualisation.plotting_helper import sig_asterix
from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes

#%% Globals

PROJECT_DIR = "/Users/sm5911/Documents/Keio_UV_Paraquat_Antioxidant"
SAVE_DIR = "/Users/sm5911/OneDrive - Imperial College London/Publications/Keio_Paper/Figures/Fig2"

DPI = 900
P_VALUE_THRESHOLD = 0.05
FDR_METHOD = 'fdr_bh'

#%% Functions

def stats(metadata,
          features,
          group_by='treatment',
          control='BW',
          feat='speed_50th',
          pvalue_threshold=0.05,
          fdr_method='fdr_bh'):
        
    assert all(metadata.index == features.index)
    features = features[[feat]]

    # print mean sample size
    sample_size = metadata.groupby(group_by).count()
    print("Mean sample size of %s/window: %d" % (group_by, 
                                                 int(sample_size[sample_size.columns[-1]].mean())))

    n = len(metadata[group_by].unique())
    if n > 2:
   
        # Perform ANOVA - is there variation among strains?
        stats, pvals, reject = univariate_tests(X=features, 
                                                y=metadata[group_by], 
                                                control=control, 
                                                test='ANOVA',
                                                comparison_type='multiclass',
                                                multitest_correction=fdr_method,
                                                alpha=pvalue_threshold,
                                                n_permutation_test=None)

        # get effect sizes
        effect_sizes = get_effect_sizes(X=features,
                                        y=metadata[group_by],
                                        control=control,
                                        effect_type=None,
                                        linked_test='ANOVA')

        # compile results
        anova_results = pd.concat([stats, effect_sizes, pvals, reject], axis=1)
        anova_results.columns = ['stats','effect_size','pvals','reject']     
        anova_results['significance'] = sig_asterix(anova_results['pvals'])
        anova_results = anova_results.sort_values(by=['pvals'], ascending=True) # rank by p-value
             
    # Perform t-tests
    stats_t, pvals_t, reject_t = univariate_tests(X=features,
                                                  y=metadata[group_by],
                                                  control=control,
                                                  test='t-test',
                                                  comparison_type='binary_each_group',
                                                  multitest_correction=fdr_method,
                                                  alpha=pvalue_threshold)
    
    effect_sizes_t = get_effect_sizes(X=features,
                                      y=metadata[group_by],
                                      control=control,
                                      linked_test='t-test')
    
    stats_t.columns = ['stats_' + str(c) for c in stats_t.columns]
    pvals_t.columns = ['pvals_' + str(c) for c in pvals_t.columns]
    reject_t.columns = ['reject_' + str(c) for c in reject_t.columns]
    effect_sizes_t.columns = ['effect_size_' + str(c) for c in effect_sizes_t.columns]
    ttest_results = pd.concat([stats_t, pvals_t, reject_t, effect_sizes_t], axis=1)
        
    nsig = sum(reject_t.sum(axis=1) > 0)
    print("%d significant features between any %s vs %s (t-test, P<%.2f, %s)" %\
          (nsig, group_by, control, pvalue_threshold, fdr_method))

    return anova_results, ttest_results


def main():
    
    metadata_path = Path(PROJECT_DIR) / 'metadata.csv'
    features_path = Path(PROJECT_DIR) / 'features.csv'
    
    metadata = pd.read_csv(metadata_path, header=0, index_col=None, dtype={'comments':str})
    features = pd.read_csv(features_path, header=0, index_col=None)
    
    # subset metadata results for bluelight videos only 
    bluelight_videos = [i for i in metadata['imgstore_name'] if 'bluelight' in i]
    metadata = metadata[metadata['imgstore_name'].isin(bluelight_videos)]
    
    # subset metadata for window 5 (20-30 seconds after blue light pulse 3)
    metadata = metadata[metadata['window']==5]
    
    # subset to remove antioxidant results
    metadata = metadata[~metadata['drug_type'].isin(['NAC','Vitamin C'])]

    # subset for results for live cultures only
    metadata = metadata.query("is_dead=='N'")
    
    # subset for 1mM paraquat results only
    metadata = metadata[metadata['drug_imaging_plate_conc']!=0.5]
    
    treatment_cols = ['food_type','drug_type']
    metadata['treatment'] = metadata[treatment_cols].astype(str).agg('-'.join, axis=1)
    metadata['treatment'] = [i.replace('-nan','') for i in metadata['treatment']]

    # drop fepD+paraquat results
    metadata = metadata[metadata['treatment']!='fepD-Paraquat']
    
    # reindex features summmaries for new metadata subset
    features = features.reindex(metadata.index)[['speed_50th']]
    assert all(metadata.index == features.index)

    # boxplots
    
    plot_df = metadata.join(features)
    order = ['BW','fepD','BW-Paraquat']
    colour_dict = dict(zip(order, sns.color_palette(palette='tab10', n_colors=len(order))))

    plt.close('all')
    sns.set_style('ticks')
    fig = plt.figure(figsize=[10,10])
    ax = fig.add_subplot(1,1,1)
    sns.boxplot(x='treatment', 
                y='speed_50th', 
                data=plot_df, 
                order=order,
                palette=colour_dict,
                showfliers=False, 
                showmeans=False,
                meanprops={"marker":"x", 
                           "markersize":5,
                           "markeredgecolor":"k"},
                medianprops={'color': 'black'},
                flierprops={"marker":"x", 
                            "markersize":15, 
                            "markeredgecolor":"r"},
                # boxprops={'facecolor': 'lightgray'},
                width=0.75)
    sns.stripplot(x='treatment', 
                  y='speed_50th', 
                  data=plot_df,
                  s=13,
                  order=order,
                  hue=None,
                  palette=None,
                  color='dimgray',
                  marker=".",
                  edgecolor='k',
                  linewidth=0.3)
    
    ax.axes.get_xaxis().get_label().set_visible(False) # remove x axis label
    ax.axes.set_xticklabels([l.get_text().replace('-','\n+ ') for l in ax.axes.get_xticklabels()], 
                            fontsize=30)
    ax.tick_params(axis='x', which='major', pad=15)
    ax.axes.set_ylabel('Speed (µm s$^{-1}$)', fontsize=30, labelpad=25)
    plt.yticks(fontsize=20)
    plt.ylim(-20, 250)
        
    # do stats
    anova_results, ttest_results = stats(metadata,
                                         features,
                                         group_by='treatment',
                                         control='BW',
                                         feat='speed_50th',
                                         pvalue_threshold=P_VALUE_THRESHOLD,
                                         fdr_method=FDR_METHOD)
    
    # load t-test results for window
    pvals = ttest_results[[c for c in ttest_results.columns if 'pval' in c]]
    pvals.columns = [c.replace('pvals_','') for c in pvals.columns]

    # Add p-value to plot        
    for i, treatment in enumerate(order[1:], start=1):
        pval = pvals[treatment]
        p = pval.loc['speed_50th']
        text = ax.get_xticklabels()[i]
        assert text.get_text() == treatment.replace('-','\n+ ')
        
        trans = transforms.blended_transform_factory(ax.transData, ax.transAxes) #y=scaled
        p_text = sig_asterix([p])[0]
        ax.text(i, 1.01, p_text, fontsize=35, ha='center', va='bottom', transform=trans)
        
    plt.subplots_adjust(left=0.08, bottom=0.2, right=0.99)
    plt.savefig(Path(SAVE_DIR) / 'Fig2a.png', dpi=DPI)  
      
    return

#%% Main

if __name__ == '__main__':
    main()