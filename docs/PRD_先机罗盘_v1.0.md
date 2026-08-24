# 先机罗盘 · Foresight Compass

> **当前初赛创意口径（2026-08-24）**：对外定位已收敛为“跨境新品首单前的证据决策系统”，第四张卡统一展示为“最小市场验证卡”。为兼容既有 API、历史任务和代码示例，本文中的 `private_domain`、`PrivateDomainHook` 等底层字段名暂不迁移，其业务含义均指验证人群、验证渠道、验证话术与停止条件，不代表产品扩展到独立的私域营销场景。初赛执行口径以 [初赛版PRD.md](初赛版PRD.md) 和 [初赛提交材料.md](初赛提交材料.md) 为准。
## —— 产品需求文档（PRD）v1.0
### 可直接交付 UI 设计师 & 研发工程师的开发规格书

---

| 字段 | 内容 |
|------|------|
| **产品名称** | 先机罗盘 · Foresight Compass |
| **产品代号** | LumiSense-Forecast |
| **赛题归属** | AI+跨境电商私域流量赛 · 场景三「AI 市场洞察」 |
| **文档类型** | 完整 PRD（UI+R&D 可直接开发） |
| **版本** | v1.0 · 2026-08-13 |
| **状态** | 初稿（待 UI 研审 / 待技术评审） |
| **撰写** | 产品战略团队 · 主理人（Fang） |
| **参考架构** | Pico Harness / MindBridge 事件驱动 Runtime / Globex 双塔向量召回 / anker-ai-product-studio HITL 闸门 |

---

## 目录

| # | 章节 | 面向角色 |
|---|------|---------|
| 0 | 文档控制与变更日志 | 全部 |
| 一 | 产品概述：愿景、定位、核心价值主张 | 产品/全部 |
| 二 | 用户画像、故事与核心场景 | UI/产品/研发 |
| 三 | 功能需求规格（含验收标准） | 研发/UI/测试 |
| 四 | 非功能需求 | 研发/运维/测试 |
| 五 | 数据模型与 Schema 设计 | 研发/数据 |
| 六 | API 接口设计 | 研发/前端 |
| 七 | UI 交互规格与页面结构 | UI/前端 |
| 八 | 技术架构总览（Harness + Runtime + 自进化） | 研发/架构师 |
| 九 | Harness 层详细设计（基于 Pico） | 研发/架构师 |
| 十 | 事件驱动多Agent Runtime（基于 MindBridge） | 研发/架构师 |
| 十一 | 冷启动伪数据方案与 Demo 设计 | 全部 |
| 十二 | 跨境电商行业知识库设计 | 研发/产品 |
| 十三 | 技术选型对比与最终决策 | 研发/架构师/CTO |
| 十四 | 自进化飞轮架构 | 研发/架构师 |
| 十五 | Demo 演示脚本与评审预期 | 全部/评委 |
| 十六 | 里程碑路线图与交付计划 | 全部 |
| A | 附录 A：赛题要求→功能映射对照表 | 评委/产品 |
| B | 附录 B：竞品差异化矩阵 | 评委/产品 |
| C | 附录 C：术语表 | 全部 |

---

# 〇、文档控制与变更日志

## 0.1 变更记录

| 版本 | 日期 | 作者 | 变更内容 | 审批 |
|------|------|------|---------|------|
| v1.0 | 2026-08-13 | Fang | 初稿，完整 PRD | -- |

## 0.2 术语声明

| 术语 | 定义 |
|------|------|
| **决策卡 Decision Card** | 核心输出单元，带证据链、最小验证动作、反向条件、复核签字位的行动指令 |
| **Harness** | 统一处理 Agent 调用/上下文管理/记忆读写/工具执行/运行审计的中间件层 |
| **CollaborationBlackboard** | 基于"黑板模式"的事件驱动多Agent协作机制 |
| **反向条件 Failure Condition** | 决策卡中"什么情况下此结论失效"的字段 |
| **冷启动 Cold Start** | 使用合成伪数据构建初始可演示系统，后续切换真实数据源 |
| **验证落点 Minimum Validation Hook** | 决策卡强制字段，描述验证人群、验证渠道、验证话术与停止条件；底层兼容名为 `PrivateDomainHook` |

---

# 一、产品概述

## 1.1 一句话定位

**先机罗盘不做又一个数据看板，而是把全球多语言公开数据编译成中小跨境卖家首单前可执行的选品方向、定价策略、竞争打法和最小市场验证计划，并为每条结论附上可追溯证据、有效期与推翻条件。**

## 1.2 愿景

> 到 2027 年，让每一个跨境卖家在做出任何市场进入/选品/定价决策前，都能在 60 秒内获得一张「AI 生成 + 人工复核」的处方级决策卡，每条结论可点击追溯到原始数据来源，精确到「找哪个人群、在哪找、第一句话说什么」。

## 1.3 核心价值主张（为什么不是又一个 Jungle Scout）

| 维度 | 现有工具（JS/H10/卖家精灵） | 先机罗盘 |
|------|---------------------------|---------|
| **输出形态** | 指标/曲线/榜单（描述性） | **决策卡（处方性）——直接给"怎么办"** |
| **语言覆盖** | 英文为主 | **葡/阿/西/印尼/日/英多语言原生** |
| **数据时效** | 滞后（已卖好的才上榜） | **领先指标（运价/海关/TikTok→Shopee套利窗口）** |
| **备货前验证** | 无固定流程 | **每张卡强制带最小验证动作与停止条件** |
| **可证伪性** | 无（只告诉你"好卖"） | **每张卡带反向条件（什么时候失效）** |
| **合规** | 无 AI 标记 | **EU AI Act §50 原生内嵌（C2PA + 复核签字）** |
| **成本** | $49-$499/月 | **≈$0（公开数据 + 免费 LLM）** |

## 1.4 目标用户

### 一级用户（核心）

| 类型 | 画像 | 典型场景 | 核心痛点 |
|------|------|---------|---------|
| **副业新手** | 1人，业余运营，预算极紧 | 第一次选品，怕压货 | 不知道从哪开始；一次选错=本金归零 |
| **多平台试探期卖家** | 2-5人，有1平台经验 | 把A平台爆款搬去B平台 | 不知道新市场差异；搬品失败率高 |
| **工厂转型卖家** | 有产能缺市场认知 | 凭"能造什么"决定"卖什么" | 产能与需求脱节 |

### 二级用户（延伸）

| 类型 | 使用方式 |
|------|---------|
| **跨境电商服务商**（代运营/培训） | 批量生成品类洞察报告作为客户交付物 |
| **投资机构**（出海基金） | 扫描赛道机会，辅助尽职调查 |
| **平台方**（TikTok Shop/Shopee） | 招商时展示"这个品类在你平台有机会" |

## 1.5 产品边界

### ✅ In Scope（v1 必做）

- 四类决策卡引擎（选品/定价/竞争/最小市场验证）
- 多语言评论「我喜欢但是」痛点抽取与聚类
- 供应链领先指标预判（运价/海关/原料）
- 跨平台套利窗口捕捉
- 双塔向量召回（Chroma 本地 MVP）
- AgentLoop 主循环（Think→Act→Observe→Reflect）
- 事件驱动多Agent Runtime（CollaborationBlackboard）
- Harness 中间件层（上下文治理/记忆/Checkpoint/安全/评测）
- AGUI 事件流（SSE → 前端进度条 + 直觉vs有据双屏）
- 长期记忆 Store（Chroma + SQLite）
- 冷启动伪数据系统（可切换至真实数据）
- EU AI Act §50 合规标记
- Streamlit 前端（MVP）/ 后续升级 React

### ❌ Out of Scope（v1 不做）

- 自动下单/自动广告投放（超出"洞察"边界）
- 实时价格监控与自动调价
- 社交媒体自动发帖/私信
- 多租户 SaaS 化
- 移动端 App（MVP 仅 Web）
- 付费订阅/支付系统

---

# 二、用户故事与核心场景

## 2.1 Epic 1：获取一张选品方向卡

```
作为一个 副业新手卖家，
我想 输入一个我感兴趣的品类关键词（如"宠物喂食器"），
以便 在 60 秒内获得一张告诉我"做什么子品类、切哪个市场、以什么卖点切入"的决策卡，
并且 卡片上的每个结论都能点击看到原始数据来源。
```

**验收标准：**
- [ ] 从输入关键词到输出首张决策卡 ≤ 90 秒（冷启动 ≤ 30 秒）
- [ ] 卡片包含：行动指令 / 证据链（≥3条可下钻）/ 最小验证动作 / 反向条件 / 数据源披露 / 复核签字位
- [ ] 证据链中至少 1 条来自非英语数据源
- [ ] 缺少验证落点时卡片不生成，提示“无法确定最小验证动作”
- [ ] 反向条件 ≥ 1 条

## 2.2 Epic 2：「直觉 vs 有据」对照视图

```
作为一个 多平台试探期卖家，
我想 在看 AI 决策卡的同时并排看到"如果我自己凭经验会怎么做"的对照视图，
以便 判断 AI 的建议是否值得采纳。
```

**验收标准：**
- [ ] 左右分屏：左侧=AI决策卡，右侧=经验驱动空白模板
- [ ] 底部量化对比：AI命中已知痛点数 vs 经验命中数
- [ ] 对照视图可导出为 PNG/PDF

## 2.3 Epic 3：供应链信号预警

```
作为一个 工厂转型卖家，
我想 设置品类×市场的供应链监控，
以便 当运价异动或海关进口量突变时收到"该结论已失效"推送。
```

