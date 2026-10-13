# 卖家精灵适配桥

先机罗盘不在页面内复刻一个“卖家精灵”界面。它把 SellerSprite 当作外部数据能力层，按 API、CLI、MCP、Agent 四种官方接入方式完成研究，再把经过来源校验的结果写回先机罗盘的证据链。

## 当前协议

- 文件：`sellersprite-research-task-{market}-{timestamp}.json`
- ASIN 清单：`sellersprite-asins-{market}-{timestamp}.csv`（只有实时结果里存在真实 ASIN 时生成）
- Schema：`seller-assistant.task.v1`（保留历史 schema 名称，避免下游导入器失效）
- 前端入口：报告右上角“复制卖家精灵研究条件”和“导出研究包 JSON”
- 适配实现：`src/features/integrations/sellerSpriteAdapter.js`

## 四种真实接入方式

### API

后端支持两种传输：默认 REST API，或设置 `SELLERSPRITE_TRANSPORT=mcp` 后通过官方 MCP 服务调用 `product_research`。两种方式都使用固定的 `secret-key` 请求头，MCP 失败时可由 `SELLERSPRITE_MCP_FALLBACK_REST=true` 回退到 API。配置 `SELLERSPRITE_SECRET_KEY` 后，以下 Amazon 站点会优先使用 SellerSprite 的实时价格、BSR、销量和评分信号：US、JP、UK、DE、FR、IT、ES、CA、IN、MX。巴西（BR）不在当前 SellerSprite Amazon 站点列表中，因此继续使用 Mercado Livre/Olist 等本地数据源，不把 SellerSprite 数据冒充成巴西数据。

### CLI

SellerSprite 官方 CLI 通过 `pip install sellersprite-cli` 安装，可用 `sellersprite config --key ... --project` 配置项目级密钥（CLI 写入 `SELLERSPRITE_KEY`，后端同时接受这个名称和 `SELLERSPRITE_SECRET_KEY`），再用 `sellersprite product search`、`sellersprite market research`、`sellersprite trend review` 等命令批量查询。前端只复制命令模板，不在浏览器保存密钥。

### MCP

官方 MCP 地址是 `https://mcp.sellersprite.com/mcp`，传输类型为 `streamableHttp`，请求头名称固定为 `secret-key`。前端提供可复制的客户端配置，用户将自己的密钥填入后即可在 ChatGPT、Codex、Claude 等客户端调用 `product_research`、`market_research`、`review` 等工具。

### Agent

Agent 负责把研究目标拆成工具调用，例如先用 `product_research` 筛选潜力 ASIN，再用 `asin_detail`、`traffic_keyword`、`review` 补齐竞品和评论证据。前端复制的是研究任务提示词，结果仍需回到证据校验流程，不把模型口述当成市场事实。

任务包中的 `integrations.sellersprite` 会记录目标站点是否支持、查询关键词、官方 endpoint 和是否需要 secret-key，方便后续接入卖家精灵账号或内部工作流。

## 已验证的卖家精灵工作流

卖家精灵官方产品库的输入是 ASIN：可以在 Amazon 页面通过插件“加入产品库”，再在产品库中做市场分析、产品对比和关键词拓展；产品库支持导出 Excel。官方网页端没有“导入本系统 JSON 研究包”的入口。因此前端提供四种真实交接：API 直连服务端、CLI 复制本地命令、MCP 复制客户端配置、Agent 复制自然语言研究任务。报告仍可复制站点和关键词到卖家精灵「选产品」；当 SellerSprite API 返回真实 ASIN 时才导出 ASIN 清单。Mock 报告没有真实 ASIN 时不会伪造清单。

任务包包含：目标市场和 locale、Listing 草稿种子、渠道和人群、价格锚点、币种、到岸成本待补字段、HS/合规复核项、验证契约、停止条件，以及带来源的 evidence refs。

当前没有写死第三方 App 的 deep link 或私有 URL Scheme；SellerSprite 的数据接入走官方 API、CLI 或 MCP，前端导出的 JSON 只承载研究任务和证据引用，不冒充可直接导入卖家精灵的文件。
