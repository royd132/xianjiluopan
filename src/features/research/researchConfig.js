import {
  Activity,
  CircleDollarSign,
  Globe2,
  MessageCircleMore,
  PackageSearch,
  Sparkles,
  Target,
  Users,
} from 'lucide-react';

export const markets = [
  { code: 'BR', name: '巴西', flag: 'BR' },
  { code: 'US', name: '美国', flag: 'US' },
  { code: 'MY', name: '马来西亚', flag: 'MY' },
  { code: 'MX', name: '墨西哥', flag: 'MX' },
];

const categoryPatterns = [
  { key: 'pet_feeder', pattern: /(宠物|喂食|pet|feeder)/i },
  { key: 'portable_blender', pattern: /(榨汁|果汁|blender|juicer)/i },
  { key: 'noise_cancelling_headphones', pattern: /(耳机|降噪|headphone|earbud|anc)/i },
  { key: 'coffee_grinder', pattern: /(咖啡|磨豆|coffee|grinder)/i },
];

export const scopeLabels = {
  target_market: '目标市场',
  cross_market: '跨市场产品证据',
  category_proxy: '目标市场类目代理',
  macro: '全球宏观',
  unknown: '适用范围待确认',
};

export const freshnessLabels = {
  live: '近期',
  recent: '近期',
  historical: '历史基线',
  structural: '结构性基线',
  unknown: '时间待确认',
};

const capabilitySignalLabels = {
  'runtime:fx': '汇率缓存',
  'runtime:reviews': '评论语料',
  'runtime:trade': '贸易数据',
  'runtime:gscpi': '供应链指数',
  'runtime:qwen': 'Qwen 模型配置',
  source_backed_price: '有来源的竞品价格',
  native_market_reviews: '目标市场原生评论',
  current_competitor_listings: '当前竞品 listing',
};

export function capabilitySignals(items = []) {
  return items.map((item) => capabilitySignalLabels[item] || item).join('、');
}

export function categoryKeyForQuery(value) {
  return categoryPatterns.find((item) => item.pattern.test(value))?.key || 'generic';
}

export const agents = [
  { label: '市场采集', detail: '趋势 / 评论 / 价格 / 贸易信号', icon: Globe2 },
  { label: '痛点分析', detail: '原语让步结构已聚类', icon: MessageCircleMore },
  { label: '供应链校验', detail: '贸易 / 运价 / 汇率已校验', icon: Activity },
  { label: '策略编译', detail: '通过可信度闸门', icon: Sparkles },
];

export const demoEvidence = [
  {
    source: 'Google Trends · Brazil',
    type: '趋势',
    claim: '“pet feeder”近 90 天搜索热度上升',
    value: '+64%',
    verified: false,
  },
  {
    source: 'Amazon Brasil · 217 条葡语评论',
    type: '评论',
    claim: '“喜欢，但夜间噪音大”集中出现',
    value: '38%',
    verified: false,
  },
  {
    source: 'UN Comtrade · HS 8509',
    type: '海关',
    claim: '巴西相关品类进口额同比增长',
    value: '+41%',
    verified: false,
  },
];

export const demoCards = [
  {
    id: 'product',
    type: '选品方向',
    icon: PackageSearch,
    tone: 'blue',
    confidence: 88,
    title: '做「静音款」宠物自动喂食器，切入巴西市场',
    summary: '主打夜间不吵醒主人，避开容量与联网功能的正面价格战。',
    metric: '机会分',
    metricValue: '86',
    source: '5 个数据源',
  },
  {
    id: 'pricing',
    type: '定价策略',
    icon: CircleDollarSign,
    tone: 'amber',
    confidence: 82,
    title: '锚定 US$49.90，首发价控制在 US$44–52',
    summary: '以静音电机与易拆洗结构支撑 18% 溢价，目标毛利 31%。',
    metric: '建议毛利',
    metricValue: '31%',
    source: '84 个价格样本',
  },
  {
    id: 'competitive',
    type: '竞争打法',
    icon: Target,
    tone: 'violet',
    confidence: 85,
    title: '把“分贝数”变成可验证卖点，而不是泛讲智能',
    summary: '详情页首屏对比夜间运行分贝，重点攻击 Top 10 的共同表达空位。',
    metric: '表达空位',
    metricValue: '72%',
    source: 'Top 10 竞品',
  },
  {
    id: 'private',
    type: '私域人群',
    icon: Users,
    tone: 'green',
    confidence: 91,
    title: '先找“养宠 + 夜班 / 浅眠”人群做种子测试',
    summary: '承接至 WhatsApp 养宠群，用“让它半夜别吵醒你”完成首轮验证。',
    metric: '复购信号',
    metricValue: '强',
    source: '12 个人群样本',
    hook: {
      audience: '养宠 + 夜班 / 浅眠人群',
      channel: 'WhatsApp 巴西本地养宠群',
      message: '让它半夜别吵醒你',
    },
  },
];

export const demoPainPoints = [
  { id: 'noise', label: '夜间噪音', value: 88, count: 82, x: 18, y: 22, size: 58, color: '#2563eb' },
  { id: 'clean', label: '清洗困难', value: 69, count: 47, x: 48, y: 42, size: 43, color: '#059669' },
  { id: 'jam', label: '容易卡粮', value: 61, count: 38, x: 72, y: 51, size: 38, color: '#d97706' },
  { id: 'portion', label: '份量不准', value: 51, count: 29, x: 84, y: 67, size: 32, color: '#7c3aed' },
  { id: 'wifi', label: '联网不稳', value: 35, count: 18, x: 37, y: 73, size: 26, color: '#64748b' },
];

export const demoReviews = {
  noise: {
    original: 'Adoro o alimentador, mas o motor faz muito barulho durante a madrugada.',
    translation: '我很喜欢这个喂食器，但电机在半夜运行时声音很大。',
    meta: '葡萄牙语 · 巴西 · Mock 原语样本',
  },
  clean: {
    original: 'Ótimo produto, porém desmontar para limpar dá muito trabalho.',
    translation: '产品很好，不过拆开清洗非常麻烦。',
    meta: '葡萄牙语 · 巴西 · Mock 原语样本',
  },
  jam: {
    original: 'Funciona bem, mas a ração trava quando os grãos são maiores.',
    translation: '运行不错，但颗粒稍大时就会卡粮。',
    meta: '葡萄牙语 · 巴西 · Mock 原语样本',
  },
  portion: {
    original: 'Gosto do aplicativo, mas a porção nunca parece igual.',
    translation: '我喜欢它的应用，但每次出粮量看起来都不一样。',
    meta: '葡萄牙语 · 巴西 · Mock 原语样本',
  },
  wifi: {
    original: 'É bonito, porém perde a conexão com frequência.',
    translation: '外观很好看，但经常断开连接。',
    meta: '葡萄牙语 · 巴西 · Mock 原语样本',
  },
};

export const demoSupplySignals = [
  { name: '巴西进口需求', value: '+41%', note: '同比', state: 'positive', bars: [24, 32, 29, 41, 46, 58, 66] },
  { name: '南美海运 FBX', value: '+6.2%', note: '近 30 天', state: 'watch', bars: [32, 27, 38, 34, 44, 49, 53] },
  { name: 'USD / BRL', value: '5.43', note: '稳定区间', state: 'stable', bars: [45, 43, 47, 42, 44, 46, 45] },
];