**验收标准：**
- [ ] 用户可配置监控规则（品类×市场×信号类型×阈值）
- [ ] 反向条件触发时自动推送失效通知
- [ ] 推送包含：原卡片摘要/触发条件/当前值/建议动作

## 2.4 Epic 4：跨语言隐性痛点探索

```
作为一个 想切入巴西市场的卖家，
我想 看到巴西消费者对竞品的葡语评论中被翻译工具忽略的隐性痛点，
以便 找到"大家都喜欢但都抱怨同一个问题"的差异化切入点。
```

**验收标准：**
- [ ] 痛点雷达图：X轴=痛点类型，Y轴=提及频次×情感强度
- [ ] 每个痛点点开后显示原始评论（保留原文）+ 中文翻译
- [ ] `hidden_pain: true` 评论高亮显示
- [ ] 支持按语言筛选（pt/ar/es/id/en/ja）

## 2.5 核心 Happy Path

```
输入(5s) → Agent 并行分析(30-60s) → 四卡输出(即时) → 人工复核 → 执行最小市场验证
```

**AGUI 进度条事件序列：**
1. `agent.start:collector_pt-BR` → "正在采集巴西市场数据..."
2. `agent.done:collector_pt-BR` → "✅ 巴西评论 217 条已采集"
3. `agent.start:analyzer_sentiment` → "正在进行情感分析..."
4. `observe:evidence_linked` → "✅ 已关联 3 条海关数据"
5. `reflect:gate_passed` → "🎴 决策卡生成中..."
6. `complete` → 四卡呈现

---

# 三、功能需求规格

## 3.1 功能一：决策卡引擎（核心）

### 描述

系统核心输出引擎。接收品类+市场输入，经 Agent 管线处理后输出最多四类标准化决策卡。**每张卡必须通过 Schema 强约束校验才能输出——缺少任意必填字段则不生成。**

### 决策卡 Schema（Pydantic —— 研发直接可用）

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class CardType(str, Enum):
    PRODUCT_SELECTION = "product_selection"
    PRICING = "pricing"
    COMPETITIVE = "competitive"
    PRIVATE_DOMAIN = "private_domain"

class ConfidenceLevel(str, Enum):
    HIGH = "high"      # ●●●●○
    MEDIUM = "medium"  # ●●●○○
    LOW = "low"        # ●●○○○

class EvidenceItem(BaseModel):
    """证据链条目——每条必须可溯源"""
    source_name: str = Field(..., description="数据源名称")
    source_type: str = Field(..., description="trend/review/customs/freight/rss/social")
    claim: str = Field(..., description="支撑的论断")
    raw_value: str = Field(..., description="原始数值或文本")
    url: Optional[str] = Field(None)
    collected_at: str = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)

class PrivateDomainHook(BaseModel):
    """最小市场验证落点，保留旧类名以兼容 API"""
    seed_audience: str = Field(..., description="种子人群")
    channel: str = Field(..., description="承接渠道")
    hook_message: str = Field(..., description="话术钩子")
    expected_conversion_hint: Optional[str] = None

class FailureCondition(BaseModel):
    """反向条件——什么情况下此结论失效"""
    condition: str = Field(...)
    metric_to_watch: str = Field(...)
    threshold: str = Field(...)
    action_on_trigger: str = Field(...)  # recalculate/abort/watch

class DecisionCard(BaseModel):
    """决策卡——核心数据结构"""
    card_id: str                          # UUID v4
    card_type: CardType
    version: int = 1
    
    # 行动指令区
    action_title: str                     # "做静音款宠物喂食器·切巴西市场"
    action_detail: str                    # 1-3句详情
    
    # 置信度与时效
    confidence: ConfidenceLevel
    confidence_score: float               # 0.0-1.0
    validity_days: int = 14               # 有效期天数
    generated_at: str                     # ISO 8601
    expires_at: str                       # ISO 8601
    
    # 证据链（≥3条）
    evidences: List[EvidenceItem] = Field(..., min_length=3)
    
    # 最小市场验证落点（强制，字段名保持兼容）
    private_domain_hook: PrivateDomainHook
    
    # 反向条件（≥1条）
    failure_conditions: List[FailureCondition] = Field(..., min_length=1)
    
    # 数据源披露
    data_sources: List[str]
    collection_timestamp: str
    
    # 合规标记（EU AI Act §50）
    ai_generated: bool = True
    c2pa_signature: Optional[str] = None   # v2
    human_review_status: str = "pending"  # pending/approved/rejected/discussed
    human_reviewer: Optional[str] = None
    human_reviewed_at: Optional[str] = None
    
    # 卡片专属扩展
    card_specific_data: dict = Field(default_factory=dict)


# ======== 各卡专属数据 ========

class ProductSelectionData(BaseModel):
    opportunity_category: str
    target_market: str
    differentiation_point: str
    avoid_risks: List[str] = []
    blue_ocean_index: float = Field(..., ge=0.0, le=1.0)
    competitor_count_top10: int

class PricingData(BaseModel):
    anchor_price: float
    price_range_p25: float
    price_range_p75: float
    currency: str = "USD"
    gross_margin_assumption: dict       # {cost, freight, platform_fee, margin_pct}
    price_adjustment_triggers: List[dict] = []

class CompetitiveData(BaseModel):
    pain_point_aligned_copy: str        # 痛点对位卖点话术
    channel_recommendation: str
    defense_actions: List[str] = []
    competitor_price_monitor_list: List[str] = []

class PrivateDomainData(BaseModel):
    audience_persona: dict              # {age, gender, income, behavior, pain_points}
    gathering_places: List[str]
    hook_messages: List[str]            # 多条话术选项
    repurchase_signal_strength: str     # strong/moderate/weak
```

### 验收标准

| # | 验收项 | 通过标准 | 优先级 |
|---|--------|---------|--------|
| F-001 | Schema强约束 | 缺private_domain_hook返回`CARD_REJECTED_MISSING_HOOK` | 🟢P0 |
| F-002 | 证据链数量 | evidences ≥ 3，否则置信度降为LOW | 🟢P0 |
| F-003 | 反向条件 | failure_conditions ≥ 1 | 🟢P0 |
| F-004 | EU AI Act标记 | ai_generated=True + status=pending | 🟢P0 |
| F-005 | 有效期管理 | 过期后前端灰显+"已过期请重算" | 🟡P1 |
| F-006 | 版本递增 | 重算时version++，旧卡归档 | 🟡P1 |
| F-007 | JSON导出 | 支持导出完整JSON | 🔵P2 |

---

## 3.2 功能二：多语言「我喜欢但是」痛点雷达

### 描述

采集全球多语言电商平台公开评论，用LLM直接对原文（不翻译）进行结构化抽取，识别"正面整体+负面局部"让步结构，聚合成可视化痛点雷达。

### 让步结构检测规则（多语言正则）

| 语言 | 正则标记词 | 示例 |
|------|-----------|------|
| English | `\b(but\|however\|although\|though)\b` | "I love it **but** the battery..." |
| Portuguese | `\b(mas\|porém\|contudo\|todavia)\b` | "Adoro **mas** a bateria..." |
| Arabic | `\b(لكن\|ولكن\|غير أن)\b` | "جميل **لكن** البطارية..." |
| Spanish | `\b(pero\|sin embargo\|no obstante)\b` | "Me gusta **pero** la batería..." |
| Indonesian | `\b(tetapi\|namun\|akan tetapi)\b` | "Suka **tetapi** baterai..." |
| Japanese | `\b(が\|しかし\|だが\|でも)\b` | "好き**が**電池..." |
| Chinese | `\b(但是\|不过\|然而\|美中不足)\b` | "很喜欢**但是**电池..." |

### 验收标准

| # | 验收项 | 通过标准 | 优先级 |
|---|--------|---------|--------|
| F-201 | 多语言覆盖 | en/pt/ar/es/id 至少4种 | 🟢P0 |
| F-202 | 隐性痛点占比 | hidden_pain=true 占总检测评论 ≥15% | 🟢P0 |
| F-203 | 雷达渲染 | 气泡大小∝opportunity_index，颜色按pain_type分组 | 🟢P0 |
| F-204 | 原文下钻 | 点击展开原文+中文翻译 | 🟡P1 |

---

## 3.3 功能三：供应链波动「提前量」预判

### 数据源

| 信号类型 | 数据源 | 更新频率 | 用于 |
|---------|--------|---------|------|
| 海运运价 | FBX / SCFI | 周/日 | 定价卡毛利假设 |
| 海关进口量 | UN Comtrade / 中国海关 | 月/季 | 选品卡市场需求验证 |
| 原材料期货 | LME / CBOT / DCE | 日 | 成本趋势预判 |
| 汇率 | ECB / 人民银行 | 日 | 定价本地币种换算 |

### 预置预警规则示例

```python
PRESET_RULES = [
    {
        "rule_id": "freight-001",
        "name": "南美航线运价暴涨",
        "metric": "FBX12_wow_pct_change",
        "condition": "pct_change_gt",
        "threshold": 15.0,
        "affected_card_types": ["pricing"],
        "action": "recalculate",
        "message": "⚠️ 南美航线运价周环比上涨{value}%，定价卡毛利可能失效"
    },
    {
        "rule_id": "customs-001", 
        "name": "目标市场进口暴增",
        "metric": "import_yoy_pct",
        "threshold": 40.0,
        "affected_card_types": ["product_selection"],
        "action": "notify_only",
        "message": "📈 {market} HS{code} 进口额 YoY+{value}%，蓝海窗口可能在收窄"
    }
]
```

---

## 3.4 功能四：跨平台套利窗口捕捉

监测同一品类在不同平台的供需错配（如 TikTok 爆了但 Shopee 还没铺货）。

---

## 3.5 功能五：最小市场验证地图

**映射逻辑**：品类痛点 → 受困扰的人群 → 该人群在目标市场的聚集地 → 最佳触达话术

示例：`"静音喂食器"` → `养宠+夜班人群` → `WhatsApp养宠社群` → `"让它半夜别吵醒你"`

---

# 四、非功能需求

## 4.1 性能

| 指标 | MVP目标 |
|------|--------|
| 端到端响应（输入→首卡） | ≤90秒（伪数据≤30秒） |
| SSE事件延迟 | ≤2秒 |
| 并发用户 | ≥5（MVP单机） |
| 向量检索延迟（百万级） | ≤500ms |
| 首页加载 | ≤3秒 |

## 4.2 可靠性

| 指标 | 目标 |
|------|------|
| 卡片生成成功率 | ≥95%（数据充足时） |
| LLM容错 | 单模型失败自动fallback链 |
| 数据采集容错 | 单源失败降级输出+标注 |
| Checkpoint恢复率 | ≥98% |

## 4.3 安全

- XSS/SQL注入防护
- API Key环境变量存储
- 文件操作沙箱隔离
- 敏感信息脱敏（手机/邮箱/地址）
- 高风险操作二次确认

## 4.4 合规（EU AI Act §50）

| 要求 | 实现 |
|------|------|
| AI生成标识 | `ai_generated:true` + 前端🤖标签 |
| C2PA凭证 | v1占位，v2对接签名服务 |
| 人工复核 | pending→approved/rejected流转 |
| 透明度 | 数据源披露+证据链下钻 |

---

# 五、数据模型设计

## 5.1 核心ER关系

```
User(1)──<(N) InsightTask(N)──<(N) DecisionCard(N)
                                          │
                              ┌────────────┼────────────┐
                              │            │            │
                        FailureCondition  RawEvidence   (card_specific_data)
                                              │
                        ┌─────────┬─────────┼─────────┐
                        │         │         │         │
                      Review   TrendPoint  SupplySignal
