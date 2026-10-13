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
  CircleDollarSign,
  ChevronDown,
  Clock3,
  Compass,
  Copy,
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
import { SkillBankPanel } from './features/skills/SkillBank';
import { formatReportTime, remainingValidityDays, ScoreRing } from './features/shared/utils';
import { buildSellerSpriteTask, downloadSellerSpriteAsins, downloadSellerSpriteTask } from './features/integrations/sellerSpriteAdapter';

const navSectionIds = { radar: 'pain-radar', alerts: 'supply-chain', evolution: 'evolution-center', skills: 'skill-bank', sources: 'source-catalog' };

function MiniBars({ values, state }) {
  return (
    <div className={`mini-bars ${state}`} aria-label="趋势图">
      {values.map((v, index) => <span key={index} style={{ height: `${v}%` }} />)}
    </div>
  );
}

function App() {
  const [market, setMarket] = useState('BR');
  const [workspaceId, setWorkspaceId] = useState(() => {
    try {
      return window.localStorage.getItem('foresight.workspace') || 'default';
    } catch {
      return 'default';
    }
  });
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
  const [reviewStatuses, setReviewStatuses] = useState({});
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('workspace');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
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
  const [monitorSubscriptions, setMonitorSubscriptions] = useState([]);
  const [decisionContract, setDecisionContract] = useState(null);
  const [plannedInvestment, setPlannedInvestment] = useState('30000');
  const [investmentStage, setInvestmentStage] = useState('首批备货');
  const economicsDefaults = { selling_price: '199', product_cost: '62', packaging_cost: '4', domestic_shipping: '6', international_shipping: '24', duty_rate_pct: '8', vat_rate_pct: '0', platform_fee_rate_pct: '15', payment_fee_rate_pct: '2', ad_cost_per_order: '18', return_rate_pct: '4', target_margin_pct: '20' };
  const economicsRef = useRef({ ...economicsDefaults });
  const [economicsResult, setEconomicsResult] = useState(null);
  const [economicsLoading, setEconomicsLoading] = useState(false);
  const [validationMetrics, setValidationMetrics] = useState({ sample_count: '', intent_rate: '', cpc: '', pain_confirmation_rate: '', actual_spend: '1800', outcome: 'inconclusive' });
  const [validationSubmitting, setValidationSubmitting] = useState(false);
  const [runtimeState, setRuntimeState] = useState('checking');
  const [runtimeMessage, setRuntimeMessage] = useState('正在检测多 Agent Runtime');
  const [mutationProtection, setMutationProtection] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);
  const [calibration, setCalibration] = useState(null);
  const [adminToken, setAdminToken] = useState(foresightClient.getAdminToken());
  const [evolution, setEvolution] = useState(null);
  const [evolutionLoading, setEvolutionLoading] = useState(false);
  // `recoverable` is the runtime's own verdict: the run stopped mid-flight AND a
  // checkpoint exists. The UI mirrors it instead of guessing from "task stopped".
  const [taskRecoverable, setTaskRecoverable] = useState(false);
  const [taskControlBusy, setTaskControlBusy] = useState(false);
  const [skills, setSkills] = useState(null);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [retrievedSkills, setRetrievedSkills] = useState(null);
  const [retrievedFor, setRetrievedFor] = useState('');
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

  const modeBlockReason = (item) => {
    if (!currentCapability) return '正在读取当前市场的数据能力';
    const gaps = currentCapability.blocking_reasons || currentCapability.missing_signals || [];
    return capabilitySignals(gaps) || `${reportModeLabels[item]} 暂不可用`;
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

  const loadSkills = async () => {
    try {
      setSkills(await foresightClient.getSkills());
    } catch {
      setSkills(null);
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
        setMutationProtection(payload.mutation_protection || null);
        setDataStatus(payload.real_data || null);
        setCalibration(payload.calibration || null);
        const initialCapability = capabilities.find((item) => item.market === 'BR' && item.category_key === 'pet_feeder');
        // Keep the one-click path deterministic. Real and hybrid modes require
        // fresh source caches and (for real) a live model adapter; those remain
        // explicit operator choices instead of surprising the first click.
        setResearchMode(modes.includes('mock') ? 'mock' : modes.includes('hybrid') ? 'hybrid' : 'real');
        setRuntimeState('connected');
        setRuntimeMessage('多 Agent Runtime 已连接');
        loadEvolution();
        loadSkills();
        loadMonitorSubscriptions();
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
    setDecisionContract(null);
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
    setTaskRecoverable(false);
    setSelectedPain('noise');
    if (query !== '宠物自动喂食器' || market !== 'BR') setToast('离线固定样例已载入；启动后端可运行多品类、多市场冷启动');
    setRunning(true);
  };

  const loadMonitoring = async (category = reportCategory, targetMarket = reportMarket) => {
    if (runtimeState !== 'connected') return;
    setMonitoringLoading(true);
    try {
      const subscription = monitorSubscriptions.find((item) => item.category === category && item.market === targetMarket);
      if (subscription) {
        const checked = await foresightClient.checkMonitoringSubscription(subscription.subscription_id);
        setMonitoring(checked.snapshot);
        setMonitorSubscriptions((items) => items.map((item) => item.subscription_id === subscription.subscription_id ? checked.subscription : item));
      } else {
        setMonitoring(await foresightClient.getMonitoring(category, targetMarket));
      }
    } catch (error) {
      // 409 说明当前模式压根没有快照源，不是可以重试的临时故障
      setToast(error.status === 409 ? '当前模式没有公开数据快照，需先配置数据缓存' : '监控快照暂不可用');
    } finally {
      setMonitoringLoading(false);
    }
  };

  const loadRuntimeResult = async (taskId) => {
    const payload = await foresightClient.getResearch(taskId);
    if (!payload.result) {
      setCurrentTaskId(taskId);
      setTaskRecoverable(Boolean(payload.recoverable));
      if (payload.status === 'running' || payload.status === 'cancel_requested') {
        setRunning(payload.status === 'running');
        setAgentStep(Math.min(payload.event_count || 0, agents.length));
        setRuntimeMessage(payload.status === 'cancel_requested' ? '任务正在停止，可从最近检查点恢复' : '正在恢复任务事件流…');
        connectRuntimeEvents(taskId);
      } else {
        setRunning(false);
        setAgentStep(agents.length);
        setRuntimeMessage(payload.error || `任务状态：${payload.status || '未知'}`);
      }
      return;
    }
    if (payload.result?.cards) {
      setDecisionCards(mapRuntimeCards(payload.result.cards));
      setReviewStatuses(Object.fromEntries(payload.result.cards.map((card) => [card.card_id, card.human_review_status || 'pending'])));
      setReportEvidence(mapRuntimeEvidence(payload.result.cards));
      setInsightPainPoints(mapRuntimePainPoints(payload.result.pain_points));
      setInsightReviews(mapRuntimeReviews(payload.result.pain_points, markets.find((item) => item.code === payload.result.request.market)?.name || payload.result.request.market));
      setInsightSupplySignals(mapRuntimeSupplySignals(payload.result.supply_signals));
      setReportCategory(payload.result.request.category);
      setReportMarket(payload.result.request.market);
      setQuery(payload.result.request.category);
      setMarket(payload.result.request.market);
      setWorkspaceId(payload.result.request.workspace_id || 'default');
      setReportGeneratedAt(payload.result.completed_at);
      setReportMode(payload.result.mode);
      setResearchMode(payload.result.mode === 'real' || payload.result.mode === 'hybrid' ? payload.result.mode : 'mock');
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
    // `recoverable` comes from the runtime, so a shared link to an interrupted
    // task offers resume without the viewer having watched it stop.
    setTaskRecoverable(Boolean(payload.recoverable));
    window.setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  };

  const refreshSourceStatus = async () => {
    try {
      setDataStatus(await foresightClient.getDataStatus());
      setToast('数据源状态已刷新；密钥只在后端配置，不会写入浏览器');
    } catch (error) {
      setToast(error.message || '数据源状态读取失败');
    }
  };

  const loadMonitorSubscriptions = async () => {
    if (runtimeState !== 'connected') return;
    try {
      const payload = await foresightClient.getMonitoringSubscriptions(workspaceId);
      setMonitorSubscriptions(payload.items || []);
    } catch {
      setMonitorSubscriptions([]);
    }
  };

  const toggleMonitoringSubscription = async () => {
    const existing = monitorSubscriptions.find((item) => item.category === reportCategory && item.market === reportMarket);
    try {
      if (existing) {
        await foresightClient.deleteMonitoringSubscription(existing.subscription_id);
        setToast('已取消该市场的监控订阅');
      } else {
        await foresightClient.createMonitoringSubscription({ workspace_id: workspaceId, category: reportCategory, market: reportMarket, cadence: 'weekly', channels: ['in_app'] });
        setToast('已登记每周市场快照；当前仅支持手动刷新');
      }
      loadMonitorSubscriptions();
    } catch (error) {
      setToast(error.message || '监控订阅更新失败');
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const payload = await foresightClient.getResearchHistory(workspaceId, 50);
      setHistoryItems(payload.items || []);
    } catch {
      setHistoryItems([]);
      setToast('历史记录暂不可用，请检查运行时连接');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (runtimeState === 'connected') loadMonitorSubscriptions();
  }, [runtimeState, workspaceId]);

  const changeWorkspace = (nextWorkspaceId) => {
    setWorkspaceId(nextWorkspaceId);
    try {
      window.localStorage.setItem('foresight.workspace', nextWorkspaceId);
    } catch {
      // Private browsing can deny local storage; the current session still works.
    }
    setHistoryItems([]);
    setMonitorSubscriptions([]);
    setMonitoring(null);
    setToast(`已切换到${nextWorkspaceId === 'default' ? 'Demo 空间' : 'Pilot 空间'}`);
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

  const connectRuntimeEvents = (taskId, { resumed = false } = {}) => {
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
      onTaskCompleted: () => {
        setTaskRecoverable(false);
        loadRuntimeResult(taskId);
      },
      onTaskFailed: (payload) => {
        setTaskRecoverable(true);
        if (researchMode === 'mock') {
          setToast('Mock Runtime 任务失败，已切换离线演示');
          runLocalFallback();
          return;
        }
        setRunning(false);
        setRuntimeMessage(`${researchMode === 'real' ? '真实' : '混合'}任务失败，未静默降级`);
        setToast(payload?.message || payload?.error || '数据或模型未满足当前模式合同，请查看后端任务事件');
      },
      onTaskCancelled: () => {
        setRunning(false);
        // The run stopped at a node boundary and the harness saved a checkpoint
        // before it did, so the resume affordance is real rather than optimistic.
        setTaskRecoverable(true);
        setRuntimeMessage('任务已取消，可从最近检查点恢复');
      },
    });
  };

  const cancelCurrentTask = async () => {
    if (!currentTaskId) return;
    setTaskControlBusy(true);
    try {
      await foresightClient.cancelResearch(currentTaskId);
      setRuntimeMessage('取消请求已发送，等待任务在节点边界停下');
    } catch (error) {
      setToast(error.message || '取消失败，请确认任务仍在本进程内');
    } finally {
      setTaskControlBusy(false);
    }
  };

  const resumeCurrentTask = async () => {
    if (!currentTaskId) return;
    setTaskControlBusy(true);
    try {
      await foresightClient.resumeResearch(currentTaskId);
      setTaskRecoverable(false);
      setRunning(true);
      setAgentStep(0);
      setRuntimeMessage('已从最近检查点恢复，重新接入事件流');
      // Without reconnecting, the cancelled stream's EventSource stays closed and
      // the resumed run would finish silently with the UI still showing 0%.
      connectRuntimeEvents(currentTaskId, { resumed: true });
      setToast('任务已从检查点恢复');
    } catch (error) {
      setToast(error.message || '没有可用检查点，无法恢复');
    } finally {
      setTaskControlBusy(false);
    }
  };

  const startAnalysis = async () => {
    if (!query.trim()) {
      setToast('请先输入一个品类关键词');
      return;
    }
    if (!modeAvailable(researchMode)) {
      if (researchMode === 'real' && modeAvailable('hybrid')) {
        setResearchMode('hybrid');
        setToast(`真实模式缺少${modeBlockReason('real')}，已自动切换为公开数据 + 明示回退`);
      } else {
        setToast(`${reportModeLabels[researchMode]}暂不可用：${modeBlockReason(researchMode)}。请切换为场景化 Mock 或公开数据模式`);
      }
      return;
    }
    if (running) return;
    setReviewStatus('pending');
    setReviewStatuses({});
    setAgentStep(0);
    setRunning(true);
    try {
      const payload = await foresightClient.createResearch({
        category: query,
        market,
        workspace_id: workspaceId,
        mode: researchMode,
        languages: ['pt', 'en', 'es'],
        planned_investment: plannedInvestment ? Number(plannedInvestment) : null,
        investment_stage: investmentStage || null,
      });
      setRuntimeState('connected');
      setRuntimeMessage(`任务 ${payload.task_id.slice(0, 8)} 已进入协作黑板`);
      // Cancel/resume act on the task that is actually running, not on whatever
      // report was loaded before this one.
      setCurrentTaskId(payload.task_id);
      setTaskRecoverable(false);
      connectRuntimeEvents(payload.task_id);
    } catch (error) {
      if (researchMode === 'mock') {
        runLocalFallback();
        return;
      }
      setRunning(false);
      setRuntimeMessage(`${researchMode === 'real' ? '真实' : '混合'}任务未启动，未静默降级`);
      setToast(error?.payload?.detail || error?.message || '当前模式不可用，请检查数据缓存、Qwen 或后端连接');
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

  const exportSellerSpriteResearchPack = () => {
    const task = buildSellerSpriteTask({
      category: reportCategory,
      market: selectedReportMarket,
      generatedAt: reportGeneratedAt,
      mode: reportMode,
      cards: decisionCards,
      evidence: reportEvidence,
      contract: decisionContract,
    });
    downloadSellerSpriteTask(task);
    setToast('已请求下载研究包；该 JSON 供留档使用');
  };

  const calculateEconomics = async () => {
    setEconomicsLoading(true);
    try {
      const payload = Object.fromEntries(Object.entries(economicsRef.current).map(([key, value]) => [key, Number(value || 0)]));
      setEconomicsResult(await foresightClient.calculateEconomics(payload));
      setToast('首单单位经济模型已更新');
    } catch (error) {
      setToast(error.message || '成本计算失败，请检查输入');
    } finally {
      setEconomicsLoading(false);
    }
  };

  const exportSellerSpriteAsins = () => {
    const task = buildSellerSpriteTask({
      category: reportCategory,
      market: selectedReportMarket,
      generatedAt: reportGeneratedAt,
      mode: reportMode,
      cards: decisionCards,
      evidence: reportEvidence,
      contract: decisionContract,
    });
    if (!task.asin_list.length) {
      setToast('当前报告没有真实 Amazon ASIN，不能生成卖家精灵产品库清单');
      return;
    }
    downloadSellerSpriteAsins(task);
    setToast(`已请求下载 ${task.asin_list.length} 个 ASIN 清单；请在卖家精灵中继续查询和添加`);
  };

  const copySellerSpriteResearchInput = () => {
    const marketplace = selectedReportMarket?.code || reportMarket;
    const supported = ['US', 'JP', 'UK', 'DE', 'FR', 'IT', 'ES', 'CA', 'IN', 'MX'].includes(marketplace);
    if (!supported) {
      setToast('当前市场不在已适配的 SellerSprite API 站点列表，请生成美国站报告后再使用');
      return;
    }
    const text = [
      'SellerSprite Product Research',
      `Marketplace: ${marketplace}`,
      `Keyword: ${reportCategory}`,
      '',
      'Workflow: 在卖家精灵「选产品」中使用关键词查询；若已有 ASIN，请通过插件「加入产品库」。',
    ].join('\n');
    copyText(text, supported ? '卖家精灵研究条件已复制，可到「选产品」继续查询' : '研究条件已复制；当前市场不在卖家精灵支持列表');
  };

  const openSellerSpriteDocs = (url) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const copySellerSpriteApiTemplate = () => {
    const text = [
      "curl --location --request POST 'https://api.sellersprite.com/v1/product/research' \\",
      "  --header 'secret-key: YOUR_SELLERSPRITE_KEY' \\",
      "  --header 'Content-Type: application/json' \\",
      `  --data-raw '{\"marketplace\":\"${reportMarket || 'US'}\",\"keyword\":\"${reportCategory}\",\"page\":1,\"size\":50}'`,
    ].join('\n');
    copyText(text, 'API 请求模板已复制；密钥只在服务端配置');
  };

  const copySellerSpriteCliTemplate = () => {
    const text = [
      'python -m pip install sellersprite-cli',
      'sellersprite config --key YOUR_SELLERSPRITE_KEY --project',
      `sellersprite product search --marketplace ${reportMarket || 'US'} --keyword "${reportCategory}" --size 50`,
    ].join('\n');
    copyText(text, 'SellerSprite CLI 命令已复制');
  };

  const copySellerSpriteMcpConfig = () => {
    const config = {
      mcpServers: {
        'sellersprite-mcp': {
          type: 'streamableHttp',
          url: 'https://mcp.sellersprite.com/mcp',
          headers: { 'secret-key': 'YOUR_SELLERSPRITE_KEY' },
        },
      },
    };
    const backendEnv = [
      '# 先机罗盘后端 .env（本系统实际调用官方 MCP）',
      'SELLERSPRITE_SECRET_KEY=YOUR_SELLERSPRITE_KEY',
      'SELLERSPRITE_TRANSPORT=mcp',
      'SELLERSPRITE_MCP_FALLBACK_REST=true',
    ].join('\n');
    copyText(`${backendEnv}\n\n# 外部 MCP 客户端（可选）\n${JSON.stringify(config, null, 2)}`, '后端 MCP 配置已复制；替换密钥并重启后端');
  };

  const copySellerSpriteAgentPrompt = () => {
    const text = `请调用 sellersprite-mcp，分析 ${reportMarket || 'US'} 站点「${reportCategory}」：筛选近 30 天有增长、评分 4.0 以上的潜力 ASIN，返回价格、月销量、BSR、评分和主要评论痛点，并标注每个字段的来源工具。`;
    copyText(text, 'Agent 任务提示词已复制');
  };

  const shareReport = () => {
    const url = currentTaskId
      ? `${window.location.origin}${window.location.pathname}?task=${encodeURIComponent(currentTaskId)}`
      : window.location.href;
    copyText(url, '可恢复报告链接已复制');
  };

  const acknowledgeContract = async () => {
    if (!currentTaskId || !decisionContract) return;
    try {
      const contract = await foresightClient.acknowledgeContract(currentTaskId, { operator: 'demo-user' });
      setDecisionContract(contract);
      setToast('系统判定已确认并写入审计记录');
      loadHistory();
    } catch (error) {
      setToast(error.message || '确认失败');
    }
  };

  const updateExecutionTask = async (executionTaskId, status) => {
    if (!currentTaskId) return;
    try {
      const contract = await foresightClient.updateExecutionTask(currentTaskId, executionTaskId, { status });
      setDecisionContract(contract);
      setToast('执行任务状态已保存');
    } catch (error) {
      setToast(error.message || '执行任务更新失败');
    }
  };

  const saveAdminToken = (event) => {
    event.preventDefault();
    const saved = foresightClient.setAdminToken(adminToken);
    setAdminToken(saved);
    setToast(saved ? '管理令牌已保存，写操作已授权' : '管理令牌已清除');
  };

  const setReview = async (status, targetCardId = null) => {
    const runtimeCardId = targetCardId || selectedCard?.runtimeCard?.card_id || decisionCards[0]?.runtimeCard?.card_id;
    setReviewStatus(status);
    if (runtimeCardId) setReviewStatuses((current) => ({ ...current, [runtimeCardId]: status }));
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

  const evaluateSkill = async (skillId, skillName) => {
    const label = skillName || skillId;
    setSkillsLoading(true);
    try {
      const payload = await foresightClient.evaluateSkill(skillId);
      await loadSkills();
      setToast(payload.decision === 'ready'
        ? `${label} 已通过 Validation / Holdout 门禁`
        : `${label} 未通过门禁，状态已置为 ${payload.decision}`);
    } catch (error) {
      setToast(error.message || '只有 candidate 状态可以被评测');
    } finally {
      setSkillsLoading(false);
    }
  };

  const promoteSkill = async (skillId, skillName) => {
    const label = skillName || skillId;
    setSkillsLoading(true);
    try {
      const supersedesActive = (skills?.active_skills || []).some((item) => item.name === label);
      await foresightClient.promoteSkill(skillId);
      await loadSkills();
      setToast(supersedesActive
        ? `${label} 已激活，旧版本已退役，可随时回滚`
        : `${label} 已激活，后续任务将检索到该 Skill`);
    } catch (error) {
      setToast(error.message || 'Skill 尚未通过评测门禁');
    } finally {
      setSkillsLoading(false);
    }
  };

  const rollbackSkill = async (name) => {
    setSkillsLoading(true);
    try {
      await foresightClient.rollbackSkill(name);
      await loadSkills();
      setToast(`${name} 已回滚至上一可用版本`);
    } catch (error) {
      setToast(error.message || `${name} 没有可回滚的历史版本`);
    } finally {
      setSkillsLoading(false);
    }
  };

  // The only route that returns a skill's description / evidence_policy / body —
  // there is no per-skill detail endpoint, so the "why did this hit" panel reuses
  // the same retrieval the research run performs, with the current report scope.
  const loadRetrievedSkills = async () => {
    setSkillsLoading(true);
    try {
      setRetrievedSkills(await foresightClient.retrieveSkills(reportCategory, reportMarket));
      setRetrievedFor(`${reportMarket} · ${reportCategory}`);
    } catch (error) {
      setRetrievedSkills(null);
      setToast(error.message || '技能检索不可用');
    } finally {
      setSkillsLoading(false);
    }
  };

  const handleNav = (id) => {
    setActiveNav(id);
    setMobileNav(false);
    if (id === 'history') { setHistoryOpen(true); loadHistory(); }
    if (id === 'settings') { setActiveNav('sources'); setToast('运行设置已合并到数据源登记册'); }
    if (id === 'workspace' || id === 'sources') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    // 这三个板块和决策契约一起渲染，未生成报告时不在 DOM 中
    const targetId = navSectionIds[id];
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    setToast('该板块随决策契约一起生成，请先运行一次研究任务');
    document.getElementById('research-entry')?.scrollIntoView({ behavior: 'smooth' });
  };

  const openFailures = evolution?.failure_cases?.filter((item) => item.status === 'open') || [];
  // `candidates` is the union of candidate and ready rows (skills.py status()),
  // so the badge has to read each row's own status rather than the array name.
  const readySkillCount = skills?.candidates?.filter((item) => item.status === 'ready').length || 0;
  // Rollback needs two versions of the same name; the backend reports exactly
  // which names qualify so the button is disabled instead of always 409ing.
  const rollbackableNames = useMemo(
    () => new Set(skills?.rollbackable_names || []),
    [skills],
  );
  const reviewTargetCardId = selectedCard?.runtimeCard?.card_id || decisionCards[0]?.runtimeCard?.card_id;
  const activeReviewStatus = reviewStatuses[reviewTargetCardId] || reviewStatus;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>
        <div className="brand" aria-label="先机罗盘决策工作台">
          <div className="brand-mark" aria-hidden="true"><span>01</span><i /></div>
          <div className="brand-copy"><strong>先机</strong><em>罗盘</em><span>FIELD LOG / DECISION DESK</span></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="关闭导航"><X size={18} /></button>
        </div>
        <nav className="nav-list" aria-label="主导航">
          <button className={activeNav === 'workspace' ? 'active' : ''} onClick={() => handleNav('workspace')}><LayoutDashboard size={18} />首单决策台</button>
          <button className={activeNav === 'radar' ? 'active' : ''} onClick={() => handleNav('radar')}><Target size={18} />痛点雷达</button>
          <button className={activeNav === 'alerts' ? 'active' : ''} onClick={() => handleNav('alerts')}><Bell size={18} />失效条件{failureConditionCount > 0 && <span className="nav-badge">{failureConditionCount}</span>}</button>
          <button className={activeNav === 'history' ? 'active' : ''} onClick={() => handleNav('history')}><History size={18} />决策记录</button>
          <button className={activeNav === 'evolution' ? 'active' : ''} onClick={() => handleNav('evolution')}><Activity size={18} />演进中心{openFailures.length > 0 && <span className="nav-badge">{openFailures.length}</span>}</button>
          <button className={activeNav === 'skills' ? 'active' : ''} onClick={() => handleNav('skills')}><Boxes size={18} />技能库{readySkillCount > 0 && <span className="nav-badge">{readySkillCount}</span>}</button>
          <button className={activeNav === 'sources' ? 'active' : ''} onClick={() => handleNav('sources')}><Database size={18} />数据源</button>
        </nav>

        <div className="sidebar-section-label">工作空间</div>
        <label className="workspace-switcher" title="切换工作空间">
          <span className="workspace-avatar">{workspaceId === 'default' ? 'D' : 'P'}</span>
          <span><strong>{workspaceId === 'default' ? 'Demo 空间' : 'Pilot 空间'}</strong><small>{reportModeLabels[researchMode]}</small></span>
          <select aria-label="工作空间" value={workspaceId} onChange={(event) => changeWorkspace(event.target.value)}>
            <option value="default">Demo 空间</option>
            <option value="pilot">Pilot 空间</option>
          </select>
          <ChevronDown size={16} />
        </label>
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
            {mutationProtection === 'token' && (
              <form className="admin-token" onSubmit={saveAdminToken}>
                <input
                  type="password"
                  value={adminToken}
                  onChange={(event) => setAdminToken(event.target.value)}
                  placeholder="X-Admin-Token"
                  aria-label="管理令牌"
                  autoComplete="off"
                />
                <button type="submit">授权</button>
              </form>
            )}
            <span className={`data-status ${runtimeState}`}><i />{runtimeMessage}</span>
            <button className="icon-button" onClick={() => { setHistoryOpen(true); loadHistory(); }} aria-label="查看历史"><History size={18} /></button>
            <button className="avatar-button" title="当前用户">方</button>
          </div>
        </header>

        <div className="page-wrap">
          {activeNav === 'sources' && (
            <section className="source-catalog-panel" id="source-catalog" aria-labelledby="source-catalog-title">
              <div className="source-catalog-header">
                <div><span className="eyebrow">DATA REGISTRY · 01</span><h1 id="source-catalog-title">数据源登记册</h1><p>这里列出决策工作台实际读取的本地数据集与分析引擎。每个来源都标明用途、覆盖范围和当前可用状态。</p></div>
                <div className="source-registry-actions"><span className={`source-registry-status ${runtimeState}`}><i />{runtimeState === 'connected' ? '运行时已同步' : '等待运行时'}</span><button className="secondary-button" onClick={refreshSourceStatus}>刷新连接状态</button></div>
              </div>
              <section className="seller-connect-panel" aria-labelledby="seller-connect-title">
                <div className="seller-connect-header">
                  <div><span className="eyebrow">SELLERSPRITE CONNECT · 04 WAYS</span><h2 id="seller-connect-title">卖家精灵连接中心</h2><p>同一个 SellerSprite 能力层，按团队的工作方式接入。真实数据回到先机罗盘后，才会进入价格、竞品和评论证据链。</p></div>
                  <div className={`seller-connect-status ${dataStatus?.sellersprite_mcp || dataStatus?.sellersprite_live ? 'ready' : 'pending'}`}><i />{dataStatus?.sellersprite_mcp ? 'MCP 已启用' : dataStatus?.sellersprite_live ? 'API 已连接' : '等待 secret-key'}</div>
                </div>
                <div className="seller-connect-grid">
                  <article className="seller-connect-card api">
                    <div className="seller-connect-icon"><Database size={22} /></div><span className="seller-connect-kicker">01 · SERVER</span><h3>API</h3><p>标准 HTTP 接口，直接把选品、竞品和评论结果送入后端证据链。</p><code>POST /v1/product/research</code><button className="seller-connect-action" onClick={copySellerSpriteApiTemplate}>复制 API 请求模板</button><button className="seller-connect-link" onClick={() => openSellerSpriteDocs('https://open.sellersprite.com/api/2')}>查看 API 文档 <ExternalLink size={13} /></button>
                  </article>
                  <article className="seller-connect-card cli">
                    <div className="seller-connect-icon"><PanelTop size={22} /></div><span className="seller-connect-kicker">02 · LOCAL TOOL</span><h3>CLI</h3><p>本地批量查询和脚本化复用，适合运营、数据和研发一起跑同一套条件。</p><code>pip install sellersprite-cli</code><button className="seller-connect-action" onClick={copySellerSpriteCliTemplate}>复制 CLI 命令</button><button className="seller-connect-link" onClick={() => openSellerSpriteDocs('https://github.com/opensellersprite/sellersprite-cli')}>查看 CLI 文档 <ExternalLink size={13} /></button>
                  </article>
                  <article className="seller-connect-card mcp">
                    <div className="seller-connect-icon"><MessageCircleMore size={22} /></div><span className="seller-connect-kicker">03 · AI PROTOCOL</span><h3>MCP</h3><p>把官方 MCP 注册为 Agent Runtime 工具；连接后由 Agent 调用 45 个 SellerSprite 工具并回写证据。</p><code>SELLERSPRITE_TRANSPORT=mcp</code><button className="seller-connect-action" onClick={copySellerSpriteMcpConfig}>复制后端 MCP 配置</button><button className="seller-connect-link" onClick={() => openSellerSpriteDocs('https://open.sellersprite.com/mcp')}>查看 MCP 配置指南 <ExternalLink size={13} /></button>
                  </article>
                  <article className="seller-connect-card agent">
                    <div className="seller-connect-icon"><Sparkles size={22} /></div><span className="seller-connect-kicker">04 · WORKFLOW</span><h3>Agent</h3><p>把研究目标交给 Agent，自动组合选品、市场、竞品、关键词与评论工具。</p><code>product_research → review</code><button className="seller-connect-action" onClick={copySellerSpriteAgentPrompt}>复制 Agent 任务</button><button className="seller-connect-link" onClick={() => openSellerSpriteDocs('https://open.sellersprite.com/mcp')}>查看 Agent 场景 <ExternalLink size={13} /></button>
                  </article>
                </div>
                <div className="seller-connect-note"><ShieldCheck size={15} />密钥只进后端环境变量 <code>SELLERSPRITE_SECRET_KEY</code>；前端只生成模板和任务，不读取或保存密钥。</div>
              </section>
              <div className="source-catalog-list">
                {[
                  { key: 'amazon_reviews', ageKey: 'reviews', name: 'Amazon Reviews 2023 · review sample', label: '评论样本', use: '提取评分、痛点、购买意向与负面主题', scope: '宠物用品等品类 · 多市场静态快照' },
                  { key: 'amazon_metadata', name: 'Amazon Reviews 2023 · product metadata', label: '商品元数据', use: '读取商品价格、类目、评分和竞品基线', scope: '当前宠物自动喂食器场景' },
                  { key: 'trade', name: 'UN Comtrade local cache', label: '海关贸易', use: '估算进口规模、贸易流向与结构性需求', scope: '目标市场年度进口数据' },
                  { key: 'fx', name: 'ECB reference rates via Frankfurter', label: '汇率快照', use: '统一成本、价格和投入预算的币种口径', scope: 'BRL / USD / EUR 等市场货币' },
                  { key: 'gscpi', name: 'Federal Reserve Bank of New York · GSCPI', label: '供应链压力', use: '判断物流与供应链压力对首单的影响', scope: '全球月度公开指数' },
                  { key: 'lsci', name: 'World Bank / UNCTAD · LSCI', label: '航运连接度', use: '补充目标市场运输可达性判断', scope: '目标市场年度结构指标' },
                  { key: 'olist', name: 'Olist public dataset', label: '巴西电商样本', use: '补充巴西电商履约、评价与订单结构', scope: '巴西公开历史快照' },
                  { key: 'mercado_livre', name: 'Mercado Livre · current listings', label: '当前竞品', use: '读取巴西在售商品、价格和 listing 结构', scope: '需配置应用授权；失败时回退历史价格' },
                  { key: 'sellersprite', name: '卖家精灵 · API / MCP', label: '亚马逊研究', use: '由 Agent 调用站点竞品价格、BSR、销量和评分工具', scope: '需配置 secret-key 与 MCP 传输；按站点启用' },
                  { key: 'repro', name: 'RePro · Brazilian Portuguese reviews', label: '葡语校准', use: '校准本地化评论痛点与卖家话术，不作为商业证据', scope: '10,000 条 · CC BY-NC-SA 4.0' },
                  { key: 'google_trends', name: 'Google Trends API · Alpha', label: '搜索趋势', use: '接入关键词需求趋势和地区热度', scope: '需申请 Alpha 访问权限' },
                  { key: 'qwen', name: 'QwenReviewExtractor', label: '分析引擎', use: '对评论文本做主题、情绪和证据字段抽取', scope: '只在真实模式启用，不等同于数据集' },
                  { key: 'mock', name: 'Scenario Mock fixtures', label: '演示样例', use: '本地演示和联调，不代表真实市场观测', scope: '固定场景 · 禁止当作真实证据' },
                ].map((source) => {
                  const available = source.key === 'mock' || source.key === 'qwen' ? (source.key === 'mock' || Boolean(dataStatus?.[source.key])) : Boolean(dataStatus?.[source.key]);
                  const age = dataStatus?.cache_age_days?.[source.ageKey || source.key];
                  const stale = (dataStatus?.stale_caches || []).some((item) => item.startsWith(`${source.ageKey || source.key}:`));
                  const stateLabel = stale ? `过期 · ${age}d` : available ? age == null ? '可用' : `可用 · ${age}d` : source.key.endsWith('_live') ? '已配置待验证' : '未接入';
                  return <article className="source-catalog-row" key={source.key}><div className="source-catalog-mark">{source.key === 'mock' ? 'M' : source.key === 'qwen' ? 'AI' : 'DS'}</div><div className="source-catalog-main"><div className="source-catalog-name"><strong>{source.name}</strong><span>{source.label}</span></div><p>{source.use}</p><small>{source.scope}</small></div><div className={`source-catalog-state ${available && !stale ? 'available' : 'missing'}`}><i />{stateLabel}</div></article>;
                })}
              </div>
            </section>
          )}
          <section className="query-workbench" id="research-entry">
            <div className="section-heading-row">
              <div>
                <span className="eyebrow">首单投资决策台</span>
                <h1>先把钱停在证据前面</h1>
                <p>首单之前，先回答一个不舒服但重要的问题：这笔投入，凭什么现在发生？</p>
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
            {(running || taskRecoverable) && currentTaskId && (
              <div className="task-control-row">
                {running && runtimeState === 'connected' && (
                  <button className="secondary-button" onClick={cancelCurrentTask} disabled={taskControlBusy || (mutationProtection === 'token' && !adminToken)} title="在最近一个节点边界停下，已保存的检查点可用于恢复">
                    <XCircle size={15} />中断任务
                  </button>
                )}
                {taskRecoverable && (
                  <button className="secondary-button" onClick={resumeCurrentTask} disabled={taskControlBusy || (mutationProtection === 'token' && !adminToken)}>
                    <RefreshCw className={taskControlBusy ? 'spin' : ''} size={15} />从检查点恢复
                  </button>
                )}
                <span className="task-control-note">
                  {mutationProtection === 'token' && !adminToken
                    ? '取消与恢复是受保护的写操作，请先在右上角填入管理令牌'
                    : taskRecoverable
                      ? '任务已停在可恢复位置，检查点会带回已完成的 Agent 产物'
                      : '取消不会丢进度，已完成的 Agent 产物会写进检查点'}
                </span>
              </div>
            )}
            <div className="query-options">
              <div className="quick-tags"><span>快速开始</span>{['宠物喂食器', '便携榨汁机', '降噪耳机'].map((tag) => <button key={tag} onClick={() => setQuery(tag)}>{tag}</button>)}</div>
              <div className="market-picker"><span>目标市场</span>{markets.map((item) => <button key={item.code} className={market === item.code ? 'active' : ''} onClick={() => setMarket(item.code)}><b>{item.code}</b>{item.name}</button>)}</div>
              <div className="market-picker data-mode-picker"><span>数据模式</span>{['real', 'hybrid', 'mock'].map((item) => <button key={item} disabled={!modeAvailable(item)} className={researchMode === item ? 'active' : ''} onClick={() => setResearchMode(item)}>{reportModeLabels[item]}</button>)}</div>
              <div className="market-picker investment-picker"><span>决策阶段</span>{['打样', '首批小单', '首批备货', '广告测试'].map((stage) => <button key={stage} className={investmentStage === stage ? 'active' : ''} onClick={() => setInvestmentStage(stage)}>{stage}</button>)}</div>
              <div className="market-picker investment-picker"><span>计划投入（¥）</span><input type="number" value={plannedInvestment} onChange={(e) => setPlannedInvestment(e.target.value)} placeholder="30000" style={{ width: 120, padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d5dd', fontSize: 14 }} /></div>
            </div>
            <details className="economics-editor">
              <summary><CircleDollarSign size={15} />补齐首单单位经济（建议）<span>商品成本、物流、平台费和退货损耗会改变 Go / Validate / Stop</span></summary>
              <div className="economics-grid">
                {[
                  ['selling_price', '目标售价'], ['product_cost', '产品成本'], ['packaging_cost', '包装'],
                  ['domestic_shipping', '国内段'], ['international_shipping', '国际段'], ['ad_cost_per_order', '单笔广告'],
                  ['duty_rate_pct', '关税 %'], ['vat_rate_pct', 'VAT/GST %'], ['platform_fee_rate_pct', '平台费 %'],
                  ['payment_fee_rate_pct', '支付费 %'], ['return_rate_pct', '退货率 %'], ['target_margin_pct', '目标毛利 %'],
                ].map(([key, label]) => <label key={key}>{label}<input type="number" min="0" step="0.1" defaultValue={economicsDefaults[key]} onChange={(event) => { economicsRef.current[key] = event.target.value; }} /></label>)}
              </div>
              <div className="economics-actions"><small>请保证所有金额使用同一币种；当前仅作首单测算，不替代税务/合规意见。</small><button className="secondary-button" onClick={calculateEconomics} disabled={economicsLoading}>{economicsLoading ? '计算中…' : '计算单位经济'}</button></div>
              {economicsResult && <div className="economics-result"><div><span>落地成本</span><strong>{economicsResult.landed_cost}</strong></div><div><span>贡献利润</span><strong className={economicsResult.contribution_profit >= 0 ? 'positive' : 'negative'}>{economicsResult.contribution_profit}</strong></div><div><span>贡献毛利</span><strong>{economicsResult.contribution_margin_pct}%</strong></div><div><span>盈亏平衡售价</span><strong>{economicsResult.break_even_price}</strong></div><div><span>目标毛利允许 CPC</span><strong>{economicsResult.max_cpc_at_target_margin}</strong></div></div>}
            </details>
            <div className={`capability-note ${currentCapability?.real_available ? 'ready' : 'limited'}`}>
              <Database size={14} />
              <span>{capabilityText}</span>
              {(!currentCapability?.real_available && currentCapability?.blocking_reasons?.length > 0) && (
                <span className="capability-gaps">← 缺少：{currentCapability.blocking_reasons.map((r) => r.startsWith('runtime:') ? r.slice(8) : r).join('、')}</span>
              )}
              {currentCapability?.known_gaps?.length > 0 && (
                <span className="capability-gaps">⚡ 已知缺口：{capabilitySignals(currentCapability.known_gaps)}</span>
              )}
            </div>
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
              <button className="secondary-button seller-task-button" onClick={copySellerSpriteResearchInput} title="卖家精灵网页端按关键词或 ASIN 工作，不直接导入本系统 JSON"><Copy size={16} />复制卖家精灵研究条件</button>
              <button className="secondary-button" onClick={exportSellerSpriteAsins} title="只有真实 SellerSprite ASIN 才会生成清单；Mock 报告不会伪造 ASIN"><Download size={16} />导出 ASIN 清单</button>
              <button className="secondary-button" onClick={exportSellerSpriteResearchPack} title="导出给内部 API 或工作流使用的 JSON 研究包"><Download size={16} />导出研究包 JSON</button>
              <button className="secondary-button" onClick={() => window.print()}><Printer size={16} />打印/PDF</button>
              <button className="secondary-button" onClick={exportReport}><Download size={16} />JSON</button>
              <button className="secondary-button" onClick={shareReport}><ExternalLink size={16} />分享</button>
            </div>
          </section>

          <section className="monitoring-bar">
            <div><span className="monitoring-icon"><RadioTower size={17} /></span><p><strong>市场监控快照</strong><small>{monitoring ? `最近读取 ${formatReportTime(monitoring.generated_at)} · 手动刷新` : '等待读取公开数据快照'}</small></p></div>
            <div className="monitoring-summary"><span>当前触发</span><strong>{monitoring?.trigger_count ?? '—'}</strong><small>项阈值</small></div>
            <div className="monitoring-summary"><span>覆盖信号</span><strong>{monitoring?.signals?.length ?? '—'}</strong><small>项</small></div>
            <div className="monitoring-actions"><button className="secondary-button" onClick={toggleMonitoringSubscription}>{monitorSubscriptions.some((item) => item.category === reportCategory && item.market === reportMarket) ? '已登记 · 取消' : '登记每周快照'}</button><button className="secondary-button" onClick={() => loadMonitoring(reportCategory, reportMarket)} disabled={monitoringLoading}>{monitoringLoading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}手动刷新</button></div>
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
                        <> → 本次实验预算上限 <strong style={{ color: '#d97706' }}>¥{decisionContract.allowed_investment.toLocaleString()}</strong></>
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
              {decisionContract.execution_tasks?.length > 0 && (
                <div className="execution-task-list"><div className="execution-task-title"><strong>下一步执行清单</strong><small>把判断变成可追踪动作</small></div>{decisionContract.execution_tasks.map((task) => <div className={`execution-task ${task.status}`} key={task.task_id}><select value={task.status} onChange={(event) => updateExecutionTask(task.task_id, event.target.value)}><option value="todo">待执行</option><option value="in_progress">进行中</option><option value="done">已完成</option><option value="blocked">已阻塞</option></select><span>{task.title}</span><small>{task.status === 'done' ? '已完成' : task.status === 'in_progress' ? '进行中' : task.status === 'blocked' ? '已阻塞' : '待执行'}</small></div>)}
                  <div className="execution-task-add" style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <input type="text" placeholder="新增执行任务…" id="new-task-input" style={{ flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d5dd', fontSize: 13 }} onKeyDown={async (event) => {
                      if (event.key !== 'Enter') return;
                      const title = event.target.value.trim();
                      if (!title) return;
                      try {
                        const contract = await foresightClient.createExecutionTask(currentTaskId, { title, status: 'todo' });
                        setDecisionContract(contract);
                        event.target.value = '';
                        setToast('已添加执行任务');
                      } catch (error) { setToast(error.message || '添加失败'); }
                    }} />
                    <button className="secondary-button" style={{ fontSize: 13, whiteSpace: 'nowrap' }} onClick={async () => {
                      const input = document.getElementById('new-task-input');
                      const title = (input?.value || '').trim();
                      if (!title) return;
                      try {
                        const contract = await foresightClient.createExecutionTask(currentTaskId, { title, status: 'todo' });
                        setDecisionContract(contract);
                        input.value = '';
                        setToast('已添加执行任务');
                      } catch (error) { setToast(error.message || '添加失败'); }
                    }}>+ 添加</button>
                  </div>
                </div>
              )}
              {decisionContract.human_override && decisionContract.system_verdict && (
                <div style={{ marginTop: 12, padding: '8px 12px', background: '#fef3c7', borderRadius: 6, fontSize: 13, color: '#92400e', display: 'flex', alignItems: 'center', gap: 7 }}>
                  <AlertTriangle size={15} />
                  <span>人工覆盖：系统判定={decisionContract.system_verdict}，已由人工覆盖为 {decisionContract.human_override}</span>
                </div>
              )}
              {decisionContract.verdict === 'STOP' && !decisionContract.human_override && currentTaskId && (
                <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>是否接受系统判定？</span>
                  <button className="secondary-button" style={{ fontSize: 13 }} onClick={acknowledgeContract} disabled={Boolean(decisionContract.acknowledged_at)}>{decisionContract.acknowledged_at ? 'STOP 已确认' : '接受 STOP'}</button>
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

          {(decisionContract?.verdict === 'GO' || decisionContract?.verdict === 'STOP') && currentTaskId && (
            <section className="outcome-feedback" style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, padding: 20, marginBottom: 24 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>闭环反馈 · 校准系统预测</h3>
              <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 12px' }}>系统判定为 <strong>{decisionContract.verdict}</strong>。实际执行后，结果如何？这决定了后续策略的准确性。</p>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <button className="secondary-button" style={{ borderColor: '#10b981', color: '#059669' }} onClick={async () => {
                  try {
                    await foresightClient.recordActualOutcome(currentTaskId, { verdict_was_correct: true, operator: 'demo-user' });
                    setToast('已记录：系统判定正确。此反馈将用于校准后续策略');
                  } catch (error) { setToast(error.message || '记录失败'); }
                }}><CheckCircle2 size={15} />判定正确</button>
                <button className="secondary-button" style={{ borderColor: '#ef4444', color: '#dc2626' }} onClick={async () => {
                  const notes = window.prompt('为什么判定错了？简短说明将帮助系统改进：');
                  if (notes === null) return;
                  try {
                    await foresightClient.recordActualOutcome(currentTaskId, { verdict_was_correct: false, notes, operator: 'demo-user' });
                    setToast('已记录：系统判定有误，反馈已写入校准数据库');
                  } catch (error) { setToast(error.message || '记录失败'); }
                }}><XCircle size={15} />判定有误</button>
              </div>
            </section>
          )}

          {decisionContract?.verdict === 'VALIDATE' && currentTaskId && (
            <section className="validation-form" style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 10, padding: 20, marginBottom: 24 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>提交验证结果 · 首单晋级闸门</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
                <label style={{ fontSize: 13 }}>本次实际验证花费（¥）<input type="number" value={validationMetrics.actual_spend} onChange={(e) => setValidationMetrics({ ...validationMetrics, actual_spend: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>样本量 <small style={{ color: '#6b7280' }}>要求 ≥30</small><input type="number" value={validationMetrics.sample_count} onChange={(e) => setValidationMetrics({ ...validationMetrics, sample_count: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>购买意向率（%） <small style={{ color: '#6b7280' }}>要求 ≥12%</small><input type="number" step="1" value={validationMetrics.intent_rate} onChange={(e) => setValidationMetrics({ ...validationMetrics, intent_rate: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>CPC（¥） <small style={{ color: '#6b7280' }}>{decisionContract?.promotion_criteria?.max_cpc == null ? '可选 · 当前未设阈值' : `要求 ≤ ¥${decisionContract.promotion_criteria.max_cpc.toFixed(2)}`}</small><input type="number" step="0.1" min="0" value={validationMetrics.cpc} onChange={(e) => setValidationMetrics({ ...validationMetrics, cpc: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
                <label style={{ fontSize: 13 }}>痛点确认率（%） <small style={{ color: '#6b7280' }}>要求 ≥30%</small><input type="number" step="1" value={validationMetrics.pain_confirmation_rate} onChange={(e) => setValidationMetrics({ ...validationMetrics, pain_confirmation_rate: e.target.value })} style={{ display: 'block', width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4 }} /></label>
              </div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginTop: 12 }}>
                <label style={{ fontSize: 13 }}>实验结论 <small style={{ color: '#6b7280' }}>影响 gray zone 判定</small>
                  <select value={validationMetrics.outcome} onChange={(e) => setValidationMetrics({ ...validationMetrics, outcome: e.target.value })} style={{ display: 'block', padding: '6px 8px', borderRadius: 6, border: '1px solid #d0d5dd', marginTop: 4, minWidth: 130 }}>
                    <option value="inconclusive">不确定</option>
                    <option value="positive">正面</option>
                    <option value="negative">负面</option>
                  </select>
                </label>
                {economicsResult && <span style={{ fontSize: 12, color: '#6b7280' }}>单位经济数据将随验证结果一同提交</span>}
              </div>
              <button className="primary-button" disabled={validationSubmitting} onClick={async () => {
                if (!validationMetrics.sample_count || !validationMetrics.intent_rate || !validationMetrics.pain_confirmation_rate) {
                  setToast('请填写样本量、购买意向率和痛点确认率');
                  return;
                }
                if (Number(validationMetrics.actual_spend) < 0 || Number(validationMetrics.sample_count) < 0 || Number(validationMetrics.intent_rate) < 0 || Number(validationMetrics.intent_rate) > 100 || Number(validationMetrics.cpc) < 0 || Number(validationMetrics.pain_confirmation_rate) < 0 || Number(validationMetrics.pain_confirmation_rate) > 100) {
                  setToast('请检查验证指标范围：比例应为 0–100，CPC、花费和样本量不能为负');
                  return;
                }
                setValidationSubmitting(true);
                try {
                  const metrics = {};
                  if (validationMetrics.sample_count) metrics.sample_count = Number(validationMetrics.sample_count);
                  if (validationMetrics.intent_rate) metrics.intent_rate = Number(validationMetrics.intent_rate) / 100;
                  if (validationMetrics.cpc) metrics.cpc = Number(validationMetrics.cpc);
                  if (validationMetrics.pain_confirmation_rate) metrics.pain_confirmation_rate = Number(validationMetrics.pain_confirmation_rate) / 100;
                  const body = {
                    actual_spend: Number(validationMetrics.actual_spend) || 0,
                    metrics,
                    outcome: validationMetrics.outcome || 'inconclusive',
                  };
                  if (economicsResult) {
                    body.economics = Object.fromEntries(
                      Object.entries(economicsRef.current).map(([k, v]) => [k, Number(v || 0)])
                    );
                  }
                  const contract = await foresightClient.submitValidationResult(currentTaskId, body);
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
            <div><span className="metric-icon violet"><Clock3 size={18} /></span><p>决策有效期<small>建议复核周期</small></p><strong>{remainingValidityDays(decisionCards)}<em>天</em></strong></div>
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
              <button className={activeReviewStatus === 'approved' ? 'approved active' : 'approved'} onClick={() => setReview('approved', reviewTargetCardId)}><CheckCircle2 size={16} />采纳</button>
              <button className={activeReviewStatus === 'discussed' ? 'discussed active' : 'discussed'} onClick={() => setReview('discussed', reviewTargetCardId)}><MessageCircleMore size={16} />待议</button>
              <button className={activeReviewStatus === 'rejected' ? 'rejected active' : 'rejected'} onClick={() => setReview('rejected', reviewTargetCardId)}><XCircle size={16} />驳回</button>
            </div>
          </section>

          <EvolutionPanel
            evolution={evolution}
            evolutionLoading={evolutionLoading}
            calibration={calibration}
            onLoadEvolution={loadEvolution}
            onCreateCandidate={createEvolutionCandidate}
            onActivatePolicy={activateEvolutionPolicy}
            onRollbackPolicy={rollbackEvolutionPolicy}
            onRelaxPolicy={async () => {
              setEvolutionLoading(true);
              try {
                const payload = await foresightClient.relaxEvolutionPolicy();
                await loadEvolution();
                setToast(`${payload.candidate_version} 放松候选已通过评测门禁，可激活以降低门槛`);
              } catch (error) {
                setToast(error.message || '当前策略已是基线版本，无法进一步放松');
              } finally {
                setEvolutionLoading(false);
              }
            }}
          />

          <SkillBankPanel
            skills={skills}
            skillsLoading={skillsLoading}
            retrievedSkills={retrievedSkills}
            retrievedFor={retrievedFor}
            rollbackableNames={rollbackableNames}
            onLoadSkills={loadSkills}
            onEvaluate={evaluateSkill}
            onPromote={promoteSkill}
            onRollback={rollbackSkill}
            onRetrieveSkills={loadRetrievedSkills}
          />

          <footer><span><Compass size={15} />先机罗盘 · 决策可追溯，结论可证伪</span><span>数据模式：{reportModeLabels[reportMode] || reportMode}{reportMode === 'real' ? ' · 当前竞品价仍需授权源' : ''}</span></footer>
            </>
          )}
        </div>
      </main>

      {selectedCard && <CardDetailModal card={selectedCard} onClose={() => setSelectedCard(null)} onCopy={copyText} onReview={setReview} reviewStatus={reviewStatuses[selectedCard.runtimeCard?.card_id] || 'pending'} evidence={reportEvidence} reportMarket={reportMarket} generatedAt={reportGeneratedAt} reportMode={reportMode} />}

      {selectedEvidence && <EvidenceDetailModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}

      {historyOpen && <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setHistoryOpen(false)}><aside className="history-drawer"><div className="drawer-head"><div><span className="eyebrow">工作记录</span><h2>决策记录</h2></div><button className="icon-button" onClick={() => setHistoryOpen(false)}><X size={18} /></button></div>{historyLoading ? <div className="history-empty"><LoaderCircle className="spin" size={24} /><p>正在读取历史记录…</p></div> : historyItems.length ? historyItems.map((item) => { const result = item.result; const request = item.request || {}; const contract = result?.contract; return <button className="history-item" key={item.task_id} onClick={() => { setHistoryOpen(false); loadRuntimeResult(item.task_id).catch(() => setToast('这条报告无法载入')); }}><span className="history-icon"><FileText size={17} /></span><span><strong>{request.category || '未命名研究'}</strong><small>{request.market || '—'} · {formatReportTime(item.updated_at)}</small></span><b>{contract ? `${contract.verdict} · ${contract.evidence_coverage?.maturity || '—'}` : item.status}</b></button>; }) : <div className="history-empty"><History size={24} /><strong>暂无决策记录</strong><p>完成一次研究任务后，决策契约会出现在这里。</p></div>}</aside></div>}
      {toast && <div className="toast"><Check size={16} />{toast}</div>}
    </div>
  );
}

export default App;
