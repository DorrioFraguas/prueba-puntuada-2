#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

Get best focussed TIF/CZI images based on focus measure

input
-----
image_root_dir (str): path to parent directory of images to be processed


supported methods
-----------------
GLVA: Graylevel variance (Krotkov, 86)
BREN: Brenner's (Santos, 97)

----------------------------
@author: Saul Moore (sm5911)
@date: 16/03/2020

"""

# TODO: Fix python-bioformats/javabridge 32-bit compatibility issue with macOS Catalina

#%% Imports

import os, sys, glob, time
import numpy as np
import pandas as pd
import czifile #tifffile, bioformats, javabridge, unicodedata
from PIL import Image
from matplotlib import pyplot as plt
from shutil import copyfile
from cv2 import subtract
from pathlib import Path


#%% Functions

def fmeasure(im, method='BREN'):
    """ Python implementation of MATLAB's fmeasure module
    
        params
        ------
        im (array): 2D numpy array
        method (str): focus measure algorithm
        
        supported methods
        --------------------
        GLVA: Graylevel variance (Krotkov, 86)
        BREN: Brenner's (Santos, 97)
    """
               
    # measure focus
    if method == 'GLVA':
        FM = np.square(np.std(im))
        return FM
    
    elif method == 'BREN':
        M, N = im.shape
        DH = np.zeros((M, N))
        DV = np.zeros((M, N))
        DV[:M-2,:] = subtract(im[2:,:],im[:-2,:])
        DH[:,:N-2] = subtract(im[:,2:],im[:,:-2])
        FM = np.maximum(DH, DV)
        FM = np.square(FM)
        FM = np.mean(FM)
        return FM
    
    else:
        raise Exception('Method not supported.')
 
    
def findImageFiles(image_root_dir, imageFormat):
    """ Return dataframe of image filepaths for images in the given directory 
        that match the given file regex string. 
    """
    
    # search for CZI or TIFF images in directory
    if type(imageFormat) != str:
        raise Exception('ERROR: Image format (str) not provided.')
    else:
        if imageFormat.lower().endswith('czi'):
            file_regex_list = ['*.czi','*/*.czi']
        elif imageFormat.lower().endswith('tif'):
            file_regex_list = ['*.tif','*/*.tif']

    # find image files
    print("Finding image files in %s" % image_root_dir)
    image_list = []
    for file_regex in file_regex_list:
        images = list(Path(image_root_dir).rglob(file_regex))
        image_list.extend(images)
    
    if len(image_list) == 0:
        raise Exception('ERROR: Unable to locate images. Check directory!')
    else:
        print("%d image files found." % len(image_list))
        return pd.DataFrame(image_list, columns=["filepath"])
   
 
# =============================================================================
# def getMetadata(filePath):
#     """ Get metadata associated with image file as xml.
# 
#     Input: filePath: name and path to image
#     
#     Output: omeXMLObject: xml object based on OME standard ready to be parsed
#     
#     """
#     xml=bioformats.get_omexml_metadata(filePath)
#     # xml is in unicode and may contain characters like 'mu'
#     # these characters will fail the xml parsing, thus recode the information
#     xml_normalized = unicodedata.normalize('NFKD',xml).encode('ascii','ignore')
#     
#     omeXMLObject = bioformats.OMEXML(xml_normalized)
#     
# #    # Parse XML with beautiful soup
# #    from bs4 import BeautifulSoup as bs    
# #    soup = bs(xml_normalized)
# #    prettysoup = bs.prettify(soup)
# #            
# #    # Extract metadata from XML
# #    import re
# #    image_series = re.findall(r'Image:[0-9]+', prettysoup)
# #    image_series = [im.split(':')[-1] for im in image_series]
# 
#     return omeXMLObject
# =============================================================================

