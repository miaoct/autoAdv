import numpy as np
import tensorflow as tf
import os
from PIL import Image
import argparse

parser = argparse.ArgumentParser(description='What R U doing')
parser.add_argument('--folder', default='/home/haojieyuan/Data/ImageNet/nips2017_dev', type=str)
parser.add_argument('--out', default='./tmp.tfrecords', type=str)
args = parser.parse_args()


writer = tf.python_io.TFRecordWriter(args.out)

f1 = open('/home/haojieyuan/Data/ImageNet/nips2017_dev_gt_label.txt')
f2 = open('/home/haojieyuan/Data/ImageNet/nips2017_dev_target_label.txt')
img_prefix = args.folder

for line1, line2 in zip(f1, f2):
    img_name = line1.strip().split(' ')[0]
    gt_label = line1.strip().split(' ')[1]
    tgt_label = line2.strip().split(' ')[1]

    image = Image.open(os.path.join(img_prefix, img_name)).tobytes()
    label = int(gt_label)
    target_label = int(tgt_label)


    # to tf records
    example = tf.train.Example(
        features=tf.train.Features(
            feature={
                'img_raw':tf.train.Feature(bytes_list=tf.train.BytesList(value=[image])),
                'label':tf.train.Feature(int64_list=tf.train.Int64List(value=[label])),
                'target_label':tf.train.Feature(int64_list=tf.train.Int64List(value=[target_label]))}))

    writer.write(record=example.SerializeToString())

writer.close()