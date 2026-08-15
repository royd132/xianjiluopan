import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Bell,
  BookOpen,
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Clipboard,
  Clock3,
  Compass,
  Download,
  ExternalLink,
  FileText,
  Globe2,
  History,
  LayoutDashboard,
  LoaderCircle,
  MessageCircleMore,
  PackageSearch,
  PanelTop,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import productImage from './assets/pet-feeder.png';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const markets = [
  { code: 'BR', name: '巴西', flag: 'BR' },
  { code: 'US', name: '美国', flag: 'US' },
  { code: 'MY', name: '马来西亚', flag: 'MY' },
  { code: 'MX', name: '墨西哥', flag: 'MX' },
];

const agents = [
  { label: '市场采集', detail: '趋势 / 评论 / 价格 / 贸易信号', icon: Globe2 },
  { label: '痛点分析', detail: '原语让步结构已聚类', icon: MessageCircleMore },
  { label: '供应链校验', detail: '贸易 / 运价 / 汇率已校验', icon: Activity },
  { label: '策略编译', detail: '通过可信度闸门', icon: Sparkles },
];

const demoEvidence = [
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

const demoCards = [
  {
    id: 'product',
    type: '选品方向',
    icon: PackageSearch,
    tone: 'blue',
    confidence: 88,
    title: '做「静音款」宠物自动喂食器，切入巴西市场',
    summary: '主打夜间不吵醒主人，避开容量与联网功能的正面价格战。',
    metric: '蓝海指数',
    metricValue: '8.6',
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

const cardPresentation = {
  product_selection: { id: 'product', type: '选品方向', icon: PackageSearch, tone: 'blue', metric: '蓝海指数' },
  pricing: { id: 'pricing', type: '定价策略', icon: CircleDollarSign, tone: 'amber', metric: '建议毛利' },
  competitive: { id: 'competitive', type: '竞争打法', icon: Target, tone: 'violet', metric: '表达空位' },
  private_domain: { id: 'private', type: '私域人群', icon: Users, tone: 'green', metric: '复购信号' },
};

function mapRuntimeCards(runtimeCards) {
  return runtimeCards.map((card) => {
    const presentation = cardPresentation[card.card_type];
    const data = card.card_specific_data || {};
    let metricValue = '—';
    if (card.card_type === 'product_selection') metricValue = String(Math.round((data.blue_ocean_index || 0.86) * 100) / 10);
    if (card.card_type === 'pricing') metricValue = `${data.gross_margin_pct || 31}%`;
    if (card.card_type === 'competitive') metricValue = `${data.expression_gap_pct || 72}%`;
    if (card.card_type === 'private_domain') metricValue = data.repurchase_signal_strength === 'strong' ? '强' : '中';
    return {
      ...presentation,
      confidence: Math.round(card.confidence_score * 100),
      title: card.action_title,
      summary: card.action_detail,
      metricValue,
      source: `${card.evidences.length} 条证据`,
      hook: {
        audience: card.private_domain_hook.seed_audience,
        channel: card.private_domain_hook.channel,
        message: card.private_domain_hook.hook_message,
      },
      failureConditions: card.failure_conditions,
      runtimeCard: card,
    };
  });
}

const evidenceTypeLabels = { trend: '趋势', review: '评论', customs: '海关', freight: '运价', price: '竞品价格', social: '社媒' };
const painPositions = [
  { x: 18, y: 22, size: 58, color: '#2563eb' },
  { x: 48, y: 42, size: 43, color: '#059669' },
  { x: 72, y: 51, size: 38, color: '#d97706' },
  { x: 84, y: 67, size: 32, color: '#7c3aed' },
  { x: 37, y: 73, size: 26, color: '#64748b' },
];

function mapRuntimeEvidence(runtimeCards) {
  const seen = new Set();
  return runtimeCards.flatMap((card) => card.evidences || []).filter((item) => {
    if (seen.has(item.evidence_id)) return false;
    seen.add(item.evidence_id);
    return true;
  }).map((item) => ({
    source: item.source_name,
    type: evidenceTypeLabels[item.source_type] || item.source_type,
    claim: item.claim,
    value: item.raw_value,
    verified: item.verified,
    url: item.url,
  }));
}

function mapRuntimePainPoints(items) {
  return items.map((item, index) => ({
    id: item.pain_type,
    label: item.label,
    value: Math.round(item.opportunity_index * 100),
    count: item.mentions,
    ...painPositions[index % painPositions.length],
  }));
}

function mapRuntimeReviews(items, marketName) {
  return Object.fromEntries(items.map((item) => [item.pain_type, {
    original: item.sample_original,
    translation: item.sample_translation,
    meta: `${item.languages.join(' / ')} · ${marketName} · Mock 原语样本`,
  }]));
}

function mapRuntimeSupplySignals(items) {
  const bars = [[24, 32, 29, 41, 46, 58, 66], [32, 27, 38, 34, 44, 49, 53], [45, 43, 47, 42, 44, 46, 45]];
  return items.map((item, index) => ({
    name: item.label,
    value: item.signal_type === 'fx' ? String(item.current_value) : `${item.change_pct >= 0 ? '+' : ''}${item.change_pct}%`,
    note: item.period,
    state: item.status,
    bars: bars[index % bars.length],
  }));
}

const demoPainPoints = [
  { id: 'noise', label: '夜间噪音', value: 88, count: 82, x: 18, y: 22, size: 58, color: '#2563eb' },
  { id: 'clean', label: '清洗困难', value: 69, count: 47, x: 48, y: 42, size: 43, color: '#059669' },
  { id: 'jam', label: '容易卡粮', value: 61, count: 38, x: 72, y: 51, size: 38, color: '#d97706' },
  { id: 'portion', label: '份量不准', value: 51, count: 29, x: 84, y: 67, size: 32, color: '#7c3aed' },
  { id: 'wifi', label: '联网不稳', value: 35, count: 18, x: 37, y: 73, size: 26, color: '#64748b' },
];

const demoReviews = {
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

const demoSupplySignals = [
  { name: '巴西进口需求', value: '+41%', note: '同比', state: 'positive', bars: [24, 32, 29, 41, 46, 58, 66] },
  { name: '南美海运 FBX', value: '+6.2%', note: '近 30 天', state: 'watch', bars: [32, 27, 38, 34, 44, 49, 53] },
  { name: 'USD / BRL', value: '5.43', note: '稳定区间', state: 'stable', bars: [45, 43, 47, 42, 44, 46, 45] },
];

function MiniBars({ values, state }) {
  return (
    <div className={`mini-bars ${state}`} aria-label="趋势图">
      {values.map((v, index) => <span key={index} style={{ height: `${v}%` }} />)}
    </div>
  );
}

function formatReportTime(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
}

function ScoreRing({ value, size = 42 }) {
  return (
    <div className="score-ring" style={{ '--score': `${value * 3.6}deg`, width: size, height: size }}>
      <span>{value}</span>
    </div>
  );
}

function App() {
  const [market, setMarket] = useState('BR');
  const [query, setQuery] = useState('宠物自动喂食器');
  const [mode, setMode] = useState('evidence');
  const [running, setRunning] = useState(false);
  const [agentStep, setAgentStep] = useState(4);
  const [selectedCard, setSelectedCard] = useState(null);
  const [selectedPain, setSelectedPain] = useState('noise');
  const [reviewStatus, setReviewStatus] = useState('pending');
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('workspace');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [decisionCards, setDecisionCards] = useState(demoCards);
  const [reportEvidence, setReportEvidence] = useState(demoEvidence);
  const [insightPainPoints, setInsightPainPoints] = useState(demoPainPoints);
  const [insightReviews, setInsightReviews] = useState(demoReviews);
  const [insightSupplySignals, setInsightSupplySignals] = useState(demoSupplySignals);
  const [reportCategory, setReportCategory] = useState('宠物自动喂食器');
  const [reportMarket, setReportMarket] = useState('BR');
  const [reportGeneratedAt, setReportGeneratedAt] = useState(new Date().toISOString());
  const [reportMode, setReportMode] = useState('mock-offline');
  const [runtimeState, setRuntimeState] = useState('checking');
  const [runtimeMessage, setRuntimeMessage] = useState('正在检测多 Agent Runtime');
  const [evolution, setEvolution] = useState(null);
  const [evolutionLoading, setEvolutionLoading] = useState(false);
  const resultsRef = useRef(null);
  const eventSourceRef = useRef(null);

  const selectedMarket = useMemo(() => markets.find((item) => item.code === market), [market]);
  const selectedReportMarket = useMemo(() => markets.find((item) => item.code === reportMarket), [reportMarket]);
  const selectedReview = insightReviews[selectedPain] || Object.values(insightReviews)[0];
  const pricingFailure = decisionCards.find((card) => card.id === 'pricing')?.failureConditions?.[0];
  const productDecision = decisionCards.find((card) => card.id === 'product') || demoCards[0];
  const competitiveDecision = decisionCards.find((card) => card.id === 'competitive') || demoCards[2];
  const opportunityScore = Math.round(Number(decisionCards.find((card) => card.id === 'product')?.metricValue || 8.6) * 10);
  const leadPain = insightPainPoints[0] || demoPainPoints[0];
  const demandSignal = insightSupplySignals[0] || demoSupplySignals[0];

  const loadEvolution = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/evolution`);
      if (!response.ok) throw new Error('evolution unavailable');
      setEvolution(await response.json());
    } catch {
      setEvolution(null);
    }
  };

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!running || runtimeState === 'connected') return;
    setAgentStep(0);
    const timer = window.setInterval(() => {
      setAgentStep((current) => {
        if (current >= agents.length) {
          window.clearInterval(timer);
          setRunning(false);
          window.setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
          return agents.length;
        }
        return current + 1;
      });
    }, 720);
    return () => window.clearInterval(timer);
  }, [running, runtimeState]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/health`)
      .then((response) => {
        if (!response.ok) throw new Error('runtime unavailable');
        return response.json();
      })
      .then(() => {
        setRuntimeState('connected');
        setRuntimeMessage('多 Agent Runtime 已连接');
        loadEvolution();
      })
      .catch(() => {
        setRuntimeState('offline');
        setRuntimeMessage('离线演示模式');
      });
    return () => eventSourceRef.current?.close();
  }, []);

  const runLocalFallback = () => {
    setRuntimeState('offline');
    setRuntimeMessage('后端未启动，使用巴西宠物喂食器固定样例');
    setDecisionCards(demoCards);
    setReportEvidence(demoEvidence);
    setInsightPainPoints(demoPainPoints);
    setInsightReviews(demoReviews);
    setInsightSupplySignals(demoSupplySignals);
    setReportCategory('宠物自动喂食器');
    setReportMarket('BR');
    setReportGeneratedAt(new Date().toISOString());
    setReportMode('mock-offline');
    setSelectedPain('noise');
    if (query !== '宠物自动喂食器' || market !== 'BR') setToast('离线固定样例已载入；启动后端可运行多品类、多市场冷启动');
    setRunning(true);
  };

  const loadRuntimeResult = async (taskId) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/research/${taskId}`);
    const payload = await response.json();
    if (payload.result?.cards) {
      setDecisionCards(mapRuntimeCards(payload.result.cards));
      setReportEvidence(mapRuntimeEvidence(payload.result.cards));
      setInsightPainPoints(mapRuntimePainPoints(payload.result.pain_points));
      setInsightReviews(mapRuntimeReviews(payload.result.pain_points, markets.find((item) => item.code === payload.result.request.market)?.name || payload.result.request.market));
      setInsightSupplySignals(mapRuntimeSupplySignals(payload.result.supply_signals));
      setReportCategory(payload.result.request.category);
      setReportMarket(payload.result.request.market);
      setReportGeneratedAt(payload.result.completed_at);
      setReportMode(payload.result.mode);
      setSelectedPain(payload.result.pain_points[0]?.pain_type || 'noise');
      setRuntimeMessage(`6 个 Agent 已完成 · Trace ${payload.result.trace_id.slice(0, 8)}`);
    }
    setAgentStep(agents.length);
    setRunning(false);
    window.setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  };

  const connectRuntimeEvents = (taskId) => {
    eventSourceRef.current?.close();
    const source = new EventSource(`${API_BASE_URL}/api/v1/research/${taskId}/events`);
    eventSourceRef.current = source;
    let completedAgents = 0;
    source.addEventListener('agent.started', (event) => {
      const payload = JSON.parse(event.data);
      setRuntimeMessage(payload.message);
    });
    source.addEventListener('agent.completed', (event) => {
      const payload = JSON.parse(event.data);
      completedAgents += 1;
      setAgentStep(Math.min(Math.ceil(completedAgents / 1.5), agents.length - 1));
      setRuntimeMessage(payload.message);
    });
    source.addEventListener('gate.passed', () => {
      setAgentStep(agents.length - 1);
      setRuntimeMessage('安全评测闸门已通过');
    });
    source.addEventListener('task.completed', async () => {
      source.close();
      await loadRuntimeResult(taskId);
    });
    source.addEventListener('task.failed', () => {
      source.close();
      setToast('Runtime 任务失败，已切换离线演示');
      runLocalFallback();
    });
  };

  const startAnalysis = async () => {
    if (!query.trim()) {
      setToast('请先输入一个品类关键词');
      return;
    }
    setReviewStatus('pending');
    setAgentStep(0);
    setRunning(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: query, market, mode: 'mock', languages: ['pt', 'en', 'es'] }),
      });
      if (!response.ok) throw new Error('runtime unavailable');
      const payload = await response.json();
      setRuntimeState('connected');
      setRuntimeMessage(`任务 ${payload.task_id.slice(0, 8)} 已进入协作黑板`);
      connectRuntimeEvents(payload.task_id);
    } catch {
      runLocalFallback();
    }
  };

  const copyText = async (text, message = '已复制到剪贴板') => {
    try {
      await navigator.clipboard.writeText(text);
      setToast(message);
    } catch {
      setToast('复制失败，请手动选择文本');
    }
  };

  const exportReport = () => {
    const payload = {
      product: reportCategory,
      market: selectedReportMarket,
      generatedAt: reportGeneratedAt,
      dataMode: reportMode,
      cards: decisionCards,
      evidence: reportEvidence,
      painPoints: insightPainPoints,
      compliance: { aiGenerated: true, humanReviewStatus: reviewStatus },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `先机罗盘_${reportCategory}_${reportMarket}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    setToast('洞察报告已导出');
  };

  const setReview = async (status) => {
    setReviewStatus(status);
    const runtimeCardId = selectedCard?.runtimeCard?.card_id || decisionCards[0]?.runtimeCard?.card_id;
    if (runtimeCardId && runtimeState === 'connected') {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/cards/${runtimeCardId}/review`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status,
            reviewer: 'demo-user',
            reason: status === 'rejected' ? '证据数量与原语覆盖不足，需要提高发布门槛' : null,
            failure_type: status === 'rejected' ? 'weak_evidence' : null,
          }),
        });
        if (!response.ok) throw new Error('review failed');
        await loadEvolution();
      } catch {
        setToast('反馈已保存在页面，Runtime 写入失败');
        return;
      }
    }
    setToast(status === 'approved' ? '已采纳，反馈将沉淀至案例库' : status === 'rejected' ? '已驳回此建议' : '已标记为待议');
  };

  const createEvolutionCandidate = async () => {
    setEvolutionLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/evolution/candidates`, { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'candidate failed');
      await loadEvolution();
      setToast(`${payload.candidate_version} 已通过 Validation / Holdout 门禁`);
    } catch (error) {
      setToast(error.message || '请先驳回一张真实 Runtime 决策卡');
    } finally {
      setEvolutionLoading(false);
    }
  };

  const activateEvolutionPolicy = async (version) => {
    setEvolutionLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/evolution/policies/${version}/activate`, { method: 'POST' });
      if (!response.ok) throw new Error('activate failed');
      await loadEvolution();
      setToast(`${version} 已激活，后续任务将使用新证据门槛`);
    } catch {
      setToast('策略尚未通过评测门禁');
    } finally {
      setEvolutionLoading(false);
    }
  };

  const rollbackEvolutionPolicy = async () => {
    setEvolutionLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/evolution/rollback`, { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'rollback failed');
      await loadEvolution();
      setToast(`已回滚至 ${payload.version}`);
    } catch (error) {
      setToast(error.message || '当前策略已是基线版本');
    } finally {
      setEvolutionLoading(false);
    }
  };

  const handleNav = (id) => {
    setActiveNav(id);
    setMobileNav(false);
    if (id === 'history') setHistoryOpen(true);
    if (id === 'settings') setToast('数据源与预警设置将在下一版本开放');
    if (id === 'alerts') document.getElementById('supply-chain')?.scrollIntoView({ behavior: 'smooth' });
    if (id === 'radar') document.getElementById('pain-radar')?.scrollIntoView({ behavior: 'smooth' });
    if (id === 'evolution') document.getElementById('evolution-center')?.scrollIntoView({ behavior: 'smooth' });
    if (id === 'workspace') window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const activePolicy = evolution?.active_policy;
  const readyPolicy = evolution?.policy_versions?.find((item) => item.status === 'ready');
  const latestEvolutionRun = evolution?.evolution_runs?.[0];
  const openFailures = evolution?.failure_cases?.filter((item) => item.status === 'open') || [];
  const validationImprovement = latestEvolutionRun?.metrics?.validation_improvement || 0;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Compass size={21} strokeWidth={2.4} /></div>
          <div><strong>先机罗盘</strong><span>Foresight Compass</span></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="关闭导航"><X size={18} /></button>
        </div>
        <nav className="nav-list" aria-label="主导航">
          <button className={activeNav === 'workspace' ? 'active' : ''} onClick={() => handleNav('workspace')}><LayoutDashboard size={18} />洞察工作台</button>
          <button className={activeNav === 'radar' ? 'active' : ''} onClick={() => handleNav('radar')}><Target size={18} />痛点雷达</button>
          <button className={activeNav === 'alerts' ? 'active' : ''} onClick={() => handleNav('alerts')}><Bell size={18} />失效条件<span className="nav-badge">2</span></button>
          <button className={activeNav === 'history' ? 'active' : ''} onClick={() => handleNav('history')}><History size={18} />历史洞察</button>
          <button className={activeNav === 'evolution' ? 'active' : ''} onClick={() => handleNav('evolution')}><Activity size={18} />演进中心{openFailures.length > 0 && <span className="nav-badge">{openFailures.length}</span>}</button>
        </nav>
        <div className="sidebar-section-label">工作空间</div>
        <button className="workspace-switcher" onClick={() => setToast('当前为 Demo 工作空间')}>
          <span className="workspace-avatar">D</span>
          <span><strong>Demo 空间</strong><small>冷启动数据模式</small></span>
          <ChevronDown size={16} />
        </button>
        <div className="sidebar-foot">
          <button onClick={() => handleNav('settings')}><Settings size={17} />设置</button>
          <div className="compliance-mini"><ShieldCheck size={16} /><span>EU AI Act §50<br /><small>合规标记已开启</small></span></div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setMobileNav(true)} aria-label="打开导航"><PanelTop size={20} /></button>
          <div className="breadcrumb"><span>洞察工作台</span><ArrowRight size={14} /><strong>{query || '新建洞察'}</strong></div>
          <div className="top-actions">
            <span className={`data-status ${runtimeState}`}><i />{runtimeMessage}</span>
            <button className="icon-button" onClick={() => setHistoryOpen(true)} aria-label="查看历史"><History size={18} /></button>
            <button className="avatar-button" title="当前用户">方</button>
          </div>
        </header>

        <div className="page-wrap">
          <section className="query-workbench">
            <div className="section-heading-row">
              <div>
                <span className="eyebrow">全球市场机会扫描</span>
                <h1>今天，应该卖什么？</h1>
                <p>把分散的趋势、评论、竞品与供应链信号，编译成备货前可以验证的行动指令。</p>
              </div>
              <div className="mode-switch" aria-label="洞察模式">
                <button className={mode === 'intuition' ? 'active' : ''} onClick={() => setMode('intuition')}>直觉</button>
                <button className={mode === 'evidence' ? 'active' : ''} onClick={() => setMode('evidence')}><BadgeCheck size={15} />有据 AI</button>
              </div>
            </div>

            <div className="search-row">
              <div className="search-field">
                <Search size={20} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && startAnalysis()} placeholder="输入想研究的品类，例如：宠物自动喂食器" />
                {query && <button className="clear-search" onClick={() => setQuery('')} aria-label="清空"><X size={16} /></button>}
              </div>
              <button className="primary-button" onClick={startAnalysis} disabled={running}>
                {running ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}
                {running ? '分析中' : '开始洞察'}
              </button>
            </div>
            <div className="query-options">
              <div className="quick-tags"><span>快速开始</span>{['宠物喂食器', '便携榨汁机', '降噪耳机'].map((tag) => <button key={tag} onClick={() => setQuery(tag)}>{tag}</button>)}</div>
              <div className="market-picker"><span>目标市场</span>{markets.map((item) => <button key={item.code} className={market === item.code ? 'active' : ''} onClick={() => setMarket(item.code)}><b>{item.code}</b>{item.name}</button>)}</div>
            </div>
          </section>

          {(running || agentStep < agents.length) && (
            <section className="agent-progress" aria-live="polite">
              <div className="progress-top">
                <div><LoaderCircle className="spin" size={18} /><strong>{runtimeState === 'connected' ? '多 Agent Runtime' : 'Agent 演示'}正在洞察 {selectedMarket?.name}市场</strong></div>
                <span>{Math.min(agentStep * 25 + 8, 96)}%</span>
              </div>
              <div className="progress-track"><span style={{ width: `${Math.min(agentStep * 25 + 8, 96)}%` }} /></div>
              <div className="agent-grid">
                {agents.map((agent, index) => {
                  const Icon = agent.icon;
                  const done = index < agentStep;
                  const active = index === agentStep;
                  return <div key={agent.label} className={`${done ? 'done' : ''} ${active ? 'active' : ''}`}><span>{done ? <Check size={15} /> : active ? <LoaderCircle className="spin" size={15} /> : <Icon size={15} />}</span><div><strong>{agent.label}</strong><small>{done ? agent.detail : active ? '正在处理…' : '等待中'}</small></div></div>;
                })}
              </div>
            </section>
          )}

          <section className="report-header" ref={resultsRef}>
            <div className="report-product">
              {/(宠物|喂食|pet|feeder)/i.test(reportCategory)
                ? <img src={productImage} alt="宠物自动喂食器演示概念" />
                : <span className="report-product-placeholder"><PackageSearch size={26} /></span>}
              <div><span className="eyebrow">机会报告 · {selectedReportMarket?.code} · {reportMode === 'mock' ? '场景化 Mock' : '离线固定样例'}</span><h2>{reportCategory}</h2><p>{selectedReportMarket?.name}市场 · 本次任务完成于 {formatReportTime(reportGeneratedAt)}</p></div>
            </div>
            <div className="report-actions">
              <button className="secondary-button" onClick={exportReport}><Download size={16} />导出</button>
              <button className="secondary-button" onClick={() => copyText(window.location.href, '报告链接已复制')}><ExternalLink size={16} />分享</button>
            </div>
          </section>

          <section className="signal-strip">
            <div><span className="metric-icon blue"><TrendingUp size={18} /></span><p>机会指数<small>需求、痛点与竞争空位</small></p><strong>{opportunityScore}<em>/100</em></strong></div>
            <div><span className="metric-icon green"><MessageCircleMore size={18} /></span><p>首要隐性痛点<small>{leadPain.label}</small></p><strong>{leadPain.count}<em>条</em></strong></div>
            <div><span className="metric-icon amber"><Boxes size={18} /></span><p>需求信号<small>{demandSignal.name}</small></p><strong>{demandSignal.value}<em>{demandSignal.note}</em></strong></div>
            <div><span className="metric-icon violet"><Clock3 size={18} /></span><p>机会窗口<small>建议复核周期</small></p><strong>14<em>天</em></strong></div>
          </section>

          {mode === 'intuition' ? (
            <section className="comparison-panel">
              <div className="comparison-side intuition-side"><span className="comparison-label">经验直觉</span><h3>继续堆功能、跟随畅销款，再用低价测试</h3><p>没有明确验证对象，样品、首批备货和广告预算容易同时暴露在风险中。</p><div className="hit-score"><span>决策依据</span><strong>经验</strong></div></div>
              <div className="comparison-divider"><span>VS</span></div>
              <div className="comparison-side evidence-side"><span className="comparison-label"><BadgeCheck size={14} />有据 AI</span><h3>{productDecision.title}</h3><p>{competitiveDecision.summary}</p><div className="hit-score"><span>证据对象</span><strong>{reportEvidence.length} 条</strong></div></div>
            </section>
          ) : (
            <>
              <div className="content-title"><div><span className="eyebrow">决策处方</span><h2>四张卡，回答怎么做</h2></div><span className="validity"><Clock3 size={15} />结论有效期剩余 14 天</span></div>
              <section className="card-grid">
                {decisionCards.map((card) => {
                  const Icon = card.icon;
                  return (
                    <article key={card.id} className={`decision-card ${card.tone}`} onClick={() => setSelectedCard(card)} tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && setSelectedCard(card)}>
                      <div className="card-head"><span className="card-type"><Icon size={17} />{card.type}</span><ScoreRing value={card.confidence} /></div>
                      <h3>{card.title}</h3><p>{card.summary}</p>
                      <div className="card-footer"><div><small>{card.metric}</small><strong>{card.metricValue}</strong></div><span>{card.source}<ArrowRight size={15} /></span></div>
                    </article>
                  );
                })}
              </section>
            </>
          )}

          <section className="insight-grid">
            <article className="panel radar-panel" id="pain-radar">
              <div className="panel-head"><div><span className="eyebrow">原语洞察</span><h2>“我喜欢，但是…” 痛点雷达</h2></div><span className="mock-pill">Mock 原语样本</span></div>
              <div className="radar-body">
                <div className="bubble-chart" aria-label="痛点机会气泡图">
                  <div className="axis-label y-label">提及频次 × 情感强度</div><div className="axis-label x-label">差异化可行性 →</div>
                  <div className="grid-lines" />
                  {insightPainPoints.map((point) => <button key={point.id} aria-label={`${point.label}，机会指数 ${point.value}`} className={`pain-bubble ${selectedPain === point.id ? 'selected' : ''}`} style={{ left: `${point.x}%`, top: `${point.y}%`, width: point.size, height: point.size, '--bubble': point.color }} onClick={() => setSelectedPain(point.id)}><span>{point.label}</span><small>{point.value}</small></button>)}
                </div>
                <div className="review-card">
                  <div className="review-top"><span className="hidden-tag"><Zap size={13} />隐性痛点</span><span>{selectedReview?.meta}</span></div>
                  <blockquote>“{selectedReview?.original}”</blockquote>
                  <p>{selectedReview?.translation}</p>
                  <button onClick={() => setToast(`已定位 ${insightPainPoints.find((item) => item.id === selectedPain)?.count || 0} 条同类样本`)}>查看同类样本 <ArrowRight size={14} /></button>
                </div>
              </div>
            </article>

            <article className="panel supply-panel" id="supply-chain">
              <div className="panel-head"><div><span className="eyebrow">领先指标</span><h2>供应链信号</h2></div><button className="icon-button" onClick={() => setToast('信号已刷新')} aria-label="刷新信号"><RefreshCw size={17} /></button></div>
              <div className="supply-list">
                {insightSupplySignals.map((signal) => <div className="supply-row" key={signal.name}><div><span className={`status-dot ${signal.state}`} /><p><strong>{signal.name}</strong><small>{signal.note}</small></p></div><MiniBars values={signal.bars} state={signal.state} /><strong>{signal.value}</strong></div>)}
              </div>
              <div className="alert-card"><AlertTriangle size={18} /><div><strong>反向条件已登记</strong><p>{pricingFailure ? `${pricingFailure.metric_to_watch} ${pricingFailure.threshold} 时重新计算定价。` : '真实数据 Provider 接入后按阈值触发重新计算。'}</p></div><button onClick={() => setToast('阈值已进入决策卡；实时触发器属于下一阶段')}>待接入</button></div>
            </article>
          </section>

          <section className="evidence-panel">
            <div className="panel-head"><div><span className="eyebrow">可追溯依据</span><h2>这项决策，凭什么？</h2></div><span className="verified-pill"><ShieldCheck size={15} />{reportEvidence.length} 条结构校验通过</span></div>
            <div className="evidence-table">
              {reportEvidence.map((item, index) => <button key={item.source} onClick={() => item.url ? window.open(item.url, '_blank', 'noopener,noreferrer') : setToast(`Mock 来源：${item.source}`)}><span className="evidence-index">{String(index + 1).padStart(2, '0')}</span><span className="evidence-source"><small>{item.type}</small><strong>{item.source}</strong></span><span className="evidence-claim">{item.claim}</span><strong className="evidence-value">{item.value}</strong><span className="evidence-open"><ExternalLink size={15} /></span></button>)}
            </div>
          </section>

          <section className="review-bar">
            <div><ShieldCheck size={19} /><span><strong>AI 生成 · 等待人工复核</strong><small>你的反馈将用于优化下一次决策</small></span></div>
            <div className="review-buttons">
              <button className={reviewStatus === 'approved' ? 'approved active' : 'approved'} onClick={() => setReview('approved')}><CheckCircle2 size={16} />采纳</button>
              <button className={reviewStatus === 'discussed' ? 'discussed active' : 'discussed'} onClick={() => setReview('discussed')}><MessageCircleMore size={16} />待议</button>
              <button className={reviewStatus === 'rejected' ? 'rejected active' : 'rejected'} onClick={() => setReview('rejected')}><XCircle size={16} />驳回</button>
            </div>
          </section>

          <section className="evolution-panel" id="evolution-center">
            <div className="evolution-head">
              <div><span className="eyebrow">Harness Evolution</span><h2>策略演进中心</h2><p>失败案例不会直接改写线上策略，候选必须通过 Validation 与 Holdout 非回归门禁。</p></div>
              <div className="evolution-head-actions">
                <span className="policy-version"><ShieldCheck size={15} />当前 {activePolicy?.version || 'policy-v1'}</span>
                <button className="icon-button" onClick={loadEvolution} aria-label="刷新演进状态"><RefreshCw size={17} /></button>
              </div>
            </div>
            <div className="evolution-flow" aria-label="策略演进流程">
              {['失败案例', '候选策略', 'Validation', 'Holdout', '人工激活'].map((step, index) => <div key={step} className={index === 0 && openFailures.length ? 'active' : index > 0 && latestEvolutionRun ? 'done' : ''}><span>{index + 1}</span><strong>{step}</strong></div>)}
            </div>
            <div className="evolution-metrics">
              <div><span>待处理失败案例</span><strong>{openFailures.length}</strong><small>{openFailures[0]?.failure_type === 'weak_evidence' ? '证据门槛不足' : openFailures.length ? '等待候选生成' : '暂无开放案例'}</small></div>
              <div><span>候选版本</span><strong>{readyPolicy?.version || latestEvolutionRun?.candidate_version || '—'}</strong><small>{readyPolicy ? '评测通过，等待激活' : latestEvolutionRun?.candidate_version === activePolicy?.version ? '已激活为稳定版本' : '不会覆盖当前稳定版本'}</small></div>
              <div><span>Validation 提升</span><strong>{latestEvolutionRun ? `+${Math.round(validationImprovement * 100)}%` : '—'}</strong><small>{latestEvolutionRun ? `${latestEvolutionRun.metrics.validation.candidate.accuracy * 100}% 准确率` : '基线与候选双回放'}</small></div>
              <div><span>Holdout 非回归</span><strong>{latestEvolutionRun ? (latestEvolutionRun.decision === 'ready' ? '通过' : '拒绝') : '—'}</strong><small>{latestEvolutionRun ? `${latestEvolutionRun.metrics.holdout.candidate.recall * 100}% 召回率` : '保护未参与生成的数据'}</small></div>
            </div>
            <div className="evolution-actions">
              <p><BadgeCheck size={16} />活动策略要求至少 {activePolicy?.policy?.minimum_evidence_count || 3} 条证据、{activePolicy?.policy?.minimum_non_english_evidence || 1} 条非英语证据。</p>
              <div>
                <button className="secondary-button" onClick={rollbackEvolutionPolicy} disabled={evolutionLoading || !activePolicy?.parent_version}><History size={15} />回滚</button>
                {readyPolicy && <button className="secondary-button activate-policy" onClick={() => activateEvolutionPolicy(readyPolicy.version)} disabled={evolutionLoading}><ShieldCheck size={15} />激活 {readyPolicy.version}</button>}
                <button className="primary-button compact" onClick={createEvolutionCandidate} disabled={evolutionLoading || openFailures.length === 0}>{evolutionLoading ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}生成候选并评测</button>
              </div>
            </div>
          </section>

          <footer><span><Compass size={15} />先机罗盘 · 决策可追溯，结论可证伪</span><span>数据模式：场景化 Mock 冷启动 · 非真实实时市场结果</span></footer>
        </div>
      </main>

      {selectedCard && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSelectedCard(null)}><div className="card-modal" role="dialog" aria-modal="true" aria-label={`${selectedCard.type}详情`}><button className="modal-close icon-button" onClick={() => setSelectedCard(null)}><X size={19} /></button><CardDetail card={selectedCard} onCopy={copyText} onReview={setReview} reviewStatus={reviewStatus} evidence={reportEvidence} reportMarket={reportMarket} generatedAt={reportGeneratedAt} /></div></div>}

      {historyOpen && <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setHistoryOpen(false)}><aside className="history-drawer"><div className="drawer-head"><div><span className="eyebrow">工作记录</span><h2>历史洞察</h2></div><button className="icon-button" onClick={() => setHistoryOpen(false)}><X size={18} /></button></div>{[
        ['宠物自动喂食器', '巴西', '刚刚', '86'], ['便携榨汁机', '墨西哥', '昨天', '74'], ['降噪耳机', '日本', '8月10日', '69'],
      ].map((item, index) => <button className="history-item" key={item[0]} onClick={() => { setQuery(item[0]); setHistoryOpen(false); setToast(`已载入：${item[0]}`); }}><span className="history-icon"><FileText size={17} /></span><span><strong>{item[0]}</strong><small>{item[1]} · {item[2]}</small></span><b>{item[3]}</b></button>)}</aside></div>}
      {toast && <div className="toast"><Check size={16} />{toast}</div>}
    </div>
  );
}