# =============================================================================
# def readMetadata(omeXMLObject, imageID=0):
#     """ Parses most common meta data out of OME-xml structure.
#     
#     Input: omeXMLObject: OME-XML object with meta data
#            imageID: the image in multi-image files the meta data should 
#                     come from. Default=0
#      
#     Output: meta: dict with meta data
#      
#     Warning: If some keys are not found, software replaces the values 
#              with default values.
#     """       
#     meta={'AcquisitionDate': omeXMLObject.image(imageID).AcquisitionDate}
#     meta['Name']=omeXMLObject.image(imageID).Name
#     meta['SizeC']=omeXMLObject.image(imageID).Pixels.SizeC
#     meta['SizeT']=omeXMLObject.image(imageID).Pixels.SizeT
#     meta['SizeX']=omeXMLObject.image(imageID).Pixels.SizeX
#     meta['SizeY']=omeXMLObject.image(imageID).Pixels.SizeY
#     meta['SizeZ']=omeXMLObject.image(imageID).Pixels.SizeZ
# 
#     # Most values are not included in bioformats parser. 
#     # Thus, we have to find them ourselves
#     # The normal find procedure is problematic because each item name 
#     # is proceeded by a schema identifier
#     try:
#         pixelsItems=omeXMLObject.image(imageID).Pixels.node.items()  
#         meta.update(dict(pixelsItems))
#     except:
#         print('Could not read meta data in LoadImage.read_standard_meta\n\
#                used default values')
#         meta['PhysicalSizeX']=1.0
#         meta['PhysicalSizeXUnit']='mum'
#         meta['PysicalSizeY']=1.0
#         meta['PhysicalSizeYUnit']='mum'
#         meta['PysicalSizeZ']=1.0
#         meta['PhysicalSizeZUnit']='mum'
#         for c in range(meta['SizeC']):
#             meta['Channel_'+str(c)]='Channel_'+str(c)
#     return meta
# =============================================================================

def crop_image_nonzero(img):
    """ A function to delete the all-zero rows and columns of a 
        matrix of size n x m, to crop an image down to size (non-zero pixels) """
        
    hor_profile = img.any(axis=0)
    ver_profile = img.any(axis=1)
    
    hor_first = np.where(hor_profile != 0)[0].min()
    hor_last = np.where(hor_profile != 0)[0].max()
    ver_first = np.where(ver_profile != 0)[0].min()
    ver_last = np.where(ver_profile != 0)[0].max()
    
    img = img[ver_first:ver_last, hor_first:hor_last]

    return img
        
