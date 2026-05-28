import torch
import torch.nn as nn
import torch.nn.functional as F

class TextCNN(nn.Module):
    """TextCNN模型"""
    def __init__(self,config):
        super(TextCNN,self).__init__()
        self.embedding = nn.Embedding(config.vocab_size,config.embed_size,padding_idx=0)
        self.convs = nn.ModuleList([
            nn.Conv1d(config.embed_size,config.num_filters,k)
            for k in config.filter_sizes
        ])
        self.dropout = nn.Dropout(config.dropout)
        self.fc = nn.Linear(len(config.filter_sizes)*config.num_filters,1)

    def forward(self,x):
        # x:(batch,seq_len)
        x = self.embedding(x)  #(batch,seq_len,embed_size)
        x = x.permute(0,2,1) #(batch,embed_size,seq_len)

        conv_outputs = []
        for conv in self.convs:
            conv_out = nn.functional.relu(conv(x)) #(bath,num_filters,seq_len-k+1)
            pooled = nn.functional.max_pool1d(conv_out,conv_out.shape[2]).squeeze(2)
            conv_outputs.append(pooled)

        x = torch.cat(conv_outputs,dim=1)
        x = self.dropout(x)
        x= torch.sigmoid(self.fc(x))
        return x


class LSTM(nn.Module):
    """LSTM模型"""

    def __init__(self, config):
        super(LSTM, self).__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.embed_size, padding_idx=0)
        self.lstm = nn.LSTM(config.embed_size, config.hidden_size,
                            batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(config.dropout)
        self.fc = nn.Linear(config.hidden_size * 2, 1)

    def forward(self, x):
        x = self.embedding(x)  # (batch, seq_len, embed_size)
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden_size*2)
        pooled = F.max_pool1d(lstm_out.permute(0, 2, 1), lstm_out.shape[1]).squeeze(2)
        x = self.dropout(pooled)
        x = torch.sigmoid(self.fc(x))
        return x


class FastText(nn.Module):
    """FastText模型"""

    def __init__(self, config):
        super(FastText, self).__init__()
        self.embedding = nn.Embedding(config.vocab_size, config.embed_size, padding_idx=0)
        self.fc = nn.Linear(config.embed_size, 1)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        x = self.embedding(x)  # (batch, seq_len, embed_size)
        x = x.mean(dim=1)  # 平均池化 (batch, embed_size)
        x = self.dropout(x)
        x = torch.sigmoid(self.fc(x))
        return x
