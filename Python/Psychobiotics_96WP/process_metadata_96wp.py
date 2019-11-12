#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROCESS METADATA (96-well plate)

A script written to process microbiome assay project metadata CSV file. It
performs the following actions:
    1. Finds masked video files and adds filenames (paths) for missing entries in metadata
    2. Records the number of video segments (12min chunks) for each entry (2hr video/replicate) in metadata
    3. Records the number of featuresN results files for each entry
    4. Saves updated metadata file
    
Required fields in metadata: 
    ['filename','date_recording_yyyymmdd','instrument_name','well_number','run_number','camera_number','food_type']

@author: sm5911
@date: 13/10/2019

"""
#%% IMPORTS

# General imports
import os, sys, re, time, datetime#, json, glob
import numpy as np
import pandas as pd

# Path to Github / local helper functions
sys.path.insert(0, '/Users/sm5911/Documents/GitHub/PhD_Project/Python/Psychobiotics_96WP')

# Custom imports
from helper import lookforfiles

if __name__ == '__main__':
    # Record script start time
    tic = time.time()    
    
#%% INPUT HANDLING
    
    print("\nRunning script", sys.argv[0], "...")
    if len(sys.argv) > 1:
        COMPILED_METADATA_FILEPATH = sys.argv[1]  
        
    PROJECT_ROOT_DIR = COMPILED_METADATA_FILEPATH.split("/AuxiliaryFiles/")[0]
        
    IMAGING_DATES = None
    if len(sys.argv) > 2:
        IMAGING_DATES = list(sys.argv[2:])
        print("Using %d imaging dates provided: %s" % (len(IMAGING_DATES), IMAGING_DATES))        

#%% PATHS TO RESULTS DIRECTORIES (User-defined optional)
    
    daymetadata_dir = os.path.join(PROJECT_ROOT_DIR, "AuxiliaryFiles")
    maskedvideo_dir = os.path.join(PROJECT_ROOT_DIR, "MaskedVideos")
    featuresN_dir = os.path.join(PROJECT_ROOT_DIR, "Results")
    rawvideo_dir = os.path.join(PROJECT_ROOT_DIR, "RawVideos")
                        
#%% COMPILE FULL METADATA FROM EXPERIMENT DAY METADATA
       
    if not os.path.exists(COMPILED_METADATA_FILEPATH):
        day_metadata_parent_directory = os.path.dirname(COMPILED_METADATA_FILEPATH)
        print("Compiling full metadata from day-metadata files in %s" % day_metadata_parent_directory)
        AuxFileList = os.listdir(day_metadata_parent_directory)
        ExperimentDates = sorted([expdate for expdate in AuxFileList if re.match(r'\d{8}', expdate)])
        if IMAGING_DATES:
            ExperimentDates = [expdate for expdate in ExperimentDates if expdate in IMAGING_DATES]
        
        day_metadata_df_list = []
        for expdate in ExperimentDates:
            expdate_metadata_path = os.path.join(daymetadata_dir, expdate, 'metadata_' + expdate + '.csv')
            try:
                expdate_metadata = pd.read_csv(expdate_metadata_path)
                day_metadata_df_list.append(expdate_metadata)   
            except Exception as EE:
                print("WARNING:", EE)
        
        # Concatenate into a single full metadata
        metadata = pd.concat(day_metadata_df_list, axis=0, ignore_index=True, sort=False)
    else:
        metadata = pd.read_csv(COMPILED_METADATA_FILEPATH)
        print("Found existing compiled metadata.")
                            
#%% Hydra rig dictionary of unique camera IDs across channels
        
    CAM2CH_LIST = [('22956818', 'Ch1', 'Hydra01'), # Hydra01
                   ('22956816', 'Ch2', 'Hydra01'),
                   ('22956813', 'Ch3', 'Hydra01'),
                   ('22956805', 'Ch4', 'Hydra01'),
                   ('22956807', 'Ch5', 'Hydra01'),
                   ('22956832', 'Ch6', 'Hydra01'),
                   ('22956839', 'Ch1', 'Hydra02'), # Hydra02
                   ('22956837', 'Ch2', 'Hydra02'),
                   ('22956836', 'Ch3', 'Hydra02'),
                   ('22956829', 'Ch4', 'Hydra02'),
                   ('22956822', 'Ch5', 'Hydra02'),
                   ('22956806', 'Ch6', 'Hydra02'),
                   ('22956814', 'Ch1', 'Hydra03'), # Hydra03
                   ('22956827', 'Ch2', 'Hydra03'),
                   ('22956819', 'Ch3', 'Hydra03'),
                   ('22956833', 'Ch4', 'Hydra03'),
                   ('22956823', 'Ch5', 'Hydra03'),
                   ('22956840', 'Ch6', 'Hydra03'),
                   ('22956812', 'Ch1', 'Hydra04'), # Hydra04
                   ('22956834', 'Ch2', 'Hydra04'),
                   ('22956817', 'Ch3', 'Hydra04'),
                   ('22956811', 'Ch4', 'Hydra04'),
                   ('22956831', 'Ch5', 'Hydra04'),
                   ('22956809', 'Ch6', 'Hydra04'),
                   ('22594559', 'Ch1', 'Hydra05'), # Hydra05
                   ('22594547', 'Ch2', 'Hydra05'),
                   ('22594546', 'Ch3', 'Hydra05'),
                   ('22436248', 'Ch4', 'Hydra05'),
                   ('22594549', 'Ch5', 'Hydra05'),
                   ('22594548', 'Ch6', 'Hydra05')]
    
    # Convert list of camera-channel-hydra triplets to a dictionary with 
    # hydra-channel unique keys, and camera serial numbers as values
    HYCH2CAM_DICT = {}
    for line in CAM2CH_LIST:
        HYCH2CAM_DICT[(line[2], line[1])] = line[0]
        
    # Camera to well number mappings
    UPRIGHT_96WP = pd.DataFrame.from_dict({('Ch1',0):[ 'A1', 'B1', 'C1', 'D1'],
                                           ('Ch1',1):[ 'A2', 'B2', 'C2', 'D2'],
                                           ('Ch1',2):[ 'A3', 'B3', 'C3', 'D3'],
                                           ('Ch1',3):[ 'A4', 'B4', 'C4', 'D4'],
                                           ('Ch2',0):[ 'E1', 'F1', 'G1', 'H1'],
                                           ('Ch2',1):[ 'E2', 'F2', 'G2', 'H2'],
                                           ('Ch2',2):[ 'E3', 'F3', 'G3', 'H3'],
                                           ('Ch2',3):[ 'E4', 'F4', 'G4', 'H4'],
                                           ('Ch3',0):[ 'A5', 'B5', 'C5', 'D5'],
                                           ('Ch3',1):[ 'A6', 'B6', 'C6', 'D6'],
                                           ('Ch3',2):[ 'A7', 'B7', 'C7', 'D7'],
                                           ('Ch3',3):[ 'A8', 'B8', 'C8', 'D8'],
                                           ('Ch4',0):[ 'E5', 'F5', 'G5', 'H5'],
                                           ('Ch4',1):[ 'E6', 'F6', 'G6', 'H6'],
                                           ('Ch4',2):[ 'E7', 'F7', 'G7', 'H7'],
                                           ('Ch4',3):[ 'E8', 'F8', 'G8', 'H8'],
                                           ('Ch5',0):[ 'A9', 'B9', 'C9', 'D9'],
                                           ('Ch5',1):['A10','B10','C10','D10'],
                                           ('Ch5',2):['A11','B11','C11','D11'],
                                           ('Ch5',3):['A12','B12','C12','D12'],
                                           ('Ch6',0):[ 'E9', 'F9', 'G9', 'H9'],
                                           ('Ch6',1):['E10','F10','G10','H10'],
                                           ('Ch6',2):['E11','F11','G11','H11'],
                                           ('Ch6',3):['E12','F12','G12','H12']})
    
#%% OBTAIN MASKED VIDEO FILEPATHS FOR METADATA
    
    n_filepaths = sum([isinstance(path, str) for path in metadata.filename])
    n_entries = len(metadata.filename)
    print("%d/%d filename entries found in metadata" % (n_filepaths, n_entries))
    if not n_entries == n_filepaths:
        print("Attempting to fetch filenames for %d entries..." % (n_entries - n_filepaths))    
        
        # Return list of pathnames for masked videos in the data directory under given imaging dates
        maskedfilelist = []
        date_total = []
        print("Looking in '%s' for MaskedVideo files..." % maskedvideo_dir)
        for i, expDate in enumerate(IMAGING_DATES):
            tmplist = lookforfiles(os.path.join(maskedvideo_dir, expDate), ".*.hdf5$")
            date_total.append(len(tmplist))
            maskedfilelist.extend(tmplist)
        print("%d masked video snippets found for imaging dates provided:\n%s" % \
              (len(maskedfilelist), [*zip(IMAGING_DATES, date_total)]))    
    
    
    #%% # Parse over metadata entries and use well number/run number/date/hydra rig 
    # information to locate and fill in missing filename entries
        
        for i, filepath in enumerate(metadata.filename):            
            if isinstance(filepath, str):
                # If filepath is already present, make sure there are no whitespaces
                metadata.loc[i,'filename'] = filepath.replace(" ", "")  
            
            else:
                file_info = metadata.iloc[i]
                
                # Extract date/run/hydra/plate/well info
                date = str(file_info['date_recording_yyyymmdd'].astype(int))             # which experiment date?
                hydra = file_info['instrument_name']                                     # which Hydra rig?
                well_number = str(file_info['well_number'])                              # which well in 96-well plate?
                run_number = str(int(file_info['run_number']))                           # which run?
                
                # Obtain channel number from well-to-channel mapping dictionary: 'UPRIGHT_96WP'
                channel = UPRIGHT_96WP.iloc[np.where(UPRIGHT_96WP == well_number)].columns[0][0]
                
                # Obtain camera serial number unique ID using hydra/channel combination, using dictionary: HYCH2CAM_DICT
                cameraID = HYCH2CAM_DICT[(hydra,channel)]                                # which camera?
                
                # Update cameraID in metadata
                metadata.loc[i,'camera_number'] = cameraID
                
                # Use run/date/cameraID to construct regex query to find results filename                                            
                # Query by regex using run/date/camera info
                file_querystr1 = '_run{0}_'.format(run_number)
                file_querystr2 = '_' + date + '_\d{6}.' + cameraID
                
                # Retrieve filepath, using data recorded in metadata
                for file in maskedfilelist:
                    # If folder name contains '_runX_' (WARNING: this is manually assigned/typed when recording)
                    if re.search(file_querystr1, file.lower()): # or re.search(file_querystr1, file.lower()):
                        # If filepath contains: '_date_XXXXXX.cameraID'...
                        # NB: auto-generated to include date/time(exact time not known)/cameraID
                        if re.search(file_querystr2, file.lower()):
                            # Record filepath to MaskedVideo file: '*/metadata.hdf5'
                            metadata.loc[i,'filename'] = os.path.dirname(file)
                                
        matches = sum([isinstance(path, str) for path in metadata.filename]) - n_filepaths
        print("Complete!\n%d/%d filenames added.\n" % (matches, n_entries - n_filepaths))
    
    #%% OBTAIN RAW VIDEO FILEPATHS FOR COUNTING SNIPPETS
        
        # Return list of pathnames for raw videos in the data directory for given imaging dates
        rawvideolist = []
        date_total = []
        print("Looking in '%s' for RawVideo files..." % rawvideo_dir)
        for i, expDate in enumerate(IMAGING_DATES):
            tmplist = lookforfiles(os.path.join(rawvideo_dir, expDate), ".*.mp4$")
            date_total.append(len(tmplist))
            rawvideolist.extend(tmplist)
    
        # Get list of pathnames for featuresN files for given imaging dates
        featuresNlist = []
        print("Looking in '%s' for featuresN files..." % featuresN_dir)
        for i, expDate in enumerate(IMAGING_DATES):
            tmplist = lookforfiles(os.path.join(featuresN_dir, str(expDate)), ".*_featuresN.hdf5$")
            featuresNlist.extend(tmplist)
        
        # Pre-allocate columns in metadata for storing n_video_chunks, n_featuresN_files
        metadata['rawvideo_snippets'] = ''
        metadata['featuresN_exists'] = ''
        
        # Add n_video_snippets, n_featuresN_files as columns to metadata
        for i, masked_dirpath in enumerate(metadata.filename):
            # If filepath is present, return the filepaths to the rest of the chunks for that video
            if isinstance(masked_dirpath, str):
                # Record number of video segments (chunks) in metadata
                raw_dirpath = masked_dirpath.replace("/MaskedVideos", "/RawVideos")
                snippetlist = [snippet for snippet in rawvideolist if raw_dirpath in snippet] 
                n_snippets = len(snippetlist)
                metadata.loc[i, 'rawvideo_snippets'] = int(n_snippets)
                
                # Record the number of featuresN files
                featuresN_dirpath = masked_dirpath.replace("/MaskedVideos", "/Results")
                featlist = [featpath for featpath in featuresNlist if featuresN_dirpath in featpath]
                n_featuresN = len(featlist)
                metadata.loc[i, 'featuresN_exists'] = (n_featuresN * n_snippets == n_snippets)
                
        print("(Metadata updated: Checked for featuresN files and tallied number of RawVideo snippets found.)")
        
        
#%% # TODO: Read JSON files, extract hydra imaging rig temperature and humidity info,
#       and append to metadata
#    rig_data_colnames = ['filename_JSON_snippet','frame_number','rig_internal_humidity_percent','rig_internal_temperature_C']
#    rig_data_full = pd.DataFrame(columns=rig_data_colnames)
#    for i, filepath in enumerate(metadata['filename']):
#        if i % 10 == 0:
#            print("Extracting hydra rig data from JSON snippets for file: %d/%d" % (i,len(metadata['filename'])))
#        raw_json_dir = filepath.replace("/MaskedVideos","/RawVideos")
#        extra_json_filelist = glob.glob(os.path.join(raw_json_dir, "*.extra_data.json"))
#        for json_snippet in extra_json_filelist:
#            with open(json_snippet) as fid:
#                extras = json.load(fid)
#                rig_data_snippet = pd.DataFrame(index=range(len(extras)), columns=rig_data_colnames)
#                for d, dictionary in enumerate(extras):
#                    rig_data_snippet.loc[d, rig_data_colnames] = json_snippet, dictionary['frame_index'], dictionary['humidity'], dictionary['tempo']
#                    rig_data_full = pd.concat([rig_data_full, rig_data_snippet], axis=0, sort=False).reset_index(drop=True)

#%% OPTIONAL EXTRAS
         
    # Ensure 'food_type' entries are grouped correctly by converting to uppercase
    metadata['food_type'] = metadata['food_type'].str.upper()   
 
    # Calculate L1 diapause duration (if possible) and append to results
    diapause_required_columns = ['date_bleaching_yyyymmdd','time_bleaching',\
                                 'date_L1_refed_yyyymmdd','time_L1_refed_OP50']
    
    if all(x in metadata.columns for x in diapause_required_columns):
        # Extract bleaching dates and times
        bleaching_datetime = [datetime.datetime.strptime(date_str + ' ' + time_str, '%Y%m%d %H:%M:%S') for date_str, time_str\
                              in zip(metadata['date_bleaching_yyyymmdd'].astype(str), metadata['time_bleaching'])]
        # Extract dispensing dates and times
        dispense_L1_datetime = [datetime.datetime.strptime(date_str + ' ' + time_str, '%Y%m%d %H:%M:%S') for date_str, time_str\
                                in zip(metadata['date_L1_refed_yyyymmdd'].astype(str), metadata['time_L1_refed_OP50'])]
        # Estimate duration of L1 diapause
        L1_diapause_duration = [dispense - bleach for bleach, dispense in zip(bleaching_datetime, dispense_L1_datetime)]
        
        # Add duration of L1 diapause to metadata
        metadata['L1_diapause_seconds'] = [int(timedelta.total_seconds()) for timedelta in L1_diapause_duration]

#%%
    # Save full metadata
    print("Saving updated metadata to: '%s'" % COMPILED_METADATA_FILEPATH)
    metadata.to_csv(COMPILED_METADATA_FILEPATH, index=False)        

    # Record script end time
    toc = time.time()
    print("Done.\n(Time taken: %.1f seconds)" % (toc-tic))