```

## 5.2 存储方案

| 数据 | MVP存储 | 演进 |
|------|---------|------|
| 用户/任务/卡片 | SQLite | PostgreSQL |
| 原始证据 | JSON文件 | 对象存储(S3/OSS) |
| 向量索引 | ChromaDB本地 | Qdrant/Milvus集群 |
| 运行日志 | JSONL(append-only) | ClickHouse/Elastic |
| 配置 | YAML文件 | 配置中心 |
| Mock数据 | SQLite预填充+CSV种子 | 同左 |

---

# 六、API接口设计

## 6.1 接口清单

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/v1/tasks` | 创建洞察任务 |
| GET | `/api/v1/tasks/:id` | 查询任务状态 |
| GET | `/api/v1/tasks/:id/stream` | SSE进度流 |
| GET | `/api/v1/cards/:id` | 获取单张决策卡 |
| GET | `/api/v1/cards/:id/evidence` | 证据链详情 |
| POST | `/api/v1/cards/:id/review` | 人工复核 |
| GET | `/api/v1/pain-radar/:task_id` | 痛点雷达数据 |
| GET | `/api/v1/supply-chain/alerts` | 供应链预警列表 |
| POST | `/api/v1/supply-chain/rules` | 创建预警规则 |
| GET | `/api/v1/categories/seed` | 种子品类列表 |
| GET | `/api/v1/health` | 健康检查 |

## 6.2 SSE事件格式

```
event: agent_start
data: {"agent_id":"collector_br","type":"collector","market":"BR","message":"正在采集巴西Amazon评论..."}

event: agent_progress  
data: {"agent_id":"collector_br","progress":0.6,"collected":130,"target":217}

event: agent_done
data: {"agent_id":"collector_br","duration_sec":12.3,"records_collected":217}

event: reflect
data: {"gate":"passed","confidence":0.82,"cards_to_generate":4}

event: complete
data: {"task_id":"...","status":"completed","duration_sec":42,"cards_generated":4}
```

## 6.3 错误码

| HTTP | Error Code | 含义 |
|------|-----------|------|
| 400 | INVALID_KEYWORD | 关键词为空或超长 |
| 409 | TASK_ALREADY_RUNNING | 已有运行中的任务 |
| 422 | CARD_REJECTED_MISSING_HOOK | 缺少最小验证动作 |
| 503 | LLM_PROVIDER_DOWN | 所有LLM不可用 |
| 503 | DATA_SOURCE_TIMEOUT | 数据源超时（降级输出） |

---

# 七、UI交互规格

## 7.1 信息架构

```
先机罗盘首页
├── Hero区（搜索框 + 品类快捷入口 + 直觉/有据切换开关）
├── 洞察工作区
│   ├── 进度面板（SSE实时进度条 + Agent状态指示器）
│   ├── 结果展示区
│   │   ├── 四宫格决策卡（Tab切换/网格并列两种视图）
│   │   ├── 痛点雷达图（独立Panel，可折叠）
│   │   └── 供应链仪表盘（独立Panel，可折叠）
│   └── 操作栏（导出/分享/新建）
├── 历史记录侧边栏
├── 设置页（数据源/预警规则/关于/合规说明）
└── 页脚（EU AI Act标识 + 数据源披露）
```

## 7.2 首页布局规格

```
┌──────────────────────────────────────────────────────────┐
│ 🔍 先机罗盘 · Foresight Compass     ⚙️设置  📋历史      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│   ┌──────────────────────────────────────┐               │
│   │  输入品类关键词...          [开始洞察] │               │
│   └──────────────────────────────────────┘               │
│                                                          │
│  热门：[宠物喂食器] [便携榨汁机] [环形灯] [降噪耳机] [手表带]│
│  市场：☑巴西 ☑美国 ☑马来西亚 ☑墨西哥 ☑全部              │
│                                                          │
│  ┌────────────────┬────────────────┐                    │
│  │ ☭ 直觉模式     │ ☭ 有据模式(AI) │ ← 切换             │
│  └────────────────┴────────────────┘                    │
└──────────────────────────────────────────────────────────┘
```

## 7.3 决策卡详情视觉规范

```
┌──────────────────────────────────────────────────────────┐
│ 🎴 选品方向卡                      ●●●●○  有效14天       │
│ ──────────────────────────────────────────────────────── │
│ ▶ 行动指令                                                  │
│   ┌──────────────────────────────────────────────────┐   │
│   │ 做「静音款」宠物自动喂食器 · 切入巴西市场         │   │
│   │ 主打"夜间不吵醒主人"差异化                         │   │
│   └──────────────────────────────────────────────────┘   │
│ ▼ 凭什么（证据链·3条）                                     │
│   📊 Google Trends/Brazil "pet feeder" 90d +64%  [▸曲线] │
│   💬 葡语评论217条中38%出现"喜欢但太吵"    [▸82条原文]   │
│   📦 巴西HS 8509进口额同比+41%           [▸UN Comtrade] │
│ ▶ 最小市场验证                                               │
│   人群：养宠+夜班/浅眠  渠道：WhatsApp养宠群                │
│   话术："让它半夜别吵醒你"  [📋一键复制]                   │
│ ▶ 什么情况下失效                                             │
│   ⚠️ Top10出现≥2款静音款→窗口关闭                         │
│   ⚠️ FBX南美运价环比>+15%→毛利需重算                       │
│ ▶ 数据源与合规                                               │
│   GT/Reddit/UN Comtrade/FBX/Amazon-BR  2026-08-13 14:20  │
│   🤖AI生成·需人工复核(EU AI Act §50)                       │
│ ──────────────────────────────────────────────────────── │
│ 人工复核：[✅采纳] [❌驳回] [💬待议]                        │
└──────────────────────────────────────────────────────────┘
```

## 7.4 Design Token（UI团队可直接使用）

