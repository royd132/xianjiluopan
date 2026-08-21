# 先机罗盘公开数据缓存

> 核验日期：2026-08-21。原始数据默认只保存在本地，不随 Git 仓库分发；仓库提交下载脚本、来源清单和校验方法。

## 已下载并验证

| 数据 | 本地结果 | 产品用途 | 公开仓库策略 |
|---|---|---|---|
| ECB 汇率 / Frankfurter | 4 个币对，各 929 条，最新 2026-08-20 | 汇率风险、定价换算 | 脚本可复现，原始 CSV 忽略 |
| NY Fed GSCPI | 343 条月度数据，最新 2026-07-31 | 全球供应链压力 | 脚本可复现，原始 CSV 忽略 |
| World Bank / UNCTAD LSCI | 4 国共 64 条，最新可用年度 2021 | 市场航运连接度基线 | 脚本可复现，原始 CSV 忽略 |
| UN Comtrade | 88 条，4 国 × 2 个 HS × 2015–2025 | 进口额与同比变化 | 仅本地缓存，不再分发原始记录 |
| Amazon Reviews 2023 类目样本 | 4 类 × 4,000 条 | 多品类评论冷启动 | 研究用途本地缓存，不分发原文 |
| Amazon 自动喂食器商品元数据 | 250 个候选商品；严格口径 50 个商品、23 个有效价格 | 2023 商品级价格快照 | 研究用途本地缓存，不分发原文 |
| Amazon 商品匹配评论 | 流式扫描 355,676 条，保留 500 条；严格口径 75 条 | Qwen 商品级痛点抽取 | 研究用途本地缓存，不分发原文 |
| Olist 巴西电商样本 | `pet_shop` 1,710 个订单、1,947 条明细、650 条葡语评论 | 巴西历史成交先验与原语证据 | 来源脚本可复现，原始 CSV 忽略 |
| Amazon Reviews Multi 西语测试集 | 5,000 条 | 西语抽取器评测，不作为墨西哥市场事实 | 研究用途本地缓存，不分发原文 |

`scripts/data/verify_datasets.py` 会解析全部 CSV/JSONL 并输出行数与 SHA-256 前缀。2026-08-21 本机校验全部通过。

## 下载命令

安装数据脚本依赖：

```powershell
pip install -e ".[data]"
```

按来源单独下载：

```powershell
python scripts/data/download_fx.py
python scripts/data/download_gscpi.py
python scripts/data/download_world_bank_shipping.py
python scripts/data/download_comtrade.py
python scripts/data/download_amazon_samples.py
python scripts/data/download_amazon_metadata_sample.py
python scripts/data/download_amazon_matched_reviews.py
python scripts/data/download_olist.py
python scripts/data/download_multilingual_reviews.py
python scripts/data/verify_datasets.py
```

也可执行 `scripts/data/download_all.ps1`。Amazon 原始评论文件约 2.33 GB，脚本使用 HTTP Range 流式解压，只落盘与目标商品关联的记录。

## 真实模式如何使用

BR × 自动宠物喂食器的真实闭环当前使用：

1. Amazon 2023 商品元数据价格快照；
2. 与商品 ASIN 关联的 Amazon 原始评论；
3. Qwen 结构化痛点抽取，输出必须回指输入 review ID；
4. Olist `pet_shop` 葡语评论和历史成交；
5. ECB 汇率、UN Comtrade、NY Fed GSCPI、World Bank LSCI；
6. Harness 工具权限、组件快照、Trace、Checkpoint 与证据门禁。

真实模式不再使用冷启动的“Top 10 竞品空位”数值。由于当前 listing API 不可得，竞争卡会生成“审计 20 个现售商品”的验证任务，而不会伪造覆盖率。

## 没有接入的来源

| 缺口 | 尝试结果 | 当前处理 |
|---|---|---|
| 当日 Amazon / Mercado Libre 竞品价 | 官方公开搜索接口无可用免密路径；Mercado Libre 返回 403 | 使用 2023 商品快照，显式要求接入当前报价后重算 |
| Google Trends | 无官方公共 API，非官方抓取稳定性与条款风险较高 | 真实模式不生成搜索增长率 |
| Reddit 社媒 | 匿名 JSON 接口返回 403 | 不作为真实证据，不用 Mock 冒充 |
| GDELT 新闻趋势 | 本次请求触发 429 | 作为可选趋势 Provider，未进入当前结果 |
| 马来语电商评论 | 找到的数据多为合成、语言相邻或许可不清 | MY 真实模式披露原语缺口，不把印尼语/合成文本冒充马来语 |
| Shopee 当前商品样本 | 已下载 2026-08-06 快照，但样本为台湾站且价格被标记为 `[PREMIUM]` | 通过质量闸门拒绝，不接入 MY 决策 |
| SCFI 完整历史 | 上海航交所条款限制公开使用 | 本地旧缓存不进入真实 Provider，改用 NY Fed GSCPI |

## 许可与使用边界

- Amazon Reviews 2023 数据卡未给出明确再分发许可；仅用于本地研究与比赛验证，不随仓库提交原文。
- Amazon Reviews Multi 的原始数据许可限制研究使用；西语测试集只用于模型评测。
- UN Comtrade 条款对再分发和发布有限制；仓库只保留获取脚本与字段说明。
- Olist 官方公开数据仓库采用 MIT License，但结果仍按最小必要原则本地缓存。
- NY Fed、World Bank、ECB/Frankfurter 数据通过官方或官方数据衍生接口获取，并保留来源 URL 与采集日期。
- 任何来源都不能因为“网页可访问”就自动等同于“可公开再分发”。
