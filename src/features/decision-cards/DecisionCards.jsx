import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Bell,
  BookOpen,
  CheckCircle2,
  Clipboard,
  Clock3,
  MessageCircleMore,
  ShieldCheck,
  Users,
  X,
  XCircle,
} from 'lucide-react';
import { mapRuntimeEvidence, reportModeLabels } from '../research/runtimeMappers';
import { scopeLabels, freshnessLabels } from '../research/researchConfig';
import { formatReportTime, ScoreRing } from '../shared/utils';

export function DecisionCardGrid({ cards, onSelectCard }) {
  return (
    <>
      <div className="content-title" id="decision-cards">
        <div><span className="eyebrow">决策处方</span><h2>四张卡，回答怎么做</h2></div>
        <span className="validity"><Clock3 size={15} />结论有效期剩余 14 天</span>
      </div>
      <section className="card-grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.id} className={`decision-card ${card.tone}`} onClick={() => onSelectCard(card)} tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && onSelectCard(card)}>
              <div className="card-head"><span className="card-type"><Icon size={17} />{card.type}</span><ScoreRing value={card.confidence} /></div>
              <h3>{card.title}</h3><p>{card.summary}</p>
              <div className="card-footer"><div><small>{card.metric}</small><strong>{card.metricValue}</strong></div><span>{card.source}<ArrowRight size={15} /></span></div>
            </article>
          );
        })}
      </section>
    </>
  );
}

export function CardDetailModal({ card, onClose, onCopy, onReview, reviewStatus, evidence, reportMarket, generatedAt, reportMode }) {
  const Icon = card.icon;
  const detailEvidence = card.runtimeCard ? mapRuntimeEvidence([card.runtimeCard]).slice(0, 3) : evidence.slice(0, 3);
  const reportCode = `FC-${reportMarket}-${new Date(generatedAt).toISOString().slice(2, 10).replaceAll('-', '')}`;
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="card-modal" role="dialog" aria-modal="true" aria-label={`${card.type}详情`}>
        <button className="modal-close icon-button" onClick={onClose}><X size={19} /></button>
        <div className="modal-content">
          <div className="modal-title"><span className={`modal-icon ${card.tone}`}><Icon size={20} /></span><div><span className="eyebrow">{card.type} · {reportCode}</span><h2>{card.title}</h2></div><div className="confidence-block"><ScoreRing value={card.confidence} size={48} /><small>置信度</small></div></div>
          <div className="action-box"><span>行动指令</span><p>{card.summary}</p></div>
          <div className="detail-section"><h3><BookOpen size={17} />凭什么 <span>证据链 · {detailEvidence.length} 条</span></h3>{detailEvidence.map((item) => <div className="detail-evidence" key={item.source}><BadgeCheck size={16} /><div><strong>{item.claim}</strong><small>{item.source}</small></div><b>{item.value}</b></div>)}</div>
          <div className="detail-two-col">
            <div className="detail-section hook-box"><h3><Users size={17} />最小市场验证</h3><p><b>验证人群</b> {card.hook?.audience}</p><p><b>验证渠道</b> {card.hook?.channel}</p><div className="copy-hook"><span>{card.hook?.message}</span><button onClick={() => onCopy(card.hook?.message)}><Clipboard size={15} />复制</button></div></div>
            <div className="detail-section failure-box"><h3><AlertTriangle size={17} />什么时候失效</h3>{(card.failureConditions || [{ condition: '关键市场信号越过阈值' }]).slice(0, 2).map((item) => <p key={item.condition}>{item.condition}</p>)}<button><Bell size={15} />失效条件已登记</button></div>
          </div>
          <div className="modal-compliance"><ShieldCheck size={17} /><span>AI 生成 · {reportModeLabels[reportMode] || reportMode} · 需人工复核<small>{detailEvidence.map((item) => item.source).join(' / ')} · 任务完成于 {formatReportTime(generatedAt)}</small></span></div>
          <div className="modal-actions"><span>复核这张卡</span><div><button className={reviewStatus === 'approved' ? 'active approved' : ''} onClick={() => onReview('approved')}><CheckCircle2 size={16} />采纳</button><button className={reviewStatus === 'discussed' ? 'active discussed' : ''} onClick={() => onReview('discussed')}><MessageCircleMore size={16} />待议</button><button className={reviewStatus === 'rejected' ? 'active rejected' : ''} onClick={() => onReview('rejected')}><XCircle size={16} />驳回</button></div></div>
        </div>
      </div>
    </div>
  );
}