```css
:root {
  --color-primary: #2563EB;
  --color-success: #059669;
  --color-warning: #D97706;
  --color-danger: #DC2626;
  --color-bg-primary: #FFFFFF;
  --color-bg-secondary: #F8FAFC;
  --color-text-primary: #0F172A;
  --color-text-secondary: #64748B;
  --color-border: #E2E8F0;
  --color-card-high: #DCFCE7;
  --color-card-medium: #FEF3C7;
  --color-card-low: #FEE2E2;
  --radius-md: 8px;
  --radius-lg: 12px;
  --shadow-card: 0 1px 3px rgba(0,0,0,0.08);
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

---

# 八、技术架构总览

## 8.1 分层架构

```
┌─────────────────────────────────────────────────┐
│  表现层: Streamlit(MVP) → React+Next.js(v2)     │
│  SSE消费者 · 决策卡渲染器 · 痛点雷达图表          │
├─────────────────────────────────────────────────┤
│  API层: FastAPI · SSE Endpoint · RESTful CRUD   │
├─────────────────────────────────────────────────┤
│  ★ Harness层（基于Pico）                         │
│  上下文治理 │ 记忆管理(4层) │ Checkpoint/Resume  │
│  工具安全治理 │ TraceWriter审计                   │
├─────────────────────────────────────────────────┤
│  ★ Agent Runtime层（基于MindBridge事件驱动）       │
│  CollaborationBlackboard 黑板模式                 │
│  Coordinator(协调) ↔ Collector(采集×N)           │
│                  ↔ NLPAnalyzer(分析×N)           │
│                  ↔ Retrieval/Compiler            │
│                  SafetyAgent(闸门校验)            │
├─────────────────────────────────────────────────┤
│  AgentLoop主循环                                   │
│  Think→Act(调度fork)→Observe(收集+压缩)            │
│  →Reflect(三道闸门)→[二次Act/出卡]                │
├─────────────────────────────────────────────────┤
│  能力层: 双塔向量召回 │ LLM路由Fallback           │
│  数据采集(多源) │ 供应链信号(运价/海关)            │
├─────────────────────────────────────────────────┤
│  数据层: SQLite │ ChromaDB │ JSON Files │ CSV    │
├─────────────────────────────────────────────────┤
│  ★ 自进化层: Rubric评测 → 失效监控 → 反馈沉淀     │
│  → 记忆更新 → 模型微调(SFT/LoRA)                 │
└─────────────────────────────────────────────────┘
```

## 8.2 核心架构决策（ADR）

| # | 决策 | 选择 | 替代方案 |
|---|------|------|---------|
| ADR-001 | 编排框架 | LangGraph StateGraph(MVP)+自研事件驱动(v2) | 纯LangChain SequentialChain |
| ADR-002 | 前端 | Streamlit(MVP)→React+Next.js(v2) | Gradio/Flask Jinja2 |
| ADR-003 | 向量库 | ChromaDB(MVP)→Qdrant/Milvus(v2) | FAISS/Pinecone |
| ADR-004 | Embedding | all-MiniLM-L6-v2(本地)→Gemini Embedding(免费API) | OpenAI Ada(付费) |
| ADR-005 | LLM策略 | 多Provider路由+Fallback链 | 单一Provider |
| ADR-006 | 协议 | SSE(单向推送) | WebSocket/Polling |
| ADR-007 | Harness | 自研(参考Pico) | LangSmith(付费)/无Harness |

---

# 九、Harness层详细设计（基于Pico）

> ⭐ 核心技术章节——统一管理Agent上下文/记忆/状态恢复/安全/审计。

> 📌 **研究结论（来自 `2-pico.pdf` 源码级提取）**：Pico 的 Harness 范式可概括为「**有状态、有边界、有验证、有复盘**的执行链路」。迁移到跨境电商AI决策引擎时，**最高杠杆的三处**是：
> ① **上下文/记忆的 freshness 机制**（决策强依赖数据时效，过期数据比没记住更危险）；
> ② **workspace 漂移 + 误信旧状态检测**（防过期市场数据驱动错误决策）；
> ③ **评测的 verifier 走样本外业务指标回测**（而非模型自评）。
> 下文 9.2~9.6 对应该范式的五个模块，每个均标注 Pico 原始实现参数，研发可直接对齐。

## 9.1 Harness组件

```
┌─────────────────────────────────────────────────┐
│              LumiSenseHarness                   │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ContextMgr│ │MemoryStore│ │CheckpointMgr   │  │
│  │上下文治理│ │记忆存储   │ │快照/恢复       │  │
│  └────┬─────┘ └────┬─────┘ └───────┬────────┘  │
│       └────────────┼──────────────┘            │
│  ┌────────────────▼────────────────────────┐   │
│  │           ToolExecutor                   │   │
│  │   工具执行器(沙箱+审批+去重+脱敏)        │   │
│  └────────────────┬───────────────────────┘   │
│  ┌────────────────▼────────────────────────┐   │
│  │           TraceWriter                   │   │
│  │   运行审计(JSONL append-only)            │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## 9.2 上下文管理 ContextManager

### 问题：Prompt膨胀

一次完整"洞察"涉及5-8个子Agent、10-20次工具调用，上下文易超限且冗余降低推理质量。

### 方案：分层上下文+预算裁剪

```python
class ContextLayer(Enum):
    SYSTEM = "system"              # L0: 系统指令（固定保留）
    TASK_CONTEXT = "task"          # L1: 任务定义+用户输入（固定保留）
    ACTIVE_EVIDENCE = "active"     # L2: 当前处理的证据（低概率裁剪）
    HISTORICAL_OBSERVE = "history" # L3: 历史观察（中概率裁剪）
    TOOL_OUTPUT = "tool"           # L4: 工具原始输出（高概率裁剪）

class ContextBudget:
    def __init__(self, max_tokens: int = 128000):
        self.layer_weights = {
            ContextLayer.SYSTEM: 0.0,       # 不可裁剪
            ContextLayer.TASK_CONTEXT: 0.0,
            ContextLayer.ACTIVE_EVIDENCE: 0.3,
            ContextLayer.HISTORICAL_OBSERVE: 0.6,
            ContextLayer.TOOL_OUTPUT: 0.9,   # 最优先裁剪
        }
    
    def trim(self, messages: list) -> list:
        pressure = self._count_tokens(messages) / (self.max_tokens * 0.85)
        if pressure > 0.9:
            messages = self._summarize_tool_outputs(messages)
        if pressure > 0.8:
            messages = self._prune_old_observes(messages, keep_n=5)
        return messages
```

### Pico 具体实现参考（来自 `2-pico.pdf` 第06章，研发可直接对齐）

Pico 的上下文治理不是抽象分层，而是**固定 section 顺序 + 固定预算 + 固定裁剪顺序**的确定性装箱算法：

```python
# 入口处先裁长输出（避免原始 dump 撑爆上下文）
MAX_TOOL_OUTPUT = 4000
def clip(text: str, limit: int = MAX_TOOL_OUTPUT) -> str:
    return text[:limit] + "..." if len(text) > limit else text

# 固定 section 预算（Pico 实测值，单位：字符）
DEFAULT_SECTION_FLOORS = {
    "prefix": 3600,           # L0 系统指令 + L1 任务定义（稳定背景）
    "memory": 1600,           # 工作记忆（任务摘要/最近文件/新鲜文件摘要）
    "relevant_memory": 1200,  # 相关记忆召回（每条 note 平分，防一条超长挤掉其他）
    "history": 5200,          # 历史分析过程（近因优先，最近6轮保留detail）
    "current_request": 0,     # 当前决策问题——永远原样，绝不裁剪
}
TOTAL_BUDGET = 12000

# 超预算时的收缩顺序（被裁概率从高到低）
DEFAULT_REDUCTION_ORDER = ("relevant_memory", "history", "memory", "prefix")
# current_request 不在收缩顺序中——这是"保底约束：当前用户请求永远不裁坏"
```

> ⚠️ **关键适配差异（来自研究 Agent 提醒）**：Pico 预算是 **char 级**，而决策引擎处理中文/英文混合报表、JSON 数据，**必须升级为 token-aware 预算**（中文 1 字 ≈ 1-2 token，英文 1 词 ≈ 1.3 token）。建议用 `tiktoken` 或本地 tokenizer 替换 `len(text)` 计数。

### 目标（参考Pico基线）

| 指标 | Pico基线 | 先机罗盘目标 |
|------|---------|------------|
| 平均压缩率 | 16-19%（实测 6964→5418 字符，18.01%；最高 35.63%） | 15-25%（token-aware） |
| 最高压缩率 | 33% | ≥30% |
| 裁坏率 | 0%（当前请求绝不裁坏） | 0%（freshness校验 + current_request 永不裁剪双保险）|

## 9.3 记忆系统 MemoryStore（4层分层）

```
L0: Task Summary（任务摘要）        → 内存（当前任务生命周期）
L1: Category Knowledge（品类知识）   → ChromaDB（跨任务持久化，可检索）
L2: Session Notes（过程笔记）       → SQLite（当前会话有序）
L3: Relevant Recall（相关记忆召回）  → ChromaDB+SQLite（跨会话用户画像）
```

### Freshness校验（防重复读取）

```python
class MemoryFreshness:
    def __init__(self, ttl_seconds: int = 300):  # 5分钟TTL
        self.ttl = ttl_seconds
        self._access_log: dict[str, float] = {}
    
    def is_fresh(self, memory_key: str) -> bool:
        last = self._access_log.get(memory_key, 0)
        return (time.time() - last) < self.ttl
    
    def should_recall(self, memory_key: str) -> bool:
        return not self.is_fresh(memory_key)
```

### Pico 具体实现参考（`2-pico.pdf` 第05章）

Pico 的 freshness 机制比简单 TTL 更精确——**基于内容哈希而非时间**，且写操作主动失效旧摘要：

```python
class FileSummaryStore:
    """文件摘要存储（对应 Pico file_summaries）"""
    def __init__(self):
        self._summaries: dict[str, dict] = {}  # path → {summary, created_at, content_hash}
    
    def file_freshness(self, path: str) -> bool:
        """基于文件内容哈希判断摘要是否仍新鲜（而非简单TTL）"""
        current_hash = hashlib.md5(Path(path).read_bytes()).hexdigest()
        stored = self._summaries.get(path)
        return stored is not None and stored["content_hash"] == current_hash
    
    def invalidate_file_summary(self, path: str):
        """write_file / patch_file 后主动失效旧摘要——避免旧结论复用"""
        self._summaries.pop(path, None)

class ExplainableRetriever:
    """
    可解释召回排序（Pico retrieval_candidates）——非语义检索，便于复盘。
    排序优先级：tag命中 > 关键词重叠 > 时间新旧 > 插入顺序
    """
    def rank(self, candidates: list, query) -> list:
        return sorted(candidates, key=lambda c: (
            -self._tag_hit(c, query),       # tag 命中优先级最高
            -self._keyword_overlap(c, query), # 关键词重叠次之
            -self._recency(c),               # 时间新旧
            self._insertion_order(c)         # 插入顺序兜底
        ))
```

