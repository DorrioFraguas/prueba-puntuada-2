#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worm tapping experiments

@author: sm5911
@date: 08/08/2022

"""

#%% Imports

import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path
from matplotlib import pyplot as plt

from preprocessing.compile_hydra_data import compile_metadata, process_feature_summaries
from filter_data.clean_feature_summaries import clean_summary_results
from write_data.write import write_list_to_file
from visualisation.plotting_helper import sig_asterix, boxplots_sigfeats
from time_series.plot_timeseries import plot_timeseries_feature, plot_timeseries
from time_series.time_series_helper import get_strain_timeseries
# from analysis.keio_screen.follow_up.lawn_leaving_rate import fraction_on_food, timeseries_on_food

from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes
from tierpsytools.preprocessing.filter_data import select_feat_set

#%% Globals

PROJECT_DIR = "/Volumes/hermes$/Saul/Keio_Screen/Data/Keio_Plate_Tap"
SAVE_DIR = "/Users/sm5911/Documents/Keio_Plate_Tap"

N_WELLS = 6
FPS = 25

nan_threshold_row = 0.8
nan_threshold_col = 0.05

FEATURE_SET = ['speed_50th']

THRESHOLD_FILTER_DURATION = 25 # threshold trajectory length (n frames) / 25 fps => 1 second
THRESHOLD_FILTER_MOVEMENT = 10 # threshold movement (n pixels) * 12.4 microns per pixel => 124 microns
THRESHOLD_LEAVING_DURATION = 50 # n frames a worm has to leave food for => a true leaving event

#%% Functions

def tap_stats(metadata,
              features,
              group_by='treatment',
              control='BW',
              save_dir=None,
              feature_set=None,
              pvalue_threshold=0.05,
              fdr_method='fdr_by'):
    
    # check case-sensitivity
    assert len(metadata[group_by].unique()) == len(metadata[group_by].str.upper().unique())
    
    if feature_set is not None:
        feature_set = [feature_set] if isinstance(feature_set, str) else feature_set
        assert isinstance(feature_set, list)
        assert(all(f in features.columns for f in feature_set))
    else:
        feature_set = features.columns.tolist()
        
    features = features[feature_set].reindex(metadata.index)

    # print mean sample size
    sample_size = metadata.groupby(group_by).count()
    print("Mean sample size of %s: %d" % (group_by, int(sample_size[sample_size.columns[-1]].mean())))

    n = len(metadata[group_by].unique())
        
    fset = []
    if n > 2:
   
        # Perform ANOVA - is there variation among strains at each window?
        anova_path = Path(save_dir) / 'ANOVA' / 'ANOVA_results.csv'
        anova_path.parent.mkdir(parents=True, exist_ok=True)

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

        # compile + save results
        test_results = pd.concat([stats, effect_sizes, pvals, reject], axis=1)
        test_results.columns = ['stats','effect_size','pvals','reject']     
        test_results['significance'] = sig_asterix(test_results['pvals'])
        test_results = test_results.sort_values(by=['pvals'], ascending=True) # rank by p-value
        test_results.to_csv(anova_path, header=True, index=True)

        # use reject mask to find significant feature set
        fset = pvals.loc[reject['ANOVA']].sort_values(by='ANOVA', ascending=True).index.to_list()

        if len(fset) > 0:
            print("%d significant features found by ANOVA by '%s' (P<%.2f, %s)" %\
                  (len(fset), group_by, pvalue_threshold, fdr_method))
            anova_sigfeats_path = anova_path.parent / 'ANOVA_sigfeats.txt'
            write_list_to_file(fset, anova_sigfeats_path)
             
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
    
    # save results
    ttest_path = Path(save_dir) / 't-test' / 't-test_results.csv'
    ttest_path.parent.mkdir(exist_ok=True, parents=True)
    ttest_results.to_csv(ttest_path, header=True, index=True)
    
    nsig = sum(reject_t.sum(axis=1) > 0)
    print("%d significant features between any %s vs %s (t-test, P<%.2f, %s)" %\
          (nsig, group_by, control, pvalue_threshold, fdr_method))

    return

def tap_boxplots(metadata,
                 features,
                 group_by='treatment',
                 control='BW',
                 save_dir=None,
                 stats_dir=None,
                 feature_set=None,
                 pvalue_threshold=0.05,
                 drop_insignificant=False,
                 scale_outliers=False,
                 ylim_minmax=None):
    
    feature_set = features.columns.tolist() if feature_set is None else feature_set
    assert isinstance(feature_set, list) and all(f in features.columns for f in feature_set)
                    
    # load t-test results for window
    if stats_dir is not None:
        ttest_path = Path(stats_dir) / 't-test' / 't-test_results.csv'
        ttest_df = pd.read_csv(ttest_path, header=0, index_col=0)
        pvals = ttest_df[[c for c in ttest_df.columns if 'pval' in c]]
        pvals.columns = [c.replace('pvals_','') for c in pvals.columns]
    
    boxplots_sigfeats(features,
                      y_class=metadata[group_by],
                      control=control,
                      pvals=pvals,
                      z_class=None,
                      feature_set=feature_set,
                      saveDir=Path(save_dir),
                      drop_insignificant=drop_insignificant,
                      p_value_threshold=pvalue_threshold,
                      scale_outliers=scale_outliers,
                      ylim_minmax=ylim_minmax)
    
    return


def main():
    
    aux_dir = Path(PROJECT_DIR) / 'AuxiliaryFiles'
    res_dir = Path(PROJECT_DIR) / 'Results'
    
    metadata_path_local = Path(SAVE_DIR) / 'metadata.csv'
    features_path_local = Path(SAVE_DIR) / 'features.csv'
    
    if not metadata_path_local.exists() or not features_path_local.exists():
        metadata, metadata_path = compile_metadata(aux_dir, 
                                                   n_wells=N_WELLS, 
                                                   add_well_annotations=False,
                                                   from_source_plate=True)
        
        features, metadata = process_feature_summaries(metadata_path, 
                                                       results_dir=res_dir, 
                                                       compile_day_summaries=True, 
                                                       imaging_dates=None,
                                                       align_bluelight=False, 
                                                       window_summaries=True,
                                                       n_wells=N_WELLS)

        # Clean results - Remove bad well data + features with too many NaNs/zero std + impute NaNs
        features, metadata = clean_summary_results(features,
                                                   metadata,
                                                   feature_columns=None,
                                                   nan_threshold_row=nan_threshold_row,
                                                   nan_threshold_col=nan_threshold_col,
                                                   max_value_cap=1e15,
                                                   imputeNaN=True,
                                                   min_nskel_per_video=None,
                                                   min_nskel_sum=None,
                                                   drop_size_related_feats=False,
                                                   norm_feats_only=False)
        
        # save clean metadata and features
        metadata.to_csv(metadata_path_local, index=False)
        features.to_csv(features_path_local, index=False)
        
    else:
        metadata = pd.read_csv(metadata_path_local, header=0, index_col=None, dtype={'comments':str})
        features = pd.read_csv(features_path_local, header=0, index_col=None)

    assert not features.isna().sum(axis=1).any()
    assert not (features.std(axis=1) == 0).any()
    
    # load feature set
    if FEATURE_SET is not None:
        # subset for selected feature set (and remove path curvature features)
        if isinstance(FEATURE_SET, int) and FEATURE_SET in [8,16,256]:
            features = select_feat_set(features, 'tierpsy_{}'.format(FEATURE_SET), append_bluelight=True)
            features = features[[f for f in features.columns if 'path_curvature' not in f]]
        elif isinstance(FEATURE_SET, list) or isinstance(FEATURE_SET, set):
            assert all(f in features.columns for f in FEATURE_SET)
            features = features[FEATURE_SET].copy()
    feature_list = features.columns.tolist()
    
    # TODO: For no tap control use 20220803 mutant worm experiments (no bluelight, use prestim)
    
    treatment_cols = ['food_type','drug_type'] # 'tap_stimulus'
    metadata['treatment'] = metadata[treatment_cols].astype(str).agg('-'.join, axis=1)
    control = 'BW-nan' # none
    
    # perform anova and t-tests comparing each treatment to BW control
    tap_stats(metadata,
              features,
              group_by='treatment',
              control=control,
              save_dir=Path(SAVE_DIR) / 'Stats',
              feature_set=feature_list,
              pvalue_threshold=0.05,
              fdr_method='fdr_by')
    
    # boxplots comparing each treatment to BW control for each feature
    tap_boxplots(metadata,
                 features,
                 group_by='treatment',
                 control=control,
                 save_dir=Path(SAVE_DIR) / 'Plots',
                 stats_dir=Path(SAVE_DIR) / 'Stats',
                 feature_set=feature_list,
                 pvalue_threshold=0.05,
                 scale_outliers=None,
                 ylim_minmax=(0,250)) # ylim_minmax for speed feature only
         
    # timeseries plots of speed for each treatment vs control
    strain_list = list(metadata['treatment'].unique())
    plot_timeseries_feature(metadata,
                            project_dir=Path(PROJECT_DIR),
                            save_dir=Path(SAVE_DIR) / 'timeseries-speed',
                            group_by='treatment',
                            control=control,
                            groups_list=strain_list,
                            feature='speed',
                            n_wells=6,
                            bluelight_stim_type=None,
                            video_length_seconds=360,
                            bluelight_timepoints_seconds=None,
                            smoothing=10,
                            fps=FPS,
                            ylim_minmax=(0,200))
        
    # bespoke timeseries    
    groups = ['BW-nan','fepD-nan','BW-Paraquat']        
    feature = 'speed'
    save_dir = Path(SAVE_DIR) / 'timeseries-speed' / 'rescues'
    ts_plot_dir = save_dir / 'Plots'
    ts_plot_dir.mkdir(exist_ok=True, parents=True)
    save_path = ts_plot_dir / 'speed_bluelight.pdf'
    
    plt.close('all')
    fig, ax = plt.subplots(figsize=(15,6), dpi=300)
    col_dict = dict(zip(groups, sns.color_palette('tab10', len(groups))))

    for group in groups:
        
        # get control timeseries
        group_ts = get_strain_timeseries(metadata,
                                         project_dir=Path(PROJECT_DIR),
                                         strain=group,
                                         group_by='treatment',
                                         feature_list=[feature],
                                         save_dir=save_dir,
                                         n_wells=N_WELLS,
                                         verbose=True)
        
        ax = plot_timeseries(df=group_ts,
                             feature=feature,
                             error=True,
                             max_n_frames=300*FPS, 
                             smoothing=10*FPS, 
                             ax=ax,
                             bluelight_frames=None,
                             colour=col_dict[group])

    plt.ylim(0, 200)
    xticks = np.linspace(0, 300*FPS, int(300/60)+1)
    ax.set_xticks(xticks)
    ax.set_xticklabels([str(int(x/FPS/60)) for x in xticks])   
    ax.set_xlabel('Time (minutes)', fontsize=20, labelpad=10)
    ylab = feature.replace('_50th'," (µm s$^{-1}$)")
    ax.set_ylabel(ylab, fontsize=20, labelpad=10)
    ax.legend(groups, fontsize=12, frameon=False, loc='best', handletextpad=1)
    plt.subplots_adjust(left=0.1, top=0.98, bottom=0.15, right=0.98)

    # save plot
    print("Saving to: %s" % save_path)
    plt.savefig(save_path)
    
    return

#%% Main

if __name__ == '__main__':
    main()
    
    