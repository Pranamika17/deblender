import os
# import tfplot
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt


class DataSampler:
    """
    Creates TensorFlow Dataset objects from directories containing
    .tfrecord TensorFlow binaries and passes tensors to graph. The
    resulting sampler is reinitializable onto any of three datasets
    (training, validation, testing) via the initialize method.
    """
    def __init__(self, train_path, valid_path, test_path, batch_size,
            shuffle=True):

        self.batch_size = batch_size
        self.shuffle = shuffle

        valid, test = map(self.make_dataset, [valid_path, test_path])
        train = self.make_dataset(train_path, train=True)

        self.iter = tf.data.Iterator.from_structure(train.output_types,
            train.output_shapes)
        train_init, valid_init, test_init = map(self.iter.make_initializer,
            [train, valid, test])
        self.init_ops = dict(zip(['train', 'valid', 'test'],
            [train_init, valid_init, test_init]))

    def make_dataset(self, filepath, train=False):
        files = [os.path.join(filepath, file) for file in \
                 os.listdir(filepath) if file.endswith('.tfrecords')]
        dataset = tf.data.TFRecordDataset(files).map(self.decoder)

        if train:
            if self.shuffle:
                dataset = dataset.shuffle(buffer_size=10000)
            return dataset.repeat().batch(self.batch_size)
        else:
            return dataset.batch(self.batch_size)

    def initialize(self, dataset='train'):
        try:
            return self.init_ops.get(dataset)
        except:
            raise ValueError('Dataset unknown or unavailable.')

    def decoder(self, example_proto):
        keys_to_features = {'latent' : tf.FixedLenFeature(4000, tf.float32),
                            'target' : tf.FixedLenFeature(400, tf.float32),
                            'metadata' : tf.FixedLenFeature(4, tf.float32)}
        parsed_features = tf.parse_single_example(
            example_proto,
            keys_to_features)
        return (parsed_features['latent'],
            parsed_features['target'],
            parsed_features['metadata'])

    def get_batch(self):
        x, y, z = self.iter.get_next()
        x = tf.reshape(x, [-1, 4000, 1])
        y = tf.reshape(y, [-1, 400, 1])
        z = tf.reshape(z, [-1, 4])
        return x, y, z


def np_to_tfrecords(X, Y, Z, file_path_prefix, verbose=False):
    """
    Converts 2-D NumPy arrays to TensorFlow binaries.

    Author: Sangwoong Yoon
    """
    def _dtype_feature(ndarray):
        """Match appropriate tf.train.Feature class with dtype of ndarray."""
        assert isinstance(ndarray, np.ndarray)
        dtype_ = ndarray.dtype
        if dtype_ == np.float64 or dtype_ == np.float32:
            return lambda array: tf.train.Feature(
                float_list=tf.train.FloatList(value=array))
        elif dtype_ == np.int64 or dtype_ == np.int32:
            return lambda array: tf.train.Feature(
                int64_list=tf.train.Int64List(value=array))
        else:
            raise ValueError("The input should be numpy ndarray. \
                               Instead got {}".format(ndarray.dtype))

    assert isinstance(X, np.ndarray)
    assert len(X.shape) == 2

    assert isinstance(Y, np.ndarray) or Y is None

    """ Load appropriate tf.train.Feature class depending on dtype. """
    dtype_feature_x = _dtype_feature(X)
    if Y is not None:
        assert X.shape[0] == Y.shape[0]
        assert len(Y.shape) == 2
        dtype_feature_y = _dtype_feature(Y)
    if Z is not None:
        assert X.shape[0] == Z.shape[0]
        assert len(Z.shape) == 2
        dtype_feature_z = _dtype_feature(Z)

    """ Generate TFRecord writer. """
    result_tf_file = file_path_prefix + '.tfrecords'
    writer = tf.python_io.TFRecordWriter(result_tf_file)
    if verbose:
        print("Serializing {:d} examples into {}".format(
            X.shape[0], result_tf_file))

    """ Iterate over each sample and serialize it as ProtoBuf. """
    for idx in range(X.shape[0]):
        x = X[idx]
        if Y is not None:
            y = Y[idx]
        if Z is not None:
            z = Z[idx]

        d_feature = {}
        d_feature['latent'] = dtype_feature_x(x)
        if Y is not None:
            d_feature['target'] = dtype_feature_y(y)
        if Z is not None:
            d_feature['metadata'] = dtype_feature_z(z)

        features = tf.train.Features(feature=d_feature)
        example = tf.train.Example(features=features)
        serialized = example.SerializeToString()
        writer.write(serialized)

    if verbose:
        print("Writing {} done!".format(result_tf_file))


def restore_session(sess, ckptdir):
    """
    Restores the checkpoint session from disk.
    """
    meta_graph = [os.path.join(ckptdir, file) for file in \
                  os.listdir(ckptdir) if file.endswith('.meta')][0]
    restorer = tf.train.import_meta_graph(meta_graph)
    restorer.restore(sess, tf.train.latest_checkpoint(ckptdir))


def plot_spectrum(spec):
    """
    Plots 1-D data and returns matplotlib figure for use with tfplot.
    """
    plt.style.use('seaborn')
    fig, ax = tfplot.subplots(figsize=(4, 3))
    im = ax.plot(np.arange(1210, 1280, 0.25), spec)
    return fig


def get_total_parameters():
    """
    Computes the total number of learnable variables in default graph.
    """
    total_parameters = 0
    for variable in tf.trainable_variables():
        shape = variable.get_shape()
        variable_parameters = 1
        for dim in shape:
            variable_parameters *= dim.value
        total_parameters += variable_parameters
    return total_parameters