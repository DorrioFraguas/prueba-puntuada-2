#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keio Antioxidants - Experiments adding antioxidants to E. coli BW25113 (control) and fepD mutant
bacteria of the Keio Collection

@author: sm5911
@date: 18/05/2022

"""

#%% Imports

import numpy as np
import pandas as pd
import seaborn as sns
from tqdm import tqdm
from pathlib import Path
from matplotlib import pyplot as plt
from preprocessing.compile_hydra_data import compile_metadata, process_feature_summaries
from filter_data.clean_feature_summaries import clean_summary_results
from visualisation.plotting_helper import sig_asterix, boxplots_sigfeats
from write_data.write import write_list_to_file
from time_series.time_series_helper import get_strain_timeseries
from time_series.plot_timeseries import plot_timeseries_motion_mode
# from analysis.keio_screen.check_keio_screen_worm_trajectories import check_tracked_objects

from tierpsytools.analysis.statistical_tests import univariate_tests, get_effect_sizes
from tierpsytools.preprocessing.filter_data import select_feat_set

#%% Globals

PROJECT_DIR = "/Volumes/hermes$/Keio_Antioxidants_6WP"
SAVE_DIR = "/Users/sm5911/Documents/Keio_Antioxidants"

BLUELIGHT_WINDOWS_ONLY_TS = True
BLUELIGHT_TIMEPOINTS_MINUTES = [30,31,32]
FPS = 25
VIDEO_LENGTH_SECONDS = 38*60
SMOOTH_WINDOW_SECONDS = 5

N_TOP_FEATS = None # Tierpsy feature set to use: 16, 256, '2k', None
IMAGING_DATES = ['20220418']

nan_threshold_row = 0.8
nan_threshold_col = 0.05
# motion_modes = ['forwards','backwards','stationary']

# WINDOW_DICT_SECONDS = {0:(1830,1860), 1:(1890,1920), 2:(1950,1980)}

window_list = sorted(WINDOW_DICT_SECONDS.keys()) # [8]
feature_set = ['speed_50th']
control_treatment = 'BW-none-nan-H2O'


#%% Functions

def antioxidants_window_stats(metadata, 
                              features, 
                              group_by,
                              control,
                              save_dir,
                              windows=None,
                              feature_set=None, 
                              pvalue_threshold=0.05, 
                              fdr_method='fdr_by'):
    
    """ Pairwise t-tests for each window comparing a feature of worm behaviour on mutant strains 
        vs control 
        
        Parameters
        ----------
        metadata : pandas.DataFrame
        
        features : pandas.DataFrame
            Dataframe of compiled window summaries
            
        group_by : str
            Column name of variable containing control and other groups to compare, eg. 'gene_name'
            
        control : str
            Name of control group in 'group_by' column in metadata
            
        save_dir : str
            Path to directory to save results files
            
        windows : list
            List of window numbers at which to compare strains (corrected for multiple testing)
            
        feat : str
            Feature to test
        
        pvalue_threshold : float
            P-value significance threshold
            
        fdr_method : str
            Multiple testing correction method to use
    """

    # check case-sensitivity
    assert len(metadata[group_by].unique()) == len(metadata[group_by].str.upper().unique())
        
    # subset for list of windows
    if windows is None:
        windows = sorted(metadata['window'].unique())
    else:
        assert all(w in sorted(metadata['window'].unique()) for w in windows)
        metadata = metadata[metadata['window'].isin(windows)]
    
    if feature_set is not None:
        feature_set = [feature_set] if isinstance(feature_set, str) else feature_set
        assert isinstance(feature_set, list)
        assert(all(f in features.columns for f in feature_set))
    else:
        feature_set = features.columns.tolist()
        
    features = features[feature_set].reindex(metadata.index)

    # print mean sample size
    sample_size = metadata.groupby([group_by, 'window']).count()
    print("Mean sample size of %s/window: %d" % (group_by, 
                                                 int(sample_size[sample_size.columns[-1]].mean())))

    n = len(metadata[group_by].unique())

    for window in windows:
        window_meta = metadata[metadata['window']==window]
        window_feat = features.reindex(window_meta.index)
        
        fset = []
        if n > 2:
       
            # Perform ANOVA - is there variation among strains at each window?
            anova_path = Path(save_dir) / 'ANOVA' / 'ANOVA_results_window_{}.csv'.format(window)
            anova_path.parent.mkdir(parents=True, exist_ok=True)
    
            stats, pvals, reject = univariate_tests(X=window_feat, 
                                                    y=window_meta[group_by], 
                                                    control=control, 
                                                    test='ANOVA',
                                                    comparison_type='multiclass',
                                                    multitest_correction=fdr_method,
                                                    alpha=pvalue_threshold,
                                                    n_permutation_test=None)
    
            # get effect sizes
            effect_sizes = get_effect_sizes(X=window_feat,
                                            y=window_meta[group_by],
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
                print("%d significant features found by ANOVA for '%s' in window %d (P<%.2f, %s)" %\
                      (len(fset), group_by, window, pvalue_threshold, fdr_method))
                anova_sigfeats_path = anova_path.parent / 'ANOVA_sigfeats_window_{}.txt'.format(window)
                write_list_to_file(fset, anova_sigfeats_path)
                 
        # Perform t-tests
        stats_t, pvals_t, reject_t = univariate_tests(X=window_feat,
                                                      y=window_meta[group_by],
                                                      control=control,
                                                      test='t-test',
                                                      comparison_type='binary_each_group',
                                                      multitest_correction=fdr_method,
                                                      alpha=pvalue_threshold)
        
        effect_sizes_t = get_effect_sizes(X=window_feat,
                                          y=window_meta[group_by],
                                          control=control,
                                          linked_test='t-test')
        
        stats_t.columns = ['stats_' + str(c) for c in stats_t.columns]
        pvals_t.columns = ['pvals_' + str(c) for c in pvals_t.columns]
        reject_t.columns = ['reject_' + str(c) for c in reject_t.columns]
        effect_sizes_t.columns = ['effect_size_' + str(c) for c in effect_sizes_t.columns]
        ttest_results = pd.concat([stats_t, pvals_t, reject_t, effect_sizes_t], axis=1)
        
        # save results
        ttest_path = Path(save_dir) / 't-test' / 'window_{}_t-test_results.csv'.format(window)
        ttest_path.parent.mkdir(exist_ok=True, parents=True)
        ttest_results.to_csv(ttest_path, header=True, index=True)
        
        nsig = sum(reject_t.sum(axis=1) > 0)
        print("%d significant features between any %s vs %s in window %s (t-test, P<%.2f, %s)" %\
              (nsig, group_by, control, window, pvalue_threshold, fdr_method))
        
    return

def antioxidants_boxplots(metadata, 
                          features, 
                          control,
                          group_by='treatment',
                          feature_set=None,
                          drop_insignificant=True,
                          windows=None,
                          save_dir=None,
                          stats_dir=None,
                          pvalue_threshold=0.05):
    """ boxplots for 30, 31, 32 min BL pulses """
    
    feature_set = features.columns.tolist() if feature_set is None else feature_set
    assert isinstance(feature_set, list) and all(f in features.columns for f in feature_set)
        
    windows = metadata['window'].unique().tolist() if windows is None else windows
    assert isinstance(windows, list) and all(w in metadata['window'].unique() for w in windows)
    
    for window in windows:
        window_meta = metadata[metadata['window']==window]
        window_feat = features.reindex(window_meta.index)
        
        # load t-test results for window
        if stats_dir is not None:
            ttest_path = Path(stats_dir) / 't-test' / 'window_{}_t-test_results.csv'.format(window)
            ttest_df = pd.read_csv(ttest_path, header=0, index_col=0)
            pvals = ttest_df[[c for c in ttest_df.columns if 'pval' in c]]
            pvals.columns = [c.replace('pvals_','') for c in pvals.columns]
        
        boxplots_sigfeats(features=window_feat,
                          y_class=window_meta[group_by],
                          control=control,
                          pvals=pvals if stats_dir is not None else None,
                          z_class=None,
                          feature_set=feature_set,
                          saveDir=Path(save_dir) / 'window_{}'.format(window),
                          drop_insignificant=drop_insignificant,
                          p_value_threshold=pvalue_threshold,
                          scale_outliers=True)
    
    return


def antioxidants_timeseries(metadata,
                            project_dir,
                            save_dir=None,
                            control='BW-none-nan-H2O',
                            group_by='treatment'):
    """ Timeseries plots for worm motion mode on BW and fepD bacteria with and without the 
        addition of antioxidants: Trolox (vitamin E), trans-resveratrol, vitamin C and NAC
    """
    
    # Each treatment vs BW control    
    control_list = np.repeat(control, metadata[group_by].nunique()-1)
    treatment_list = [t for t in sorted(metadata[group_by].unique()) if t!= control]
    
    # control_list = list(np.concatenate([np.array(['fepD-none-nan-H2O']),
    #                                     np.repeat(control, 12)]))
    # treatment_list = ['fepD-none-nan-EtOH','fepD-none-nan-H2O','BW-none-nan-EtOH',
    #                   'BW-vitC-500.0-H2O','fepD-vitC-500.0-H2O',
    #                   'BW-NAC-500.0-H2O','BW-NAC-1000.0-H2O',
    #                   'fepD-NAC-500.0-H2O','fepD-NAC-1000.0-H2O',
    #                   'BW-trolox-500.0-EtOH','fepD-trolox-500.0-EtOH',
    #                   'BW-trans-resveratrol-500.0-EtOH','fepD-trans-resveratrol-500.0-EtOH']
    # title_list = ['fepD: H2O vs EtOH','BW vs fepD','BW: H2O vs EtOH',
    #               'BW vs BW + vitC','BW vs fepD + vitC',
    #               'BW vs BW + NAC','BW vs BW + NAC',
    #               'BW vs fepD + NAC','BW vs fepD + NAC',
    #               'BW vs BW + trolox','BW vs fepD + trolox',
    #               'BW vs BW + trans-resveratrol','BW vs fepD + trans-resveratrol']
    # labs = [('fepD + H2O', 'fepD + EtOH'),('BW', 'fepD'),('BW + H2O', 'BW + EtOH'),
    #         ('BW', 'BW + vitC (500ug/mL)'),('BW', 'fepD + vitC (500ug/mL)'),
    #         ('BW', 'BW + NAC (500ug/mL)'),('BW', 'BW + NAC (1000ug/mL)'),
    #         ('BW', 'fepD + NAC (500ug/mL)'),('BW', 'fepD + NAC (1000ug/mL)'),
    #         ('BW', 'BW + trolox (500ug/mL in EtOH)'),('BW', 'fepD + trolox (500ug/mL in EtOH)'),
    #         ('BW', 'BW + trans-resveratrol (500ug/mL in EtOH)'),
    #         ('BW', 'fepD + trans-resveratrol (500ug/mL in EtOH)')]
    
    # for control, treatment, title, lab in tqdm(zip(control_list, treatment_list, title_list, labs)):
    plt.close('all')
    for control, treatment in tqdm(zip(control_list, treatment_list)):
        
        # get timeseries for control data
        control_ts = get_strain_timeseries(metadata[metadata[group_by]==control], 
                                           project_dir=project_dir, 
                                           strain=control,
                                           group_by=group_by,
                                           n_wells=6,
                                           save_dir=Path(save_dir) / 'Data' / control,
                                           verbose=False,
                                           return_error_log=False)
        
        # get timeseries for treatment data
        treatment_ts = get_strain_timeseries(metadata[metadata[group_by]==treatment], 
                                             project_dir=project_dir, 
                                             strain=treatment,
                                             group_by=group_by,
                                             n_wells=6,
                                             save_dir=Path(save_dir) / 'Data' / treatment,
                                             verbose=False)
 
        colour_dict = dict(zip([control, treatment], sns.color_palette("pastel", 2)))
        bluelight_frames = [(i*60*FPS, i*60*FPS+10*FPS) for i in BLUELIGHT_TIMEPOINTS_MINUTES]

        for mode in motion_modes:
                    
            print("Plotting timeseries '%s' fraction for '%s' vs '%s'..." %\
                  (mode, treatment, control))
    
            fig, ax = plt.subplots(figsize=(15,5), dpi=200)
    
            ax = plot_timeseries_motion_mode(df=control_ts,
                                             window=SMOOTH_WINDOW_SECONDS*FPS,
                                             error=True,
                                             mode=mode,
                                             max_n_frames=VIDEO_LENGTH_SECONDS*FPS,
                                             title=None,
                                             saveAs=None,
                                             ax=ax,
                                             bluelight_frames=bluelight_frames,
                                             colour=colour_dict[control],
                                             alpha=0.25)
            
            ax = plot_timeseries_motion_mode(df=treatment_ts,
                                             window=SMOOTH_WINDOW_SECONDS*FPS,
                                             error=True,
                                             mode=mode,
                                             max_n_frames=VIDEO_LENGTH_SECONDS*FPS,
                                             title=None,
                                             saveAs=None,
                                             ax=ax,
                                             bluelight_frames=bluelight_frames,
                                             colour=colour_dict[treatment],
                                             alpha=0.25)
        
            xticks = np.linspace(0, VIDEO_LENGTH_SECONDS*FPS, int(VIDEO_LENGTH_SECONDS/60)+1)
            ax.set_xticks(xticks)
            ax.set_xticklabels([str(int(x/FPS/60)) for x in xticks])   
            ax.set_xlabel('Time (minutes)', fontsize=15, labelpad=10)
            ax.set_ylabel('Fraction {}'.format(mode), fontsize=15, labelpad=10)
            ax.legend([control, treatment], fontsize=12, frameon=False, loc='best')
            plt.subplots_adjust(left=0.08, bottom=0.18, right=0.97, top=0.95)
    
            if BLUELIGHT_WINDOWS_ONLY_TS:
                ax.set_xlim([min(BLUELIGHT_TIMEPOINTS_MINUTES)*60*FPS-60*FPS, 
                             max(BLUELIGHT_TIMEPOINTS_MINUTES)*60*FPS+70*FPS])
    
            if save_dir is not None:
                ts_plot_dir = Path(save_dir) /\
                    ('Plots/bluelight' if BLUELIGHT_WINDOWS_ONLY_TS else 'Plots') / treatment
                ts_plot_dir.mkdir(exist_ok=True, parents=True)
                save_path = ts_plot_dir / '{0}_{1}.pdf'.format(treatment, mode)
                print("Saving to: %s" % save_path)
                plt.savefig(save_path)  
                plt.close()

    return


#%% Main
if __name__ == '__main__':
    
    aux_dir = Path(PROJECT_DIR) / 'AuxiliaryFiles'    
    results_dir =  Path(PROJECT_DIR) / 'Results'
    
    metadata_path_local = Path(SAVE_DIR) / 'clean_metadata.csv'
    features_path_local = Path(SAVE_DIR) / 'clean_features.csv'
    
    if not metadata_path_local.exists() or not features_path_local.exists():
    
        # load metadata    
        metadata, metadata_path = compile_metadata(aux_dir, 
                                                   imaging_dates=IMAGING_DATES, 
                                                   add_well_annotations=False, 
                                                   n_wells=6)
        
        features, metadata = process_feature_summaries(metadata_path, 
                                                       results_dir, 
                                                       compile_day_summaries=True, 
                                                       imaging_dates=IMAGING_DATES, 
                                                       align_bluelight=False, 
                                                       window_summaries=True,
                                                       n_wells=6)
     
        # Subset results (rows) to remove entries for wells with unknown strain data for 'gene_name'
        if metadata['food_type'].isna().any():
            n = metadata.shape[0]
            metadata = metadata.loc[~metadata['food_type'].isna(),:]
            features = features.reindex(metadata.index)
            print("%d entries removed with no gene name metadata" % (n - metadata.shape[0]))
     
        # Create is_bad_well column - refer to manual metadata for bad 35mm petri plates
        metadata['is_bad_well'] = False
    
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
            
    # Load Tierpsy feature set + subset (columns) for selected features only
    if feature_set is not None:
        assert all(f in features.columns for f in feature_set)
    elif N_TOP_FEATS is not None:
        features = select_feat_set(features, 'tierpsy_{}'.format(N_TOP_FEATS), append_bluelight=False)
        features = features[[f for f in features.columns if 'path_curvature' not in f]]
        feature_set = features.columns.tolist()
    else:
        feature_set = features.columns.tolist()
        
    metadata['imaging_plate_drug_conc'] = metadata['imaging_plate_drug_conc'].astype(str)
    metadata['treatment'] = metadata[['food_type','drug_type','imaging_plate_drug_conc','solvent']
                                     ].astype(str).agg('-'.join, axis=1)
    
    antioxidants_window_stats(metadata, 
                              features, 
                              control=control_treatment,
                              group_by='treatment',
                              save_dir=Path(SAVE_DIR) / 'Stats' / ('All_features' if N_TOP_FEATS is None 
                                                                   else 'Top{}'.format(N_TOP_FEATS)),
                              windows=window_list,
                              feature_set=feature_set,
                              pvalue_threshold=0.05,
                              fdr_method='fdr_by')
        
    antioxidants_boxplots(metadata, 
                          features, 
                          control=control_treatment,
                          group_by='treatment',
                          feature_set=feature_set,
                          drop_insignificant=False,
                          windows=window_list,
                          save_dir=Path(SAVE_DIR) / 'Plots' / ('All_features' if N_TOP_FEATS is None 
                                                               else 'Top{}'.format(N_TOP_FEATS)),
                          stats_dir=Path(SAVE_DIR) / 'Stats' / ('All_features' if N_TOP_FEATS is None 
                                                                else 'Top{}'.format(N_TOP_FEATS)),
                          pvalue_threshold=0.05)
    
    # subset metadata for a single window to avoid duplicate filename in metadata for timeseries
    metadata = metadata.query("window==0")
    # antioxidants_timeseries(metadata, 
    #                         control=control_treatment,
    #                         group_by='treatment',
    #                         project_dir=Path(PROJECT_DIR),
    #                         save_dir=Path(SAVE_DIR) / 'timeseries')
    # TODO: Get timeseries for speed
    
    # # Check length/area of tracked objects - prop bad skeletons
    # results_df = check_tracked_objects(metadata, 
    #                                    length_minmax=(200, 2000), 
    #                                    width_minmax=(20, 500),
    #                                    save_to=Path(SAVE_DIR) / 'tracking_checks.csv')

