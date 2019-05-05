#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRIPT: FOOD CHOICE

A script written to analyse the food choice assay videos and Tierpsy-generated 
feature summary data. It calculates, plots and saves results for worm food preference
(for each video separately).

@author: sm5911
@date: 21/03/2019

"""

# GENERAL IMPORTS / DEPENDENCIES
import os, time#, sys
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import patches as mpatches

# CUSTOM IMPORTS
#sys.path.insert(0, '/Users/sm5911/Documents/GitHub/PhD_Project/Python') # OPTIONAL: Path to GitHub functions
from Calculate import foodchoice, summarystats
from Plot import hexcolours, plotpie, plottimeseries
from Save import savefig
from Find import changepath

#%% PRE-AMBLE

# Global variables
PROJECT_ROOT_DIR = '/Volumes/behavgenom$/Saul/FoodChoiceAssay/' # Project working directory
DATA_DIR = PROJECT_ROOT_DIR.replace('Saul', 'Priota/Data') # Location of features files

# Plot parameters
fps = 25 # frames per second
smooth_window = 25*60*2 # 2-minute moving average window for time-series plot smoothing

# Conduct analysis on new videos only?
NEW = True

# Read metadata
fullMetaData = pd.read_csv(os.path.join(PROJECT_ROOT_DIR, "fullmetadata.csv"), header=0, index_col=0)

if NEW:
    fullMetaData = fullMetaData[fullMetaData['worm number']==10]

n_files = len(fullMetaData['filename'])
print("%d video file entries found in metadata." % n_files)

# Extract assay information
pretreatments = list(np.unique(fullMetaData['Prefed_on']))
assaychoices = list(np.unique(fullMetaData['Food_Combination']))
treatments = list(np.unique([assay.split('/') for assay in assaychoices]))
treatments.insert(len(treatments),"None") # treatments = [OP50, HB101, None]
concentrations = list(np.unique(fullMetaData['Food_Conc']))

# Plot parameters
colours = hexcolours(len(treatments)) # Create a dictionary of colours for each treatment (for plotting)
colour_dict = {key: value for (key, value) in zip(treatments, colours)}

#%% CALCULATE MEAN NUMBER OF WORMS ON/OFF FOOD IN EACH FRAME (FOR EACH VIDEO SEPARATELY)
# - PROPORTION of total worms in each frame 
errorlog = 'ErrorLog_FoodChoice.txt'
FAIL = []
tic = time.time()
for i, maskedfilepath in enumerate(fullMetaData['filename']):
    toc = time.time()
    # Extract file information
    file_info = fullMetaData.iloc[i,:]
    date = file_info['date(YEARMODA)']
    conc = file_info['Food_Conc']
    assaychoice = file_info['Food_Combination']
    prefed = file_info['Prefed_on']
    print("\nProcessing file: %d\n%s\nAssay:  %s\nConc:   %.3f\nPrefed: %s" % (i + 1,\
          maskedfilepath, assaychoice, conc, prefed))
    try:
        # Specify file paths
        onfoodpath = changepath(maskedfilepath, returnpath='onfood')
        foodchoicepath = changepath(maskedfilepath, returnpath='foodchoice')

        # Read on/off food results
        onfood_df = pd.read_csv(onfoodpath, header=0, index_col=0)
        
        # Calculate mean + count number of worms on/off food in each frame
        # NB: Store proportions, along with total nworms, ie. mean (worms per frame) and later calculate mean (per frame across videos)
        choice_df = foodchoice(onfood_df, mean=True, tellme=True)
        
        # Save food choice results
        directory = os.path.dirname(foodchoicepath)
        if not os.path.exists(directory):
            os.makedirs(directory)
        choice_df.to_csv(foodchoicepath)
        print("Food choice results saved. \n(Time taken: %d seconds)\n" % (time.time() - toc))
    except:
        FAIL.append(maskedfilepath)
        print("ERROR! Failed to calculate food preference in file:\n %s\n" % maskedfilepath)
print("Complete!\n(Total time taken: %d seconds.)\n" % (time.time() - tic))

# If errors, save error log to file
if FAIL:
    fid = open(os.path.join(PROJECT_ROOT_DIR, errorlog), 'w')
    print(FAIL, file=fid)
    fid.close()

#%% FOOD CHOICE SUMMARY STATS + PIE/BOX PLOTS (FOR EACH VIDEO SEPARATELY)
# - Calculate summary statistics for mean proportion worms feeding in each video
# - Plot and save pie charts + box plots of worm food preference

# =============================================================================
# # NB: Cannot pre-allocate full results dataframe to store food choice mean 
# #     proportion feeding per frame across all videos due to file size = 23GB
# colnames = ['filename','worm_number','Food_Conc','Food_Combination','Prefed_on',\
#             'Acclim_time_s','frame_number','Food','Mean']
# results_df = pd.DataFrame(columns=colnames)
# =============================================================================
    
tic = time.time()
for i, maskedfilepath in enumerate(fullMetaData['filename']):
    # Extract file information
    file_info = fullMetaData.iloc[i,:]
    date = file_info['date(YEARMODA)']
    conc = file_info['Food_Conc']
    assaychoice = file_info['Food_Combination']
    prefed = file_info['Prefed_on']
    print("Processing file: %d\n%s\nAssay:  %s\nConc:   %.3f\nPrefed: %s" % (i + 1,\
          maskedfilepath, assaychoice, conc, prefed))
    
    # Specify file paths
    foodchoicepath = changepath(maskedfilepath, returnpath='foodchoice')
    statspath = changepath(maskedfilepath, returnpath='summary')
    pieplotpath = changepath(maskedfilepath, returnpath='plots', figname='PiePlot.eps')
    boxplotpath = changepath(maskedfilepath, returnpath='plots', figname='BoxPlot.eps')
    try:
        # READ FOOD CHOICE RESULTS (csv)
        choice_df = pd.read_csv(foodchoicepath, header=0, index_col=0)
        
        # CALCULATE FOOD CHOICE SUMMARY STATISTICS
        feeding_stats = summarystats(choice_df)
        
        #NB: Save summary stats?
        #feeding_stats.to_csv(statspath) # Save to CSV

        # Define plot labels/colours
        colnames = list(choice_df.columns)
        labels = [lab.split('_')[0] for lab in colnames]
        colours = [colour_dict[treatment] for treatment in labels]
        # Specify seaborn colour palette
        RGBAcolours = sns.color_palette(colours)
        palette = {key: val for key, val in zip(colnames, RGBAcolours)}
        # sns.palplot(sns.color_palette(values))
        
        # PLOT PIE CHART OF MEAN ON/OFF FOOD
        df_pie = feeding_stats.loc['mean']
        df_pie = df_pie.loc[df_pie!=0] # Remove any empty rows
        plt.close("all")
        fig = plotpie(df_pie, rm_empty=False, show=True, labels=labels,\
                      colors=colours, textprops={'fontsize': 15}, startangle=90,\
                      wedgeprops={'edgecolor': 'k', 'linewidth': 1,\
                                  'linestyle': 'solid', 'antialiased': True})
        # Save pie charts
        directory = os.path.dirname(pieplotpath)
        if not os.path.exists(directory):
            os.makedirs(directory)
        savefig(pieplotpath, tellme=False)
        
        # Convert to long format, collate info
        choice_df['frame_number'] = choice_df.index
        choice_df_long = choice_df.melt(id_vars='frame_number', value_vars=choice_df.columns[:-1],\
                                        var_name='Food', value_name='Mean')
        
        # Append file info
        choice_df_long['filename'] = maskedfilepath
        choice_df_long['worm_number'] = file_info['worm number']
        choice_df_long['Food_Conc'] = conc
        choice_df_long['Food_Combination'] = assaychoice
        choice_df_long['Prefed_on'] = prefed
        choice_df_long['Acclim_time_s'] = file_info['Acclim_time_s']
            
        # Box plots (Seaborn): Mean proportion of worms feeding on each food
        plt.close("all")
        fig, ax = plt.subplots(figsize=(9,7))
        ax = sns.boxplot(x='Food', y='Mean', hue='Food', data=choice_df_long, palette=palette, dodge=False)
        # NB: Could also produce violinplots, but why not swarmplots? Too many points?
        # ax = sns.violinplot(x='Food', y='Mean', hue='Food', data=choice_df_long, palette=palette, dodge=False)
        ax.set_ylim(-0.1,1.1)
        ax.set_xlim(-1,len(treatments)+0.25)
        ax.set_xlabel("Food",fontsize=20)
        ax.set_ylabel("Mean Proportion Feeding",fontsize=20)
        ax.xaxis.labelpad = 15; ax.yaxis.labelpad = 15
        ax.tick_params(labelsize=13, pad=5)
        fig.tight_layout(rect=[0.02, 0.07, 0.95, 0.95])
        plt.text(0.03, 0.93, "{0} worms".format(file_info['worm number']), transform=ax.transAxes, fontsize=20)
        plt.text(len(treatments)+0.25, -0.35, "Prefed on: {0}".format(prefed),\
                 horizontalalignment='right', fontsize=25)
        plt.legend(loc="upper right", borderaxespad=0.4, frameon=False, fontsize=15)
        plt.show(); plt.pause(0.0001)
            
        # Save box plots
        savefig(boxplotpath, saveFormat='eps', tellme=False)
        print("Plots saved.\n")
        
# =============================================================================
#         # Append to full results dataframe
#         results_df = results_df.append(choice_df_long[colnames])
# =============================================================================
    except:
        print("Error processing file:\n%s" % maskedfilepath)
        continue
print("Done.\n(Time taken: %d seconds.)" % (time.time() - tic))

# =============================================================================
# size = sys.getsizeof(results_df)
# # File size is too big! Not a good idea to save as full results file
# =============================================================================


#%% Time-series plots of proportion feeding through time (FOR EACH VIDEO SEPARATELY)

tic = time.time()
for i, maskedfilepath in enumerate(fullMetaData['filename']):
    toc = time.time()
    # Extract file information
    file_info = fullMetaData.iloc[i,:]
    conc = file_info['Food_Conc']
    assaychoice = file_info['Food_Combination']
    prefed = file_info['Prefed_on']
    print("\nProcessing file: %d\n%s\nAssay:  %s\nConc:   %.3f\nPrefed: %s" % (i + 1,\
          maskedfilepath, assaychoice, conc, prefed))
    
    # Specify file paths
    foodchoicepath = changepath(maskedfilepath, returnpath='foodchoice')
    plotpath = changepath(maskedfilepath, returnpath='plots', figname='FoodChoiceTS.eps') # Path to save time series plots

    # READ FOOD CHOICE (COUNT) RESULTS
    choice_df = pd.read_csv(foodchoicepath, header=0, index_col=0)
    
    # Shift plot to include acclimation time before assay recording (t=0 is pick time)
    acclim = int(file_info['Acclim_time_s'] * fps)
    choice_df.index = choice_df.index + acclim 
    
    # PLOT TIME-SERIES ON/OFF FOOD (count)
    plt.close("all")
    fig = plottimeseries(choice_df, colour_dict, window=smooth_window, acclimtime=acclim,\
                         legend=True, ls='-', figsize=(12,6))
    
    # SAVE TIME SERIES PLOTS
    directory = os.path.dirname(plotpath)
    if not os.path.exists(directory):
        os.makedirs(directory)
    savefig(plotpath, saveFormat='eps', tellme=False)
    print("Time series plots saved.\n(Time taken: %d seconds.)\n" % (time.time() - toc))
print("Complete!\n(Total time taken: %d seconds.)\n" % (time.time() - tic))


#%% FIGURE 1 - Box plots of food choice (Grouped by prefed on, assay type, and concentration)
# - Subset results by grouping files by assay type (control/choice experiment) and by food concentration

tic = time.time()
# Group files in metadata by prefed, assaychoice and concentration treatment combinations
groupedMetaData = fullMetaData.groupby(['Prefed_on','Food_Combination','Food_Conc'])

# For each prefood-assaychoice-concentration treatment combination
for p, prefood in enumerate(pretreatments):
    # Initialise plot for prefed group
    plt.close("all")
    fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(16,10), sharey=True) # 15 subplots (3 assay types, 5 assay concentrations)
    for a, assay in enumerate(assaychoices):
        for c, conc in enumerate(concentrations):
            try:
                # Get prefood-assaychoice-concentration group
                df_conc = groupedMetaData.get_group((prefood,assay,conc))
                
                # Get group info
                info = df_conc.iloc[0,:]
                
                if df_conc.shape[0] == 1:
                    # Read food choice data (mean proportion feeding)
                    foodchoicepath = changepath(info['filename'], returnpath='foodchoice')
                    df = pd.read_csv(foodchoicepath, header=0, index_col=0)
                    
                elif df_conc.shape[0] > 1:
                    # Read food choice data for each file and compile into df for plotting
                    df = pd.DataFrame()
                    for row in range(df_conc.shape[0]):
                        info = df_conc.iloc[row,:]
                        foodchoicepath = changepath(info['filename'], returnpath='foodchoice')
                        tmp_df = pd.read_csv(foodchoicepath, header=0, index_col=0)
                        if df.empty:
                            df = tmp_df
                        else:
                            df = df.append(tmp_df, sort=True)
                    
                # Plot labels/colours
                colnames = list(df.columns)
                
                labels = [lab.split('_')[0] for lab in colnames]
                colours = [colour_dict[treatment] for treatment in labels]
                
                # Seaborn colour palette
                RGBAcolours = sns.color_palette(colours)
                palette = {key: val for key, val in zip(colnames, RGBAcolours)}
                # sns.palplot(sns.color_palette(values))
        
                # Convert to long format
                df['frame_number'] = df.index
                df_long = df.melt(id_vars='frame_number', value_vars=df.columns[:-1],\
                                  var_name='Food', value_name='Mean')
                
                # Plot Seaborn boxplots
                sns.boxplot(x='Food', y='Mean', hue='Food', ax=axs[a,c], data=df_long, palette=palette, dodge=False)
                axs[a,c].get_legend().set_visible(False)
                axs[a,c].set_ylabel('')    
                axs[a,c].set_xlabel('')
                axs[a,c].set_xticklabels(labels=labels)
                axs[a,c].set_ylim(-0.15, 1.15)
                axs[a,c].set_xlim(-0.9,len(np.unique(df_long['Food'])))
                axs[a,c].text(0.81, 0.9, ("n={0}".format(df_conc.shape[0])),\
                              transform=axs[a,c].transAxes, fontsize=12)
                if a == 0:
                    axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
                                  horizontalalignment='center', fontsize=18,\
                                  transform=axs[a,c].transAxes)
                if c == 0 and a == 1:
                    axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=30, fontsize=20)
            except Exception as e:
                print("No videos found for concentration: %s\n(Assay: %s, Prefed on: %s)\n" % (e, assay, prefood))
                axs[a,c].axis('off')
                axs[a,c].text(0.81, 0.9, "n=0", fontsize=12, transform=axs[a,c].transAxes)
                if a == 0:
                    axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
                                  horizontalalignment='center', fontsize=18,\
                                  transform=axs[a,c].transAxes)
                if c == 0 and a == 1:
                    axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=30, fontsize=20)
    plt.text(0.95, -0.6, "Prefed on: {0}".format(prefood), horizontalalignment='center', fontsize=20)
    patches = []
    for i, (key, value) in enumerate(colour_dict.items()):
        patch = mpatches.Patch(color=value, label=key)
        patches.append(patch)
    fig.legend(handles=patches, labels=list(colour_dict.keys()), loc="upper right", borderaxespad=0.4,\
               frameon=False, fontsize=15)
    fig.tight_layout(rect=[0.02, 0.07, 0.9, 0.95])
    fig.subplots_adjust(hspace=0.2, wspace=0.2)    
    plt.show(); plt.pause(2)
    # Save figure 1
    fig_name = "FoodChoiceBox_prefed" + prefood + ".eps"
    figure_out = os.path.join(PROJECT_ROOT_DIR, "Results", "Plots", fig_name)
    savefig(figure_out, saveFormat='eps', tight_layout=False)
print("Complete!\n(Time taken: %d seconds)" % (time.time() - tic))

#%% FIGURE 2 
# - OPTIONAL: Plot as fraction of a constant total?

#%% FIGURE 3 - Time series plots of food choice by concentration and by assay type (GROUPED BY ASSAY/CONC)
# Plot time series plots - proportion on-food through time  

# TODO: Shift to Account for acclim time
# TODO: Put error bars on time-series => df_std
# TODO: Acclimation: crop for boxplot, shift for time-series
# TODO: std errorbars on TS plots:
# -- Add time column (secs)
# -- Bin columns by small index/frame intervals (~1s to 2min), and average by within-bin = FOR EACH VID
# -- Average across different videos = Append to growing df, then take mean + std (by rounded time/index) (could add file_id column for easy plot groupby)
# -- BEFORE YOU CALL plottimeseries (give mean + std)
# NB: DONT DO STATS AFTER ROLLING WINDOW!

tic = time.time()
# Group files in metadata by prefed, assaychoice and concentration treatment combinations
groupedMetaData = fullMetaData.groupby(['Prefed_on','Food_Combination','Food_Conc'])

# For each prefood-assaychoice-concentration treatment combination
for p, prefood in enumerate(pretreatments):
    # Initialise plot for prefed group
    plt.close("all")
    xmax = 180000
    fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(15,10), sharex=True) # 15 subplots (3 assay types, 5 assay concentrations)
    for a, assay in enumerate(assaychoices):
        for c, conc in enumerate(concentrations):
            try:
                # Get prefood-assaychoice-concentration group
                df_conc = groupedMetaData.get_group((prefood,assay,conc))
                
                # Get group info
                info = df_conc.iloc[0,:]
                
                # If single file, read food choice data (mean proportion feeding)
                if df_conc.shape[0] == 1:
                    foodchoicepath = changepath(info['filename'], returnpath='foodchoice')
                    df = pd.read_csv(foodchoicepath, header=0, index_col=0)   
                    
                    # Shift df indices to account for acclimation period prior 
                    # to assay recording (t0 = pick time)
                    acclim = int(info['Acclim_time_s'] * fps)
                    df.index = df.index + acclim
                    
                # If multiple files, read food choice data for each file and compile into df for plotting
                elif df_conc.shape[0] > 1:
                    df = pd.DataFrame()
                    for row in range(df_conc.shape[0]):
                        info = df_conc.iloc[row,:]
                        foodchoicepath = changepath(info['filename'], returnpath='foodchoice')
                        tmp_df = pd.read_csv(foodchoicepath, header=0, index_col=0)  
                        
                        # Shift df indices to account for acclimation period prior 
                        # to assay recording (t0 = pick time)
                        acclim = int(info['Acclim_time_s'] * fps)
                        tmp_df.index = tmp_df.index + acclim
                        
                        if df.empty:
                            df = tmp_df
                        else:
                            df = df.append(tmp_df, sort=True)
                            
                # Mean per frame across videos
                df['frame'] = df.index
                df_mean = df.groupby('frame').mean()
                df_std = df.groupby('frame').std()

                # Remove erroneous frames where on/off food does not sum to 1
                frames_to_rm = np.where(np.round(df_mean.sum(axis=1),decimals=5)!=1)[0]
                if frames_to_rm.size != 0:
                    print("%d frames found in which feeding proportions do not sum to 1." % len(frames_to_rm))
                
                # Time series plots
                plottimeseries(df_mean, colour_dict, window=smooth_window,\
                               legend=False, annotate=False, ax=axs[a,c], yerr=df_std) # acclimtime=acclim
                
                # Add number of replicates (videos) for each treatment combination
                axs[a,c].text(0.79, 0.9, ("n={0}".format(df_conc.shape[0])),\
                              transform=axs[a,c].transAxes, fontsize=13)
                
                # Set axis limits
                if max(df_mean.index) > xmax:
                    xmax = max(df_mean.index)
                axs[a,c].set_xlim(-xmax/15, np.round(xmax,-5))
                axs[a,c].set_ylim(-0.1, 1.15)
                                
                # Set column labels on first row
                if a == 0:
                    axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
                                  horizontalalignment='center', fontsize=18,\
                                  transform=axs[a,c].transAxes)
                    
                # Set main y axis label + ticks along first column of plots
                if c == 0:
                    yticks = list(np.round(np.linspace(0,1,num=6,endpoint=True),decimals=1))
                    axs[a,c].set_yticks(yticks)
                    axs[a,c].set_yticklabels(yticks)
                    if a == 1:
                        axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=25, fontsize=20)
                else:
                    axs[a,c].set_yticklabels([])
                    
                # Set main x axis label + ticks along final row of plots
                if a == len(assaychoices) - 1:
                    xticks = np.linspace(0,np.round(xmax,-5),num=5,endpoint=True).astype(int)
                    axs[a,c].set_xticks(xticks)
                    xticklabels = np.ceil(np.linspace(0,np.round(xmax,-5),num=5,endpoint=True)/fps/1800)/2
                    xticklabels = [str(int(lab*60)) for lab in xticklabels]
                    axs[a,c].set_xticklabels(xticklabels)
                    if c == 2:
                        axs[a,c].set_xlabel("Time (minutes)", labelpad=25, fontsize=20)
                else:
                    axs[a,c].set_xticklabels([])

            except Exception as e:
                # Empty plots
                print("No videos found for concentration: %s\n(Assay: %s, Prefed on: %s)\n" % (e, assay, prefood))
                
                # Add number of replicates (videos) for each treatment combination
                axs[a,c].text(0.79, 0.9, "n=0", fontsize=13, transform=axs[a,c].transAxes)
                                
                # Set column labels on first row
                if a == 0:
                    axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
                                  horizontalalignment='center', fontsize=18,\
                                  transform=axs[a,c].transAxes)
                axs[a,c].axis('off')
    
    # Add 'prefed on' to multiplot
    plt.text(max(df_mean.index), -0.7, "Prefed on: {0}".format(prefood), horizontalalignment='right', fontsize=30)
    
    # Add legend
    patches = []
    for key, value in colour_dict.items():
        patch = mpatches.Patch(color=value, label=key)
        patches.append(patch)
    fig.legend(handles=patches, labels=treatments, loc="upper right", borderaxespad=0.4,\
               frameon=False, fontsize=15)
    
    # Tight-layout + adjustments
    fig.tight_layout(rect=[0.02, 0.02, 0.9, 0.93])
    fig.subplots_adjust(hspace=0.2, wspace=0.2)
    plt.show(); plt.pause(1)
    
    # Save figure 3
    fig_name = "FoodChoiceTS_prefed" + prefood + ".eps"
    figure_out = os.path.join(PROJECT_ROOT_DIR, "Results", "Plots", fig_name)
    savefig(figure_out, saveFormat='eps', tight_layout=False)
print("Complete!\n(Time taken: %d seconds)" % (time.time() - tic))

#%%
#        df_count_long = df_count.melt(id_vars='frame_number', value_vars=df_count.columns[1:], var_name='Food', value_name='Count')
        # Seaborn Swarm plots?? too many observations to plot swarm!!!
#        sns.swarmplot(x="Food", y="Mean", data=df_mean_long)
#        ax = sns.swarmplot(x=Food, , data=df_mean_long)
#        sns.swarmplot(data=df_mean)
#        df_mean['frame_number'] = df_mean.index
#        df_mean_long = df_mean.melt(id_vars='frame_number', value_vars=df_mean.columns[:-1], var_name='Food', value_name='Mean')


# - Appends mean summary statistics to metadata + saves meta-results file 
#resultcolumns = ['MeanFood_L', 'MeanFood_R', 'MeanNone', 'CountFood_L', 'CountFood_R', 'CountNone']
#out_df = pd.DataFrame(index=fullMetaData.index, columns=resultcolumns)
    # Record MEAN values in out dataframe + append to metadata => metaresults?
    #out_df.iloc[filemeta.index,:] = feeding_stats_mean.loc['mean'].values
#print("Appending food preference results to metadata..")
#df = pd.concat([fullMetaData, out_df], axis=1, ignore_index=False)
#df.to_csv(os.path.join(PROJECT_ROOT_DIR, "Results", "fullresults.csv")

#group_prefed = fullMetaData.groupby('Prefed_on')
#for p, prefood in enumerate(pretreatments):
#    df_prefed = group_prefed.get_group(prefood)
#    plt.close("all")
#    fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(16,10)) # OPTIONAL: sharey=True
#    group_assaychoice = df_prefed.groupby('Food_Combination')
#    for a, assay in enumerate(assaychoices):
#        df_assay = group_assaychoice.get_group(assay) # Group by assay type
#        group_conc = df_assay.groupby('Food_Conc')
#        concs = np.unique(df_assay['Food_Conc'])
#        for c, conc in enumerate(concs):
#            # PLOT FOOD CHOICE BY CONCENTRATION + ASSAY TYPE (15x subplots)
#            try:
#                df_conc = group_conc.get_group(conc)
#                info = df_conc.iloc[0,:]
#                xlabs = info['Food_Combination'].split('/'); xlabs.insert(len(xlabs), "None")
#                if df_conc.shape[0] < 3:
#                    # Plot points not boxplots in cases where n = 1 or 2 videos only
#                    for i in range(len(treatments)):
#                        axs[a,c].scatter(x=np.repeat((i + 1),df_conc.shape[0]),\
#                                         y=df_conc[df_conc.columns[-len(treatments):][i]],\
#                                         marker='.', s=150, color=colour_dict[xlabs[i]],\
#                                         linewidths=1, edgecolors='k')
#                    axs[a,c].set_xticks(ticks=list(np.round(np.arange(1,4,1))))
#                    axs[a,c].set_xlim(0.5,3.5)
#                else:
#                    # Plot boxplots of replicate means (each video) for prop on/off food, by assay data and concentration
#                    bp_dict = df_conc.plot(y=df_conc.columns[-len(treatments):], kind='box',\
#                                           ax=axs[a,c], patch_artist=True, return_type='dict')
#                    # COLOUR BOXPLOTS BY FOOD
#                    for i, box in enumerate(bp_dict['boxes']):
#                        box.set_edgecolor('black')
#                        box.set_facecolor(colour_dict[xlabs[i]])
#                    for item in ['whiskers', 'fliers', 'medians', 'caps']:
#                        plt.setp(bp_dict[item], color='black')
#                axs[a,c].set_xticklabels(labels=xlabs, fontsize=13)
#                axs[a,c].set_yticks(ticks=list(np.round(np.arange(0,1.1,0.2), decimals=1)))
#                axs[a,c].set_yticklabels(labels=list(np.round(np.arange(0,1.1,0.2), decimals=1)), fontsize=13)
#                axs[a,c].set_ylim(-0.05,1.05)
#                axs[a,c].text((len(xlabs)-0.2), 0.93, ("n={0}".format(df_conc.shape[0])), fontsize=15)
#                if a == 0:
#                    axs[a,c].text(2, 1.15, ("conc={0}".format(info['Food_Conc'])),\
#                                  horizontalalignment='center', fontsize=18)
#                if c == 0 and a == 1:
#                    axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=30, fontsize=20)
#            except Exception as e:
#                print(e)
#                continue
#    patches = []
#    for key, value in colour_dict.items():
#        patch = mpatches.Patch(color=value, label=key)
#        patches.append(patch)
#    fig.legend(handles=patches, labels=treatments, loc="upper right", borderaxespad=0.4,\
#               frameon=False, fontsize=15)
#    fig.tight_layout(rect=[0.02, 0, 0.9, 0.95])
#    fig.subplots_adjust(hspace=0.25, wspace=0.25)
#    plt.show()
#    # SAVE FIGURE 1
#    fig_name = "FoodChoiceBox_prefed" + prefood + ".png"
#    figure_out = os.path.join(PROJECT_ROOT_DIR, "Results", "Plots", fig_name)
#    save_fig(figure_out, tight_layout=False)
    
# =============================================================================
#                                 # Store only the intersection! ie. shared frames among all video files..
#                                 df['frame'] = df.index; tmp_df['frame'] = tmp_df.index
#                                 df = df.groupby('frame').sum().add(tmp_df.groupby('frame').sum(),\
#                                                 fill_value=0).reset_index(level='frame', drop=True)
#                                 # Drop uncommon frames to keep same number of replicates for each frame in video - intersection
#                                 df = df.iloc[list(set(df.index).intersection(tmp_df.index))]
# =============================================================================

#        rgb_colours = [hex2rgb(hex) for hex in colours]

#tic = time.time()
## Group by PREFED
#group_prefed = fullMetaData.groupby('Prefed_on')
#for p, prefood in enumerate(pretreatments):
#    # Get prefed group
#    df_prefed = group_prefed.get_group(prefood)
#    
#    # Initialise plot for prefed group
#    plt.close("all")
#    fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(16,10), sharey=True) # 15 subplots (3 assay types, 5 assay concentrations)
#    ymax = 0
#    
#    # Group by ASSAY TYPE
#    group_assaychoice = df_prefed.groupby('Food_Combination')
#    for a, assay in enumerate(assaychoices):
#        try:
#            # Get assay type
#            df_assay = group_assaychoice.get_group(assay) # Group by assay type
#            
#            # Group by CONCENTRATION
#            group_conc = df_assay.groupby('Food_Conc')
#            for c, conc in enumerate(concentrations):
#                try:
#                    # Get concentration group
#                    df_conc = group_conc.get_group(conc)
#                    info = df_conc.iloc[0,:]
#                    
#                    # Specify plot colours
#                    colourkeys = info['Food_Combination'].split('/')
#                    if colourkeys[0] == colourkeys[1]:
#                        colnames = ["{}_{}".format(lab, i + 1) for i, lab in enumerate(colourkeys)]
#                    else:
#                        colnames = copy.deepcopy(colourkeys)
#                    colourkeys.insert(len(colourkeys), "None")
#                    colnames.insert(len(colnames), "None")
#
#                    
#                    if df_conc.shape[0] == 1:
#                        foodchoicepath = info['filename'].replace("Priota/Data/FoodChoiceAssay/MaskedVideos/",\
#                                                "Saul/FoodChoiceAssay/Results/FoodChoice/")
#                        foodchoicepath = foodchoicepath.replace(".hdf5", "_FoodChoice.csv")
#                        df = pd.read_csv(foodchoicepath, header=0, index_col=0)
#                    elif df_conc.shape[0] > 1:
#                        df = pd.DataFrame()
#                        for row in range(df_conc.shape[0]):
#                            info = df_conc.iloc[row,:]
#                            xlabs = info['Food_Combination'].split('/'); xlabs.insert(len(xlabs), "None")
#                            foodchoicepath = info['filename'].replace("Priota/Data/FoodChoiceAssay/MaskedVideos/",\
#                                                                      "Saul/FoodChoiceAssay/Results/FoodChoice/")
#                            foodchoicepath = foodchoicepath.replace(".hdf5", "_FoodChoice.csv")
#                            tmp_df = pd.read_csv(foodchoicepath, header=0, index_col=0)
#                            if df.empty:
#                                df = tmp_df
#                            else:
#                                df = df.append(tmp_df)
#                    
#                    # Convert to long format
#                    df['frame_number'] = df.index
#                    df = df.melt(id_vars='frame_number', value_vars=df.columns[:-1],\
#                                 var_name='Food', value_name='Mean')
#                                        
#                    # Specify seaborn colour palette
#                    values = sns.color_palette([colour_dict[key] for key in colourkeys])
#                    palette = {key: val for key, val in zip(colnames, values)}
#                    # sns.palplot(sns.color_palette(colour_dict.values()))
#                    
#                    axs[a,c] = sns.boxplot(x='Food', y='Mean', hue='Food', data=df, palette=palette, dodge=False) # Boxplots
#                    if df.max(axis=0).max() > ymax:
#                        ymax = df.max(axis=0).max()
#                    axs[a,c].set_ylim(-0.5, ymax+0.5)
#                    axs[a,c].set_xticklabels(labels=colnames, fontsize=13)
#                    axs[a,c].text(0.79, 0.9, ("n={0}".format(df_conc.shape[0])),\
#                                  transform=axs[a,c].transAxes, fontsize=15)
#                    if a == 0:
#                        axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
#                                      horizontalalignment='center', fontsize=18,\
#                                      transform=axs[a,c].transAxes)
#                    if c == 0 and a == 1:
#                        axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=30, fontsize=20)
#                except Exception as e:
#                    print("No videos found for concentration: %s\n(Assay: %s, Prefed on: %s)\n" % (e, assay, prefood))
#                    axs[a,c].axis('off')
#                    axs[a,c].text(0.79, 0.9, "n=0", fontsize=15, transform=axs[a,c].transAxes)
#                    if a == 0:
#                        axs[a,c].text(0.5, 1.15, ("conc={0}".format(conc)),\
#                                      horizontalalignment='center', fontsize=18,\
#                                      transform=axs[a,c].transAxes)
#                    if c == 0 and a == 1:
#                        axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=30, fontsize=20)
#                    pass
#        except Exception as e:
#            print("No videos found for assay type: %s\n(Prefed on: %s)\n" % (e, prefood))
#            pass
#    plt.text(0.95, -1.6, "Prefed on: {0}".format(prefood), horizontalalignment='center', fontsize=20)
#    plt.show(); plt.pause(2)
#    # Save figure 1
#    fig_name = "FoodChoiceBox_prefed" + prefood + ".eps"
#    figure_out = os.path.join(PROJECT_ROOT_DIR, "Results", "Plots", fig_name)
#    savefig(figure_out, saveFormat='eps', tight_layout=False)
#print("Complete!\n(Time taken: %d seconds)" % (time.time() - tic))

#tic = time.time()
#group_prefed = fullMetaData.groupby('Prefed_on')
#for p, prefood in enumerate(pretreatments):
#    df_prefed = group_prefed.get_group(prefood)
#    plt.close("all")
#    fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(16,10), sharey=True) # 15 subplots (3 assay types, 5 concentrations)
#    group_assaychoice = df_prefed.groupby('Food_Combination')
#    for a, assay in enumerate(assaychoices):
#        try:
#            df_assay = group_assaychoice.get_group(assay) # Group by assay type
#            group_conc = df_assay.groupby('Food_Conc')
#            for c, conc in enumerate(concentrations):
#                try:
#                    df_conc = group_conc.get_group(conc)
#                    info = df_conc.iloc[0,:]
#                    labs = info['Food_Combination'].split('/'); labs.insert(len(labs), "None")
#                    if df_conc.shape[0] == 1:
#                        foodchoicepath = info['filename'].replace("Priota/Data/FoodChoiceAssay/MaskedVideos/",\
#                                                "Saul/FoodChoiceAssay/Results/FoodChoice/")
#                        foodchoicepath = foodchoicepath.replace(".hdf5", "_FoodChoice.csv")
#                        df = pd.read_csv(foodchoicepath, header=0, index_col=0)
#                    elif df_conc.shape[0] > 1:
#                        df = pd.DataFrame()
#                        for row in range(df_conc.shape[0]):
#                            info = df_conc.iloc[row,:]
#                            labs = info['Food_Combination'].split('/'); labs.insert(len(labs), "None")
#                            foodchoicepath = info['filename'].replace("Priota/Data/FoodChoiceAssay/MaskedVideos/",\
#                                                                      "Saul/FoodChoiceAssay/Results/FoodChoice/")
#                            foodchoicepath = foodchoicepath.replace(".hdf5", "_FoodChoice.csv")
#                            tmp_df = pd.read_csv(foodchoicepath, header=0, index_col=0)
#                            if df.empty:
#                                df = tmp_df
#                            else:
#                                df = df.append(tmp_df)
#                    # Pie charts
#                    df_pie = df.mean(axis=0)
#                    df_pie.index = labs
#                    df_pie = df_pie.loc[df_pie!=0] # Remove any empty rows
#                    colours = [colour_dict[treatment] for treatment in df_pie.index]
#                    axs[a,c].pie(df_pie, labels=df_pie.index, colors=colours, autopct='%1.1f%%',\
#                                 textprops={'fontsize': 11},\
#                                 wedgeprops={"edgecolor": "k", 'linewidth': 1, 'linestyle':\
#                                             'solid', 'antialiased': True}, startangle=90)
#                    axs[a,c].axis('equal')
#                    axs[a,c].text(0, -1.25, ("n={0}".format(df_conc.shape[0])),\
#                                  horizontalalignment='center', fontsize=12)
#                    if a == 0:
#                        axs[a,c].text(0, 1.3, "conc={0}".format(conc),\
#                                      horizontalalignment='center', fontsize=18)
#                    if c == 0 and a == 1:
#                        axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=40, fontsize=20)
#                except Exception as e:
#                    print("No videos found for concentration: %s\n(Assay: %s, Prefed on: %s)\n" % (e, assay, prefood))
#                    axs[a,c].axis('off')
#                    axs[a,c].text(0.5, -1.25, "n=0", horizontalalignment='center', fontsize=12)
#                    if a == 0:
#                        axs[a,c].text(0.5, 1.3, ("conc={0}".format(conc)),\
#                                      horizontalalignment='center', fontsize=18)
#                    if c == 0 and a == 1:
#                        axs[a,c].set_ylabel("Mean Proportion Feeding", labelpad=40, fontsize=20)
#                    pass
#        except Exception as e:
#            print("No videos found for assay type: %s\n(Prefed on: %s)\n" % (e, prefood))
#            pass
#    plt.text(1, -1.9, "Prefed on: {0}".format(prefood), horizontalalignment='center', fontsize=20)
#    patches = []
#    for key, value in colour_dict.items():
#        patch = mpatches.Patch(color=value, label=key)
#        patches.append(patch)
#    fig.legend(handles=patches, labels=treatments, loc="upper right", borderaxespad=0.4,\
#               frameon=False, fontsize=15)
#    fig.tight_layout(rect=[0, 0.07, 0.9, 0.95])
#    fig.subplots_adjust(hspace=0.3, wspace=0.3)
#    plt.show(); plt.pause(2)
#    # Save figure 2
#    fig_name = "FoodChoicePie_prefed" + prefood + ".eps"
#    figure_out = os.path.join(PROJECT_ROOT_DIR, "Results", "Plots", fig_name)
#    savefig(figure_out, saveFormat='eps', tight_layout=False)
#print("Complete!\n(Time taken: %d seconds)" % (time.time() - tic))
