# 🐉 Xdhdyp-BKT

基于贝叶斯知识追踪(Bayesian Knowledge Tracing)的智能学习系统

## 📖 项目简介

Xdhdyp-BKT是一个基于贝叶斯知识追踪算法的智能学习系统，旨在提供个性化的学习体验和智能的题目推荐。系统通过分析用户的学习行为和答题历史，动态调整学习路径，帮助用户更高效地掌握知识。

## ⚠️ 项目状态

> **注意：本项目目前处于开发阶段，部分功能尚未完善**
>
> - 🚧 核心功能已实现，但仍在持续优化中
> - 🔄 推荐算法需要更多数据支持
> - 📊 数据可视化功能待增强
> - 🔍 部分高级功能尚未实现
> - 🐛 可能存在未知的bug
>
> ### 平台兼容性说明
>
> - ✅ 已测试平台：
>
>   - Windows 11
>   - Windows 10
> - ⚠️ 未测试平台：
>
>   - Linux
>   - macOS
>   - 其他Windows版本
>
>> **注意：** 由于目前仅在Windows 10/11上进行了测试，其他平台可能存在兼容性问题。如果您在其他平台上使用遇到问题，欢迎提交Issue。
>>
>
> 欢迎提交Issue报告问题或提出改进建议！

## ✨ 主要功能

- 🎯 智能题目推荐
- 🛣️ 个性化学习路径
- 📊 实时学习进度追踪
- 📈 详细的答题分析
- 📉 遗忘曲线预测
- 📊 多维度学习数据可视化

## 🛠️ 技术特点

- 💻 基于PyQt6的现代化GUI界面
- 🧮 贝叶斯知识追踪(BKT)算法
- 🤖 智能推荐系统
- 💾 数据持久化存储
- 📊 用户行为分析

## 📥 安装说明

### 系统要求

- Windows 10/11
- Python 3.12.8 或更高版本
- 至少 4GB 可用内存
- 至少 1GB 可用磁盘空间

### 详细安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/BKT-Xhydra.git
cd BKT-Xhydra
```

2. **创建虚拟环境**

```bash
# 确保已安装Python 3.12.8
python --version

# 创建虚拟环境
python -m venv .venv
```

3. **激活虚拟环境**

```bash
# Windows系统
.venv\Scripts\activate

# 如果使用PowerShell，可能需要先执行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

4. **安装依赖**

```bash
# 更新pip
python -m pip install --upgrade pip

# 安装依赖包
pip install -r requirements.txt
```

5. **运行程序**

```bash
# 确保在项目根目录下
python launcher.py
```

### 常见问题

1. **虚拟环境激活失败**

   - 确保使用管理员权限运行命令提示符
   - 检查Python是否正确安装
   - 尝试重新创建虚拟环境
2. **依赖安装失败**

   - 检查网络连接
   - 尝试使用国内镜像源：
     ```bash
     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
     ```
3. **程序无法启动**

   - 确保所有依赖都已正确安装
   - 检查是否在正确的目录下运行
   - 查看错误日志获取详细信息

### 更新说明

如需更新到最新版本：

```bash
# 拉取最新代码
git pull origin master

# 更新依赖
pip install -r requirements.txt --upgrade
```

## 📁 项目结构

```
BKT-Xhydra/
├── models/                    # 模型相关代码
│   ├── bkt_model.py          # BKT模型实现
│   ├── recommender.py        # 推荐系统
│   ├── question_processor.py # 题目处理器
│   └── forgetting_curve.py   # 遗忘曲线模型
├── data/                     # 数据文件
│   ├── static/              # 静态资源
│   └── recommendation/      # 推荐系统数据
├── launcher.py              # 程序入口
├── login_window.py         # 登录界面
├── main_window.py          # 主界面
├── system.py               # 答题系统
├── update_checker.py       # 更新检查器
├── launcher.iss           # 安装程序配置
├── requirements.txt       # 项目依赖
└── LICENSE               # 授权文件
```

## 🔧 开发环境

- 🐍 Python 3.12.8
- 🖥️ PyQt6
- 📊 pandas
- 🔢 numpy
- 📈 matplotlib

## 🤝 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。

## 📄 授权条款

本项目采用 **[MIT 许可证](LICENSE)** 发布，允许商业和非商业用途的免费使用。

## 👨‍💻 开发团队

- xdhdyp (闲得慌的一匹) - 主要开发者
- Cursor AI - AI辅助开发

## 🙏 致谢

感谢所有为本项目提供帮助和建议的贡献者。

## 📝 开发声明

本项目由 xdhdyp 与 Cursor AI 共同开发完成。项目采用 MIT 许可证发布，详细条款请参见 [LICENSE](LICENSE) 文件。

### 功能完善度说明

- ✅ 已完成功能：

  - 基础答题系统
  - 用户登录注册
  - 简单的学习进度追踪
  - 基础的数据存储
- 🚧 开发中功能：

  - 智能推荐系统优化
  - 遗忘曲线预测
  - 高级数据分析
  - 多维度可视化
- 📋 计划功能：

  - 多用户协同学习
  - 知识图谱构建
  - 自适应学习路径
  - 移动端支持

> **注意：** 由于项目仍在开发中，部分功能可能不稳定或未完全实现。建议在使用时注意数据备份，并关注项目更新。
