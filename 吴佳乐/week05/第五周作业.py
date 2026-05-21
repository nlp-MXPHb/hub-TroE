import torch
import torch.nn as nn
import numpy as np
import math
import random
import os
import re
from transformers import BertTokenizer

tokenizers = BertTokenizer.from_pretrained(
    r"C:\Users\mynam\Desktop\培训\深度学习培训\第八周 文本匹配\week8 文本匹配问题\week8 文本匹配问题\bert-base-chinese"
)


class TransformerDecoder(nn.Module):
    def __init__(self, vocab_size, d_model=256, nhead=4, num_layers=4,
                 max_len=512, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.position_embedding = nn.Embedding(max_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=d_model * 4,
                dropout=dropout,
                activation='gelu',
                batch_first=True,
                norm_first=True,  #归一化在残差的前面
            ) for _ in range(num_layers)
        ])
        self.ln_f = nn.LayerNorm(d_model)

    def forward(self, x):
        batch_size, seq_len = x.shape
        # 因果mask: 上三角为 -inf
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device) * float('-inf'), diagonal=1
        )
        positions = torch.arange(seq_len, device=x.device).unsqueeze(0)
        h = self.token_embedding(x)*math.sqrt(self.d_model)  #
        h = h + self.position_embedding(positions)
        h = self.dropout(h)
        for layer in self.layers:
            h = layer(h, src_mask=causal_mask)
        h = self.ln_f(h)
        return h


class LanguageModel(nn.Module):
    def __init__(self, vocab_size):
        super(LanguageModel, self).__init__()
        self.decoder = TransformerDecoder(vocab_size)
        self.fc = nn.Linear(self.decoder.d_model, vocab_size)
        self.loss = nn.functional.cross_entropy

    def forward(self, x, y=None):
        h = self.decoder(x)  # (batch, seq_len, d_model)
        y_pred = self.fc(h)  # (batch, seq_len, vocab_size)
        if y is not None:
            return self.loss(y_pred.view(-1, y_pred.shape[-1]), y.view(-1))
        else:
            return torch.softmax(y_pred, dim=-1)

# #加载字表
# def build_vocab(vocab_path):
#     vocab = {'<PAD>':0}
#     with open(vocab_path,encoding='utf8') as f:
#         for idx,word in enumerate(f):
#             word = word.strip()
#             vocab[word] = idx+1
#     return vocab

#加载语料
def load_corpus(path):
    corpus = ''
    with open(path,encoding='gbk') as f:
        for line in f:
            corpus+=line.strip()
    return corpus

#随机生成一个样本
#从文本中截取随机窗口,前n个字作为输入,最后一个字作为输出
def build_sample(window_size,corpus):
    start = random.randint(0,len(corpus)-1-window_size)
    end = start + window_size
    window = corpus[start:end]
    target = corpus[start+1:end+1]
    x = tokenizers.encode(window,add_special_tokens = False)
    y = tokenizers.encode(target,add_special_tokens = False)
    return x,y

#  0 1 2 3 4
#  start  0 - 1
#  end =  3 - 4

# 建立数据集
# sample_length 输入需要的样本数量,需要多少生成多少
# vocab 词表
# window_size 样本长度
# corpus 语料字符串
def build_dataset(sample_length,window_size,corpus):
    dataset_x = []
    dataset_y = []
    pad_id = tokenizers.pad_token_id
    for i in range(sample_length):
        x, y = build_sample(window_size, corpus)
        x = x[:window_size] + [pad_id] * max(0, window_size - len(x))
        y = y[:window_size] + [pad_id] * max(0, window_size - len(y))
        dataset_x.append(x)
        dataset_y.append(y)
    return torch.LongTensor(dataset_x), torch.LongTensor(dataset_y)

# 建立模型
def build_model():
    model = LanguageModel(tokenizers.vocab_size)
    return model

# 文本生成测试代码
def generate_sentence(openings, model, window_size):
    model.eval()
    with torch.no_grad():
        pred_char = ''
        while pred_char != '\n' and len(openings) <= 30:
            openings += pred_char
            x = tokenizers.encode(openings[-window_size:], add_special_tokens=False)
            x = torch.LongTensor([x])
            if torch.cuda.is_available():
                x = x.cuda()
            y = model(x)[0][-1]
            index = sampling_strategy(y)
            pred_char = tokenizers.decode([index])  # id → 字
    return openings

def sampling_strategy(prob_distribution):
    if random.random() > 0.1:
        strategy = 'greedy'
    else:
        strategy = 'sampling'

    if strategy == "greedy":
        return int(torch.argmax(prob_distribution))
    elif strategy == "sampling":
        prob_distribution = prob_distribution.cpu().numpy()
        return np.random.choice(list(range(len(prob_distribution))), p=prob_distribution)

#计算文本ppl
def calc_perplexity(sentence, model, vocab, window_size):
    prob = 0
    model.eval()
    with torch.no_grad():
        for i in range(1, len(sentence)):
            start = max(0, i - window_size)
            window = sentence[start:i]
            x = [vocab.get(char, vocab["<UNK>"]) for char in window]
            x = torch.LongTensor([x])
            target = sentence[i]
            target_index = vocab.get(target, vocab["<UNK>"])
            if torch.cuda.is_available():
                x = x.cuda()
            pred_prob_distribute = model(x)[0][-1]
            target_prob = pred_prob_distribute[target_index]
            prob += math.log(target_prob, 10)
    return 2 ** (prob * ( -1 / len(sentence)))

def train(corpus_path,save_weight = True):
    epoch_num = 20  #训练轮数
    batch_size = 64 #每次训练样本个数
    train_sample = 50000  #每轮训练总共训练的样本总数
    window_size = 10 #样本文本长度
    corpus = load_corpus(corpus_path)
    model = build_model() #建立模型
    if torch.cuda.is_available():
        model = model.cuda()
    optim = torch.optim.Adam(model.parameters(),lr=0.01) #建立优化器
    print("文本词表模型加载完毕,开始训练")
    for epoch in range(epoch_num):
        model.train()
        watch_loss = []
        for batch in range(int(train_sample//batch_size)):
            x,y = build_dataset(batch_size,window_size,corpus) #构建一组训练样本
            if torch.cuda.is_available():
                x,y = x.cuda(),y.cuda()
            optim.zero_grad() #梯度归零
            loss = model(x,y)  #计算loss
            loss.backward()
            optim.step()
            watch_loss.append(loss.item())
        print("=========\n第%d轮平均loss:%f" % (epoch + 1, np.mean(watch_loss)))
        print(generate_sentence("让他在半年之前，就不能做出", model,window_size))
        print(generate_sentence("李慕站在山路上，深深的呼吸", model,window_size))
    if not save_weight:
        return
    else:
        base_name = os.path.basename(corpus_path).replace("txt", "pth")
        model_path = os.path.join("model", base_name)
        torch.save(model.state_dict(), model_path)
        return

if __name__ == "__main__":
    # build_vocab_from_corpus("corpus/all.txt")
    train("corpus.txt", False)