**决策引擎扩展字段**（Pico `working` 预留字段 → 直接映射）：

| Pico 字段 | 决策引擎语义 | 用途 |
|-----------|------------|------|
| `current_plan` | 当前选品/定价/库存计划 | 任务板当前阶段 |
| `open_questions` | 待确认的市场问题 | 指挥 Agent 下一步 fork 方向 |
| `confirmed_findings` | 已证实的市场结论 | 写入 L1 品类知识，后续检索召回 |
| `blocked_on` | 缺某数据源/资质 | 触发降级输出 + 标注 |
| `next_action` | 下一动作 | Checkpoint 恢复入口 |

### 效果目标

| 指标 | Pico基线 | 目标 |
|------|---------|------|
| 重复读取次数 | 8→3（12个记忆依赖任务，on/off/irrelevant三对照验证） | N→0 |
| 额外工具调用 | 0.67→0.25 | ≤0.1次/任务 |
| 任务正确率 | 66.7%→100%（且 irrelevant 组无同等收益，证明结构化记忆而非多塞上下文的功劳） | 显著提升 |

## 9.4 Checkpoint/Resume（任务恢复）

```python
class Checkpoint(BaseModel):
    checkpoint_id: str
    task_id: str
    phase: str  # collecting/analyzing/retrieving/compiling/reviewing/done
    phase_progress: float  # 0.0-1.0
    completed_agents: List[str]
    agent_results: Dict[str, Any]
    context_snapshot_hash: str  # workspace drift检测
    evidence_files: List[str]
    resume_count: int = 0
    total_elapsed_sec: float = 0.0
```

### Workspace Drift检测

```python
class WorkspaceDriftDetector:
    def detect_drift(self, checkpoint, current_state) -> DriftResult:
        checks = {
            "config_changed": self._check_config_hash(checkpoint),
            "data_stale": self._check_data_freshness(checkpoint),
            "model_changed": self._check_model_version(checkpoint),
        }
        critical_any = any(c.critical for c in checks.values() if c)
        return DriftResult(
            has_drift=critical_any or sum(1 for c in checks.values() if c.drifted) >= 2,
            safe_to_resume=not critical_any
        )
```
**目标：workspace drift识别率100%，无误信旧状态继续执行。**

### Pico 具体实现参考（`2-pico.pdf` 第07章）

Pico 把「session（可序列化状态）」与「run artifact（刚发生了什么的证据）」**彻底分开**：`SessionStore` 存 `.pico/sessions/<id>.json`（history+memory），`RunStore` 存 `.pico/runs/<id>/`（task_state.json 快照 + trace.jsonl 事件流 + report.json 聚合）。恢复走 session，不恢复进程对象。

**恢复前一致性校验（最高价值迁移点）**：

```python
class ResumeValidator:
    """
    恢复前先做一致性检查——Pico 强调「最危险的不是恢复失败，而是恢复错了还继续跑」。
    """
    def evaluate_resume_state(self, checkpoint: Checkpoint, current: dict) -> ResumeVerdict:
        checks = {
            "checkpoint_valid": self._check_schema(checkpoint),      # schema 版本兼容
            "key_data_fresh": self._check_key_files_freshness(checkpoint),  # 关键数据哈希
            "runtime_identity": self._check_runtime_identity(checkpoint, current),  # 运行模式(只读vs执行)
        }
        # 恢复风险五分类（Pico 10场景测试）：
        # ① 基础checkpoint恢复 ② 部分状态过期(单/多文件) ③ workspace漂移(指纹变)
        # ④ checkpoint不兼容(schema mismatch) ⑤ 工具半成功后恢复(shell半成功)
        return ResumeVerdict(
            status=self._classify(checks),
            safe_to_resume=all(v.passed for v in checks.values()),
            freshness_recheck_required=True  # 强制 freshness 重校，防误信旧状态
        )
```

**决策引擎头号风险映射**：Pico 唯一"未恢复成功"的场景是「完全无恢复基础」，而**最危险的是恢复错还继续跑**——映射为「用已失效的库存/汇率/竞品快照继续给出采购建议」。因此决策引擎必须在 Checkpoint 恢复链路强制 freshness 重校（数据源版本号 + 报表日期 + 账号指纹三者任一变更即视为 mismatch）。

### 当前边界（需在决策引擎补强）

| Pico 边界 | 决策引擎补强 |
|-----------|------------|
| run artifact 无 schema version | 给 task_state.json 加 `schema_version` 字段 |
| resume 一致性检查弱 | 显式校验（数据源版本/报表日期/运行模式） |
| 仅验证恢复成功与否 | 增加"恢复后决策一致性"断言（对比恢复前后卡片结论） |

## 9.5 工具安全治理 ToolSafety

| 规则 | 实现 | 拦截场景 |
|------|------|---------|
| 参数校验 | Pydantic Schema | 空keyword/非法market |
| 工作区隔离 | 路径白名单 | 防越权读写 |
| 高风险审批 | 删除/批量导出需确认 | 防误操作 |
| 重复调用拦截 | 同方法+同参数60s内去重 | 防死循环 |
| 敏感信息脱敏 | 正则替换手机/邮箱/IP | 隐私保护 |
| Partial Success | 结构化结果(success/partial/fail) | 部分成功不阻塞 |

### Pico `run_tool()` 标准执行序列（`2-pico.pdf` 第02/03章）

所有工具调用**统一走 `run_tool()` 入口**，不允许函数直跳——保证安全链不被绕过：

```python
def run_tool(self, tool_name: str, **kwargs) -> ToolResult:
    # 1. 注册校验 → 2. 参数校验(Pydantic) → 3. 重复调用检测(60s内同参去重)
    # 4. 高风险审批(删除/批量导出需确认) → 5. 执行 → 6. 结果裁剪(clip 4000) + 更新memory局部事实
    # 结果回到主循环，不脱离控制流
    for step in [validate_registry, validate_params, check_dedup,
                 check_high_risk_approval, execute, trim_and_update_memory]:
        result = step(tool_name, kwargs)
        if result.blocked:
            return result  # 任一环节拦截即终止，不进入下一步
    return result
```

> 这套序列已在 Pico 固定回归任务中保持 **100% 通过率 + 100% 预算内完成率 + 100% verifier 通过率**，可直接作为决策引擎工具层的实现基线。

## 9.6 运行审计与评测闭环

### 审计日志格式（JSONL）

```json
{"ts":"...","level":"INFO","task_id":"...","phase":"collecting","agent":"collector_br","event":"start","detail":{"source":"amazon_br"}}
{"ts":"...","level":"INFO","agent":"collector_br","event":"done","detail":{"duration_sec":12.3,"records":217}}
{"ts":"...","level":"WARN","agent":"nlp_analyzer","event":"tool_retry","detail":{"provider":"gemini","next_provider":"tongyi"}}
```

### 评测四层（参考Pico拆层思路）

| 层 | 指标 | 方法 |
|----|------|------|
| Harness Regression | pass_rate/attempts/tool_steps | 固定benchmark回归 |
| Context Governance | avg_prompt_len/compression_ratio | 自动统计 |
| Memory Benefit | repeat_read_count/task_correctness | 有无记忆对照 |
| Recovery Correctness | resume_success_rate/drift_detection | 断言检验 |

### Pico 合同化评测闭环（`2-pico.pdf` 第08章）

Pico 的评测核心是**「任务合同 + verifier」+ 四交集判定 + 失败分类**，避免"自己给自己打高分"：

```python
# 任务合同（决策引擎迁移为：决策任务合同）
class BenchmarkContract(BaseModel):
    id: str
    prompt: str                      # 自然语言任务
    fixture_repo: str                # 干净 fixture（防污染）
    allowed_tools: list              # 允许调用的数据源/工具白名单
    step_budget: int                 # 步数预算（控制LLM+API成本）
    expected_artifact: str           # 期望产物（如一张合法决策卡）
    verifier: str                    # 验证脚本（关键！）

# 四交集判定（缺一则不算 pass）
PASS_CONDITIONS = [
    "within_budget",        # tool_steps ≤ step_budget
    "verifier_passed",      # returncode == 0
    "expected_artifact_exists",
    "non_failure_stop_reason"  # 非 budget/error 停机
]

# 失败分类（迁移为决策引擎的失败归因）
FAILURE_CATEGORY = {
    "missing_artifact":   "数据缺失/卡片未生成",
    "budget_exceeded":    "API预算超支",
    "verifier_failed":    "验证(回测)失败",
    "failure_stop_reason": "错误停止(模型未给可执行决策)"
}
```

> ⚠️ **verifier 必须走「样本外业务指标回测」而非模型自评**：决策引擎的 verifier 应用历史窗口业务指标（ROI、转化率、库存周转）校验决策好坏，而非让模型自述"done"。评测还需补**多次运行方差 + 不同市场周期下的稳定性**，而非仅看均值。

### 评测四层（参考Pico拆层思路）

| 层 | 指标 | 方法 |
|----|------|------|
| Harness Regression | pass_rate/attempts/tool_steps | 固定benchmark回归（四交集判定） |
| Context Governance | avg_prompt_len/compression_ratio | 自动统计（token-aware） |
| Memory Benefit | repeat_read_count/task_correctness | 有无记忆对照（on/off/irrelevant 三对照） |
| Recovery Correctness | resume_success_rate/drift_detection | 断言检验 + 恢复后决策一致性断言 |

---

