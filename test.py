from __future__ import print_function
import sys  # for flushing to stdout
import numpy as np
import cv2
from keras.models import load_model
import json
import csv
import os

from dataset import Dataset
from eval import eval_score_table
from model_def import load_encoder, load_autoencoder

class Test():
    def __init__(self, imdb, model_file, batch_size, train_dir, test_dir):
        self.imdb = imdb
        self.model_file = model_file
        self.input_dim = self.imdb.get_input_dim()
        self.test_dir = test_dir
        self.batch_size = batch_size
        self.ranks = sorted([1, 5, 10, 20, 50, 100, 200])
        self.dump_score_table = True  # For debugging

        # Use pre-trained model_file
        self.encoder = load_encoder(model_file, self.imdb.use_binary_sketches)
        self.autoencoder = load_autoencoder(model_file)
        print(self.encoder.summary())
        #print(self.autoencoder.summary())
        print('Encoded feature shape: ', self.encoder.output_shape)

    def _dump_score_table(self, score_table, row_IDs, col_IDs):
        import sys

        if sys.version_info[0] == 2:  # Not named on 2.6
            access = 'wb'
            kwargs = {}
        else:
            access = 'wt'
            kwargs = {'newline': ''}

        score_table = np.array(score_table)
        dump = []
        dump += [['', ':'] + col_IDs]
        for row in range(score_table.shape[0]):
            dump += [[row_IDs[row], ':'] + score_table[row].tolist()]
        with open('score_table.csv', access, **kwargs) as f:
            wr = csv.writer(f, delimiter=',')
            for row in dump:
                wr.writerow(row)

        sorted_idx = np.argsort(score_table, axis=1)
        sorted_IDs = []
        sorted_scores = []
        col_IDs_np = np.array(col_IDs)
        for row in range(score_table.shape[0]):
            sorted_IDs += [[row_IDs[row], ':'] + col_IDs_np[sorted_idx[row]].tolist()]
            sorted_scores += [[row_IDs[row], ':'] + score_table[row, sorted_idx[row]].tolist()]

        with open('score_table_sorted_IDs.csv', access, **kwargs) as f:
            wr = csv.writer(f, delimiter=',')
            for row in sorted_IDs:
                wr.writerow(row)

        with open('score_table_sorted_scores.csv', access, **kwargs) as f:
            wr = csv.writer(f, delimiter=',')
            for row in sorted_scores:
                wr.writerow(row)

    def test_on_set(self, sketch_set):
        if sketch_set == 'test_set':
            sketch_dir = self.test_dir
            sketch_list = self.imdb.test_sketch_list
        elif sketch_set == 'full_train_set':
            sketch_dir = self.imdb.train_dir
            sketch_list = self.imdb.full_train_sketch_list
        elif sketch_set == 'limited_train_set':
            sketch_dir = self.imdb.train_dir
            sketch_list = self.imdb.limited_train_sketch_list
        else:
            sketch_dir = None
            sketch_list = None
            print('Error: Weird "sketch_set" arg:{0:s}'.format(sketch_set))
            exit(0)

        num_sketches = len(sketch_list)
        batch_size = self.batch_size

        X = np.zeros([num_sketches, 1, self.imdb.ht, self.imdb.wd])
        for i, sketch_name in enumerate(sketch_list):
            X[i] = self.imdb._get_sketch(os.path.join(sketch_dir, sketch_name)).reshape(1, self.imdb.ht, self.imdb.wd)

        vectors = self.encoder.predict(X, batch_size=batch_size)

        return vectors

    def _get_score(self, v1, v2):
        dist = np.linalg.norm(v1.flatten() - v2.flatten())
        return dist

    def perform_testing(self, test_mode):
        group1 = 'test_set'

        if test_mode == 1:
            group2 = 'limited_train_set'
        else:
            group2 = 'full_train_set'

        # Testing
        group1_vectors = self.test_on_set(group1)
        group2_vectors = self.test_on_set(group2)

        print('Computing rank-based accuracy... ')
        row_sketch_list = self.imdb.test_sketch_list
        if test_mode == 1:
            col_sketch_list = self.imdb.limited_train_sketch_list
        else:
            col_sketch_list = self.imdb.full_train_sketch_list

        num_rows = len(group1_vectors)
        num_cols = len(group2_vectors)

        if len(row_sketch_list) != num_rows or len(col_sketch_list) != num_cols:
            print('Error: score_table size mismatch')
            print('Row {0:d} {1:d} Col: {2:d} {3:d}',
                  len(row_sketch_list), num_rows, len(col_sketch_list), num_cols)

        ranks = [rank for rank in self.ranks if rank <= num_cols]  # filter bad ranks
        score_table = np.zeros([num_rows, num_cols]).astype('float32')

        for i in range(num_rows):
            for j in range(num_cols):
                score_table[i][j] = self._get_score(group1_vectors[i], group2_vectors[j])

        # Parse score table and generate accuracy metrics
        # Extract IDs from file names
        ID1 = [x.split('.')[0].split('_')[0] for x in row_sketch_list]
        ID2 = [x.split('.')[0].split('_')[0] for x in col_sketch_list]
        eval_score_table(score_table, ranks, ID1, ID2)

        if self.dump_score_table:
            self._dump_score_table(score_table, ID1, ID2)

    def dump_decoded_sketches(self, sketch_set):
        if sketch_set == 'test_set':
            sketch_list = self.imdb.test_sketch_list
        elif sketch_set == 'full_train_set':
            sketch_list = self.imdb.full_train_sketch_list
        elif sketch_set == 'limited_train_set':
            sketch_list = self.imdb.limited_train_sketch_list
        else:
            sketch_list = None
            print('Error: Weird "sketch_set" arg:{0:s}'.format(sketch_set))
            exit(0)

        num_sketches = len(sketch_list)
        batch_size = self.batch_size
        val_samples = int(np.ceil(num_sketches / batch_size)) * batch_size
        original = np.empty([val_samples, 1, self.imdb.ht, self.imdb.wd])
        decoded = np.empty(original.shape)

        gen = self.imdb.get_batch(batch_size, sketch_set)
        for batch_id in range(int(val_samples / batch_size)):
            x_batch, _ = next(gen)
            original[batch_id * batch_size:(batch_id + 1) * batch_size] = x_batch
            decoded[batch_id * batch_size:(batch_id + 1) * batch_size] = self.autoencoder.predict(x_batch)

        # Ignore the extra sketches introduced by generator
        original = original[0:num_sketches]
        decoded = decoded[0:num_sketches]

        for sketch_name, sketch1, sketch2 in zip(sketch_list, original, decoded):
            if self.imdb.use_binary_sketches:
                sketch1 = (1. - sketch1) * 255
                sketch2 = (1. - sketch2) * 255
            else:
                sketch1 = (1 + sketch1) * 255 / 2.  # Scale to range [0, 255]
                sketch1 = 255 - np.clip(sketch1, 0, 255)  # Clip to [0, 255] and invert
                sketch2 = (1 + sketch2) * 255 / 2.  # Scale to range [0, 255]
                sketch2 = 255 - np.clip(sketch2, 0, 255)  # Clip to [0, 255] and invert
            # Place original-sketch on top of decoded-sketch
            sketch = np.concatenate((sketch1, sketch2), axis=1)
            # sketch.shape is (1, wd, wd) at this point
            sketch = sketch.reshape(sketch.shape[1], sketch.shape[1])  # make shape (wd, wd)
            sketch = sketch.astype('uint8')
            cv2.imwrite(os.path.join('temp', 'decoded_' + sketch_name), sketch)


