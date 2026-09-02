import {
  BadgeCheck,
  History,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

export function EvolutionPanel({
  evolution,
  evolutionLoading,
  onLoadEvolution,
  onCreateCandidate,
  onActivatePolicy,
  onRollbackPolicy,
}) {
  const activePolicy = evolution?.active_policy;
  const readyPolicy = evolution?.policy_versions?.find((item) => item.status === 'ready');
  const latestEvolutionRun = evolution?.evolution_runs?.[0];
  const openFailures = evolution?.failure_cases?.filter((item) => item.status === 'open') || [];
  const validationImprovement = latestEvolutionRun?.metrics?.validation_improvement || 0;

  return (
    <section className="evolution-panel" id="evolution-center">
      <div className="evolution-head">
        <div>
          <span className="eyebrow">Harness Evolution</span>
          <h2>策略演进中心</h2>
          <p>失败案例不会直接改写线上策略。当前指标来自合成规则回放，只证明门禁逻辑可复现，不代表商家经营结果。</p>
        </div>
        <div className="evolution-head-actions">
          <span className="policy-version"><ShieldCheck size={15} />当前 {activePolicy?.version || 'policy-v1'}</span>
          <button className="icon-button" onClick={onLoadEvolution} aria-label="刷新演进状态"><RefreshCw size={17} /></button>
        </div>
      </div>
      <div className="evolution-flow" aria-label="策略演进流程图">
        {['失败案例', '候选策略', 'Validation', 'Holdout', '人工激活'].map((step, index) => (
          <div key={step} className={index === 0 && openFailures.length ? 'active' : index > 0 && latestEvolutionRun ? 'done' : ''}>
            <span>{index + 1}</span><strong>{step}</strong>
          </div>
        ))}
      </div>
      <div className="evolution-metrics">
        <div>
          <span>待处理失败案例</span>
          <strong>{openFailures.length}</strong>
          <small>{openFailures[0]?.failure_type === 'weak_evidence' ? '证据门槛不足' : openFailures.length ? '等待候选生成' : '暂无开放案例'}</small>
        </div>
        <div>
          <span>候选版本</span>
          <strong>{readyPolicy?.version || latestEvolutionRun?.candidate_version || '—'}</strong>
          <small>{readyPolicy ? '评测通过，等待激活' : latestEvolutionRun?.candidate_version === activePolicy?.version ? '已激活为稳定版本' : '不会覆盖当前稳定版本'}</small>
        </div>
        <div>
          <span>Validation 门禁变化</span>
          <strong>{latestEvolutionRun ? `+${Math.round(validationImprovement * 100)}pp` : '—'}</strong>
          <small>{latestEvolutionRun ? `合成回放 n=${latestEvolutionRun.metrics.validation.candidate.cases} · 规则判断准确率 ${latestEvolutionRun.metrics.validation.candidate.accuracy * 100}%` : '基线与候选双回放'}</small>
        </div>
        <div>
          <span>Holdout 非回归</span>
          <strong>{latestEvolutionRun ? (latestEvolutionRun.decision === 'ready' ? '通过' : '拒绝') : '—'}</strong>
          <small>{latestEvolutionRun ? `合成回放 n=${latestEvolutionRun.metrics.holdout.candidate.cases} · 召回率 ${latestEvolutionRun.metrics.holdout.candidate.recall * 100}%` : '保护未参与生成的数据'}</small>
        </div>
      </div>
      <div className="evolution-actions">
        <p><BadgeCheck size={16} />合成门禁集：Validation n={evolution?.evaluation_dataset?.validation || 0}，Holdout n={evolution?.evaluation_dataset?.holdout || 0}；活动策略要求至少 {activePolicy?.policy?.minimum_evidence_count || 3} 条证据。</p>
        <div>
          <button className="secondary-button" onClick={onRollbackPolicy} disabled={evolutionLoading || !activePolicy?.parent_version}><History size={15} />回滚</button>
          {readyPolicy && <button className="secondary-button activate-policy" onClick={() => onActivatePolicy(readyPolicy.version)} disabled={evolutionLoading}><ShieldCheck size={15} />激活 {readyPolicy.version}</button>}
          <button className="primary-button compact" onClick={onCreateCandidate} disabled={evolutionLoading || openFailures.length === 0}>{evolutionLoading ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}生成候选并评测</button>
        </div>
      </div>
    </section>
  );
}