# 十、事件驱动多Agent Runtime（基于MindBridge）

> ⭐ Agent编排核心——CollaborationBlackboard + Coordinator/Safety双闸门。

## 10.1 架构

```
                    ┌──────────────────┐
                    │  Blackboard      │
                    │  (共享状态板)     │
                    │  task_state      │
                    │  artifacts {}    │
                    │  claims []       │
                    └──────┬───────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
│Coordinator  │    │  Collector  │    │ NLPAnalyzer │
│Agent        │    │  (×N按源)   │    │  (×N按语言)  │
│·维护任务板  │    │ 发布Artifact│    │ 发布Artifact│
│·分发子任务  │    │ :RawReviews │    │ :PainPoints │
│·采纳/拒绝   │    └─────────────┘    └─────────────┘
│·最终裁决    │
└──────┬──────┘
       │
┌──────▼──────┐
│ SafetyAgent │
│·证据充分性  │
│·幻觉检测    │
│·合规审查    │
│·一票否决    │
└─────────────┘
```

## 10.2 Agent定义

### CoordinatorAgent（协调者）

```python
class CoordinatorAgent:
    async def run(self, task: InsightTask) -> List[DecisionCard]:
        # Phase 1: 分解子任务
        subtasks = self.decompose(task)
        for st in subtasks:
            self.blackboard.claim(st)
        
        # Phase 2: 等待Agent完成
        artifacts = await self.gather_artifacts(timeout_sec=120)
        
        # Phase 3: Safety校验
        safety_result = await self.safety_agent.review(artifacts, task)
        
        # Phase 4: 编译决策卡
        if safety_result.approved:
            return self.compiler.compile(artifacts, task)
        return self.compiler.compile_partial(artifacts, task, safety_result)
```

### CollectorAgent（采集者 × N）

按`(source, market)`组合fork：
- `(amazon_reviews, BR)`, `(amazon_reviews, US)`
- `(google_trends, BR)`, `(google_trends, US)`
- `(un_comtrade, BR)`
- `(fbx_freight, GLOBAL)` — 全球共享
- `(reddit, en)`

每个Collector独立运行，完成后发布Artifact到Blackboard + 发送AGUI事件。

### SafetyAgent（安全闸门——三道校验）

| 闸门 | 校验内容 | 未通过处理 |
|------|---------|-----------|
| 证据充分性 | evidences ≥ 3 且覆盖 ≥ 2 个不同源类型 | 补充采集（二次Act） |
| 幻觉检测 | 引用校验（每条claim可在raw_data中找到原文） | 标记"无法验证" + 降低置信度 |
| 合规审查 | EU AI Act §50 + 无欺骗性内容 | 一票否决，卡片不输出 |

## 10.3 AGUI事件协议（SSE→前端）

```python
EVENT_TYPES = {
    "agent_start": "Agent开始执行",
    "agent_progress": "进度更新",
    "agent_done": "执行完成",
    "observe": "观察到新证据",
    "reflect:gate_passed": "闸门通过",
    "reflect:gate_blocked": "闸门未通过，补充中",
    "card_generated": "决策卡生成",
    "complete": "任务完成",
    "llm_fallback": "LLM切换备用Provider",
}
```

---

# 十一、冷启动伪数据方案与Demo设计

## 11.1 冷启动架构

```
Config(data.mode)
    ├── MockDataProvider  (mode="mock")     ← Demo用
    ├── RealDataProvider   (mode="real")     ← 生产
    └── HybridProvider     (mode="hybrid")   ← 部分真实
            │
    ┌───────▼────────┐
    │ DataSource      │  统一接口
    └────────────────┘
```

配置切换：
```yaml
data:
  mode: "mock"  # mock | real | hybrid
  mock:
    seed_file: "data/mock_seed.parquet"
    deterministic: true  # Demo每次结果一致
```

## 11.2 预置种子品类（5个）

| # | 品类(英) | 品类(中) | 目标市场 | 核心痛点 | 价格带(USD) |
|---|----------|---------|---------|---------|------------|
| 1 | Pet Feeder | 宠物自动喂食器 | BR,US,MY | 噪音/容量/清洁 | $25-$80 |
| 2 | Portable Blender | 便携榨汁机 | BR,MX,ID | 续航/容量/清洗 | $15-$45 |
| 3 | LED Ring Light | LED环形灯 | US,PH,SA | 光质/支架/尺寸 | $20-$65 |
| 4 | NC Earbuds | 降噪耳机 | BR,AE,JP | 降噪深度/舒适度 | $30-$120 |
| 5 | Smart Watch Band | 智能手表带 | ID,MX,PH | 兼容性/材质/精度 | $10-$35 |

## 11.3 伪数据生成规则

### 伪评论（每品类×市场 200-500条）

分布：70%普通 + 25%让步评论(hidden_pain) + 5%差评

```python
CONCESSION_TEMPLATES = {
    "pt": ["Adoro {product} mas {pain}.", "Ótimo produto, porém {pain}."],
    "ar": ["منتج رائع لكن {pain}.", "أعجبني كثيراً ولكن {pain}."],
    "es": ["Me gusta mucho, pero {pain}.", "Bueno, sin embargo {pain}."],
    "id": ["Suka banget, tapi {pain}.", "Bagus, namun {pain}."],
    "en": ["I love it but {pain}.", "Great product, however {pain}."],
}
```

### 伪趋势数据（90天日粒度）

基准值 + 趋势分量 + 周末周期性 + 高斯噪声

### 伪供应链数据

| 信号 | 规则 | 示例 |
|------|------|------|
| FBX运价 | 基准±5%随机，偶发spike+15% | $2,850→$3,280 |
| UN Comtrade | YoY +20%~+60% | HS8509 BR: +41% |
| 汇率 | USD/BRL在5.2-5.8区间 | 5.43 |

## 11.4 Demo演示脚本（5-8分钟）

| 时间 | 操作 | 画面 | 话术要点 |
|------|------|------|---------|
| 0:00 | 进入首页 | Hero+搜索框 | "这是先机罗盘。卖家只需输入品类关键词。" |
| 0:15 | 输入"pet feeder"+选BR | 搜索框+勾选 | "想做宠物喂食器，切巴西——增量最大市场之一。" |
| 0:35 | 点击"开始洞察" | 进度面板 | "Agent开始全球并行采集。" |
| 0:35-1:10 | **观看进度条** | Agent依次亮起 | "217条葡语评论已采集...NLP分析中..." |
| 1:10 | **四卡呈现** | 四宫格+雷达 | "**30-45秒，四张决策卡同时出来。不给数据，给行动指令。**" |
| 1:30 | 点开选品卡 | Modal详情 | "做静音款喂食器，切巴西，主打夜间不吵。" |
| 1:50 | 下钻证据链 | 展开"凭什么" | "38%葡语评论说'喜欢但太吵'。海关+41%。竞品0款静音。" |
| 2:10 | 展示反向条件 | 展开"什么时候失效" | "**我们告诉你什么时候我们会错。** 运价涨了？竞品出了？自动失效。" |
| 2:30 | 痛点雷达 | 气泡图 | "每个气泡都是一个天然差异化机会。" |
| 2:50 | 点击气泡 | 原始评论抽屉 | "葡萄牙语原文——我们直接对原文抽取，不翻译。" |
| 3:10 | 最小市场验证卡 | 验证计划 | “找养宠+夜班人群，在 WhatsApp 养宠群完成意向测试与深访，再决定首批备货。” |
| 3:30 | 直觉vs有据 | 双屏对照 | "直觉vs AI，命中率差3倍以上。" |
| 3:50 | 总结 | 回四宫格 | "**不卖数据，卖决策。每张卡都是可执行的指令。**" |

---

# 十二、跨境电商行业知识库设计

## 12.1 知识分类

```
行业知识库
├── 品类本体
│   ├── 品类树(L1~4) + HS Code映射
│   ├── 品类属性模板(材质/功率/尺寸/认证)
│   └── 品类关联图谱(互补/替代/上下游)
├── 市场知识
│   ├── 国家档案(GDP/人口/电商渗透率/主流平台/语言/货币/关税)
│   ├── 平台规则(Amazon/Shopee/TikTok/AliExpress费率/禁售)
│   ├── 物流知识(头程/尾程/时效/成本/清关)
│   └── 支付习惯(偏好方式/COD地区/分期比例)
├── 竞争情报
│   ├── JS/H10/卖家精灵能力矩阵
│   ├── 定价策略(心理价位/锚定效应/奇数定价)
│   └── 营销打法(痛点营销/FOMO/社交证明)
└── 合规知识
    ├── EU AI Act §50 要求
    ├── 各国数据跨境传输规则
    └── 平台AI内容披露政策
```

## 12.2 知识注入方式

| 知识类型 | 注入方式 | 更新频率 |
|---------|---------|---------|
| 品类本体 | 结构化YAML/JSON，启动时加载 | 季度 |
| 国家档案 | ChromaDB向量索引，Agent检索时召回 | 半年 |
| 平台规则 | Config YAML + 规则引擎 | 月度（跟踪政策变化） |
| 定价策略 | Prompt模板中的Few-Shot示例 | 稳定 |
| 合规知识 | System Prompt硬编码 + SafetyAgent校验规则 | 实时跟踪法规 |

---

# 十三、技术选型对比与最终决策

## 13.1 LLM 选型

