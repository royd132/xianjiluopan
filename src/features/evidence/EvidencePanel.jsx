import {
  ArrowRight,
  Database,
  ExternalLink,
  ShieldCheck,
  X,
} from 'lucide-react';
import { scopeLabels, freshnessLabels } from '../research/researchConfig';
import { formatReportTime } from '../shared/utils';

export function EvidenceTable({ evidence, onSelectEvidence }) {
  return (
    <section className="evidence-panel" id="evidence-chain">
      <div className="panel-head">
        <div><span className="eyebrow">可追溯依据</span><h2>这项决策，凭什么？</h2></div>
        <span className="verified-pill"><ShieldCheck size={15} />{evidence.length} 条结构校验通过</span>
      </div>
      <div className="evidence-table">
        {evidence.map((item, index) => (
          <button key={`${item.source}-${index}`} onClick={() => onSelectEvidence(item)}>
            <span className="evidence-index">{String(index + 1).padStart(2, '0')}</span>
            <span className="evidence-source">
              <small>{item.type} · {scopeLabels[item.marketScope]} · {freshnessLabels[item.freshnessClass]}</small>
              <strong>{item.source}</strong>
            </span>
            <span className="evidence-claim">{item.claim}</span>
            <strong className="evidence-value">{item.value}</strong>
            <span className="evidence-open"><ArrowRight size={15} /></span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function EvidenceDetailModal({ evidence, onClose }) {
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="card-modal evidence-modal" role="dialog" aria-modal="true" aria-label="证据详情">
        <button className="modal-close icon-button" onClick={onClose}><X size={19} /></button>
        <div className="modal-content">
          <div className="modal-title evidence-modal-title">
            <span className="modal-icon blue"><Database size={20} /></span>
            <div><span className="eyebrow">{evidence.type} · {scopeLabels[evidence.marketScope]}</span><h2>{evidence.source}</h2></div>
          </div>
          <div className="evidence-detail-grid">
            <div><span>证据结论</span><p>{evidence.claim}</p></div>
            <div><span>原始值 / 原语</span><blockquote>{evidence.value}</blockquote></div>
            <div><span>观察期</span><strong>{evidence.observationPeriod || (evidence.observedAt ? formatReportTime(evidence.observedAt) : '待确认')}</strong></div>
            <div><span>读取时间</span><strong>{evidence.collectedAt ? formatReportTime(evidence.collectedAt) : '待确认'}</strong></div>
            <div><span>时间属性</span><strong>{freshnessLabels[evidence.freshnessClass]}</strong></div>
            <div><span>来源市场</span><strong>{evidence.sourceMarket || 'global / 未标注'}</strong></div>
          </div>
          <div className="modal-compliance">
            <ShieldCheck size={17} />
            <span>{evidence.evidenceKind === 'derived' ? '模型派生证据，结论已回指源记录' : '来源证据'}<small>{evidence.modelId ? `模型：${evidence.modelId}` : '未经过模型改写'}</small></span>
          </div>
          {evidence.url && (
            <div className="modal-actions">
              <span>外部来源</span>
              <div><button onClick={() => window.open(evidence.url, '_blank', 'noopener,noreferrer')}><ExternalLink size={16} />打开来源页面</button></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
