class Config:
    data_path = '作业/reviews.csv'
    vocab_path = '作业/chars.txt'
    max_seq_len = 50  #最大序列长度
    train_ratio = 0.8 #训练集比例

    #模型参数
    vocab_size = 5000 #词表大小
    embed_size = 128 #词向量维度
    hidden_size = 256 #隐藏层维度
    num_filters = 100 #卷积核数量
    filter_sizes = [2,3,4] #卷积核大小

    #训练参数
    batch_size = 64
    learning_rate = 0.001
    num_epochs = 20
    dropout = 0.5
    device = 'cuda'

    # 模型选择
    model_type = "textcnn"  # "textcnn","lstm","fasttext"
