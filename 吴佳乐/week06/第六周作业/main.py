import torch
import torch.nn as nn
from config import Config
from loader import load_data, load_vocab
from model import TextCNN, LSTM, FastText
from evaluate import evaluate
import time
import random
import numpy as np
import pandas as pd


def train_epoch(model,train_loader,optim,criterion,device):
    model.train()
    total_loss = 0
    for texts,labels in train_loader:
        texts,labels = texts.to(device),labels.to(device)

        optim.zero_grad()
        outputs = model(texts)
        loss = criterion(outputs,labels)
        loss.backward()
        optim.step()

        total_loss += loss.item()

    return total_loss/len(train_loader)

def main():
    config = Config()
    device = torch.device(config.device if torch.cuda.is_available() else "cpu")
    print(f"使用设备:{device}")

    word2idx,_ = load_vocab(config.vocab_path)
    config.vocab_size = len(word2idx)
    print(f"词表大小:{config.vocab_size}")

    #加载数据 一个是训练一个是测试
    train_loader,val_loader = load_data(config)

    #选择模型
    models = {
        'TextCNN':TextCNN(config),
        'LSTM':LSTM(config),
        'FastText':FastText(config)
    }

    results = []

    for model_name,model in models.items():
        print(f"\n{'='*50}")
        print(f"训练模型:{model_name}")
        print(f"{'='*50}")

        model = model.to(device)

        optimizer = torch.optim.Adam(model.parameters(),lr=config.learning_rate)

        criterion = nn.BCELoss()

        # 训练
        start_time = time.time()
        for epoch in range(config.num_epochs):
            loss = train_epoch(model,train_loader,optimizer,criterion,device)
            if (epoch + 1) % 5 == 0:
                val_metrics = evaluate(model, val_loader, device)
                print(f"Epoch {epoch + 1}/{config.num_epochs}, Loss: {loss:.4f}, "
                      f"Val Acc: {val_metrics['accuracy']:.4f}, F1: {val_metrics['f1']:.4f}")

        train_time = time.time() - start_time

        # 评估
        metrics = evaluate(model, val_loader, device)

        # 测速（预测100个batch的速度）
        model.eval()
        start_time = time.time()
        with torch.no_grad():
            for _ in range(100):
                for texts, _ in val_loader:
                    texts = texts.to(device)
                    _ = model(texts)
                    break  # 只测一个batch
        predict_time = time.time() - start_time

        results.append({
            '模型': model_name,
            '准确率': metrics['accuracy'],
            '精确率': metrics['precision'],
            '召回率': metrics['recall'],
            'F1分数': metrics['f1'],
            '训练时间(秒)': train_time,
            '预测速度(秒/千条)': predict_time * 1000 / len(val_loader)
        })

        print(f"\n{model_name} 最终结果:")
        print(f"  准确率: {metrics['accuracy']:.4f}")
        print(f"  F1分数: {metrics['f1']:.4f}")
        print(f"  训练时间: {train_time:.2f}秒")

        # 输出结果表格
    print("\n" + "=" * 80)
    print("实验结果对比")
    print("=" * 80)
    df_results = pd.DataFrame(results)
    # 按F1分数排序
    df_results = df_results.sort_values('F1分数', ascending=False)
    print(df_results.to_string(index=False, float_format='%.4f'))


if __name__ == "__main__":
    main()

