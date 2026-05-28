import torch
import jieba
import pandas as pd
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset,DataLoader

class ReviewDataset(Dataset):
    def __init__(self,texts,labels,word2idx,max_len = 50):
        self.texts = [self.text_to_seq(text,word2idx,max_len) for text in texts]
        self.labels = labels

    def text_to_seq(self,text,word2idx,max_len):
        words = jieba.lcut(text)[:max_len]

        pad_idx = word2idx.get('[PAD]',0)
        unk_idx = word2idx.get('[UNK]',1)

        seq = [word2idx.get(word,unk_idx) for word in words]

        seq = seq + [pad_idx]*(len(seq) - max_len)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return torch.LongTensor(self.texts[idx]),torch.LongTensor(self.labels[idx])


def load_vocab(vocab_path):
    vocab = {}

    with open(vocab_path,encoding='utf8') as f:
        for idx,line in enumerate(f):
            word = line.strip()
            vocab[word] = idx+1

    return vocab

def load_data(config):
    #读取csv数据
    df = pd.read_csv(config.data_path,encoding='utf8')

    df = df[df['label'].isin([0,1])]

    if len(df) < 10:
        print('警告:数据量不足10条,请生成更多数据')

    texts = df['review'].tolist()
    labels = df['label'].tolist()

    print(f"好评{sum(labels)},坏评{len(labels) - sum(labels)}")

    train_texts,val_texts,train_labels,val_labels = train_test_split(
        texts,labels,test_size=0.2,random_state=42,stratify=labels
    )

    print(f'训练集:{len(train_texts)}')
    print(f'验证集:{len(val_texts)}')

    #加载词表
    vocab = load_vocab(config.vocab_path)
    config.vocab_size = len(vocab)

    train_dataset = ReviewDataset(train_texts,train_labels,vocab,config.max_seq_len)
    val_dataset = ReviewDataset(val_texts,val_labels,vocab,config.max_seq_len)

    train_loader = DataLoader(train_dataset,batch_size = config.batch_size,shuffle =True)
    val_loader = DataLoader(val_dataset,batch_size=config.batch_size,shuffle = True)

    return train_loader,val_loader