| Provider | 免费额度 | 优势 | 劣势 | 角色 |
|----------|---------|------|------|------|
| **Gemini 2.0 Flash** | 15 RPM 免费 | 多语言强、长上下文1M、免费Embedding | 偶尔rate limit | **首选主力** |
| **通义千问 Qwen** | 100万token免费 | 中文能力强、国内稳定 | 多语言弱于Gemini | **中文备选** |
| **豆包 Doubao** | 永久免费 | 速度快、成本低 | 能力略弱 | **兜底第三选择** |
| **DeepSeek V3** | 超低价($0.14/M tokens) | 推理能力强 | 免费额度有限 | **超量兜底** |

**Fallback链**: Gemini → 通义 → 豆包 → DeepSeek

## 13.2 向量检索选型

| 方案 | MVP适用 | 演进 | 成本 |
|------|---------|------|------|
| **ChromaDB + all-MiniLM-L6-v2** | ✅ 百万级以内够用 | → Milvus/Qdrant | 免费 |
| FAISS | ✅ 但无元数据过滤 | — | 免费 |
| Pinecone | ❌ 付费 | 生产级 | $$/月 |
| Qdrant | ⚠️ 需部署 | ✅ 云原生 | 自托管免费 |

**决策**: MVP 用 ChromaDB + all-MiniLM-L6-v2（同一embedding做双塔查询+候选编码），演进上 Milvus 或 Qdrant。

## 13.3 编排框架选型

| 维度 | LangGraph | 自研事件驱动(CollaborationBlackboard) |
|------|-----------|-------------------------------------|
| 成熟度 | ★★★★★ | ★★★☆☆ |
| 并行能力 | ★★★★☆（fork可声明式） | ★★★★★（天然并行） |
| 可观测性 | ★★★★☆（LangSmith付费） | ★★★★★（自建AGUI） |
| 定制深度 | ★★★☆☆（受框架约束） | ★★★★★（完全控制） |
| MVP速度 | ★★★★★ | ★★★☆☆ |
| **决策** | **MVP用LangGraph** | **v2升级为事件驱动** |

## 13.4 前端选型

| 方案 | 开发速度 | 定制性 | Demo效果 | 决策 |
|------|---------|--------|---------|------|
| **Streamlit** | ★★★★★ | ★★☆☆☆ | ★★★☆☆ | **MVP** |
| Gradio | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ | 备选 |
| React+Next.js | ★★☆☆☆ | ★★★★★ | ★★★★★ | **v2** |

---

# 十四、自进化飞轮架构

> ⭐⭐⭐ **用户明确要求的必须项**——系统必须在运行中持续进化。

## 14.1 自进化三层飞轮

```
                    ┌─────────────────────────────────┐
                    │         自进化飞轮                │
                    │                                 │
│  ┌───────────────▼───────────────┐                 │
│  │  Layer 1: 运行时反馈收集       │                 │
│  │  · 人工复核结果(采纳/驳回)     │◄─────────────── │
│  │  · 反向条件触发记录            │   人工反馈      │
│  │  · 用户编辑/修正行为           │                 │
│  │  · LLM Fallback次数统计        │                 │
│  └───────────────┬───────────────┘                 │
│                  │                                 │
│  ┌───────────────▼───────────────┐                 │
│  │  Layer 2: 反馈沉淀与记忆更新   │                 │
│  │  · 采纳的卡→写入正向案例库     │                 │
│  │  │  驳回的卡→写入负样本库      │                 │
│  │  · 触发的失效条件→更新规则阈值 │                 │
│  │  · 新发现的痛点→扩充品类知识   │                 │
│  │  · 用户偏好→更新L3用户画像     │                 │
│  └───────────────┬───────────────┘                 │
│                  │                                 │
│  ┌───────────────▼───────────────┐                 │
│  │  Layer 3: 模型能力进化         │                 │
│  │  · SFT冷启动(正向+负样本)      │                 │
│  │  · LoRA/QLoRA领域微调          │                 │
│  │  · Agentic RL/GSPO强化学习     │  ← 赛后演进     │
│  │  · 双塔Embedding联训           │  ← 赛后演进     │
│  │  · 评测Rubric迭代优化           │                 │
│  └─────────────────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

## 14.2 Layer 1: 运行时反馈收集

### 反馈数据Schema

```python
class FeedbackRecord(BaseModel):
    feedback_id: str
    card_id: str
    task_id: str
    feedback_type: str  # approve/reject/discuss/edit/user_created
    user_id: str
    timestamp: str
    
    # 如果是reject
    reject_reason: Optional[str] = None    # 为什么驳回
    rejected_fields: List[str] = []       # 哪些字段有问题
    
    # 如果是edit
    edited_fields: dict = {}               # 用户改了什么
    original_values: dict = {}             # 改之前的值
    
    # 如果是user_created
    user_card_data: Optional[dict] = None  # 用户自己写的卡
    
    # 元数据
    session_duration_sec: float            # 用户看这张卡花了多久
    evidence_click_count: int              # 点了几次证据下钻
```

### 收集时机

| 事件 | 收集内容 | 触发方式 |
|------|---------|---------|
| 用户点击"采纳" | approve feedback | 显式按钮 |
| 用户点击"驳回" | reject feedback + reason | 显式按钮+必填原因 |
| 用户修改卡片文字 | edit feedback | 自动检测diff |
| 用户手动创建卡片 | user_created feedback | 显式保存 |
| 反向条件被触发 | auto_feedback | 系统自动 |
| 用户查看证据超过30秒 | implicit_interest | 自动（隐式） |

## 14.3 Layer 2: 反馈沉淀与记忆更新

### 正向案例库（采纳的卡片）

```python
class PositiveCase(BaseModel):
    case_id: str
    source_card: DecisionCard        # 原始卡片完整副本
    approval_context: dict            # 采纳时的上下文
    effectiveness_signal: Optional[str] = None  # 后续是否真的有效（追踪）
    extracted_patterns: List[str]    # 从此案例提取的可复用模式
```

**用途**：
- Few-Shot Prompt 示例（"这是一张曾被资深卖家采纳的同类卡片..."）
- 编译Agent的参考基线
- 新用户的推荐卡片候选

### 负样本库（驳回的卡片）

```python
 class NegativeCase(BaseModel):
    case_id: str
    source_card: DecisionCard
    reject_reason: str
    problematic_fields: List[str]
    suggested_fix: Optional[str] = None
```

**用途**：
- SafetyAgent 的校验训练数据
- 编译Agent 的"不要这样做"示例
- 评测 Rubric 的反模式库

### 规则阈值自适应

```python
class AdaptiveThresholdManager:
    """
    基于反馈历史动态调整系统阈值。
    例如：如果某市场的"蓝海指数"阈值导致过多误报，自动收紧。
    """
    
    def update_threshold(self, rule_id: str, feedback_history: List[FeedbackRecord]):
        false_positive_rate = self._calculate_fpr(rule_id, feedback_history)
        
        if false_positive_rate > 0.3:  # 30%以上被驳回=阈值太松
            current = self.get_threshold(rule_id)
            self.set_threshold(rule_id, current * 1.1)  # 收紧10%
            
        elif false_positive_rate < 0.05:  # 几乎全被采纳=可能太严
            current = self.get_threshold(rule_id)
            self.set_threshold(rule_id, current * 0.9)  # 放松10%
```

## 14.4 Layer 3: 模型能力进化（赛后演进）

### SFT 冷启动

```
训练数据构成:
├── 正向案例库 (采纳卡片) → SFT 正样本
├── 负样本库 (驳回卡片) → SFT 负样本
├── 人工编写的理想卡片 → SFT 黄金标准
└── 通用指令遵循数据 → 保持基础能力不变

基座模型: Qwen2.5-7B (开源，中文能力强)
微调方式: QLoRA (rank=8, lr=2e-4)
预期产出: 几十MB的LoRA权重 → Ollama本地部署
```

### Agentic RL / GSPO 强化学习

```
奖励函数设计:
├── r_adopted:     采纳 → +1.0
├── r_rejected:    驳回 → -0.5
├── r_evidence_cnt: 证据条数/3 (归一化) → +0~0.3
├── r_hook_present: 有最小验证动作 → +0.2
├── r_failure_cond: 有反向条件 → +0.1
├── r_latency:     超过90s → -0.1
└── r_hallucination: 检测到幻觉 → -1.0 (重罚)

训练范式: GSPO (Generalized Self-Play Optimization)
环境: 模拟用户 + Mock数据 + 自动评判器
```

### 评测 Rubric 迭代

| 维度 | 权重 | 评分方法 |
|------|------|---------|
| **可执行性** | 30% | 卡片是否能直接指导行动（人工打分 1-5） |
| **证据充分性** | 25% | 证据数量/质量/多样性（自动+人工） |
| **验证可执行度** | 20% | 验证人群、渠道、样本量和停止线的具体性（人工打分） |
| **可证伪性** | 15% | 反向条件的合理性和可监控性（自动验证） |
| **合规完整性** | 10% | EU AI Act要求是否全部满足（自动检查list） |

---

# 十五、Demo演示脚本与评审预期

## 15.1 评委视角的价值感知路径

```
评委第一眼（0-30s）: "又是一个数据看板？" 
  → ❌ NO! 我们直接给出**四张行动指令卡**（范式跃迁）

评委第二眼（30-90s）: "AI生成的能信吗？"
  → ❌ NO! 每条结论**可下钻到原始数据**（证据链100%可追溯）
  → **反向条件告诉评委什么时候会错**（可证伪性）

评委第三眼（90-150s）: "商家下一步怎么验证？"
  → 每张卡**强制带最小验证动作和停止条件**（缺字段=不生成）
  → **从洞察直连到"找谁、在哪、说什么"**

