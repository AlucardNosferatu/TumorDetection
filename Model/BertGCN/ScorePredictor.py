import os

import tensorflow as tf

from Data.BertGCN.DataReader import encoder_bert
from Model.TextGCN.GNN import GraphConv
from Model.TextGCN.ScorePredictor import data_load, model_build, model_train, model_test

if __name__ == '__main__':
    train = True
    test = not train
    bert_dim = 32
    files_count = 325
    all_input_, _, _ = data_load(
        new_data=False,
        stop_after=files_count,
        embed_level='graph',
        embed_encoder=encoder_bert,
        data_folder='BertGCN',
        save_by_batch=True,
        bert_dim=bert_dim,
        binary_label=False,
        start_index=0
        # 切换yes/no或者分数数据
    )
    if os.path.exists('ScorePredictor.h5'):
        model_ = tf.keras.models.load_model('ScorePredictor.h5', custom_objects={'GraphConv': GraphConv})
    else:
        model_ = model_build(feature_input=tf.keras.Input(shape=(bert_dim, 256)))
    tf.keras.utils.plot_model(model_, 'BertGCN.png', show_shapes=True, expand_nested=True, show_layer_activations=True)
    if train:
        model_train(
            model_, all_input_, None, None, use_generator=True, gen_files_count=files_count,
            batch_size=128, step_per_epoch=20, val_split=0.25, workers=8
        )
    if test:
        model_test(
            model_, all_input_, None, None, use_generator=True, gen_files_count=files_count
        )