function CardDetail({ card, onCopy, onReview, reviewStatus, evidence, reportMarket, generatedAt }) {
  const Icon = card.icon;
  const detailEvidence = card.runtimeCard ? mapRuntimeEvidence([card.runtimeCard]).slice(0, 3) : evidence.slice(0, 3);
  const reportCode = `FC-${reportMarket}-${new Date(generatedAt).toISOString().slice(2, 10).replaceAll('-', '')}`;
  return (
    <div className="modal-content">
      <div className="modal-title"><span className={`modal-icon ${card.tone}`}><Icon size={20} /></span><div><span className="eyebrow">{card.type} · {reportCode}</span><h2>{card.title}</h2></div><div className="confidence-block"><ScoreRing value={card.confidence} size={48} /><small>置信度</small></div></div>
      <div className="action-box"><span>行动指令</span><p>{card.summary}</p></div>
      <div className="detail-section"><h3><BookOpen size={17} />凭什么 <span>证据链 · {detailEvidence.length} 条</span></h3>{detailEvidence.map((item) => <div className="detail-evidence" key={item.source}><BadgeCheck size={16} /><div><strong>{item.claim}</strong><small>{item.source}</small></div><b>{item.value}</b></div>)}</div>
      <div className="detail-two-col"><div className="detail-section hook-box"><h3><Users size={17} />种子验证</h3><p><b>种子人群</b> {card.hook?.audience}</p><p><b>承接渠道</b> {card.hook?.channel}</p><div className="copy-hook"><span>{card.hook?.message}</span><button onClick={() => onCopy(card.hook?.message)}><Clipboard size={15} />复制</button></div></div><div className="detail-section failure-box"><h3><AlertTriangle size={17} />什么时候失效</h3>{(card.failureConditions || [{ condition: '关键市场信号越过阈值' }]).slice(0, 2).map((item) => <p key={item.condition}>{item.condition}</p>)}<button><Bell size={15} />失效条件已登记</button></div></div>
      <div className="modal-compliance"><ShieldCheck size={17} /><span>AI 生成 · 场景化 Mock · 需人工复核<small>{detailEvidence.map((item) => item.source).join(' / ')} · 任务完成于 {formatReportTime(generatedAt)}</small></span></div>
      <div className="modal-actions"><span>复核这张卡</span><div><button className={reviewStatus === 'approved' ? 'active approved' : ''} onClick={() => onReview('approved')}><CheckCircle2 size={16} />采纳</button><button className={reviewStatus === 'discussed' ? 'active discussed' : ''} onClick={() => onReview('discussed')}><MessageCircleMore size={16} />待议</button><button className={reviewStatus === 'rejected' ? 'active rejected' : ''} onClick={() => onReview('rejected')}><XCircle size={16} />驳回</button></div></div>
    </div>
  );
}

export default App;