def dump_train_test_sketch_pairs(X1, ID1, X2, ID2):
    for i, id in enumerate(ID1):
        stripped_id = id.split('.')[0].split('_')[0]
        if stripped_id in ID2:
            sketch1 = X1[i]
            sketch2 = X2[ID2.index(stripped_id)]
            sketch1 = (1 + sketch1) * 255 / 2.
            sketch2 = (1 + sketch2) * 255 / 2.
            sketch1 = 255 - np.clip(sketch1, 0, 255)
            sketch2 = 255 - np.clip(sketch2, 0, 255)
            sketch = np.concatenate((sketch2, sketch1), axis=1)  # Place Train-sketch on top of test-sketch
            # sketch.shape is (1, ht, wd) at this point
            sketch = sketch.reshape(sketch.shape[1], sketch.shape[1])  # make shape (ht, wd)
            sketch = sketch.astype('uint8')
            cv2.imwrite(os.path.join('temp', id + '_pair.jpg'), sketch)
        else:
            print("Warning: Stripped ID: {0:s} not found in test set. Skipping pair dump.".format(stripped_id))
    exit(0)


def set_test_config(common_cfg_file, test_cfg_file):
    with open(common_cfg_file) as f: dataset_config = json.load(f)
    with open(test_cfg_file) as f: test_config = json.load(f)

    return dataset_config, test_config


def test_net(common_cfg_file, test_cfg_file, test_mode, model_file):
    dataset_args, test_args = set_test_config(common_cfg_file, test_cfg_file)

    imdb = Dataset(dataset_args)
    imdb.prep_test(test_args)

    sw = Test(
        imdb, model_file, test_args['batch_size'],
        dataset_args['train_dir'], dataset_args['test_dir'])

    sw.dump_decoded_sketches('test_set')
    sw.perform_testing(test_mode)
