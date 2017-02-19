from __future__ import print_function
import os

# Limit execution on certain GPU/GPUs
gpu_id = '0'  # Comma seperated string of GPU IDs to be used e.g. '0, 1, 2, 3'
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = gpu_id

seed = 1337  # for reproducibility
import numpy as np
np.random.seed(seed)        # Seed Numpy
import random               # Seed random
random.seed(seed)
import tensorflow as tf
tf.set_random_seed(seed)    # Seed Tensor Flow

import argparse
from train import train_net
from test import test_net

train_dir = 'path/to/sketches_train'
test_dir  = 'path/to/sketches_test'
test2_dir = 'path/to/sketches2_test'

default_store_model = 'model.h5'

# For printing complete numpy assry while debugging
#np.set_printoptions(threshold='nan')

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", help="train/test")
    parser.add_argument("--weights", help="weights to be stored/read")
    parser.add_argument("--test_mode", help="0:test vs test, 1: test vs train+test 2: test2 vs train+test")
    parser.add_argument("--epochs", help="#epochs while training")
    args = parser.parse_args()
    
    if not args.phase:
        parser.print_help()
        parser.error('Must specify phase (train/test)')
    elif args.phase not in ['train', 'test']:
        parser.print_help()
        parser.error('phase must be (train/test)')  
    
    if args.phase == 'train':
        if args.test_mode:
            print('Ignoring test_mode parameter for training.')
        args.epochs = int(args.epochs)
    else:
        args.test_mode = int(args.test_mode)
        if args.test_mode not in range(0,3):
            parser.print_help()
            parser.error('For testing, test_mode must be 0,1 or 2.')            

    if not args.weights:
        print('No weights specified. using default: ', default_store_model)
        args.weights = default_store_model
    return args


if __name__ == '__main__':
    args = parse_arguments()
    
    if args.phase == 'train':
        train_net(train_dir, args.weights, args.epochs)
    else:
        test_net(train_dir, test_dir, test2_dir, args.test_mode, args.weights)
    
    
