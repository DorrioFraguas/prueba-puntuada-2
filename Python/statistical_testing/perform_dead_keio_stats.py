#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Perform statistics for Dead Keio strains experiment - Analyse effects of UV-killed vs live hit Keio
strains on C. elegans behaviour

For each strain, compare live vs dead for differential effects on behaviour
Compare each strain to control for significant differences, both alive and dead

- Significant features differing between dead/live bacteria for each strain by t-test

@author: sm5911
@date: 15/11/2021
"""

#%% IMPORTS

import argparse
import numpy as np
import pandas as pd
from time import time
from pathlib import Path

from read_data.paths import get_save_dir
from read_data.read import load_json
from write_data.write import write_list_to_file
from visualisation.plotting_helper import sig_asterix

from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes
from tierpsytools.preprocessing.filter_data import select_feat_set

#%% GLOBALS

JSON_PARAMETERS_PATH = "analysis/20211109_parameters_keio_dead.json"

CONTROL_STRAIN = 'wild_type'
CONTROL_TREATMENT = 'live'
    
feature_set=['motion_mode_forward_fraction_prestim',
             'motion_mode_forward_fraction_bluelight',
             'motion_mode_forward_fraction_poststim',
             'speed_50th_prestim',
             'speed_50th_bluelight',
             'speed_50th_poststim',
             'curvature_midbody_norm_abs_50th_prestim',
             'curvature_midbody_norm_abs_50th_bluelight',
             'curvature_midbody_norm_abs_50th_poststim']

#%% FUNCTIONS

def uv_killed_stats(feature, 
                    metadata, 
                    group_by='treatment', 
                    control='wild_type-live', 
                    pvalue_threshold=0.05, 
                    fdr_method='fdr_by', 
                    save_dir=None):
    """ Compare fepD/BW whether alive or dead """
    
    treatment_list = metadata[group_by].unique().tolist()
    
    # ANOVA
    if len(treatment_list) > 2:
        
        test_path = Path(save_dir) / 'ANOVA_results.csv'
        test_path.parent.mkdir(exist_ok=True, parents=True)

        stats, pvals, reject = univariate_tests(X=features,
                                                y=metadata[group_by],
                                                test='ANOVA',
                                                control=control,
                                                comparison_type='multiclass',
                                                multitest_correction=fdr_method,
                                                alpha=pvalue_threshold,
                                                n_permutation_test=None)
        
        effect_sizes = get_effect_sizes(X=features,
                                        y=metadata[group_by],
                                        control=control,
                                        effect_type=None,
                                        linked_test='ANOVA')
        
        # compile and save results
        test_results = pd.concat([stats, effect_sizes, pvals, reject], axis=1)
        test_results.columns = ['stats','effect_size','pvals','reject']     
        test_results['significance'] = sig_asterix(test_results['pvals'])
        test_results = test_results.sort_values(by=['pvals'], ascending=True) # rank pvals
        test_results.to_csv(test_path, header=True, index=True)
        
        nsig = test_results['reject'].sum()
        print("%d features (%.1f%%) signficantly different among '%s'" % (nsig, 
              (nsig/len(test_results.index))*100, group_by))

    # t-tests
    ttest_path = Path(save_dir) / 't-test_results.csv'

    stats_t, pvals_t, reject_t = univariate_tests(X=features,
                                                  y=metadata[group_by],
                                                  test='t-test',
                                                  control=control,
                                                  comparison_type='binary_each_group',
                                                  multitest_correction=fdr_method,
                                                  alpha=pvalue_threshold,
                                                  n_permutation_test=None)
    
    effect_sizes_t = get_effect_sizes(X=features,
                                      y=metadata[group_by],
                                      control=control,
                                      effect_type=None,
                                      linked_test='t-test')
    
    # compile and save results
    stats_t.columns = ['stats_' + str(c) for c in stats_t.columns]
    pvals_t.columns = ['pvals_' + str(c) for c in pvals_t.columns]
    reject_t.columns = ['reject_' + str(c) for c in reject_t.columns]
    effect_sizes_t.columns = ['effect_size_' + str(c) for c in effect_sizes_t.columns]
    ttest_results = pd.concat([stats_t, effect_sizes_t, pvals_t, reject_t], axis=1)
    ttest_results.to_csv(ttest_path, header=True, index=True)
    
    # record t-test significant features (not ordered)
    fset_ttest = pvals_t[np.asmatrix(reject_t)].index.unique().to_list()
    #assert set(fset_ttest) == set(pvals_t.index[(pvals_t < args.pval_threshold).sum(axis=1) > 0])
    print("%d significant features for any %s vs %s (t-test, %s, P<%.2f)" % (len(fset_ttest),
          group_by, control, fdr_method, pvalue_threshold))

    if len(fset_ttest) > 0:
        ttest_sigfeats_path = Path(save_dir) / 't-test_sigfeats.txt'
        write_list_to_file(fset_ttest, ttest_sigfeats_path)
    
    return
        
#%% MAIN

if __name__ == "__main__":
    tic = time()
    parser = argparse.ArgumentParser(description="Find 'hit' Keio knockout strains that alter worm behaviour")
    parser.add_argument('-j', '--json', help="Path to JSON parameters file", 
                        default=JSON_PARAMETERS_PATH, type=str)
    args = parser.parse_args()
    args = load_json(args.json)

    FEATURES_PATH = Path(args.save_dir) / 'features.csv'
    METADATA_PATH = Path(args.save_dir) / 'metadata.csv'
        
    # load feature summaries and metadata
    features = pd.read_csv(FEATURES_PATH)
    metadata = pd.read_csv(METADATA_PATH, dtype={'comments':str, 'source_plate_id':str})
    
    # subset for desired imaging dates
    if args.dates is not None:
        assert type(args.dates) == list
        metadata = metadata.loc[metadata['date_yyyymmdd'].astype(str).isin(args.dates)]
        features = features.reindex(metadata.index)

    # Load Tierpsy feature set + subset (columns) for selected features only
    if args.n_top_feats is not None:
        features = select_feat_set(features, 'tierpsy_{}'.format(args.n_top_feats), append_bluelight=True)
        features = features[[f for f in features.columns if 'path_curvature' not in f]]
    elif feature_set is not None:
        features = features[features.columns[features.columns.isin(feature_set)]]
        
    assert not features.isna().any().any()
        
    metadata['is_dead'] = ['dead' if i else 'live' for i in metadata['dead']]
    metadata['treatment'] = metadata[['gene_name','is_dead']].agg('-'.join, axis=1)
    control = CONTROL_STRAIN + '-' + CONTROL_TREATMENT
    
    uv_killed_stats(features, 
                    metadata, 
                    group_by='treatment',
                    control=control,
                    pvalue_threshold=args.pval_threshold, 
                    fdr_method=args.fdr_method,
                    save_dir=get_save_dir(args) / 'Stats' / args.fdr_method)
    
    toc = time()
    print("\nDone in %.1f seconds" % (toc - tic))
