# evaluate.py
import torch
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


def evaluate(model, data_loader, device):
    """评估模型性能"""
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for texts, labels in data_loader:
            texts, labels = texts.to(device), labels.to(device)
            outputs = model(texts)
            preds = (outputs > 0.5).float()

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    # 转换为一维数组,因为下面需要一维数组参数
    all_preds = [p[0] if isinstance(p, list) else p for p in all_preds]
    all_labels = [l[0] if isinstance(l, list) else l for l in all_labels]

    #每个参数需要传递真实标签和预测标签
    metrics = {
        'accuracy': accuracy_score(all_labels, all_preds),
        'precision': precision_score(all_labels, all_preds, zero_division=0),
        'recall': recall_score(all_labels, all_preds, zero_division=0),
        'f1': f1_score(all_labels, all_preds, zero_division=0)
    }

    return metrics