def findFocussedCZI(df, output_dir, method='BREN', imageSizeThreshXY=None, show=False):
    """ Find most focussed CZI image from dataframe of 'filepaths' to CZI image
        stacks of 96-well plate well images.
       
        params
        ------
        df (DataFrame): pandas DataFrame containing 'filepath' column of full 
                        paths to CZI files
        output_dir (str): output directory path to save results

        method (str): focus measure algorithm
        
        supported methods
        -----------------
        GLVA: Graylevel variance (Krotkov, 86)
        BREN: Brenner's (Santos, 97)
        
        imageSizeThreshXY (list/array) [int,int]: minimum threshold X,Y image size
    """
    
    file_df_list = []
    df = df.sort_values(by=['filepath']).reset_index(drop=True)    
    n = len(df['filepath'].unique())
    for f, file in enumerate(df['filepath']):
        print("\nProcessing file %d/%d (%.1f%%)" % (f+1, n, ((f+1)/n)*100))
        
        ##### TEST CODE BREAKER #####
        #if f == 1:
        #    raise Exception('STOP!')
        #############################

        # extract metadata from filename
        file = str(file)
        fname, dname = os.path.basename(file), os.path.basename(os.path.dirname(file))
        frname = fname.split('.')[0]
        plateID = frname.split("PG")[1].split("_")[0]
        conc_mM = frname.split("mM_")[0].split("_")[-1]
        
        # # get the actual image reader
        # rdr = bioformats.get_image_reader(None, path=file)
        # #with bioformats.ImageReader(path=file, url=None, perform_init=True) as reader:
        # #    img_arr = reader.read(file)
        image_arrays = czifile.imread(file)
        image_arrays.shape

        # # get total image series count
        # try:
        #     # for "whatever" reason the number of total image series can only be accessed this way
        #     totalseries = np.int(rdr.rdr.getSeriesCount())
        # except:
        #     totalseries = 1 # in case there is only ONE series
        totalseries = image_arrays.shape[1]
        zSlices = image_arrays.shape[3]

        # OPTIONAL: Get metadata (obtain instrument info)
        #omeXMLObject = getMetadata(file)
        #meta = readMetadata(omeXMLObject)
        
        # parse the CZI file
        file_info = []
        too_small_log = []
        # Loop over wells (series)
        for sc in range(totalseries):
            
            # # Set reader to series
            # rdr.rdr.setSeries(sc)
            img = np.array(image_arrays[0,sc,0,0,:,:,0])
                    
            hor_profile = img.any(axis=0)
            ver_profile = img.any(axis=1)
            
            hor_first = np.where(hor_profile != 0)[0].min()
            hor_last = np.where(hor_profile != 0)[0].max()
            ver_first = np.where(ver_profile != 0)[0].min()
            ver_last = np.where(ver_profile != 0)[0].max()
                
            # Filter small images
            if imageSizeThreshXY:
                #x, y = rdr.rdr.getSizeX(), rdr.rdr.getSizeY()
                x = hor_last - hor_first
                y = ver_last - ver_first
                if (x <= imageSizeThreshXY[0] and y <= imageSizeThreshXY[1]):
                    too_small_log.append(sc)
                else:
                    # get number of z-slices
                    #zSlices = rdr.rdr.getImageCount()

                    # Loop over z-slices    
                    for zc in range(zSlices):
                        # img = rdr.read(c=None, z=0, t=0, series=sc, index=zc,\
                        #                rescale=False)
                        img = np.array(image_arrays[0, sc, 0, zc, ver_first:ver_last, hor_first:hor_last, 0])
                        # plt.imshow(img); plt.pause(3); plt.close()
                        
                        # measure focus of raw image (uint16)
                        fm = fmeasure(img, method)
                                                
                        # store image info
                        file_info.append([file, plateID, conc_mM, sc, zc, fm])

        if len(too_small_log) > 0:
            print("WARNING: %d image series were omitted (image size too small)"\
                  % len(too_small_log))
        
        # create dataframe from list of recorded data
        colnames = ['filepath','plateID','GFP_mM','seriesID','z_slice_number','focus_measure']
        file_df = pd.DataFrame.from_records(file_info, columns=colnames)
        
        # store file info
        file_df_list.append(file_df)
        
        # get images with max focus for each well/GFP concentration
        focussed_images_df = file_df[file_df['focus_measure'] == \
                             file_df.groupby(['seriesID'])['focus_measure']\
                             .transform(max)]
        print("%d most focussed images found." % focussed_images_df.shape[0])

        # save most focussed images
        print("Saving most focussed images..")
        
        # Add dname to outDir when analysing multiple replicate folders at a time
        if df.shape[0] == len([i for i in df['filepath'] if dname in str(i)]):
            # We are analysing a single replicate folder
            outDir = os.path.join(output_dir, frname)
        else:
            # We are analysing multiple replicate folders
            outDir = os.path.join(output_dir, dname, frname)
        if not os.path.exists(outDir):
            os.makedirs(outDir)
            
        for i in range(focussed_images_df.shape[0]):
            if (i+1) % 8 == 0:
                print("%d/%d" % (i+1, focussed_images_df.shape[0]))

            # Extract image metadata from filename
            img_info = focussed_images_df.iloc[i]            
            sc = img_info['seriesID']
            zc = img_info['z_slice_number']
            
            # # We do NOT want to rescale images if comparing between them
            # rdr.rdr.setSeries(sc)
            # img = rdr.read(c=None, z=0, t=0, series=sc, index=zc, rescale=False)
            img = image_arrays[0,sc,0,zc,:,:,0]
            assert img.dtype == np.uint16 

            # Convert image to 8-bit (Warning: some information will be lost)
            #import cv2
            #img = cv2.convertScaleAbs(img, alpha=(255.0/65535.0))
            #assert img.dtype == np.uint8
 
            img = crop_image_nonzero(img)
        
            if show:
                plt.close('all')
                plt.imshow(img); plt.pause(5)
                
            # save as TIFF image
            outPath = os.path.join(outDir, frname + '_s%dz%d' % (sc, zc) + '.tif')
            
            # # Save as TIFF (bioformats)
            # bioformats.write_image(pathname=outPath,\
            #                        pixels=img,\
            #                        pixel_type=bioformats.PT_UINT16)
            
            # size = [img.shape[0], img.shape[1]]
            # img = np.reshape(img, size)
            # tifffile.imwrite(file=outPath, data=img[None, None, None, :, :], dtype=np.uint16, imagej=True, 
            #                  metadata={'channels': 1,'slices': 1,'frames': 1})
            # tifffile.imwrite(file=outPath, data=img[None, None, None, :, :], dtype=np.uint16,
            #                  ome=True, metadata={'axes':'TZCYX'}, append=False)
            # tifffile.imwrite(file=outPath, data=foo, dtype=np.uint16)
            # shape=(1,1,img.shape[0],img.shape[1],1), ome=True, metadata={'axes':'TZCYX'}, planarconfig='CONTIG'
            #tifffile.imsave(file=outPath, data=np.expand_dims(img, (0,1,2)), dtype=np.uint16, imagej=True)
            
            # Save TIF image as '.npy' for compatibility with ilastik software
            np.save(outPath.replace('.tif','.npy'), 
                    img[None, None, None, :, :], 
                    allow_pickle=True)
                        
    # concatenate dataframe from CZI file info
    df = pd.concat(file_df_list, axis=0, ignore_index=True)

    # save focus measures to file
    outDir = os.path.join(output_dir, 'focus_measures.csv')
    #df.to_csv()

    focussed_images_df = df[df['focus_measure'] == \
                         df.groupby(['plateID','GFP_mM','seriesID'])['focus_measure']\
                         .transform(max)].reset_index(drop=True)

    return focussed_images_df


