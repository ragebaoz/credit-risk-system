# 渠道客户信用风险评估与账期管理系统

## 项目背景
针对 B2B 渠道分销业务中的信用风险与账期管理问题，建立一套可动态评估、持续监控的客户信用管理体系。

## 核心功能
1. **客户信息收集**：整合工商信息、司法风险、舆情数据、财务报表等多维数据
2. **信用评估模型**：基于规则引擎 + 评分卡模型，输出风险等级
3. **账期决策引擎**：根据评估结果动态建议账期天数和授信额度
4. **定期监控预警**：持续跟踪客户状态变化，触发预警
5. **可视化报告**：生成客户信用报告和整体风险看板

## 项目结构

```
credit-risk-system/
├── config/              # 配置文件
│   ├── rules.yaml       # 评估规则配置
│   └── weights.yaml     # 模型权重配置
├── data/                # 数据存储
│   ├── clients.db       # SQLite 客户主数据库
│   └── history/         # 历史评估记录
├── src/
│   ├── collectors/      # 数据收集模块
│   │   ├── base.py
│   │   ├── enterprise.py    # 企业工商信息
│   │   ├── financial.py     # 财务数据解析
│   │   ├── judicial.py      # 司法风险
│   │   └── news.py          # 舆情监控
│   ├── models/          # 评估模型
│   │   ├── scorecard.py     # 评分卡模型
│   │   ├── rules.py         # 规则引擎
│   │   └── limits.py        # 账期限额计算
│   ├── evaluation/      # 评估执行
│   │   ├── client_eval.py   # 单客户评估
│   │   └── batch_eval.py    # 批量评估
│   ├── monitoring/      # 监控预警
│   │   ├── watcher.py       # 状态监控
│   │   └── alerts.py        # 预警通知
│   ├── utils/           # 工具函数
│   │   ├── database.py
│   │   ├── config_loader.py
│   │   └── validators.py
│   └── api/             # 对外接口
│       └── server.py
├── reports/             # 输出报告
├── scripts/             # 运维脚本
├── tests/               # 单元测试
└── requirements.txt
```

## 依赖

- Python 3.13+
- OpenCLI CLI（Node.js）：用于大众点评/天眼查浏览器自动化抓取

### OpenCLI 路径配置

默认会读取环境变量 `OPENCLI_PATH`，指向 OpenCLI 构建产物：

```bash
export OPENCLI_PATH=/Users/yuxuanyu/workspace/OpenCLI/dist/src/main.js
```

也可以复制 `.env.example` 为 `.env` 并在运行时加载。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库
python scripts/init_db.py

# 3. 配置评估规则（编辑 config/rules.yaml）

# 4. 添加客户并评估
python -m src.evaluation.client_eval --name "测试客户" --credit-code 91110000XXXXXXXX

# 5. 批量评估
python -m src.evaluation.batch_eval --input data/client_list.xlsx

# 6. 启动监控
python -m src.monitoring.watcher
```

## 评估维度说明

### 1. 基础信用维度（30%）
- 企业成立年限
- 注册资本实缴情况
- 股东背景
- 经营异常/行政处罚记录

### 2. 财务健康维度（35%）
- 资产负债率
- 流动比率/速动比率
- 营业收入增长率
- 经营现金流
- 净利润率

### 3. 履约行为维度（20%）
- 历史交易回款准时率
- 平均逾期天数
- 最大逾期金额
- 合作年限

### 4. 外部风险维度（15%）
- 司法诉讼（被告）数量
- 失信被执行人记录
- 股权冻结/质押
- 负面舆情

## 风险等级与账期映射

| 等级 | 分数范围 | 建议账期 | 建议授信额度 | 管理措施 |
|------|---------|---------|------------|---------|
| AAA | 90-100 | 90天 | 高 | 正常合作，年度复核 |
| AA | 80-89 | 60天 | 中高 | 正常合作，半年复核 |
| A | 70-79 | 30天 | 中 | 正常合作，季度复核 |
| BBB | 60-69 | 15天 | 中低 | 加强跟踪，月复核 |
| BB | 50-59 | 货到付款 | 低 | 款到发货或预付款 |
| B | 40-49 | 预付款 | 极低 | 停止新增合作 |
| C | <40 | 停止合作 | 0 | 启动催收/法律程序 |

## 数据收集说明

当前版本支持以下数据源：
- **企业工商信息**：天眼查/企查查 API（需申请 Key）
- **司法数据**：中国裁判文书网、执行信息公开网
- **舆情数据**：新闻搜索、社交媒体
- **财务数据**：客户提供的财务报表（PDF/Excel 解析）
- **内部交易数据**：ERP 系统导出数据

> **注意**：项目内置模拟数据生成器用于演示，生产环境请配置真实 API。
