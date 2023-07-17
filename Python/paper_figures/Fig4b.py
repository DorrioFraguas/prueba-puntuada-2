#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figure 4b - fepD overexpression (OE) mutants

@author: sm5911
@date: 16/06/2023

"""

#%% Imports

import pandas as pd
import seaborn as sns
from pathlib import Path
from matplotlib import pyplot as plt

from visualisation.plotting_helper import sig_asterix
from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes

#%% Globals

PROJECT_DIR_LIST = ["/Users/sm5911/Documents/Keio_FepD_Oxidative_Stress_Mutants",
                    "/Users/sm5911/Documents/Keio_FepD_Mutants_2"]
SAVE_DIR = "/Users/sm5911/OneDrive - Imperial College London/Publications/Keio_Paper/Figures/Fig4"

FEATURE = 'speed_50th'
P_VALUE_THRESHOLD = 0.05
FDR_METHOD = 'fdr_bh'
DPI = 900

STRAIN_LIST = ['BW','fepD','fepD; empty plasmid','fepD; OE acnB','fepD; OE prpB',
               'fepD; prpB; OE acnB','fepD; prpC; OE acnB'] #'fepD; OE fecA',

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
    print("Mean sample size of %s: %d" % (group_by, int(sample_size['well_name'].mean())))

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
             
    # perform t-tests
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

    if n > 2:
        return anova_results, ttest_results
    else:
        return ttest_results
    
    
def main():
    
    metadata_list = []
    features_list = []
    for project_dir in PROJECT_DIR_LIST:
        _meta = pd.read_csv(Path(project_dir) / 'metadata.csv', header=0, index_col=None, 
                           dtype={'comments':str})
        _feat = pd.read_csv(Path(project_dir) / 'features.csv', header=0, index_col=None)
        metadata_list.append(_meta)
        features_list.append(_feat)
        
    metadata = pd.concat(metadata_list, axis=0, ignore_index=True)
    features = pd.concat(features_list, axis=0, ignore_index=True)

    # subset for bluelight videos only 
    bluelight_videos = [i for i in metadata['imgstore_name'] if 'bluelight' in i]
    metadata = metadata[metadata['imgstore_name'].isin(bluelight_videos)]

    # subset for arousal window (20-30 seconds after blue light 3)
    metadata = metadata[metadata['window']==5]
    
    # subset for selected strains
    metadata['bacteria_strain'] = [i.replace('_','; ') for i in metadata['bacteria_strain']]
    assert all(s in metadata['bacteria_strain'].unique() for s in STRAIN_LIST)
    metadata = metadata[metadata['bacteria_strain'].isin(STRAIN_LIST)]

    # reindex features
    features = features.reindex(metadata.index)
        
    colours = sns.color_palette('tab10',2)
    for i in range((len(STRAIN_LIST)-2)):
        colours.append(sns.color_palette('Greys',1)[0])
    colour_dict = dict(zip(STRAIN_LIST, colours))
    
    # boxplots
    plot_df = metadata.join(features[[FEATURE]])
    
    plt.close('all')
    sns.set_style('ticks')
    fig, ax = plt.subplots(figsize=(10,10))
    sns.boxplot(x='bacteria_strain', 
                y='speed_50th',
                order=STRAIN_LIST,
                data=plot_df, 
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
                width=0.75)
    sns.stripplot(x='bacteria_strain', 
                  y='speed_50th',
                  order=STRAIN_LIST,
                  data=plot_df,
                  s=10,
                  palette=[sns.color_palette('Greys',2)[1]],
                  marker=".",
                  edgecolor='k',
                  linewidth=0.3)

    ax.axes.get_xaxis().get_label().set_visible(False) # remove x axis label
    xlabs = [l.get_text() for l in ax.axes.get_xticklabels()]
    ax.axes.set_xticklabels(xlabs, fontsize=25, ha='right', rotation=45)
    ax.tick_params(axis='x', which='major', pad=2)
    ax.axes.set_ylabel('Speed (µm s$^{-1}$)', fontsize=30, labelpad=30)                             
    plt.yticks(fontsize=30)
    plt.ylim(-20, 300)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    linewidth = 2
    ax.spines['left'].set_linewidth(linewidth)
    ax.spines['bottom'].set_linewidth(linewidth)
    ax.xaxis.set_tick_params(width=linewidth, length=linewidth*2)
    ax.yaxis.set_tick_params(width=linewidth, length=linewidth*2)
    feat_control = features.reindex(metadata[metadata['bacteria_strain']=='fepD'].index)[FEATURE]
    ax.axhline(y=feat_control.median(), xmin=0, xmax=len(STRAIN_LIST), ls='--', c='k')
    
    # do stats - compare all treatments to fepD no citrate control
    anova_results, ttest_results = stats(metadata,
                                         features,
                                         group_by='bacteria_strain',
                                         control='fepD',
                                         feat=FEATURE,
                                         pvalue_threshold=P_VALUE_THRESHOLD,
                                         fdr_method=FDR_METHOD)
    
    # load t-test results
    pvals = ttest_results[[c for c in ttest_results.columns if 'pval' in c]]
    pvals.columns = [c.replace('pvals_','') for c in pvals.columns]

    # Add p-value to plot  
    pval_label_offset = 40
    fontsize_label = 25
    meta_grouped = metadata.groupby('bacteria_strain')
    
    for i, strain in enumerate(STRAIN_LIST):
        text = ax.get_xticklabels()[i]
        assert text.get_text() == strain

        if strain == 'fepD':
            continue
        else:
            _meta = meta_grouped.get_group(strain)
            _feat = features[[FEATURE]].reindex(_meta.index)
            y_pos = _feat[FEATURE].max() + pval_label_offset
            p = pvals.loc['speed_50th',strain]
            p_text = sig_asterix([p],ns=True)[0]
            ax.text(i, y_pos, p_text, fontsize=fontsize_label, ha='center', va='top')
                
    plt.subplots_adjust(left=0.2, bottom=0.28, right=0.99)
    plt.savefig(Path(SAVE_DIR) / 'Fig4b.png', dpi=DPI)  
    
    return

#%% Main

if __name__ == '__main__':
    main()
