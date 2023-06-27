import os
import pickle
import random
import threading

import keras_nlp
import numpy as np
import pandas as pd
import tensorflow as tf
from keras_nlp.src.layers import MaskedLMMaskGenerator
from tqdm import tqdm

file_lock = threading.Lock()
bert_lock = threading.Lock()


def build_processor(
        seq_len=32, use_post_trained=False, path_post_trained='Bert.h5', saved_output=None
):
    if use_post_trained:
        print('使用后训练BERT来嵌入文本')
        masked_lm = tf.keras.models.load_model(
            path_post_trained,
            custom_objects={'BertMaskedLM': keras_nlp.models.BertMaskedLM}
        )
        processor = masked_lm.preprocessor
        tokenizer = processor.tokenizer
        processor.mask_selection_rate = 0.0
        # MLM自带的预处理器是会把文本里面的词Mask掉的，一定要更换masker成员，否则训练数据都会带[MASK]
        processor.masker = MaskedLMMaskGenerator(
            mask_selection_rate=0.0,
            mask_selection_length=96,
            mask_token_rate=0.0,
            random_token_rate=0.0,
            vocabulary_size=tokenizer.vocabulary_size(),
            mask_token_id=tokenizer.mask_token_id,
            unselectable_token_ids=[
                tokenizer.cls_token_id,
                tokenizer.sep_token_id,
                tokenizer.pad_token_id,
            ],
        )
        # 重设向量维度
        processor.packer.sequence_length = seq_len
    else:
        print('使用预训练BERT来嵌入文本')
        tokenizer = keras_nlp.models.BertTokenizer.from_preset("bert_tiny_en_uncased")
        processor = keras_nlp.models.BertPreprocessor(tokenizer=tokenizer, sequence_length=seq_len)
    if saved_output is not None:
        setattr(processor, 'saved_output_path', saved_output)
        if os.path.exists(saved_output):
            saved_output = pickle.load(open(saved_output, 'rb'))
        else:
            saved_output = {}
        setattr(processor, 'saved_output', saved_output)
    return processor


def tokenize(input_str, processor, save=True, load=True):
    if load and hasattr(processor, 'saved_output') and input_str in processor.saved_output.keys():
        vec = processor.saved_output[input_str]
    else:
        bert_lock.acquire()
        res = processor(input_str)
        bert_lock.release()
        if type(res) is not dict:
            res = res[0]
        vec = np.array(res['token_ids'])
        if save and hasattr(processor, 'saved_output'):
            file_lock.acquire()
            processor.saved_output.__setitem__(input_str, vec)
            pickle.dump(processor.saved_output, open(processor.saved_output_path, 'wb'))
            file_lock.release()
    return vec


def detokenize(input_vec, processor):
    batch = len(input_vec.shape) == 2
    text = processor.tokenizer.detokenize(input_vec)
    if not batch:
        text = [text]
    text = [item.numpy().decode('utf-8').split(' [SEP] ')[0].replace('[CLS] ', '') for item in text]
    for sep in ['.', '!', '?', ',']:
        for i in range(len(text)):
            while ' ' + sep in text[i]:
                text: list
                text[i] = text[i].replace(' ' + sep, sep)
    if len(text) == 1:
        text = text[0]
    return text


# Bert训练方式不止一种，这里只用了无标记训练任务MLM，也许可以用分数预测本身来训练？？？
def bert_train(data='../../Data/my_personality.csv'):
    assert 'XLA_FLAGS' in list(os.environ.keys())
    if type(data) is str:
        data = pd.read_csv(data)
    features = []
    for i in tqdm(range(data.shape[0])):
        text = data.iloc[i, :]['STATUS'].lower()
        features.append(text)
    # Pretrained language model.
    if os.path.exists('Bert.h5'):
        masked_lm = tf.keras.models.load_model(
            'Bert.h5',
            custom_objects={'BertMaskedLM': keras_nlp.models.BertMaskedLM}
        )
    else:
        masked_lm = keras_nlp.models.BertMaskedLM.from_preset(
            "bert_tiny_en_uncased",
        )
    ckpt = tf.keras.callbacks.ModelCheckpoint(
        filepath='Bert.h5',
        monitor='loss',
        verbose=1,
        save_best_only=True,
    )
    with tf.device('/gpu:0'):
        masked_lm.fit(x=features, batch_size=64, verbose=1, epochs=1000, callbacks=[ckpt])
    print('Done')


def bert_test(use_post_trained=True, batch_test=True):
    processor_ = build_processor(use_post_trained=use_post_trained)
    old_txt = [
        'I miss Carol a lot. Where is she now?',
        'We should be together.'
    ]
    if not batch_test:
        index = random.choice(list(range(len(old_txt))))
        old_txt = old_txt[index]
    vec_ = tokenize(
        old_txt,
        processor_
    )
    new_txt = detokenize(vec_, processor_)
    if type(old_txt) is not list:
        old_txt = [old_txt]
    old_txt = [item.lower() for item in old_txt]
    if len(old_txt) == 1:
        old_txt = old_txt[0]
    assert old_txt == new_txt
    print('use_post_trained:', use_post_trained, 'batch_test:', batch_test, 'OK')


if __name__ == '__main__':
    bert_train()
    # bert_test(use_post_trained=True, batch_test=True)
    # bert_test(use_post_trained=True, batch_test=False)
    # bert_test(use_post_trained=False, batch_test=True)
    # bert_test(use_post_trained=False, batch_test=False)
