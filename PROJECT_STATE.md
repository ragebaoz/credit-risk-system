# 信用评估系统 - 项目状态快照
# 创建时间: 2026-05-05
# 最后更新: 2026-05-05

## 项目概述
- 路径: ~/credit-risk-system
- 技术栈: Python + venv + openpyxl + Playwright
- 数据源: 天眼查浏览器抓取 + 大众点评OpenCLI抓取 + 内部交易数据
- 输出: Excel信用评估报告（数据与逻辑明细）

## 核心配置文件

### config/weights.yaml（评分卡配置）
- 6维度，权重差异≤10%，总和100%
- 缺省指标默认分: 10分（严格策略）
- 维度权重:
  - 基础信用: 18%
  - 公司规模: 16%
  - 财务健康: 16%
  - 库存周转: 16%
  - 履约行为: 18%
  - 外部风险: 16%

### config/rules.yaml（规则引擎配置）
- 否决规则: 失信被执行人、经营异常、诉讼阈值（按规模分层）
- 头部连锁保底: 门店≥1000家 → 等级不低于A
- 微型企业否决: 门店<10家 → 等级最高C

## 关键代码文件状态

### src/models/scorecard.py
- 6维度评分卡模型
- 缺省分10分（数据缺失时）
- 天眼评分调整因子: 总分 = 原始分×0.3 + 天眼评分×0.7
- 门店规模系数: <10家=0×, 50家=1×, 1000家=5×, 中间线性插值
- 库存周转: 门店<5家时维度得0分

### src/models/rules.py
- 规则引擎: 否决/保底/预警/新客户规则
- _preprocess_data: 计算实缴资本、sudden_death_risk、dp_pause_ratio等
- _check_condition: 简单条件表达式解析
- 已修复: 确保executed_count/restriction_count等字段存在

### src/collectors/browser_tianyancha.py
- Playwright + CDP连接Chrome(端口9222)
- 已扩展: 返回insured_count、tianyancha_score、self_risk_count、around_risk_count
- 实缴资本: 直接返回原始值（非计算得出）

### src/collectors/base.py
- mock数据: 直接生成paid_in_capital原始值、insured_count等
- mock_financial_info: 默认返回None（触发缺省逻辑）

## 三家企业真实数据（天眼查）

| 指标 | 名创优品 | 潮品挚尚 | 力达动漫 |
|------|---------|---------|---------|
| 注册资本 | 14,686.24万 | 100万 | 50万 |
| 实缴资本 | 13,969.30万 | - | - |
| 参保人数 | 689 | 25 | 146 |
| 天眼评分 | 90 | 58 | 53 |
| 成立日期 | 2017-10-18 | 2014-07-30 | 2016-09-22 |
| 司法案件 | 13 | 3 | 1 |
| 自身风险 | 11 | 1 | 5 |
| 周边风险 | 185 | 1 | 8 |
| 经营异常 | 0 | 0 | 0 |
| 行政处罚 | 0 | 0 | 0 |
| 被执行人 | 0 | 0 | 0 |
| 失信记录 | 0 | 0 | 0 |

## 大众点评数据

### 名创优品（8城合计1226家）
| 城市 | 门店数 |
|------|--------|
| 广州 | 215 |
| 北京 | 192 |
| 深圳 | 185 |
| 上海 | 183 |
| 成都 | 167 |
| 郑州 | 108 |
| 武汉 | 93 |
| 杭州 | 83 |

### 潮品挚尚（8城合计56家）
| 城市 | 门店数 |
|------|--------|
| 深圳 | 34 |
| 上海 | 7 |
| 北京 | 6 |
| 杭州 | 6 |
| 广州 | 2 |
| 武汉 | 1 |
| 成都 | 0 |
| 郑州 | 0 |

### 力达动漫
- 门店数: 1（未抓取城市分布）

## 评估结果（基于真实数据）

| 客户 | 天眼评分 | 原始总分 | 调整后总分 | 评分卡等级 | 规则引擎 | 最终等级 | 授信额度 |
|------|---------|---------|-----------|-----------|---------|---------|---------|
| 名创优品 | 90 | ~60 | ~81 | BBB→A | 头部保底 | **A** | 750万 |
| 潮品挚尚 | 58 | ~55 | ~56 | BBB | 无触发 | **BBB** | ~82万 |
| 力达动漫 | 53 | ~45 | ~51 | BB→B | 微型否决 | **C** | 0 |

## 已知问题

1. **天眼查详情页抓取**: 需直接访问 `https://www.tianyancha.com/company/{id}`，搜索结果页只有部分数据
2. **实缴资本缺失**: 潮品挚尚、力达动漫天眼查未显示实缴资本，需处理缺省情况
3. **缺省分严格**: 无真实财报/内部交易数据的企业得分会被显著拉低（10分）
4. **around_risk_count代理**: 关联公司数量和健康状况用around_risk_count代理，大型集团可能偏高

## 常用命令

```bash
# 生成详细报告
cd ~/credit-risk-system && python3 scripts/generate_detailed_report.py

# 天眼查数据抓取
cd ~/credit-risk-system && python3 scripts/fetch_tianyancha_real.py

# 大众点评抓取
cd ~/credit-risk-system && python3 scripts/dianping_search.py "名创优品"

# 单客户评估（不带浏览器）
cd ~/credit-risk-system && python3 -m src.evaluation.client_eval --name "名创优品" --credit-code 91440101MA5AKFAH81 --industry 零售
```

## 输出文件
- `~/Desktop/信用评估_数据与逻辑明细.xlsx` - 主报告
- `~/Desktop/信用评估报告_可交互.xlsx` - 交互式报告
- `/tmp/tianyancha_real_data.json` - 天眼查原始数据
- `/tmp/dianping_mingchuang_8cities.json` - 名创优品城市数据
- `/tmp/dianping_chaopin_8cities.json` - 潮品挚尚城市数据

## 待办/后续优化
- [ ] 潮品挚尚、力达动漫实缴资本缺失处理
- [ ] 评估结果与天眼评分差异验证（名创优品81 vs 90）
- [ ] 引入真实财务报表数据
- [ ] 引入真实内部交易数据
