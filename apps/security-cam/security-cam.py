#!/usr/bin/python3

# ****************************************************************************
# Copyright(c) 2017 Intel Corporation. 
# License: MIT See LICENSE file in root directory.
# ****************************************************************************

# Detect objects on a LIVE camera feed using
# Intel® Movidius™ Neural Compute Stick (NCS)

import os
import cv2
import sys
import numpy
import ntpath
import argparse
from time import localtime, strftime

import mvnc.mvncapi as mvnc

from utils import deserialize_output
from utils import visualize_output

# "Class of interest" - Display detections only if they match this class ID
CLASS_PERSON         = 15

# Detection threshold: Minimum confidance to tag as valid detection
CONFIDANCE_THRESHOLD = 0.40 # 60% confidant

# Variable to store commandline arguments
ARGS                 = None

# OpenCV object for video capture
cam 					= None 

# ---- Step 1: Open the enumerated device and get a handle to it -------------

def open_ncs_device():

    # Look for enumerated NCS device(s); quit program if none found.
    devices = mvnc.EnumerateDevices()
    if len( devices ) == 0:
        print( "No devices found" )
        quit()

    # Get a handle to the first enumerated device and open it
    device = mvnc.Device( devices[0] )
    device.OpenDevice()

    return device

# ---- Step 2: Load a graph file onto the NCS device -------------------------

def load_graph( device ):

    # Read the graph file into a buffer
    with open( ARGS.graph, mode='rb' ) as f:
        blob = f.read()

    # Load the graph buffer into the NCS
    graph = device.AllocateGraph( blob )

    return graph

# ---- Step 3: Pre-process the images ----------------------------------------

def pre_process_image():

    # Grab a frame from the camera
    ret, frame = cam.read()

    # Resize image [Image size is defined by choosen network, during training]
    img = cv2.resize( frame, tuple( ARGS.dim ) )

    # Convert RGB to BGR [skimage reads image in RGB, but Caffe uses BGR]
    if( ARGS.colormode == "BGR" ):
        img = img[:, :, ::-1]

    # Mean subtraction & scaling [A common technique used to center the data]
    img = img.astype( numpy.float16 )
    img = ( img - numpy.float16( ARGS.mean ) ) * ARGS.scale

    return img, frame

# ---- Step 4: Read & print inference results from the NCS -------------------

def infer_image( graph, img, frame ):

    # Load the labels file 
    labels =[ line.rstrip('\n') for line in 
                   open( ARGS.labels ) if line != 'classes\n'] 

    # Load the image as a half-precision floating point array
    graph.LoadTensor( img, 'user object' )

    # Get the results from NCS
    output, userobj = graph.GetResult()

    # Get execution time
    inference_time = graph.GetGraphOption( mvnc.GraphOption.TIME_TAKEN )

    # Deserialize the output into a python dictionary
    output_dict = deserialize_output.ssd( 
                      output, 
                      CONFIDANCE_THRESHOLD, 
                      frame.shape )

    # Print the results
    for i in range( 0, output_dict['num_detections'] ):

        # Filter a specific class/category
        if( output_dict.get( 'detection_classes_' + str(i) ) == CLASS_PERSON ):

            cur_time = strftime( "%Y_%m_%d_%H_%M_%S", localtime() )
            print( "Person detected on " + cur_time )

            # Extract top-left & bottom-right coordinates of detected objects 
            (y1, x1) = output_dict.get('detection_boxes_' + str(i))[0]
            (y2, x2) = output_dict.get('detection_boxes_' + str(i))[1]

            display_str = ( 
                labels[output_dict.get('detection_classes_' + str(i))]
                + ": "
                + str( output_dict.get('detection_scores_' + str(i) ) )
                + "%" )

            # Overlay bounding boxes, detection class and scores
            frame = visualize_output.draw_bounding_box( 
                        y1, x1, y2, x2, 
                        frame,
                        thickness=4,
                        color=(255, 255, 0),
                        display_str=display_str )

            # Capture snapshots
            photo = ( os.path.dirname(os.path.realpath(__file__))
                      + "/captures/photo_"
                      + cur_time + ".jpg" )
            cv2.imwrite( photo, frame )

    # If a display is available, show the image on which inference was performed
    if 'DISPLAY' in os.environ:
        cv2.imshow( 'NCS live inference', frame )

# ---- Step 5: Unload the graph and close the device -------------------------

def close_ncs_device( device, graph ):
    graph.DeallocateGraph()
    device.CloseDevice()
    cam.release()
    cv2.destroyAllWindows()

# ---- Main function (entry point for this script ) --------------------------

def main():

    device = open_ncs_device()
    graph = load_graph( device )

    while( True ):
        img, frame = pre_process_image()
        infer_image( graph, img, frame )

        # Display the frame for 5ms, and close the window so that the next frame 
        # can be displayed. Close the window if 'q' or 'Q' is pressed.
        if( cv2.waitKey( 5 ) & 0xFF == ord( 'q' ) ):
            break

    close_ncs_device( device, graph )

# ---- Define 'main' function as the entry point for this script -------------

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
                         description="Object detection using SSD on \
                         Intel® Movidius™ Neural Compute Stick." )

    parser.add_argument( '-g', '--graph', type=str,
                         default='../../caffe/SSD_MobileNet/graph',
                         help="Absolute path to the neural network graph file." )

    parser.add_argument( '-v', '--video', type=int,
                         default=0,
                         help="Index of your computer's V4L2 video device. \
                               ex. 0 for /dev/video0" )

    parser.add_argument( '-l', '--labels', type=str,
                         default='../../caffe/SSD_MobileNet/labels.txt',
                         help="Absolute path to labels file." )

    parser.add_argument( '-M', '--mean', type=float,
                         nargs='+',
                         default=[127.5, 127.5, 127.5],
                         help="',' delimited floating point values for image mean." )

    parser.add_argument( '-S', '--scale', type=float,
                         default=0.00789,
                         help="Absolute path to labels file." )

    parser.add_argument( '-D', '--dim', type=int,
                         nargs='+',
                         default=[300, 300],
                         help="Image dimensions. ex. -D 224 224" )

    parser.add_argument( '-c', '--colormode', type=str,
                         default="RGB",
                         help="RGB vs BGR color sequence. TensorFlow = RGB, Caffe = BGR" )

    ARGS = parser.parse_args()

    # Construct (open) the camera
    cam = cv2.VideoCapture( ARGS.video )

    cam.set( cv2.CAP_PROP_FRAME_WIDTH, 620 )
    cam.set( cv2.CAP_PROP_FRAME_HEIGHT, 480 )

    main()

# ==== End of file ===========================================================
