# zhaobiao - 招投标自动化 Skill

> AI驱动的招投标全流程辅助工具，自动监测、下载、分析招标文件，辅助投标决策

## 🎯 核心能力

| 模块 | 功能 | 输入→输出 |
|------|------|----------|
| **M1 Monitor** | 招标信息监控 | 多源网站 → 招标摘要卡片 |
| **M2 Analyze** | 项目评估 | 招标信息 → 评分+建议 |
| **M3 Generate** | 投标文件生成 | 招标文件 → 技术方案/报价/资质清单 |
| **M4 Evaluate** | 评标辅助 | 投标文件 → 评标分析报告 |
| **M5 Contract** | 合同管理 | 合同文本 → 关键条款摘要 |

## 📂 目录结构

```
zhaobiao/
├── SKILL.md                    # Skill定义与使用指南
├── docs/                       # 文档资料
│   ├── platforms-research.md   # 平台调研报告
│   ├── tender-structure.md     # 招标文件结构研究
│   ├── checklist-template.md   # 投标清单模板
│   └── user-guide.md          # 用户手册
├── references/                 # 参考知识库
│   ├── bid-strategy.md        # 投标策略
│   ├── evaluation-criteria.md # 评标标准
│   ├── contract-templates.md   # 合同模板
│   ├── industry-regulations.md# 行业法规
│   └── risk-matrix.md          # 风险矩阵
├── templates/                  # 文档模板
│   ├── technical-proposal.md  # 技术投标书模板
│   ├── price-bid.md           # 商务报价书模板
│   ├── qualification-doc.md   # 资格证明文件清单
│   └── bid-checklist.md       # 投标准备检查清单
└── scripts/                    # 自动化脚本
    ├── monitor_tenders.py     # 招标信息监控
    ├── generate_technical.py # 技术方案生成
    ├── generate_price.py      # 商务报价生成
    ├── score_evaluation.py    # 评标打分辅助
    └── extract_contract.py    # 合同条款提取
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4 playwright python-docx pypdf
playwright install chromium
```

### 2. 配置监控

编辑 `scripts/monitor_tenders.py` 中的目标平台URL和筛选条件

### 3. 启动监控

```bash
python scripts/monitor_tenders.py
```

## 📖 详细文档

- [用户手册](docs/user-guide.md) - 完整使用指南
- [平台调研](docs/platforms-research.md) - 支持的平台列表
- [招标文件结构](docs/tender-structure.md) - 标书各章节说明
- [投标清单模板](docs/checklist-template.md) - 文件清单与合规检测

## ⚙️ 系统要求

- Python 3.9+
- 网络访问（目标招投标网站）
- Telegram Bot（可选，用于工作流提醒）

## 📄 License

Private - All Rights Reserved