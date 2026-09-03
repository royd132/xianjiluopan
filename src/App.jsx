import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Bell,
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Compass,
  Database,
  Download,
  ExternalLink,
  FileText,
  History,
  LayoutDashboard,
  LoaderCircle,
  MessageCircleMore,
  PackageSearch,
  PanelTop,
  RefreshCw,
  RadioTower,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Printer,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import productImage from './assets/pet-feeder.png';
import { foresightClient } from './api/foresightClient';
import {
  mapRuntimeCards,
  mapRuntimeEvidence,
  mapRuntimePainPoints,
  mapRuntimeReviews,
  mapRuntimeSupplySignals,
  reportModeLabels,
} from './features/research/runtimeMappers';
import { useResearchEvents } from './features/research/useResearchEvents';
import {
  agents,
  capabilitySignals,
  categoryKeyForQuery,
  demoCards,
  demoEvidence,
  demoPainPoints,
  demoReviews,
  demoSupplySignals,
  freshnessLabels,
  markets,
  scopeLabels,
} from './features/research/researchConfig';
import { DecisionCardGrid, CardDetailModal } from './features/decision-cards/DecisionCards';
import { EvidenceTable, EvidenceDetailModal } from './features/evidence/EvidencePanel';
import { EvolutionPanel } from './features/evolution/EvolutionCenter';
import { formatReportTime, ScoreRing } from './features/shared/utils';

function MiniBars({ values, state }) {
  return (
    <div className={`mini-bars ${state}`} aria-label="趋势图">
      {values.map((v, index) => <span key={index} style={{ height: `${v}%` }} />)}
    </div>
  );
}

