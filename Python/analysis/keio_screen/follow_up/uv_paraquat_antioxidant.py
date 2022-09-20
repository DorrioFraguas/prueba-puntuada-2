#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keio UV Paraquat Antioxidant experiment

Investigate whether the arousal phenotype on fepD is rescued by addition of antioxidants, 
or exacerbated by addition of paraquat (when bacteria are UV killed or not)

@author: sm5911
@date: 30/06/2022

"""

#%% Imports

import numpy as np
import pandas as pd
import seaborn as sns
from tqdm import tqdm
from pathlib import Path

# from analysis.keio_screen.check_keio_screen_worm_trajectories import check_tracked_objects
from preprocessing.compile_hydra_data import compile_metadata, process_feature_summaries
from filter_data.clean_feature_summaries import clean_summary_results
from write_data.write import write_list_to_file
from visualisation.plotting_helper import sig_asterix, boxplots_sigfeats, all_in_one_boxplots
from time_series.plot_timeseries import plot_timeseries_feature #selected_strains_timeseries
from analysis.keio_screen.follow_up.lawn_leaving_rate import fraction_on_food, timeseries_on_food

from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes
from tierpsytools.preprocessing.filter_data import select_feat_set

#%% Globals

PROJECT_DIR = "/Volumes/hermes$/Keio_UV_Paraquat_Antioxidant_6WP"
SAVE_DIR = "/Users/sm5911/Documents/Keio_UV_Paraquat_Antioxidant"

N_WELLS = 6
FPS = 25

nan_threshold_row = 0.8
nan_threshold_col = 0.05

FEATURE_SET = ['speed_50th']

THRESHOLD_FILTER_DURATION = 25 # threshold trajectory length (n frames) / 25 fps => 1 second
THRESHOLD_FILTER_MOVEMENT = 10 # threshold movement (n pixels) * 12.4 microns per pixel => 124 microns
THRESHOLD_LEAVING_DURATION = 50 # n frames a worm has to leave food for => a true leaving event

BLUELIGHT_TIMEPOINTS_SECONDS = [(60, 70),(160, 170),(260, 270)]

WINDOW_DICT = {0:(65,75),1:(90,100),
               2:(165,175),3:(190,200),
               4:(265,275),5:(290,300)}

WINDOW_NAME_DICT = {0:"blue light 1", 1: "20-30 seconds after blue light 1",
                    2:"blue light 2", 3: "20-30 seconds after blue light 2",
                    4:"blue light 3", 5: "20-30 seconds after blue light 3"}

#%% Functions

def uv_paraquat_antioxidant_stats(metadata,
                                  features,
                                  group_by='treatment',
                                  control='BW',
                                  save_dir=None,
                                  feature_set=None,
                                  pvalue_threshold=0.05,
                                  fdr_method='fdr_bh'):
    
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

def uv_paraquat_antioxidant_boxplots(metadata,
                                     features,
                                     group_by='treatment',
                                     control='BW',
                                     save_dir=None,
                                     stats_dir=None,
                                     feature_set=None,
                                     pvalue_threshold=0.05):
    
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
                      pvals=pvals if stats_dir is not None else None,
                      z_class=None,
                      feature_set=feature_set,
                      saveDir=Path(save_dir),
                      drop_insignificant=True if feature_set is None else False,
                      p_value_threshold=pvalue_threshold,
                      scale_outliers=True)
    
    return

def masked_video_list_from_metadata(metadata, 
                                    group_by='treatment', 
                                    groups_list=['BW-nan-nan-N'],
                                    imgstore_col='imgstore_name',
                                    project_dir=None,
                                    save_dir=None):
    
    if groups_list is not None:
        assert isinstance(groups_list, list) and all(g in metadata[group_by].unique() for g in groups_list)
    else:
        groups_list = sorted(metadata[group_by].unique())
       
    video_dict = {}
    for group in groups_list:
        group_meta = metadata[metadata[group_by]==group].copy()
        # check all filenames are completimgstore_col'imgstore_name'].nunique() == group_meta.shape[0]
        
        if project_dir is not None:
            video_dict[group] = [str(Path(project_dir) / 'MaskedVideos' / i / 'metadata.hdf5') 
                                 for i in sorted(group_meta[imgstore_col].unique())]
        else:
            video_dict[group] = sorted(group_meta[imgstore_col].unique())
        
    if save_dir is not None:
        Path(save_dir).mkdir(exist_ok=True, parents=True)
        
        for group in groups_list:
            write_list_to_file(video_dict[group], Path(save_dir) / '{}_video_filenames.txt'.format(group))
    
    return video_dict

    
#%% Main

if __name__ == '__main__':
    
    aux_dir = Path(PROJECT_DIR) / 'AuxiliaryFiles'
    res_dir = Path(PROJECT_DIR) / 'Results'
    
    metadata_path_local = Path(SAVE_DIR) / 'metadata.csv'
    features_path_local = Path(SAVE_DIR) / 'features.csv'
    
    if not metadata_path_local.exists() and not features_path_local.exists():
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

    # subset metadata results for bluelight videos only 
    bluelight_videos = [i for i in metadata['imgstore_name'] if 'bluelight' in i]
    metadata = metadata[metadata['imgstore_name'].isin(bluelight_videos)]
    
    treatment_cols = ['food_type','drug_type','drug_imaging_plate_conc','is_dead']
    metadata['treatment'] = metadata[treatment_cols].astype(str).agg('-'.join, axis=1)
    control = 'BW-nan-nan-N'

    metadata['window'] = metadata['window'].astype(int)
    window_list = list(metadata['window'].unique())

    # save video file list for treatments (for manual inspection)
    video_dict = masked_video_list_from_metadata(metadata, 
                                                 group_by='treatment', 
                                                 groups_list=[control,'fepD-nan-nan-N'],
                                                 project_dir=Path(PROJECT_DIR),
                                                 save_dir=Path(SAVE_DIR) / 'video_filenames')
    print("Found file information for %d treatment groups" % len(video_dict.keys()))

    for window in tqdm(window_list):
        meta_window = metadata[metadata['window']==window]
        feat_window = features.reindex(meta_window.index)

        stats_dir = Path(SAVE_DIR) / 'Stats' / WINDOW_NAME_DICT[window]
        plot_dir = Path(SAVE_DIR) / 'Plots' / WINDOW_NAME_DICT[window]
    
        # perform anova and t-tests comparing each treatment to BW control
        uv_paraquat_antioxidant_stats(meta_window,
                                      feat_window,
                                      group_by='treatment',
                                      control=control,
                                      save_dir=Path(SAVE_DIR) / 'Stats' / WINDOW_NAME_DICT[window],
                                      feature_set=feature_list,
                                      pvalue_threshold=0.05,
                                      fdr_method='fdr_bh')
        
        # boxplots comparing each treatment to BW control for each feature
        uv_paraquat_antioxidant_boxplots(meta_window,
                                         feat_window,
                                         group_by='treatment',
                                         control=control,
                                         save_dir=Path(SAVE_DIR) / 'Plots' / WINDOW_NAME_DICT[window],
                                         stats_dir=Path(SAVE_DIR) / 'Stats' / WINDOW_NAME_DICT[window],
                                         feature_set=feature_list,
                                         pvalue_threshold=0.05)
        
        # antioxidants
        antiox_meta = meta_window[np.logical_and(meta_window['drug_type']!='Paraquat',
                                                 meta_window['is_dead']=='N')]
        antiox_feat = feat_window.reindex(antiox_meta.index)
        uv_paraquat_antioxidant_stats(antiox_meta,
                                      antiox_feat,
                                      group_by='treatment',
                                      control=control,
                                      save_dir=stats_dir / 'antioxidants',
                                      feature_set=feature_list,
                                      pvalue_threshold=0.05,
                                      fdr_method='fdr_bh')
        order = ['BW-nan-nan-N','fepD-nan-nan-N',
                 'BW-Vitamin C-0.5-N','BW-Vitamin C-1.0-N','fepD-Vitamin C-0.5-N','fepD-Vitamin C-1.0-N',
                 'BW-NAC-0.5-N','BW-NAC-1.0-N','fepD-NAC-0.5-N','fepD-NAC-1.0-N']
        colour_labels = sns.color_palette('tab10', 2)
        colours = [colour_labels[0] if 'BW' in s else colour_labels[1] for s in order]
        colour_dict = {key:col for (key,col) in zip(order, colours)}
        all_in_one_boxplots(antiox_meta,
                            antiox_feat,
                            group_by='treatment',
                            control=control,
                            save_dir=plot_dir / 'all-in-one' / 'antioxidants',
                            ttest_path=stats_dir / 'antioxidants' / 't-test' / 't-test_results.csv',
                            feature_set=feature_list,
                            pvalue_threshold=0.05,
                            order=order,
                            colour_dict=colour_dict,
                            figsize=(30,10),
                            ylim_minmax=(-20,380),
                            vline_boxpos=[1,5],
                            fontsize=20,
                            subplots_adjust={'bottom':0.32,'top':0.95,'left':0.05,'right':0.98})
        
        # paraquat (live)
        paraquat_meta = meta_window[np.logical_and(np.logical_or(meta_window['drug_type']=='Paraquat',
                                                                 meta_window['drug_type'].astype(str)=='nan'),
                                                   meta_window['is_dead']=='N')]
        paraquat_feat = feat_window.reindex(paraquat_meta.index)
        uv_paraquat_antioxidant_stats(paraquat_meta,
                                      paraquat_feat,
                                      group_by='treatment',
                                      control=control,
                                      save_dir=stats_dir / 'paraquat-live',
                                      feature_set=feature_list,
                                      pvalue_threshold=0.05,
                                      fdr_method='fdr_bh')
        order = ['BW-nan-nan-N','BW-Paraquat-0.5-N','BW-Paraquat-1.0-N',
                 'fepD-nan-nan-N','fepD-Paraquat-0.5-N','fepD-Paraquat-1.0-N']
        colour_labels = sns.color_palette('tab10', 2)
        colours = [colour_labels[0] if 'BW' in s else colour_labels[1] for s in order]
        colour_dict = {key:col for (key,col) in zip(order, colours)}
        all_in_one_boxplots(paraquat_meta,
                            paraquat_feat,
                            group_by='treatment',
                            control=control,
                            save_dir=plot_dir / 'all-in-one' / 'paraquat-live',
                            ttest_path=stats_dir / 'paraquat-live' / 't-test' / 't-test_results.csv',
                            feature_set=feature_list,
                            pvalue_threshold=0.05,
                            order=order,
                            colour_dict=colour_dict,
                            figsize=(20,10),
                            ylim_minmax=(-20,380),
                            vline_boxpos=[2],
                            fontsize=20,
                            subplots_adjust={'bottom':0.32,'top':0.95,'left':0.05,'right':0.98})
        
        # paraquat (dead)
        paraquat_meta = meta_window[np.logical_and(np.logical_or(meta_window['drug_type']=='Paraquat',
                                                                 meta_window['drug_type'].astype(str)=='nan'),
                                                   meta_window['is_dead']=='Y')]
        paraquat_feat = feat_window.reindex(paraquat_meta.index)
        uv_paraquat_antioxidant_stats(paraquat_meta,
                                      paraquat_feat,
                                      group_by='treatment',
                                      control='BW-nan-nan-Y',
                                      save_dir=stats_dir / 'paraquat-dead',
                                      feature_set=feature_list,
                                      pvalue_threshold=0.05,
                                      fdr_method='fdr_bh')
        order = ['BW-nan-nan-Y','BW-Paraquat-0.5-Y','BW-Paraquat-1.0-Y',
                 'fepD-nan-nan-Y','fepD-Paraquat-0.5-Y','fepD-Paraquat-1.0-Y']
        colour_labels = sns.color_palette('tab10', 2)
        colours = [colour_labels[0] if 'BW' in s else colour_labels[1] for s in order]
        colour_dict = {key:col for (key,col) in zip(order, colours)}
        all_in_one_boxplots(paraquat_meta,
                            paraquat_feat,
                            group_by='treatment',
                            control='BW-nan-nan-Y',
                            save_dir=plot_dir / 'all-in-one' / 'paraquat-dead',
                            ttest_path=stats_dir / 'paraquat-dead' / 't-test' / 't-test_results.csv',
                            feature_set=feature_list,
                            pvalue_threshold=0.05,
                            order=order,
                            colour_dict=colour_dict,
                            figsize=(20,10),
                            ylim_minmax=(-20,380),
                            vline_boxpos=[2],
                            fontsize=20,
                            subplots_adjust={'bottom':0.32,'top':0.95,'left':0.05,'right':0.98})        
        
    metadata = metadata[metadata['window']==0]
    strain_list = list(metadata['treatment'].unique())

    # # timeseries motion mode fraction for each treatment vs BW control
    # selected_strains_timeseries(metadata,
    #                             project_dir=Path(PROJECT_DIR), 
    #                             save_dir=Path(SAVE_DIR) / 'timeseries', 
    #                             strain_list=strain_list,
    #                             group_by='treatment',
    #                             control=control,
    #                             n_wells=6,
    #                             bluelight_stim_type='bluelight',
    #                             video_length_seconds=360,
    #                             bluelight_timepoints_seconds=BLUELIGHT_TIMEPOINTS_SECONDS,
    #                             motion_modes=['forwards','paused','backwards'],
    #                             smoothing=10)
        
    # timeseries plots of speed for each treatment vs control
    # fix the scale across speed timeseries plots to 0-300 um/sec for easier comparison
    plot_timeseries_feature(metadata,
                            project_dir=Path(PROJECT_DIR),
                            save_dir=Path(SAVE_DIR) / 'timeseries-speed',
                            group_by='treatment',
                            control=control,
                            groups_list=strain_list,
                            feature='speed',
                            n_wells=6,
                            bluelight_stim_type='bluelight',
                            video_length_seconds=360,
                            bluelight_timepoints_seconds=BLUELIGHT_TIMEPOINTS_SECONDS,
                            smoothing=10,
                            fps=FPS,
                            ylim_minmax=(-20,330))  
    
    # timeseries plots of fraction of worms on food
    # Use script to label lawns prior to executing these functions
    video_frac_df, leaving_events_df = fraction_on_food(metadata,
                                                        food_coords_dir=Path(SAVE_DIR) / 'lawn_leaving',
                                                        bluelight_stimulus_type='bluelight',
                                                        threshold_duration=THRESHOLD_FILTER_DURATION,
                                                        threshold_movement=THRESHOLD_FILTER_MOVEMENT,
                                                        threshold_leaving_duration=THRESHOLD_LEAVING_DURATION)
    timeseries_on_food(metadata,
                       group_by='treatment',
                       video_frac_df=video_frac_df,
                       control=control,
                       save_dir=Path(SAVE_DIR) / 'lawn_leaving',
                       bluelight_frames=[(i*FPS, j*FPS) for (i, j) in BLUELIGHT_TIMEPOINTS_SECONDS],
                       bluelight_stimulus_type='bluelight',
                       smoothing=20,
                       error=True)
    
    