def findFocussedTIF(df, output_dir, method='BREN'):
    """ Find most focussed TIF images from dataframe of 'filepaths' 
       
        params
        ------
        df (DataFrame): pandas DataFrame containing 'filepath' column
        method (str): focus measure algorithm
        
        supported methods
        -----------------
        GLVA: Graylevel variance (Krotkov, 86)
        BREN: Brenner's (Santos, 97)
    """

    # add columns to df    
    new_cols = ['GFP_mM','wellID','plateID','z_slice_number','focus_measure']
    cols = list(df.columns)  
    cols.extend(new_cols)
    df = df.reindex(columns=cols)
    df = df.sort_values(by=['filepath']).reset_index(drop=True)
    
    n = len(df['filepath'])
    for f, file in enumerate(df['filepath']):
        if (f+1) % 10 == 0:
            print("Processing file %d/%d (%.1f%%)" % (f+1, n, ((f+1)/n)*100))
        
        # extract metadata from filename
        fname = os.path.basename(file)
        ind = fname.find('_s') + 2
        df.loc[df['filepath']==file,['plateID',\
                                     'wellID',\
                                     'z_slice_number',\
                                     'GFP_mM']] = \
                                     [fname.split("_")[0].split("PG")[1],\
                                      fname[ind:ind+2],\
                                      fname[ind+3:ind+5],\
                                      fname.split("mM_")[0].split("_")[-1]]
          
        # read image and convert to greyscale
        im = np.array(Image.open(file).convert('L'))        
        #plt.imshow(im)
        
        # measure focus - method='BREN' works best according to Andre's tests
        FM = fmeasure(im, method)
        
        # record focus measure
        df.loc[df['filepath']==file, 'focus_measure'] = FM
   
    # get images with max focus for each well for each GFP concentration
    focussed_images_df = df[df['focus_measure'] == \
                         df.groupby(['GFP_mM','wellID'])['focus_measure'].transform(max)]
    
    assert len(focussed_images_df['filepath']) == \
           len(focussed_images_df['filepath'].unique())
           
    # save most focussed images
    n = len(focussed_images_df['filepath'])
    print("Saving most focussed images..")
    for f, file in enumerate(sorted(focussed_images_df['filepath'])):
        if (f+1) % 10 == 0:
            print("Saving image %d/%d (%.1f%%)" % (f+1, n, ((f+1)/n)*100))

        # create a directory to save copy
        fname, dname = os.path.basename(file), os.path.basename(os.path.dirname(file))
        
        outDir = os.path.join(output_dir, dname)
        if not os.path.exists(outDir):
            os.makedirs(outDir)

        # save copy            
        outPath = os.path.join(outDir, fname)
        copyfile(file, outPath)
   
    # save focus measures to file
    outPath = os.path.join(output_dir, 'focus_measures.csv')
    print("Saving focus measures to '%s'" % outPath)
    df.to_csv(outPath, index=False)
    
    return focussed_images_df


