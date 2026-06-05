# Orbit Wars Kaggle Notebook 使用指南

## 方案1：使用GPU训练RL模型

### 步骤1：上传notebook到Kaggle

1. 访问 https://www.kaggle.com/code
2. 点击 "New Notebook"
3. 上传 `rl_training.py` 或 `ppo_training.py`
4. 在 Settings 中启用 GPU：
   - Accelerator → GPU
   - Internet → On

### 步骤2：运行训练

```python
# 在notebook中运行
trainer = train_rl_agent(num_episodes=1000)
```

### 步骤3：下载训练好的模型

训练完成后，下载 `best_model.pth` 文件。

### 步骤4：集成到agent

将训练好的模型集成到 `main.py` 中。

## 方案2：直接提交当前agent

当前agent已经是纯启发式，无需GPU：

```bash
# 本地测试
.venv/bin/python -m pytest tests/test_agent.py

# 提交到Kaggle
.venv/bin/kaggle competitions submit orbit-wars -f main.py -m "v14 improved"
```

## 方案3：使用Kaggle API管理notebook

### 初始化notebook

```bash
cd kaggle-notebook
kaggle kernels init -p .
```

### 推送代码

```bash
kaggle kernels push
```

### 检查状态

```bash
kaggle kernels status txdywy/orbit-wars-rl-training
```

### 获取输出

```bash
kaggle kernels output txdywy/orbit-wars-rl-training
```

## 当前agent性能

| 版本 | Kaggle分数 | 本地2p胜率 | 本地4p胜率 |
|------|-----------|-----------|-----------|
| v13 | 579.3 | 100% | 96.7% |
| v9 | 513.0 | - | - |
| v6 | 546.2 | - | - |

## 改进方向

1. **RL训练**：使用PPO训练策略网络
2. **特征工程**：提取更好的状态特征
3. **参数调优**：优化commit_ratio、reserve等参数
4. **多agent训练**：self-play训练

## 文件说明

- `rl_training.py` - 基础RL训练脚本
- `ppo_training.py` - PPO训练实现
- `rl_agent.py` - 完整的RL-enhanced agent
- `kernel-metadata.json` - Kaggle notebook配置