评委第四眼（150s+）: "技术上有啥亮点？"
  → ✅ Pico Harness（分层记忆/上下文压缩/Checkpoint恢复）
  → ✅ MindBridge事件驱动Runtime（CollaborationBlackboard双闸门）
  → ✅ 自进化飞轮（三层：反馈收集→沉淀→模型进化）
  → ✅ 多语言隐性痛点挖掘（认知套利）
```

## 15.2 可能的评委追问 & 应答准备

| 追问 | 应答要点 |
|------|---------|
| "数据从哪来？准确吗？" | 公开数据（GT/Reddit/UN Comtrade/FBX/平台页）；三级标注（✅已核实/⚠️假设/❌不引用）；冷启动用伪数据保证Demo稳定 |
| "和Jungle Scout有什么不同？" | 它们主要回答发生了什么；我们进一步回答下一步如何验证、证据何时失效、什么条件会推翻结论 |
| "自进化怎么证明不是画饼？" | MVP即内置Layer1（反馈收集）+ Layer2（记忆更新）；Layer3（SFT/RL）标注为赛后演进；Demo可展示"采纳→沉淀→下次更准"的闭环 |
| "冷启动数据不是造假吗？" | 明确标注 Mock 模式；确定性场景数据仅用于复现流程；Real Provider 未安装时接口直接拒绝请求，不会把 Mock 降级结果标成真实数据 |
| "Harness这么重，MVP做得完吗？" | Pico证明了Harness在单人项目中的可行性；我们取其核心4模块（上下文/记忆/Checkpoint/安全），非全量；MVP 2-3周可完成核心 |
| "零算力怎么跑Agent？" | 全链路免费层：Gemini免费API + Chroma本地 + Streamlit本地；唯一成本是开发者时间；Demo完全离线可跑（mock模式） |

---

# 十六、里程碑路线图与交付计划

## 16.1 MVP（初赛演示可用）—— 3-4 周

| 周次 | 里程碑 | 交付物 | 负责角色 |
|------|--------|--------|---------|
| W1 | 项目脚手架 + Harness 骨架 | 可运行的 Agent 框架、ContextManager/MemoryStore/TraceWriter 基础实现 | 研发 |
| W1 | 冷启动伪数据系统 | 5个品类 × 3-5市场 × 300条评论的完整 Mock 数据集；伪趋势/海关/运价数据 | 研发+数据 |
| W2 | 决策卡引擎 v1 | Schema 定义 + 编译 Agent + 四卡渲染（至少选品卡与最小市场验证卡可用） | 研发 |
| W2 | 多语言痛点抽取 | 让步结构检测 + NLPAnalyzerAgent + 痛点雷达图前端 | 研发 |
| W3 | Agent Runtime + AGUI | CollaborationBlackboard + SSE进度流 + 前端进度面板 | 研发 |
| W3 | 直觉vs有据双屏 | 双屏对照视图 + 导出功能 | 前端+研发 |
| W4 | 集成测试 + Demo 调优 | 端到端流程打通、Demo脚本固化、Bug修复 | 全员 |
| W4 | **初赛提交** | PRD + Demo 视频/截图 + 技术文档 | 产品 |

## 16.2 v1.5（赛后 1-2 月）

- [ ] 接入 1-2 个真实数据源（如 Google Trends API / UN Comtrade API）
- [ ] LLM Fallback 链路实测与优化
- [ ] Checkpoint/Resume 完整实现
- [ ] 供应链预警规则引擎上线
- [ ] 用户反馈收集 Layer 1 完整

## 16.3 v2.0（赛后 3-6 月）

- [ ] 事件驱动 Runtime 替代 LangGraph（MindBridge 式 CollaborationBlackboard）
- [ ] React + Next.js 前端替代 Streamlit
- [ ] 向量库升级为 Qdrant / Milvus
- [ ] SFT 冷启动（基于收集的正/负样本）
- [ ] LoRA 领域微调
- [ ] C2PA 内容凭证对接

---

# 附录 A：赛题要求 → 功能映射对照表

| 赛题要求（场景三：AI市场洞察） | 映射到的功能/架构 | 优先级 | 状态 |
|-------------------------------|------------------|--------|------|
| 用数据代替直觉做决策 | 决策卡引擎（处方性输出） | 🟢P0 | ✅ 已设计 |
| 覆盖多市场/多平台数据 | CollectorAgent × N（按源/市场fork） | 🟢P0 | ✅ 已设计 |
| 输出可执行的洞察 | 行动指令字段 + 最小验证动作 | 🟢P0 | ✅ 已设计 |
| 备货前验证 | PrivateDomainHook 兼容字段承载验证计划 | 🟢P0 | ✅ 已设计 |
| AI 内容合规 | EU AI Act §50 内嵌 | 🟢P0 | ✅ 已设计 |
| 创新性/差异化 | 原语 Grounding / 可证伪处方 / 变化触发局部重算 | 🟢P0 | ✅ 已设计 |
| 可行性（零资质零算力） | 全免费技术栈 | 🟢P0 | ✅ 已论证 |
| ** Harness 要求** | Pico式分层中间件 | 🟢P0 | ✅ 已设计（第九章）|
| ** 自进化要求** | 三层飞轮（反馈→沉淀→模型进化） | 🟢P0 | ✅ 已设计（第十四章）|

---

# 附录 B：竞品差异化矩阵

| 能力维度 | Jungle Scout | Helium 10 | 卖家精灵 | **先机罗盘** |
|---------|-------------|-----------|---------|------------|
| 输出形态 | 指标/榜单 | 指标/榜单 | 指标/榜单 | **决策卡（行动指令）** |
| 语言覆盖 | 英文为主 | 英文为主 | 中文+英文 | **7语言原生** |
| 数据时效 | 滞后（已上榜） | 滞后 | 滞后 | **领先指标（运价/海关）** |
| 最小市场验证 | 无 | 无 | 无 | **强制验证动作与停止条件** |
| 可证伪性 | 无 | 无 | 无 | **反向条件** |
| 合规(EU AI Act) | 无 | 无 | 无 | **§50原生内嵌** |
| 成本 | $49-$199/月 | $39-$189/月 | ¥99-¥999/月 | **≈$0** |
| 多语言隐性痛点 | ❌ | ❌ | ❌ | **✅ 核心功能** |
| 供应链预判 | 付费版有限 | 付费版有限 | 无 | **✅ 核心功能** |
| 跨平台套利 | 手动对比 | 手动对比 | 单平台 | **✅ 自动检测** |
| 自进化能力 | 无 | 无 | 无 | **✅ 三层飞轮** |
| Harness中间件 | 无 | 无 | 无 | **✅ Pico式4层** |
| 人机协作 | 无 | 无 | 无 | **✅ HITL复核闸门** |

---

# 附录 C：术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 决策卡 | Decision Card | 带证据链/落点/反向条件/签字位的行动指令输出单元 |
| Harness | Agent Harness | 统一管理Agent调用/上下文/记忆/状态恢复/安全/审计的中间件层 |
| 黑板模式 | Blackboard Pattern | 多Agent共享状态板，Coordinator维护任务板，Agent认领并发布Artifact |
| 双塔召回 | Two-Tower Retrieval | DSSM范式：查询塔编码问题，候选塔编码文档，ANN检索+Rerank |
| 让步结构 | Concession Structure | "我喜欢X但是Y"的语法模式——正面评价+局部抱怨 |
| 隐性痛点 | Hidden Pain | 藏在好评"但是"后面的未满足需求——已验证需求×精确定位痛点 |
| 反向条件 | Failure Condition | 决策卡中"什么情况下此结论失效"的可证伪字段 |
| 验证落点 | Minimum Validation Hook | 决策卡强制字段：验证人群、验证渠道、验证话术与停止条件；底层保留兼容字段名 |
| 冷启动 | Cold Start | 使用合成伪数据的初始运行模式，后续切换为真实数据 |
| AGUI | Agent GUI Event Protocol | Agent状态→前端SSE实时推送的事件协议 |
| Checkpoint | 任务状态快照 | 中断后可恢复的任务中间状态持久化 |
| Workspace Drift | 工作区漂移 | 任务中断期间环境发生的变化（配置/数据/模型版本） |
| Freshness校验 | 新鲜度校验 | 记忆系统判断某条信息是否近期已读取过，避免重复 |
| SFT | Supervised Fine-Tuning | 有监督微调——用正负样本调整模型输出分布 |
| QLoRA | Quantized LoRA | 量化低秩适配——4bit冻结基座+少量适配器参数训练 |
| GSPO | Generalized Self-Play Optimization | 广义自博弈优化——Agent自我对弈生成强化学习训练信号 |
| Rubric | 评分规则集 | 结构化评测标准（维度+权重+评分方法） |
| C2PA | Content Credentials | 内容溯源开放标准——AI生成内容的数字签名/溯源证书 |
| SSE | Server-Sent Events | HTTP单向实时推送协议——用于AGUI事件流 |
| MCP | Model Context Protocol | Anthropic推出的LLM→外部工具/数据源的标准化连接协议 |

---

> **文档结束**
>
> 本 PRD 为 v1.0 初稿，涵盖产品定义到技术实现的完整规格。UI 团队可直接基于第七章开始设计稿，研发团队可直接基于第三~十章开始开发。第十一章提供完整的冷启动伪数据方案确保 Demo 可演示。
>
> 下一步：UI 设计评审 → 技术方案评审 → 开发排期 → Demo 联调 → 初赛提交。