def findFocussedImages(df, output_dir, method, imageFormat, imageSizeFilterXY, show=False):
    
    assert all([str(df.loc[i,'filepath']).endswith(imageFormat) for i in range(len(df))])
    
    if imageFormat.lower().endswith('czi'):
        focussed_images_df = findFocussedCZI(df, output_dir, method, imageSizeFilterXY, show)
        
    elif imageFormat.lower().endswith('tif'):
        focussed_images_df = findFocussedTIF(df, output_dir, method)
        
    return focussed_images_df

    
#%% Main
    
if __name__ == "__main__":

    tic = time.time()   

    ######################
    
    # # Start Java virtual machine (for parsing CZI files with bioformats)
    # os.environ["JAVA_HOME"] = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home"
    # javabridge.start_vm(class_path=bioformats.JARS, max_heap_size='6G')

    # classpath = javabridge.JClassWrapper('java.lang.System').getProperty('java.class.path')
    # assert pd.Series([os.path.isfile(path) for path in classpath.split(os.pathsep)]).all()    

    ######################
    ##### PARAMETERS #####
    
    # set root directory
    if len(sys.argv) > 1:
        image_root_dir = sys.argv[1]
    else: 
        # local copy
        #image_root_dir = '/Users/sm5911/Documents/PanGenomeGFP/data/fluorescence_data_local_copy'
        image_root_dir = '/Users/sm5911/Documents/PanGenome/data/dev_assay_optimisation_local_copy/201106_dev_assay_optimisation3'
        #raise Exception("No directory path provided.")    
    
    # save most focussed images in output directory?
    saveBestFocus = True        
    
    # method for calculating best focussed image: ['BREN','GLVA']
    method = 'BREN'
    
    # image file type (format): ['tif','czi']    
    imageFormat = 'czi'
    
    # Size filter to use only small images (< 1024x1024 pixels)
    imageSizeThreshXY = [1024,1024]

    ####################
    ##### COMMANDS #####
    
    # find image files
    images_df = findImageFiles(image_root_dir, imageFormat)
    
    # filter image file list
    filterStr = None
    if filterStr:
        images_df = images_df[images_df['filepath'].isin([f for f in\
                              images_df['filepath'] if filterStr in f])]
        print("Filtering for images that contain: '%s' (%d files)" % (filterStr, images_df.shape[0]))

    # output directory
    output_dir = os.path.dirname(os.path.commonprefix(list(images_df['filepath'].values))) + '_focussed'
    
    # find + save most focussed images
    print("Finding most focussed images..")
    focussed_images_df = findFocussedImages(df=images_df,\
                                            output_dir=output_dir,\
                                            method=method,\
                                            imageFormat=imageFormat,\
                                            imageSizeFilterXY=imageSizeThreshXY,\
                                            show=False)
        
    ####################
    
    # # Terminate Java virtual machine
    # javabridge.kill_vm()

    toc = time.time()
    print('Complete!\nTotal time taken: %.2f seconds.' % (toc - tic))        
