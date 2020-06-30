#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot 96-well Plate Trajectories

A script to plot trajectories for worms tracked in all the wells of the 96-well
plate to which that video belongs. Just provide a featuresN filepath from 
Tierpsy filenames summaries and a plot will be produced of tracked worm 
trajectories throughout the video, for the entire 96-well plate (imaged under
6 cameras simultaneously).

@author: sm5911
@date: 23/06/2020

"""

#%% Imports 

import sys
import h5py
import argparse
import pandas as pd
from matplotlib import pyplot as plt
from pathlib import Path

PATH_LIST = ['/Users/sm5911/Tierpsy_Versions/tierpsy-tracker']
for sysPath in PATH_LIST:
    if not sysPath in sys.path:
        sys.path.insert(0, sysPath)

from tierpsy.analysis.split_fov.FOVMultiWellsSplitter import FOVMultiWellsSplitter
from tierpsy.analysis.split_fov.helper import CAM2CH_df, serial2channel, parse_camera_serial

#%% Global dictionary

CH2PLATE_dict = {'Ch1':((0,0),True),
                 'Ch2':((1,0),False),
                 'Ch3':((0,1),True),
                 'Ch4':((1,1),False),
                 'Ch5':((0,2),True),
                 'Ch6':((1,2),False)}
  
#%% Functions
        
def gettrajdata(featuresfilepath):
    """ Read Tierpsy-generated featuresN file trajectories data and return 
        the following info as a dataframe:
        ['coord_x', 'coord_y', 'frame_number', 'worm_index_joined'] """
    # Read HDF5 file + extract info
    with h5py.File(featuresfilepath, 'r') as f:
        df = pd.DataFrame({'x': f['trajectories_data']['coord_x'],\
                           'y': f['trajectories_data']['coord_y'],\
                           'frame_number': f['trajectories_data']['frame_number'],\
                           'worm_id': f['trajectories_data']['worm_index_joined']})
    # {'midbody_speed': f['timeseries_data']['speed_midbody']}
    return(df)


# def plotbrightfield(maskedfilepath, 
#                     frame, 
#                     ax=None, 
#                     rotate=False, 
#                     **kwargs):
#     """ Plot a brightfield image from a given masked HDF5 video. """
    
#     with h5py.File(maskedfilepath, 'r') as f:
#         if frame == 'all':
#             # Extract all frames and take the brightest pixels over time
#             img = f['full_data'][:]
#             img = img.max(axis=0)
#         else:
#             # Extract a given frame (index)
#             img = f['full_data'][frame]
    
#     if rotate:
#         import numpy as np
#         img = np.rot90(img,2)            
    
#     if not ax:
#         fig, ax = plt.subplots(**kwargs)
#         plt.imshow(img, cmap='gray', vmin=0, vmax=255)
#         return(fig, ax)
#     else:
#         ax.imshow(img, cmap='gray', vmin=0, vmax=255)
#         ax.axes.get_xaxis().set_visible(False)
#         ax.axes.get_yaxis().set_visible(False)
#         return img


def plottrajectory(featurefilepath, 
                   ax=None, 
                   downsample=10, 
                   legend=True, 
                   rotate=False, 
                   img_shape=None, 
                   **kwargs):
    """ Overlay feature file trajectory data onto existing figure. 
        NB: Plot figure and axes objects must both be provided on function call. """
        
    df = gettrajdata(featurefilepath)
    
    if not ax:
        fig, ax = plt.subplots(**kwargs)
 
    # Rotate your trajectories when you plot a rotated image
    if rotate:
        if not img_shape:
            raise ValueError('Image shape missing for rotation.')
        else:
            height, width = img_shape[0], img_shape[1]
            df['x'] = width - df['x']
            df['y'] = height - df['y']
        
    # Downsample frames for plotting
    if downsample < 1 or downsample == None: # input error handling
        downsample = 1
        
    ax.scatter(x=df['x'][::downsample], y=df['y'][::downsample],\
                s=10, c=df['frame_number'][::downsample], cmap='plasma')
    #ax.tick_params(labelsize=5)
    ax.axes.get_xaxis().set_visible(False)
    ax.axes.get_yaxis().set_visible(False)
    
    if legend:
        _legend = plt.colorbar(pad=0.01)
        _legend.ax.get_yaxis().labelpad = 10 # legend spacing
        _legend.ax.set_ylabel('Frame Number', rotation=270, size=7) # legend label
        _legend.ax.tick_params(labelsize=5)
    
    ax.autoscale(enable=True, axis='x', tight=True) # re-scaling axes
    ax.autoscale(enable=True, axis='y', tight=True)
 

def getvideoset(featurefilepath):
    """ """
    dirpath = Path(featurefilepath).parent
    maskedfilepath = Path(str(dirpath).replace("Results/","MaskedVideos/"))
    
    # get camera serial from filename
    camera_serial = parse_camera_serial(featurefilepath)
    
    # get list of camera serials for that hydra rig
    hydra_rig = CAM2CH_df.loc[CAM2CH_df['camera_serial']==camera_serial,'rig']
    rig_df = CAM2CH_df[CAM2CH_df['rig']==hydra_rig.values[0]]
    camera_serial_list = list(rig_df['camera_serial'])
   
    # extract filename stem 
    file_stem = str(maskedfilepath).split('.' + camera_serial)[0]
    
    file_dict = {}
    for camera_serial in camera_serial_list:
        channel = serial2channel(camera_serial)
        _loc, rotate = CH2PLATE_dict[channel]
        
        # get path to masked video file
        maskedfilepath = Path(file_stem + '.' + camera_serial) / "metadata.hdf5"
        featurefilepath = Path(str(maskedfilepath.parent).replace("MaskedVideos/",\
                               "Results/")) / 'metadata_featuresN.hdf5'
        
        file_dict[channel] = (maskedfilepath, featurefilepath)
        
    return file_dict

    
def tile96well(featurefilepath, saveDir=None, downsample=10):
    """ Tile plots and merge into a single plot for the 
        entire 96-well plate, correcting for camera orientation. """
        
    file_dict = getvideoset(featurefilepath)
    
    # define multi-panel figure
    columns = 3
    rows = 2
    x = 25.5
    y = 16
    fig, axs = plt.subplots(rows,columns,figsize=[x,y])
    
    x_offset = 1.5 / x # for bottom left image
    width = 0.3137 # for all but top left image
    width_tl = 0.3725 # for top left image
    height = 0.5 # for all images
    
    for channel, (maskedfilepath, featurefilepath) in file_dict.items():
        
        _loc, rotate = CH2PLATE_dict[channel]
        
        # create bbox for image layout in figure
        _ri, _ci = _loc
        if (_ri == 0) and (_ci == 0):
            # first image (with well names), bbox slightly shifted
            bbox = [0, height, width_tl, height]
        else:
            # other images
            bbox = [x_offset + width * _ci, height * (rows - (_ri + 1)), width, height]   
        
        # get location of subplot for camera
        ax = axs[_loc]
        
        # plot first frame of video + annotate wells
        FOVsplitter = FOVMultiWellsSplitter(maskedfilepath)
        FOVsplitter.plot_wells(is_rotate180=rotate, ax=ax, line_thickness=10)
        
        # plot worm trajectories
        plottrajectory(featurefilepath, 
                       ax=ax, 
                       downsample=downsample,
                       legend=False, 
                       rotate=rotate, 
                       img_shape=FOVsplitter.img_shape)
        
        # set image position in figure
        ax.set_position(bbox)
        
    plt.show()
    if saveDir:
        saveName = maskedfilepath.parent.stem + '.png'
        savePath = Path(saveDir) / saveName
        fig.savefig(savePath,
                    bbox_inches='tight',
                    dpi=300,
                    pad_inches=0,
                    transparent=True)            
    return(fig)

#%% Main
    
if __name__ == "__main__":
    print("\nRunning: ", sys.argv[0])
    
    example_featuresN = Path("/Volumes/behavgenom$/Saul/MicrobiomeScreen96WP/Results/20200222/microbiome_screen2_run7_p1_20200222_122858.22956805/metadata_featuresN.hdf5")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="input file path (featuresN)", 
                        default=example_featuresN) # default to example file if none given
    parser.add_argument("--output", help="output directory path (for saving)", 
                        default=example_featuresN.parent.parent) # default output directory if none given
    # parser.add_argument("--downsample", help="downsample trajectory data by plotting the worm centroid for every 'nth' frame",
    #                     default=10)
    args = parser.parse_args()
    print("Input file:", args.input)
    print("Output directory:", args.output)
    
    tile96well(args.input, saveDir=args.output, downsample=10)

    