function App() {
  const [market, setMarket] = useState('BR');
  const [query, setQuery] = useState('宠物自动喂食器');
  const [mode, setMode] = useState('evidence');
  const [researchMode, setResearchMode] = useState('mock');
  const [supportedModes, setSupportedModes] = useState(['mock']);
  const [scenarioCapabilities, setScenarioCapabilities] = useState([]);
  const [running, setRunning] = useState(false);
  const [agentStep, setAgentStep] = useState(4);
  const [selectedCard, setSelectedCard] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
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
  const [reportMode, setReportMode] = useState(null);
  const [hasReport, setHasReport] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const [monitoring, setMonitoring] = useState(null);
  const [monitoringLoading, setMonitoringLoading] = useState(false);
  const [decisionContract, setDecisionContract] = useState(null);
  const [plannedInvestment, setPlannedInvestment] = useState('30000');
  const [investmentStage, setInvestmentStage] = useState('首批备货');
  const [validationMetrics, setValidationMetrics] = useState({ sample_count: '', intent_rate: '', cpc: '', pain_confirmation_rate: '', actual_spend: '1800' });
  const [validationSubmitting, setValidationSubmitting] = useState(false);
  const [runtimeState, setRuntimeState] = useState('checking');
  const [runtimeMessage, setRuntimeMessage] = useState('正在检测多 Agent Runtime');
  const [evolution, setEvolution] = useState(null);
  const [evolutionLoading, setEvolutionLoading] = useState(false);
  const resultsRef = useRef(null);
  const sharedTaskLoadedRef = useRef(false);
  const { connect: connectResearchEvents } = useResearchEvents();

  const selectedMarket = useMemo(() => markets.find((item) => item.code === market), [market]);
  const selectedReportMarket = useMemo(() => markets.find((item) => item.code === reportMarket), [reportMarket]);
  const selectedCategoryKey = useMemo(() => categoryKeyForQuery(query), [query]);
  const currentCapability = useMemo(
    () => scenarioCapabilities.find((item) => item.market === market && item.category_key === selectedCategoryKey),
    [scenarioCapabilities, market, selectedCategoryKey],
  );
  const selectedReview = insightReviews[selectedPain] || Object.values(insightReviews)[0];
  const pricingFailure = decisionCards.find((card) => card.id === 'pricing')?.failureConditions?.[0];
  const productDecision = decisionCards.find((card) => card.id === 'product') || demoCards[0];
  const competitiveDecision = decisionCards.find((card) => card.id === 'competitive') || demoCards[2];
  const leadPain = insightPainPoints[0] || demoPainPoints[0];
  const demandSignal = insightSupplySignals[0] || demoSupplySignals[0];
  const failureConditionCount = hasReport ? decisionCards.reduce((count, card) => count + (card.failureConditions?.length || 0), 0) : 0;

  const modeAvailable = (item) => {
    if (!supportedModes.includes(item)) return false;
    if (item === 'real') return Boolean(currentCapability?.real_available);
    if (item === 'hybrid') return currentCapability ? currentCapability.hybrid_available : true;
    return true;
  };

  const capabilityText = currentCapability
    ? currentCapability.real_available
      ? `真实模式可用 · 价格依据：${currentCapability.price_source} · 已知缺口：${capabilitySignals(currentCapability.known_gaps) || '无'}`
      : `真实模式暂不可用：${capabilitySignals(currentCapability.blocking_reasons || currentCapability.missing_signals)} · 建议使用公开数据 + 明示回退`
    : '正在识别当前品类的数据覆盖范围';

  const loadEvolution = async () => {
    try {
      setEvolution(await foresightClient.getEvolution());
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
    foresightClient.getHealth()
      .then((payload) => {
        const modes = payload.supported_modes || ['mock'];
        const capabilities = payload.scenario_capabilities || [];
        setSupportedModes(modes);
        setScenarioCapabilities(capabilities);
        const initialCapability = capabilities.find((item) => item.market === 'BR' && item.category_key === 'pet_feeder');
        setResearchMode(modes.includes('real') && initialCapability?.real_available ? 'real' : modes.includes('hybrid') ? 'hybrid' : 'mock');
        setRuntimeState('connected');
        setRuntimeMessage('多 Agent Runtime 已连接');
        loadEvolution();
      })
      .catch(() => {
        setRuntimeState('offline');
        setRuntimeMessage('离线演示模式');
      });
  }, []);

  useEffect(() => {
    if (!currentCapability) return;
    if (researchMode === 'real' && !currentCapability.real_available) {
      setResearchMode(currentCapability.hybrid_available ? 'hybrid' : 'mock');
    }
  }, [currentCapability, researchMode]);

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
    setHasReport(true);
    setCurrentTaskId(null);
    setSelectedPain('noise');
    if (query !== '宠物自动喂食器' || market !== 'BR') setToast('离线固定样例已载入；启动后端可运行多品类、多市场冷启动');
    setRunning(true);
  };

  const loadMonitoring = async (category = reportCategory, targetMarket = reportMarket) => {
    if (runtimeState !== 'connected') return;
    setMonitoringLoading(true);
    try {
      setMonitoring(await foresightClient.getMonitoring(category, targetMarket));
    } catch {
      setToast('监控快照暂不可用');
    } finally {
      setMonitoringLoading(false);
    }
  };

  const loadRuntimeResult = async (taskId) => {
    const payload = await foresightClient.getResearch(taskId);
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
      setDecisionContract(payload.result.contract || null);
      setHasReport(true);
      setCurrentTaskId(taskId);
      setSelectedPain(payload.result.pain_points[0]?.pain_type || 'noise');
      setRuntimeMessage(`6 个 Agent 已完成 · Trace ${payload.result.trace_id.slice(0, 8)}`);
      window.history.replaceState({}, '', `${window.location.pathname}?task=${encodeURIComponent(taskId)}${window.location.hash}`);
      loadMonitoring(payload.result.request.category, payload.result.request.market);
    }
    setAgentStep(agents.length);
    setRunning(false);
    window.setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  };

  useEffect(() => {
    if (runtimeState !== 'connected' || sharedTaskLoadedRef.current) return;
    const taskId = new URLSearchParams(window.location.search).get('task');
    if (!taskId) return;
    sharedTaskLoadedRef.current = true;
    loadRuntimeResult(taskId).catch(() => setToast('共享报告不存在或已过期'));
  }, [runtimeState]);

  useEffect(() => {
    if (!hasReport || !window.location.hash) return undefined;
    const timer = window.setTimeout(() => {
      document.querySelector(window.location.hash)?.scrollIntoView({ block: 'start' });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [hasReport]);

  const connectRuntimeEvents = (taskId) => {
    let completedAgents = 0;
    connectResearchEvents(taskId, {
      onAgentStarted: (payload) => setRuntimeMessage(payload?.message || 'Agent 已启动'),
      onAgentCompleted: (payload) => {
        completedAgents += 1;
        setAgentStep(Math.min(Math.ceil(completedAgents / 1.5), agents.length - 1));
        setRuntimeMessage(payload?.message || 'Agent 已完成');
      },
      onGatePassed: () => {
        setAgentStep(agents.length - 1);
        setRuntimeMessage('安全评测闸门已通过');
      },
      onTaskCompleted: () => loadRuntimeResult(taskId),
      onTaskFailed: () => {
        if (researchMode === 'mock') {
          setToast('Mock Runtime 任务失败，已切换离线演示');
          runLocalFallback();
          return;
        }
        setRunning(false);
        setRuntimeMessage(`${researchMode === 'real' ? '真实' : '混合'}任务失败，未静默降级`);
        setToast('数据或模型未满足当前模式合同，请查看后端任务事件');
      },
    });
  };

  const startAnalysis = async () => {
    if (!query.trim()) {
      setToast('请先输入一个品类关键词');
      return;
    }
    if (!modeAvailable(researchMode)) {
      setToast('当前市场与品类不满足真实模式数据合同，请切换为公开数据模式');
      return;
    }
    setReviewStatus('pending');
    setAgentStep(0);
    setRunning(true);
    try {
      const payload = await foresightClient.createResearch({
        category: query,
        market,
        mode: researchMode,
        languages: ['pt', 'en', 'es'],
        planned_investment: plannedInvestment ? Number(plannedInvestment) : null,
        investment_stage: investmentStage || null,
      });
      setRuntimeState('connected');
      setRuntimeMessage(`任务 ${payload.task_id.slice(0, 8)} 已进入协作黑板`);
      connectRuntimeEvents(payload.task_id);
    } catch {
      if (researchMode === 'mock') {
        runLocalFallback();
        return;
      }
      setRunning(false);
      setRuntimeMessage(`${researchMode === 'real' ? '真实' : '混合'}任务未启动，未静默降级`);
      setToast('当前模式不可用，请检查数据缓存、Qwen 或后端连接');
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
      decisionContract: decisionContract || null,
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
    setToast('决策报告已导出');
  };

  const shareReport = () => {
    const url = currentTaskId
      ? `${window.location.origin}${window.location.pathname}?task=${encodeURIComponent(currentTaskId)}`
      : window.location.href;
    copyText(url, '可恢复报告链接已复制');
  };

  const setReview = async (status) => {
    setReviewStatus(status);
    const runtimeCardId = selectedCard?.runtimeCard?.card_id || decisionCards[0]?.runtimeCard?.card_id;
    if (runtimeCardId && runtimeState === 'connected') {
      try {
        await foresightClient.reviewCard(runtimeCardId, {
          status,
          reviewer: 'demo-user',
          reason: status === 'rejected' ? '证据数量与原语覆盖不足，需要提高发布门槛' : null,
          failure_type: status === 'rejected' ? 'weak_evidence' : null,
        });
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
      const payload = await foresightClient.createEvolutionCandidate();
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
      await foresightClient.activateEvolutionPolicy(version);
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
      const payload = await foresightClient.rollbackEvolutionPolicy();
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

  const openFailures = evolution?.failure_cases?.filter((item) => item.status === 'open') || [];

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Compass size={21} strokeWidth={2.4} /></div>
          <div><strong>先机罗盘</strong><span>Foresight Compass</span></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="关闭导航"><X size={18} /></button>
        </div>
        <nav className="nav-list" aria-label="主导航">
          <button className={activeNav === 'workspace' ? 'active' : ''} onClick={() => handleNav('workspace')}><LayoutDashboard size={18} />首单决策台</button>
          <button className={activeNav === 'radar' ? 'active' : ''} onClick={() => handleNav('radar')}><Target size={18} />痛点雷达</button>
          <button className={activeNav === 'alerts' ? 'active' : ''} onClick={() => handleNav('alerts')}><Bell size={18} />失效条件{failureConditionCount > 0 && <span className="nav-badge">{failureConditionCount}</span>}</button>
          <button className={activeNav === 'history' ? 'active' : ''} onClick={() => handleNav('history')}><History size={18} />决策记录</button>
          <button className={activeNav === 'evolution' ? 'active' : ''} onClick={() => handleNav('evolution')}><Activity size={18} />演进中心{openFailures.length > 0 && <span className="nav-badge">{openFailures.length}</span>}</button>
        </nav>
        <div className="sidebar-section-label">工作空间</div>
        <button className="workspace-switcher" onClick={() => setToast('当前为 Demo 工作空间')}>
          <span className="workspace-avatar">D</span>
          <span><strong>Demo 空间</strong><small>{reportModeLabels[researchMode]}</small></span>
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
          <div className="breadcrumb"><span>首单决策台</span><ArrowRight size={14} /><strong>{query || '新建决策'}</strong></div>
          <div className="top-actions">
            <span className={`data-status ${runtimeState}`}><i />{runtimeMessage}</span>
            <button className="icon-button" onClick={() => setHistoryOpen(true)} aria-label="查看历史"><History size={18} /></button>
            <button className="avatar-button" title="当前用户">方</button>
          </div>
        </header>

        <div className="page-wrap">
          <section className="query-workbench" id="research-entry">
            <div className="section-heading-row">
              <div>
                <span className="eyebrow">首单投资决策台</span>
                <h1>这笔钱，现在能不能投？</h1>
                <p>在第一次不可逆投入前，检查证据是否足够；不够就设计最低成本验证，够了才 Go。</p>
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
                {running ? '生成中' : '生成首单决策'}
              </button>
            </div>
            <div className="query-options">
              <div className="quick-tags"><span>快速开始</span>{['宠物喂食器', '便携榨汁机', '降噪耳机'].map((tag) => <button key={tag} onClick={() => setQuery(tag)}>{tag}</button>)}</div>
              <div className="market-picker"><span>目标市场</span>{markets.map((item) => <button key={item.code} className={market === item.code ? 'active' : ''} onClick={() => setMarket(item.code)}><b>{item.code}</b>{item.name}</button>)}</div>
              <div className="market-picker data-mode-picker"><span>数据模式</span>{['real', 'hybrid', 'mock'].map((item) => <button key={item} disabled={!modeAvailable(item)} className={researchMode === item ? 'active' : ''} onClick={() => setResearchMode(item)}>{reportModeLabels[item]}</button>)}</div>
              <div className="market-picker investment-picker"><span>决策阶段</span>{['打样', '首批小单', '首批备货', '广告测试'].map((stage) => <button key={stage} className={investmentStage === stage ? 'active' : ''} onClick={() => setInvestmentStage(stage)}>{stage}</button>)}</div>
              <div className="market-picker investment-picker"><span>计划投入（¥）</span><input type="number" value={plannedInvestment} onChange={(e) => setPlannedInvestment(e.target.value)} placeholder="30000" style={{ width: 120, padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d5dd', fontSize: 14 }} /></div>
            </div>
            <div className={`capability-note ${currentCapability?.real_available ? 'ready' : 'limited'}`}><Database size={14} /><span>{capabilityText}</span></div>
          </section>

          {(running || agentStep < agents.length) && (
            <section className="agent-progress" aria-live="polite">
              <div className="progress-top">
                <div><LoaderCircle className="spin" size={18} /><strong>{runtimeState === 'connected' ? '多 Agent Runtime' : 'Agent 演示'}正在生成 {selectedMarket?.name}市场首单决策</strong></div>
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

          {!hasReport ? (
            <section className="report-empty" ref={resultsRef}>
              <span className="report-empty-icon"><PackageSearch size={28} /></span>
              <div><span className="eyebrow">等待首单决策</span><h2>还没有生成决策契约</h2><p>输入品类、目标市场、决策阶段和计划投入后启动。系统不会在首轮直接建议 Go。</p></div>
              <div className="empty-contract"><ShieldCheck size={16} /><span>真实模式缺少必要数据时会直接拒绝，不会自动换成演示数字。</span></div>
            </section>
          ) : (
            <>
          <section className="report-header" id="report-summary" ref={resultsRef}>
            <div className="report-product">
              {/(宠物|喂食|pet|feeder)/i.test(reportCategory)
                ? <img src={productImage} alt="宠物自动喂食器演示概念" />
                : <span className="report-product-placeholder"><PackageSearch size={26} /></span>}
              <div><span className="eyebrow">决策契约 · {selectedReportMarket?.code} · {reportModeLabels[reportMode] || reportMode}</span><h2>{reportCategory}</h2><p>{selectedReportMarket?.name}市场 · 本次任务完成于 {formatReportTime(reportGeneratedAt)}</p></div>
            </div>
            <div className="report-actions">
              <button className="secondary-button" onClick={() => window.print()}><Printer size={16} />打印/PDF</button>
              <button className="secondary-button" onClick={exportReport}><Download size={16} />JSON</button>
              <button className="secondary-button" onClick={shareReport}><ExternalLink size={16} />分享</button>
            </div>
          </section>

          <section className="monitoring-bar">
            <div><span className="monitoring-icon"><RadioTower size={17} /></span><p><strong>市场监控快照</strong><small>{monitoring ? `最近读取 ${formatReportTime(monitoring.generated_at)} · 手动刷新` : '等待读取公开数据快照'}</small></p></div>
            <div className="monitoring-summary"><span>当前触发</span><strong>{monitoring?.trigger_count ?? '—'}</strong><small>项阈值</small></div>
            <div className="monitoring-summary"><span>覆盖信号</span><strong>{monitoring?.signals?.length ?? '—'}</strong><small>项</small></div>
            <button className="secondary-button" onClick={() => loadMonitoring(reportCategory, reportMarket)} disabled={monitoringLoading}>{monitoringLoading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}刷新快照</button>
          </section>

          {decisionContract && (
            <section className="decision-contract-panel" style={{ background: decisionContract.verdict === 'GO' ? '#ecfdf5' : decisionContract.verdict === 'STOP' ? '#fef2f2' : '#fffbeb', border: '2px solid', borderColor: decisionContract.verdict === 'GO' ? '#10b981' : decisionContract.verdict === 'STOP' ? '#ef4444' : '#f59e0b', borderRadius: 12, padding: '24px 28px', marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                <span style={{ fontSize: 32, fontWeight: 800, color: decisionContract.verdict === 'GO' ? '#059669' : decisionContract.verdict === 'STOP' ? '#dc2626' : '#d97706', letterSpacing: 2 }}>{decisionContract.verdict}</span>
                <div>
                  <strong style={{ fontSize: 16 }}>
                    {decisionContract.verdict === 'GO' ? '证据充分，可以投入' : decisionContract.verdict === 'STOP' ? '证据不足，建议停止' : '当前不建议直接投入'}
                  </strong>
                  {decisionContract.planned_investment && (
                    <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: 14 }}>
                      计划投入 ¥{decisionContract.planned_investment.toLocaleString()}
                      {decisionContract.allowed_investment != null && decisionContract.verdict !== 'GO' && (
                        <> → 当前建议上限 <strong style={{ color: '#d97706' }}>¥{decisionContract.allowed_investment.toLocaleString()}</strong></>
                      )}
                    </p>
                  )}
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, fontSize: 14 }}>
                <div><span style={{ color: '#6b7280' }}>证据成熟度</span><br /><strong>{decisionContract.evidence_coverage?.maturity || '—'}</strong>
                  <div style={{ background: '#e5e7eb', borderRadius: 4, height: 6, marginTop: 4 }}>
                    <div style={{ background: decisionContract.verdict === 'GO' ? '#10b981' : '#f59e0b', borderRadius: 4, height: 6, width: `${((decisionContract.evidence_coverage?.checkpoints || []).filter(c => c.status === 'pass').length / Math.max((decisionContract.evidence_coverage?.checkpoints || []).length, 1)) * 100}%` }} />
                  </div>
                </div>
                {decisionContract.biggest_unknown && <div><span style={{ color: '#6b7280' }}>最大未知项</span><br /><strong>{decisionContract.biggest_unknown}</strong></div>}
                {decisionContract.experiment_design && <div><span style={{ color: '#6b7280' }}>下一步实验</span><br /><strong style={{ fontSize: 13 }}>{decisionContract.experiment_design.slice(0, 60)}…</strong></div>}
                {decisionContract.experiment_budget != null && <div><span style={{ color: '#6b7280' }}>实验预算</span><br /><strong>¥{decisionContract.experiment_budget.toLocaleString()}</strong></div>}
              </div>
              {decisionContract.stop_conditions?.length > 0 && (
                <details style={{ marginTop: 12, fontSize: 13 }}>
                  <summary style={{ cursor: 'pointer', color: '#6b7280' }}>Stop 条件 ({decisionContract.stop_conditions.length})</summary>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 20, color: '#374151' }}>
                    {decisionContract.stop_conditions.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </details>
              )}
              {decisionContract.human_override && decisionContract.system_verdict && (
                <div style={{ marginTop: 12, padding: '8px 12px', background: '#fef3c7', borderRadius: 6, fontSize: 13, color: '#92400e' }}>
                  ⚠ 人工覆盖：系统判定={decisionContract.system_verdict}，已由人工覆盖为 {decisionContract.human_override}
                </div>
              )}
              {decisionContract.verdict === 'STOP' && !decisionContract.human_override && currentTaskId && (
                <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>是否接受系统判定？</span>
                  <button className="secondary-button" style={{ fontSize: 13 }} onClick={() => setToast('已接受系统判定 STOP')}>接受 STOP</button>
                  <button className="secondary-button" style={{ fontSize: 13, borderColor: '#f59e0b', color: '#92400e' }} onClick={async () => {
                    const reason = window.prompt('请输入覆盖理由（将记录审计）：');
                    if (!reason) return;
                    try {
                      const contract = await foresightClient.overrideContract(currentTaskId, {
                        target_verdict: 'GO',
                        reason,
                        operator: 'demo-user',
                      });
                      setDecisionContract(contract);
                      setToast('已人工覆盖为 GO（system_verdict 保留为 STOP）');
                    } catch (error) {
                      setToast(error.message || '覆盖失败');
                    }
                  }}>人工覆盖为 GO</button>
                </div>
              )}
            </section>
          )}

          {decisionContract?.verdict === 'VALIDATE' && currentTaskId && (
            <section className="validation-form" style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 10, padding: 20, marginBottom: 24 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>提交验证结果 · 首单晋级闸门</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                <label style={{ fontSize: 13 }}>本次实际验证花费（¥）<input type="number" value={validationMetrics.actual_spend} onChange={(e) => setValidationMetrics({ ...validationMetrics, actual_spend: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>样本量 <small style={{ color: '#6b7280' }}>要求 ≥30</small><input type="number" value={validationMetrics.sample_count} onChange={(e) => setValidationMetrics({ ...validationMetrics, sample_count: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>购买意向率（%） <small style={{ color: '#6b7280' }}>要求 ≥12%</small><input type="number" step="1" value={validationMetrics.intent_rate} onChange={(e) => setValidationMetrics({ ...validationMetrics, intent_rate: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>CPC（¥） <small style={{ color: '#6b7280' }}>可选 · 当前未设阈值</small><input type="number" step="0.1" value={validationMetrics.cpc} onChange={(e) => setValidationMetrics({ ...validationMetrics, cpc: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>痛点确认率（%） <small style={{ color: '#6b7280' }}>要求 ≥30%</small><input type="number" step="1" value={validationMetrics.pain_confirmation_rate} onChange={(e) => setValidationMetrics({ ...validationMetrics, pain_confirmation_rate: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
              </div>
              <button className="primary-button" disabled={validationSubmitting} onClick={async () => {
                setValidationSubmitting(true);
                try {
                  const metrics = {};
                  if (validationMetrics.sample_count) metrics.sample_count = Number(validationMetrics.sample_count);
                  if (validationMetrics.intent_rate) metrics.intent_rate = Number(validationMetrics.intent_rate) / 100;
                  if (validationMetrics.cpc) metrics.cpc = Number(validationMetrics.cpc);
                  if (validationMetrics.pain_confirmation_rate) metrics.pain_confirmation_rate = Number(validationMetrics.pain_confirmation_rate) / 100;
                  const contract = await foresightClient.submitValidationResult(currentTaskId, {
                    actual_spend: Number(validationMetrics.actual_spend) || 0,
                    metrics,
                    outcome: 'inconclusive',
                  });
                  setDecisionContract(contract);
                  setToast(`验证结果已提交 → ${contract.verdict}`);
                } catch (error) {
                  setToast(error.message || '提交失败');
                } finally {
                  setValidationSubmitting(false);
                }
              }} style={{ marginTop: 12 }}>
                {validationSubmitting ? '提交中…' : '提交验证结果'}
              </button>
            </section>
          )}

          <section className="signal-strip">
            <div><span className="metric-icon green"><MessageCircleMore size={18} /></span><p>首要隐性痛点<small>{leadPain.label}</small></p><strong>{leadPain.count}<em>条</em></strong></div>
            <div><span className="metric-icon amber"><Boxes size={18} /></span><p>需求信号<small>{demandSignal.name}</small></p><strong>{demandSignal.value}<em>{demandSignal.note}</em></strong></div>
            <div><span className="metric-icon violet"><Clock3 size={18} /></span><p>决策有效期<small>建议复核周期</small></p><strong>14<em>天</em></strong></div>
          </section>

          {mode === 'intuition' ? (
            <section className="comparison-panel">
              <div className="comparison-side intuition-side"><span className="comparison-label">经验直觉</span><h3>继续堆功能、跟随畅销款，再用低价测试</h3><p>没有明确验证对象，样品、首批备货和广告预算容易同时暴露在风险中。</p><div className="hit-score"><span>决策依据</span><strong>经验</strong></div></div>
              <div className="comparison-divider"><span>VS</span></div>
              <div className="comparison-side evidence-side"><span className="comparison-label"><BadgeCheck size={14} />有据 AI</span><h3>{productDecision.title}</h3><p>{competitiveDecision.summary}</p><div className="hit-score"><span>证据对象</span><strong>{reportEvidence.length} 条</strong></div></div>
            </section>
          ) : (
            <>
              <div style={{ marginBottom: 12 }}><span className="eyebrow">为什么系统这么判断？</span><h2 style={{ fontSize: 18, margin: '4px 0' }}>支撑投资决策的证据层</h2></div>
              <DecisionCardGrid cards={decisionCards} onSelectCard={setSelectedCard} />
            </>
          )}

          <section className="insight-grid" id="pain-radar">
            <article className="panel radar-panel">
              <div className="panel-head"><div><span className="eyebrow">原语洞察</span><h2>“我喜欢，但是…” 痛点雷达</h2></div><span className="mock-pill">{reportMode === 'real' ? '源记录回指' : reportMode === 'hybrid' ? '公开数据优先' : 'Mock 原语样本'}</span></div>
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
              <div className="panel-head"><div><span className="eyebrow">领先指标</span><h2>供应链信号</h2></div><button className="icon-button" onClick={() => loadMonitoring(reportCategory, reportMarket)} aria-label="刷新信号" disabled={monitoringLoading}><RefreshCw className={monitoringLoading ? 'spin' : ''} size={17} /></button></div>
              <div className="supply-list">
                {insightSupplySignals.map((signal) => <div className="supply-row" key={signal.name}><div><span className={`status-dot ${signal.state}`} /><p><strong>{signal.name}</strong><small>{signal.note}</small></p></div><MiniBars values={signal.bars} state={signal.state} /><strong>{signal.value}</strong></div>)}
              </div>
              <div className="alert-card"><AlertTriangle size={18} /><div><strong>反向条件已登记</strong><p>{pricingFailure ? `${pricingFailure.metric_to_watch} ${pricingFailure.threshold} 时重新计算定价。` : '公开数据快照变化越线后重新计算。'}</p></div><button onClick={() => loadMonitoring(reportCategory, reportMarket)}>查看快照</button></div>
            </article>
          </section>

          <EvidenceTable evidence={reportEvidence} onSelectEvidence={setSelectedEvidence} />

          <section className="review-bar">
            <div><ShieldCheck size={19} /><span><strong>AI 生成 · 等待人工复核</strong><small>你的反馈将用于优化下一次决策</small></span></div>
            <div className="review-buttons">
              <button className={reviewStatus === 'approved' ? 'approved active' : 'approved'} onClick={() => setReview('approved')}><CheckCircle2 size={16} />采纳</button>
              <button className={reviewStatus === 'discussed' ? 'discussed active' : 'discussed'} onClick={() => setReview('discussed')}><MessageCircleMore size={16} />待议</button>
              <button className={reviewStatus === 'rejected' ? 'rejected active' : 'rejected'} onClick={() => setReview('rejected')}><XCircle size={16} />驳回</button>
            </div>
          </section>

          <EvolutionPanel
            evolution={evolution}
            evolutionLoading={evolutionLoading}
            onLoadEvolution={loadEvolution}
            onCreateCandidate={createEvolutionCandidate}
            onActivatePolicy={activateEvolutionPolicy}
            onRollbackPolicy={rollbackEvolutionPolicy}
          />

          <footer><span><Compass size={15} />先机罗盘 · 决策可追溯，结论可证伪</span><span>数据模式：{reportModeLabels[reportMode] || reportMode}{reportMode === 'real' ? ' · 当前竞品价仍需授权源' : ''}</span></footer>
            </>
          )}
        </div>
      </main>

      {selectedCard && <CardDetailModal card={selectedCard} onClose={() => setSelectedCard(null)} onCopy={copyText} onReview={setReview} reviewStatus={reviewStatus} evidence={reportEvidence} reportMarket={reportMarket} generatedAt={reportGeneratedAt} reportMode={reportMode} />}

      {selectedEvidence && <EvidenceDetailModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}

      {historyOpen && <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setHistoryOpen(false)}><aside className="history-drawer"><div className="drawer-head"><div><span className="eyebrow">工作记录</span><h2>决策记录</h2></div><button className="icon-button" onClick={() => setHistoryOpen(false)}><X size={18} /></button></div>{hasReport ? <button className="history-item" onClick={() => setHistoryOpen(false)}><span className="history-icon"><FileText size={17} /></span><span><strong>{reportCategory}</strong><small>{selectedReportMarket?.name} · {formatReportTime(reportGeneratedAt)}</small></span><b>{decisionContract ? `${decisionContract.verdict} · ${decisionContract.evidence_coverage?.maturity || '—'}` : '—'}</b></button> : <div className="history-empty"><History size={24} /><strong>暂无决策记录</strong><p>完成一次研究任务后，决策契约会出现在这里。</p></div>}</aside></div>}
      {toast && <div className="toast"><Check size={16} />{toast}</div>}
    </div>
  );
}

export default App;
