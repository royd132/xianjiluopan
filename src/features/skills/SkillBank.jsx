import {
  BadgeCheck,
  Boxes,
  History,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const STATUS_LABELS = {
  candidate: '待评测',
  ready: '评测通过',
  active: '已激活',
  retired: '已退役',
  rejected: '未通过',
};

export function SkillBankPanel({
  skills,
  skillsLoading,
  retrievedSkills,
  retrievedFor,
  rollbackableNames,
  onLoadSkills,
  onEvaluate,
  onPromote,
  onRollback,
  onRetrieveSkills,
}) {
  const activeSkills = skills?.active_skills || [];
  // `candidates` is the UNION of candidate and ready rows (skills.py status()),
  // so every row has to be branched on its own status field.
  const candidateSkills = skills?.candidates || [];
  const rowCount = activeSkills.length + candidateSkills.length;

  return (
    <section className="skill-bank-panel" id="skill-bank">
      <div className="skill-bank-head">
        <div>
          <span className="eyebrow">Skill Bank</span>
          <h2>技能库</h2>
          <p>Skill 是从失败案例里沉淀下来的可执行证据策略，不会自动上线。先评测、再人工激活，激活后才会被后续任务检索并注入发布门槛。</p>
        </div>
        <div className="skill-bank-head-actions">
          <span className="policy-version"><ShieldCheck size={15} />已激活 {skills?.active_count || 0} / 共 {skills?.total_skills || 0}</span>
          <button className="icon-button" onClick={onLoadSkills} aria-label="刷新技能库"><RefreshCw size={17} /></button>
        </div>
      </div>

      <div className="skill-bank-metrics">
        <div>
          <span>Skill 总数</span>
          <strong>{skills?.total_skills ?? '—'}</strong>
          <small>种子技能与失败案例沉淀的技能都计入</small>
        </div>
        <div>
          <span>已激活</span>
          <strong>{skills?.active_count ?? '—'}</strong>
          <small>{activeSkills.length ? activeSkills.map((item) => item.name).join(' / ') : '尚未激活任何 Skill'}</small>
        </div>
        <div>
          <span>待评测</span>
          <strong>{skills?.candidate_count ?? '—'}</strong>
          <small>只有 candidate 状态可以发起评测</small>
        </div>
        <div>
          <span>已通过待激活</span>
          <strong>{skills?.ready_count ?? '—'}</strong>
          <small>评测通过但尚未进入线上策略</small>
        </div>
      </div>

      <div className="skill-list">
        {rowCount === 0 ? (
          <div className="skill-empty">
            <Boxes size={22} />
            <strong>技能库还没有内容</strong>
            <p>在演进中心驳回一张真实决策卡，失败案例会被沉淀为候选 Skill。</p>
          </div>
        ) : (
          <>
            {activeSkills.map((skill) => (
              <div className="skill-row" key={`active-${skill.skill_id}`}>
                <div className="skill-row-name">
                  <span className="skill-state active">已激活</span>
                  <div><strong>{skill.name}</strong><small>{skill.skill_id}</small></div>
                </div>
                <span className="skill-version">{skill.version}</span>
                <div className="skill-actions">
                  <button className="secondary-button" disabled={skillsLoading || !rollbackableNames?.has(skill.name)} onClick={() => onRollback(skill.name)} title="回滚到该名称的上一个可用版本">
                    <History size={15} />回滚
                  </button>
                </div>
              </div>
            ))}
            {candidateSkills.map((skill) => (
              <div className="skill-row" key={skill.skill_id}>
                <div className="skill-row-name">
                  <span className={`skill-state ${skill.status}`}>{STATUS_LABELS[skill.status] || skill.status}</span>
                  <div><strong>{skill.name}</strong><small>{skill.skill_id}</small></div>
                </div>
                <span className="skill-version">{skill.version}</span>
                <div className="skill-actions">
                  <button className="secondary-button" disabled={skillsLoading || skill.status !== 'candidate'} onClick={() => onEvaluate(skill.skill_id, skill.name)} title="在 Validation / Holdout 合成回放上评测">
                    {skillsLoading ? <LoaderCircle className="spin" size={15} /> : <BadgeCheck size={15} />}评测
                  </button>
                  <button className="secondary-button activate-policy" disabled={skillsLoading || skill.status !== 'ready'} onClick={() => onPromote(skill.skill_id, skill.name)}>
                    <ShieldCheck size={15} />激活
                  </button>
                  <button className="secondary-button" disabled={skillsLoading || !rollbackableNames?.has(skill.name)} onClick={() => onRollback(skill.name)}>
                    <History size={15} />回滚
                  </button>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="skill-bank-actions">
        <p><Sparkles size={16} />命中说明来自 BM25 检索：只有 scope 覆盖当前市场与品类的 Skill 才会进入候选集，最多返回 3 条。</p>
        <div>
          <button className="secondary-button" onClick={onRetrieveSkills} disabled={skillsLoading}>
            <Search size={15} />查看当前品类会命中哪些 Skill
          </button>
        </div>
      </div>

      {retrievedSkills && (
        <div className="skill-hit-list">
          {retrievedSkills.length === 0 ? (
            <p className="skill-hit-empty">当前品类与市场没有已激活的 Skill 命中，任务将使用默认证据门槛。</p>
          ) : (
            retrievedSkills.map((hit) => (
              <div className="skill-hit" key={hit.skill_id}>
                <div><strong>{hit.name}</strong><small>{hit.description}</small></div>
                <span className="skill-version">v{hit.version} · BM25 {hit.retrieval_score}</span>
                <p>{hit.evidence_policy}</p>
              </div>
            ))
          )}
          <span className="skill-hit-scope">检索条件：{retrievedFor}</span>
        </div>
      )}
    </section>
  );
}
