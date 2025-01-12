"""Implementation of sample attack on Inception_v3"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

import numpy as np
from PIL import Image
from scipy.misc import imread, imresize, imsave
from scipy.misc import imresize

import tensorflow as tf

from nets import inception_v3, inception_v4, inception_resnet_v2, resnet_v2

slim = tf.contrib.slim

tf.flags.DEFINE_string(
    'master', '', 'The address of the TensorFlow master to use.')


tf.flags.DEFINE_string('checkpoint_path_inception_v3', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string('checkpoint_path_inception_v4', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string('checkpoint_path_inception_resnet_v2', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string('checkpoint_path_resnet', '', 'Path to checkpoint for inception network.')

tf.flags.DEFINE_string('target_model', '', 'Choosen target model: ens, resnet, inception_v3, inception_v4, inception_resnet_v2')

tf.flags.DEFINE_string(
   'input_dir', '', 'Input directory with images.')

tf.flags.DEFINE_string(
   'output_dir', '', 'Output directory with images.')

tf.flags.DEFINE_integer(
    'image_width', 299, 'Width of each input images.')

tf.flags.DEFINE_integer(
    'image_height', 299, 'Height of each input images.')

tf.flags.DEFINE_integer(
    'image_resize', 330, 'Height of each input images.')

tf.flags.DEFINE_integer(
    'batch_size', 10, 'How many images process at one time.')

tf.flags.DEFINE_float(
    'max_epsilon', 16.0, 'Maximum size of adversarial perturbation.')

tf.flags.DEFINE_float(
    'prob', 0.5, 'probability of using diverse inputs.')

# if momentum = 1, this attack becomes M-DI-2-FGSM
tf.flags.DEFINE_float(
    'momentum', 0.0, 'Momentum.')

tf.flags.DEFINE_string(
    'GPU_ID', '8', 'which GPU to use.')

FLAGS = tf.flags.FLAGS

print("print all settings\n")
print(FLAGS.master)
print(FLAGS.__dict__)

os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
os.environ['CUDA_VISIBLE_DEVICES'] = FLAGS.GPU_ID


def load_images(input_dir, output_dir, batch_shape):
  """Read png images from input directory in batches.
  Args:
    input_dir: input directory
    batch_shape: shape of minibatch array, i.e. [batch_size, height, width, 3]
  Yields:
    filenames: list file names without path of each image
      Lenght of this list could be less than batch_size, in this case only
      first few images of the result are elements of the minibatch.
    images: array with all images from this batch
  """
  images = np.zeros(batch_shape)
  filenames = []
  idx = 0
  batch_size = batch_shape[0]
  for filepath in tf.gfile.Glob(os.path.join(input_dir, '*.png')):
    temp_name = str.split(filepath, '/')
    output_name = output_dir + '/'+ temp_name[-1]
    # check if the file exist
    if os.path.isfile(output_name) == False:
      with tf.gfile.Open(filepath) as f:
        image = imread(f, mode='RGB').astype(np.float) / 255.0
    # Images for inception classifier are normalized to be in [-1, 1] interval.
      images[idx, :, :, :] = image * 2.0 - 1.0
      filenames.append(os.path.basename(filepath))
      idx += 1
    if idx == batch_size:
      yield filenames, images
      filenames = []
      images = np.zeros(batch_shape)
      idx = 0
  if idx > 0:
    yield filenames, images


def save_images(images, filenames, output_dir):
  """Saves images to the output directory.
  Args:
    images: array with minibatch of images
    filenames: list of filenames without path
      If number of file names in this list less than number of images in
      the minibatch then only first len(filenames) images will be saved.
    output_dir: directory where to save images
  """
  for i, filename in enumerate(filenames):
    # Images for inception classifier are normalized to be in [-1, 1] interval,
    # so rescale them back to [0, 1].
    with tf.gfile.Open(os.path.join(output_dir, filename), 'w') as f:
      imsave(f, (images[i, :, :, :] + 1.0) * 0.5 * 255, format='png')


def graph(x, y, i, x_max, x_min, grad):
  eps = 2.0 * FLAGS.max_epsilon / 255.0
  eps_iter = 2.0 / 255.0
  num_classes = 1001
  momentum = FLAGS.momentum

  # should keep original x here for output
  with slim.arg_scope(inception_v3.inception_v3_arg_scope()):
      logits_v3, end_points_v3 = inception_v3.inception_v3(
          input_diversity(x), num_classes=num_classes, is_training=False)

  with slim.arg_scope(inception_v4.inception_v4_arg_scope()):
      logits_v4, end_points_v4 = inception_v4.inception_v4(
          input_diversity(x), num_classes=num_classes, is_training=False)

  with slim.arg_scope(inception_resnet_v2.inception_resnet_v2_arg_scope()):
      logits_res_v2, end_points_res_v2 = inception_resnet_v2.inception_resnet_v2(
          input_diversity(x), num_classes=num_classes, is_training=False, reuse=True)

  with slim.arg_scope(resnet_v2.resnet_arg_scope()):
      logits_resnet, end_points_resnet = resnet_v2.resnet_v2_152(
          input_diversity(x), num_classes=num_classes, is_training=False)

  if FLAGS.target_model == 'ens':
      logits = (logits_v3 + logits_v4 + logits_res_v2 + logits_resnet) / 4
      prediction = (end_points_v3['Predictions'] + end_points_v4['Predictions'] + end_points_res_v2['Predictions']) / 3

  elif FLAGS.target_model == 'resnet':
      logits = logits_resnet

  elif FLAGS.target_model == 'inception_v3':
      logits = logits_v3
      prediction =  end_points_v3['Predictions']

  elif FLAGS.target_model == 'inception_v4':
      logits = logits_v4
      prediction = end_points_v4['Predictions']

  elif FLAGS.target_model == 'inception_resnet_v2':
      logits = logits_res_v2
      prediction = end_points_res_v2['Predictions']

  else:
      assert False, "Unknown arch."


  one_hot = y

  cross_entropy = tf.losses.softmax_cross_entropy(one_hot, logits)

  # compute the gradient info
  noise = tf.gradients(cross_entropy, x)[0]
  noise = noise / tf.reduce_mean(tf.abs(noise), [1,2,3], keep_dims=True)
  # accumulate the gradient
  noise = momentum * grad + noise

  x = x + eps_iter * tf.sign(noise)
  x = tf.clip_by_value(x, x_min, x_max)
  i = tf.add(i, 1)
  return x, y, i, x_max, x_min, noise


def stop(x, y, i, x_max, x_min, grad):
  num_iter = int(min(FLAGS.max_epsilon+4, 1.25*FLAGS.max_epsilon))
  return tf.less(i, num_iter)


def input_diversity(input_tensor):
  rnd = tf.random_uniform((), FLAGS.image_width, FLAGS.image_resize, dtype=tf.int32)
  rescaled = tf.image.resize_images(input_tensor, [rnd, rnd], method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
  h_rem = FLAGS.image_resize - rnd
  w_rem = FLAGS.image_resize - rnd
  pad_top = tf.random_uniform((), 0, h_rem, dtype=tf.int32)
  pad_bottom = h_rem - pad_top
  pad_left = tf.random_uniform((), 0, w_rem, dtype=tf.int32)
  pad_right = w_rem - pad_left
  padded = tf.pad(rescaled, [[0, 0], [pad_top, pad_bottom], [pad_left, pad_right], [0, 0]], constant_values=0.)
  padded.set_shape((input_tensor.shape[0], FLAGS.image_resize, FLAGS.image_resize, 3))
  return tf.cond(tf.random_uniform(shape=[1])[0] < tf.constant(FLAGS.prob), lambda: padded, lambda: input_tensor)


def main(_):

  if not os.path.exists(FLAGS.output_dir):
    os.mkdir(FLAGS.output_dir)


  eps = 2.0 * FLAGS.max_epsilon / 255.0
  num_classes = 1001
  batch_shape = [FLAGS.batch_size, FLAGS.image_height, FLAGS.image_width, 3]

  with tf.Graph().as_default():
    # Prepare graph
    x_input = tf.placeholder(tf.float32, shape=batch_shape)
    x_max = tf.clip_by_value(x_input + eps, -1.0, 1.0)
    x_min = tf.clip_by_value(x_input - eps, -1.0, 1.0)


    with slim.arg_scope(inception_resnet_v2.inception_resnet_v2_arg_scope()):
      _, end_points = inception_resnet_v2.inception_resnet_v2(
          x_input, num_classes=num_classes, is_training=False)

    predicted_labels = tf.argmax(end_points['Predictions'], 1)
    y = tf.one_hot(predicted_labels, num_classes)

    i = tf.constant(0)
    grad = tf.zeros(shape=batch_shape)
    x_adv, _, _, _, _, _ = tf.while_loop(stop, graph, [x_input, y, i, x_max, x_min, grad])

    # Run computation
    s1 = tf.train.Saver(slim.get_model_variables(scope='InceptionV3'))
    s5 = tf.train.Saver(slim.get_model_variables(scope='InceptionV4'))
    s6 = tf.train.Saver(slim.get_model_variables(scope='InceptionResnetV2'))
    s8 = tf.train.Saver(slim.get_model_variables(scope='resnet_v2'))

    with tf.Session() as sess:
      s1.restore(sess, FLAGS.checkpoint_path_inception_v3)
      s5.restore(sess, FLAGS.checkpoint_path_inception_v4)
      s6.restore(sess, FLAGS.checkpoint_path_inception_resnet_v2)
      s8.restore(sess, FLAGS.checkpoint_path_resnet)
      for filenames, images in load_images(FLAGS.input_dir, FLAGS.output_dir, batch_shape):
        adv_images = sess.run(x_adv, feed_dict={x_input: images})
        save_images(adv_images, filenames, FLAGS.output_dir)


if __name__ == '__main__':
  tf.app.run()
