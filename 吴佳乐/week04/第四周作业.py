import torch
import numpy as np
import torch.nn as nn
from PIL.GimpGradientFile import linear
from transformers import BertModel
import math


bert  = BertModel.from_pretrained(r"C:\Users\mynam\Desktop\培训\深度学习培训\第六周 语言模型\week6 语言模型和预训练\week6 语言模型和预训练\下午\bert-base-chinese", return_dict=False)
state_dict = bert.state_dict()
bert.eval()
x = np.array([2450, 15486, 102, 2110])
torch_x = torch.LongTensor([x])
seqence_output, pooler_output = bert(torch_x)
print(seqence_output.shape, pooler_output.shape)
print("state_dict keys:", state_dict.keys())  #查看所有的权值矩阵名称


class DiyBert(nn.Module):
    def __init__(self, state_dict):
        super(DiyBert, self).__init__()
        self.num_attention_heads = 12
        self.num_layers = 12
        self.hidden_size = 768
        self.attention_head_size = self.hidden_size // self.num_attention_heads

        # 保存 state_dict 供后面使用
        self.state_dict = state_dict

        # Embedding 层
        self.word_embeddings = nn.Embedding(21128, self.hidden_size)
        self.position_embeddings = nn.Embedding(512, self.hidden_size)
        self.token_type_embeddings = nn.Embedding(2, self.hidden_size)
        self.embeddings_layer_norm = nn.LayerNorm(self.hidden_size)

        # 加载 embedding 权重
        self.load_weights_embedding(state_dict)

        self.linearq = nn.Linear(self.hidden_size, self.hidden_size)
        self.lineark = nn.Linear(self.hidden_size, self.hidden_size)
        self.linearv = nn.Linear(self.hidden_size, self.hidden_size)
        self.lineardense = nn.Linear(self.hidden_size, self.hidden_size)
        self.linearNorm1 = nn.LayerNorm(self.hidden_size)
        self.linearinter = nn.Linear(self.hidden_size, self.hidden_size * 4)
        self.linearout = nn.Linear(self.hidden_size * 4, self.hidden_size)
        self.linearNorm2 = nn.LayerNorm(self.hidden_size)

        self.softmax = torch.softmax
        self.gelu = nn.GELU()

    def load_weights_embedding(self, state_dict):
        self.word_embeddings.weight.data = torch.tensor(state_dict["embeddings.word_embeddings.weight"])
        self.position_embeddings.weight.data = torch.tensor(state_dict["embeddings.position_embeddings.weight"])
        self.token_type_embeddings.weight.data = torch.tensor(state_dict["embeddings.token_type_embeddings.weight"])
        self.embeddings_layer_norm.weight.data = torch.tensor(state_dict["embeddings.LayerNorm.weight"])
        self.embeddings_layer_norm.bias.data = torch.tensor(state_dict["embeddings.LayerNorm.bias"])

    def load_weights_transformer(self, layer_idx):
        """加载某一层的 transformer 权重"""
        state_dict = self.state_dict  # 使用保存的 state_dict
        self.linearq.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.query.weight"])
        self.lineark.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.key.weight"])
        self.linearv.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.value.weight"])
        self.linearq.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.query.bias"])
        self.lineark.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.key.bias"])
        self.linearv.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.self.value.bias"])
        self.lineardense.weight.data = torch.tensor(
            state_dict[f"encoder.layer.{layer_idx}.attention.output.dense.weight"])
        self.lineardense.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.attention.output.dense.bias"])
        self.linearNorm1.weight.data = torch.tensor(
            state_dict[f"encoder.layer.{layer_idx}.attention.output.LayerNorm.weight"])
        self.linearNorm1.bias.data = torch.tensor(
            state_dict[f"encoder.layer.{layer_idx}.attention.output.LayerNorm.bias"])
        self.linearinter.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.intermediate.dense.weight"])
        self.linearinter.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.intermediate.dense.bias"])
        self.linearout.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.output.dense.weight"])
        self.linearout.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.output.dense.bias"])
        self.linearNorm2.weight.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.output.LayerNorm.weight"])
        self.linearNorm2.bias.data = torch.tensor(state_dict[f"encoder.layer.{layer_idx}.output.LayerNorm.bias"])

    def transpose_for_scores(self, x):
        """把 [batch, seq_len, hidden] 变成 [batch, num_heads, seq_len, head_size]"""
        batch_size, seq_len, _ = x.shape
        x = x.reshape(batch_size, seq_len, self.num_attention_heads, self.attention_head_size)
        return x.permute(0, 2, 1, 3)

    def forward(self, x):
        # x: [batch_size, seq_len]
        batch_size, seq_len = x.shape

        # Embedding
        wx = self.word_embeddings(x)  # [batch, seq_len, hidden]
        #px = self.position_embeddings(torch.arange(seq_len))  # [seq_len, hidden]
        #tx = self.token_type_embeddings(torch.zeros(seq_len, dtype=torch.long))  # [seq_len, hidden]

        px = self.position_embeddings(
            torch.arange(seq_len, device=x.device).expand(batch_size, -1)
        )  # [seq_len, hidden]
        #px = px.unsqueeze(0)  # [1, seq_len, hidden] - broadcasting会扩展到batch维度

        tx = self.token_type_embeddings(
            torch.zeros_like(x, dtype=torch.long)  # [batch, seq_len]
        )  # [batch, seq_len, hidden]

        x = wx + px + tx
        x = self.embeddings_layer_norm(x)

        # 循环每一层
        for i in range(self.num_layers):
            # 加载第 i 层的权重
            self.load_weights_transformer(i)

            # 保存残差
            residual = x

            # Q、K、V 计算
            q = self.linearq(x)  # [batch, seq_len, hidden]
            k = self.lineark(x)
            v = self.linearv(x)

            # 多头重塑
            q = self.transpose_for_scores(q)  # [batch, num_heads, seq_len, head_size]
            k = self.transpose_for_scores(k)
            v = self.transpose_for_scores(v)

            # 注意力计算
            qk = torch.matmul(q, k.transpose(-2, -1))  # [batch, num_heads, seq_len, seq_len]
            qk = qk / math.sqrt(self.attention_head_size)
            qk = self.softmax(qk, dim=-1)

            # 加权求和
            qkv = torch.matmul(qk, v)  # [batch, num_heads, seq_len, head_size]

            # 合并多头
            qkv = qkv.permute(0, 2, 1, 3)  # [batch, seq_len, num_heads, head_size]
            qkv = qkv.reshape(batch_size, seq_len, -1)  # [batch, seq_len, hidden]

            # Attention 输出 + 残差 + LayerNorm
            attention_out = self.lineardense(qkv)
            x = self.linearNorm1(residual + attention_out)

            # Feed Forward + 残差 + LayerNorm
            residual = x
            ff_out = self.linearinter(x)
            ff_out = self.gelu(ff_out)
            ff_out = self.linearout(ff_out)
            x = self.linearNorm2(residual + ff_out)

        return x


model = DiyBert(state_dict)
model.eval()
print(model.forward(torch_x))

