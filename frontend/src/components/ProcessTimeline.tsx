import React, { useState, useEffect, useRef, useMemo } from 'react';
import hljs from 'highlight.js/lib/core';
import python from 'highlight.js/lib/languages/python';
import 'highlight.js/styles/atom-one-dark.css';
import type { StateLog } from '../types';

hljs.registerLanguage('python', python);

interface ProcessTimelineProps {
  logs: StateLog[];
}

const statusText: Record<string, string> = {
  started: '开始',
  running: '运行中',
  completed: '完成',
  success: '成功',
  failed: '失败',
  error: '失败',
  info: '信息',
  paused: '暂停',
};

const readableAction = (action: string) => action
  .replace(/_/g, ' ')
  .replace(/\b\w/g, char => char.toUpperCase());

const compactValue = (value: any) => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
};

const renderDataRows = (log: StateLog) => {
  const data = log.data || {};
  const hiddenKeys = new Set([
    'output_image_base64', 'input_image_base64', 'output_path', 'input_image_path',
    'code_preview', 'repair_preview', 'evaluation_text', 'evaluation_preview',
    'improvements', 'error', 'error_traceback', 'error_type', 'results_preview',
    'code_generation_failed', 'brief', 'quality_verdict', 'queries_used',
    'code_path', 'code_hash', 'output_hash', 'stagnant_iterations',
  ]);

  return Object.entries(data)
    .filter(([key, value]) => !hiddenKeys.has(key) && compactValue(value))
    .slice(0, 6)
    .map(([key, value]) => {
      const displayValue = compactValue(value) || '';
      const multiline = displayValue.length > 90 || displayValue.includes('\n');
      return (
        <div className="process-data-row" key={key}>
          <span className="process-data-key">{key}</span>
          {multiline ? (
            <pre className="process-data-pre">{displayValue}</pre>
          ) : (
            <span className="process-data-value">{displayValue}</span>
          )}
        </div>
      );
    });
};

const isExpandable = (log: StateLog) => {
  const data = log.data || {};
  const agent = log.agent;
  const action = log.action;

  if (agent === 'EvaluationAgent' && action.includes('complete')) return true;
  if (agent === 'CodeGenerationAgent' && (action.includes('complete') || action.includes('repair'))) return true;
  if (agent === 'ExecutionAgent' && (action.includes('complete') || action.includes('failed'))) return true;
  if (agent === 'RetrievalAgent' && action.includes('complete')) return true;
  if (data.code_preview || data.evaluation_text || data.evaluation_preview || data.error || data.improvements) return true;
  return false;
};

// ── helpers ──

const highlightCode = (code: string): string => {
  if (!code) return '';
  try {
    const result = hljs.highlight(code, { language: 'python' });
    return result.value;
  } catch {
    return code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
};

/** Parse markdown sections like "## 标题" followed by content */
const parseMarkdownSections = (text: string): { title: string; content: string }[] => {
  if (!text) return [];
  const sections: { title: string; content: string }[] = [];
  const lines = text.split('\n');
  let currentTitle = '';
  let currentContent: string[] = [];

  for (const line of lines) {
    const h2Match = line.match(/^##\s+(.+)/);
    if (h2Match) {
      if (currentTitle || currentContent.length) {
        sections.push({ title: currentTitle, content: currentContent.join('\n').trim() });
      }
      currentTitle = h2Match[1].trim();
      currentContent = [];
    } else {
      currentContent.push(line);
    }
  }
  if (currentTitle || currentContent.length) {
    sections.push({ title: currentTitle, content: currentContent.join('\n').trim() });
  }
  return sections;
};

/** Extract dimension scores like "- 技术质量：X/10" into an array */
const parseDimensionScores = (text: string): { name: string; score: number }[] => {
  const dims: { name: string; score: number }[] = [];
  const re = /[-*]\s*(.+?)[：:]\s*(\d+(?:\.\d+)?)\s*\/?\s*10/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[1].trim();
    const score = parseFloat(m[2]);
    if (name && !isNaN(score) && !name.includes('总体评分')) {
      dims.push({ name, score: Math.min(10, Math.max(0, score)) });
    }
  }
  return dims;
};

/** Parse list items like "- item" or "1. item" from text */
const parseListItems = (text: string): string[] => {
  if (!text) return [];
  return text
    .split('\n')
    .map(line => line.replace(/^[\s]*[-*\d]+[\.\)]\s*/, '').trim())
    .filter(Boolean);
};

// ── Expanded content per agent ──

const RetrievalExpanded: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const brief: string = data.brief || '';
  const sections = useMemo(() => parseMarkdownSections(brief), [brief]);
  const queries: string[] = data.queries_used || [];

  return (
    <div className="process-expanded-content">
      <div className="process-score-display">
        <span className="process-score-label">检索质量</span>
        <span className={`process-score-value ${data.quality_score >= 7 ? 'score-high' : data.quality_score >= 5 ? 'score-mid' : 'score-low'}`}>
          {data.quality_score}<span className="process-score-max">/10</span>
        </span>
        {data.quality_verdict && (
          <span className="process-verdict-text">{data.quality_verdict}</span>
        )}
      </div>

      {queries.length > 0 && (
        <div className="process-detail-section">
          <div className="process-detail-label">搜索查询</div>
          <div className="process-tags">
            {queries.map((q: string, i: number) => (
              <span className="process-tag" key={i}>{q}</span>
            ))}
          </div>
        </div>
      )}

      {sections.length > 0 ? (
        <div className="process-structured-sections">
          {sections.map((sec, i) => (
            <div className="process-structured-section" key={i}>
              <div className="process-section-title">{sec.title}</div>
              <div className="process-section-body">
                {parseListItems(sec.content).length > 0 && sec.content.includes('-') ? (
                  <ul className="process-bullet-list">
                    {parseListItems(sec.content).map((item, j) => (
                      <li key={j}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="process-detail-text">{sec.content}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : brief ? (
        <div className="process-detail-text">{brief}</div>
      ) : null}
    </div>
  );
};

const EvaluationExpanded: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const evalText: string = data.evaluation_text || data.evaluation_preview || '';
  const sections = useMemo(() => parseMarkdownSections(evalText), [evalText]);
  const dimScores = useMemo(() => parseDimensionScores(evalText), [evalText]);
  const improvements: string = data.improvements || '';

  // Find specific sections
  const prosSection = sections.find(s => s.title.includes('主要优点'));
  const improveSection = sections.find(s => s.title.includes('需要改进') || s.title.includes('改进建议') || s.title.includes('可改进'));
  const verdictSection = sections.find(s => s.title.includes('整体评语'));

  return (
    <div className="process-expanded-content">
      {/* Score */}
      <div className="process-score-display">
        <span className="process-score-label">总体评分</span>
        <span className={`process-score-value ${data.score >= 7 ? 'score-high' : data.score >= 5 ? 'score-mid' : 'score-low'}`}>
          {data.score}<span className="process-score-max">/10</span>
        </span>
      </div>

      {/* Dimension scores */}
      {dimScores.length > 0 && (
        <div className="process-detail-section">
          <div className="process-detail-label">维度评分</div>
          <div className="process-dimension-scores">
            {dimScores.map((dim, i) => (
              <div className="process-dimension-row" key={i}>
                <span className="process-dimension-name">{dim.name}</span>
                <div className="process-dimension-bar-track">
                  <div
                    className={`process-dimension-bar-fill ${dim.score >= 7 ? 'score-high' : dim.score >= 5 ? 'score-mid' : 'score-low'}`}
                    style={{ width: `${(dim.score / 10) * 100}%` }}
                  />
                </div>
                <span className="process-dimension-value">{dim.score}/10</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pros */}
      {prosSection && (
        <div className="process-detail-section">
          <div className="process-detail-label success">主要优点</div>
          <ul className="process-bullet-list">
            {parseListItems(prosSection.content).map((item, j) => (
              <li key={j}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Improvements */}
      {(improveSection || improvements) && (
        <div className="process-detail-section">
          <div className="process-detail-label warning">需要改进</div>
          <ul className="process-bullet-list">
            {(improveSection ? parseListItems(improveSection.content) : parseListItems(improvements)).map((item, j) => (
              <li key={j}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Overall verdict */}
      {verdictSection && (
        <div className="process-detail-section">
          <div className="process-detail-label">整体评语</div>
          <div className="process-verdict-block">{verdictSection.content}</div>
        </div>
      )}

      {/* Fallback: raw eval text if no structured sections */}
      {sections.length === 0 && evalText && (
        <div className="process-detail-section">
          <div className="process-detail-label">评估详情</div>
          <div className="process-detail-text">{evalText}</div>
        </div>
      )}
    </div>
  );
};

const CodeGenExpanded: React.FC<{ log: StateLog }> = ({ log }) => {
  const data = log.data || {};
  const codePreview: string = data.code_preview || data.repair_preview || '';
  const isRepair = log.action.includes('repair');
  const highlighted = useMemo(() => highlightCode(codePreview), [codePreview]);

  return (
    <div className="process-expanded-content">
      {isRepair && (
        <div className="process-detail-badge repair">修复版本</div>
      )}
      {data.code_length && (
        <div className="process-detail-meta-row">
          <span>代码长度: <strong>{data.code_length}</strong> 字符</span>
          {data.code_path && <span className="process-path-hint">{data.code_path}</span>}
        </div>
      )}
      {highlighted && (
        <div className="process-detail-section">
          <div className="process-detail-label">
            {isRepair ? '修复代码' : '生成代码'}
          </div>
          <pre className="process-code-block">
            <code dangerouslySetInnerHTML={{ __html: highlighted }} />
          </pre>
        </div>
      )}
    </div>
  );
};

const ExecutionExpanded: React.FC<{ log: StateLog }> = ({ log }) => {
  const data = log.data || {};
  const error: string = data.error || '';
  const errorType: string = data.error_type || '';
  const errorTraceback: string = data.error_traceback || '';
  const outputPath: string = data.output_path || log.output_path || '';

  return (
    <div className="process-expanded-content">
      {error ? (
        <>
          <div className="process-detail-section">
            <div className="process-detail-label error">执行错误</div>
            <div className="process-error-summary">
              {errorType && <span className="process-error-type-badge">{errorType}</span>}
              <span className="process-error-message">{error}</span>
            </div>
          </div>
          {errorTraceback && (
            <details className="process-traceback-details">
              <summary className="process-traceback-summary">查看完整堆栈跟踪</summary>
              <pre className="process-error-block"><code>{errorTraceback}</code></pre>
            </details>
          )}
        </>
      ) : outputPath ? (
        <div className="process-detail-section">
          <div className="process-detail-label success">执行成功</div>
          <div className="process-detail-text path">{outputPath}</div>
        </div>
      ) : null}
    </div>
  );
};

const FallbackExpanded: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const codePreview = data.code_preview || data.repair_preview || '';
  const evalText = data.evaluation_text || data.evaluation_preview || '';
  const error = data.error || '';
  const improvements = data.improvements || '';

  return (
    <div className="process-expanded-content">
      {codePreview && (
        <div className="process-detail-section">
          <div className="process-detail-label">代码预览</div>
          <pre className="process-code-block">
            <code dangerouslySetInnerHTML={{ __html: highlightCode(codePreview) }} />
          </pre>
        </div>
      )}
      {evalText && (
        <div className="process-detail-section">
          <div className="process-detail-label">评估详情</div>
          <div className="process-detail-text">{evalText}</div>
        </div>
      )}
      {improvements && (
        <div className="process-detail-section">
          <div className="process-detail-label">改进建议</div>
          <div className="process-detail-text">{improvements}</div>
        </div>
      )}
      {error && (
        <div className="process-detail-section">
          <div className="process-detail-label error">错误信息</div>
          <pre className="process-error-block"><code>{error}</code></pre>
        </div>
      )}
    </div>
  );
};

const ExpandedContent: React.FC<{ log: StateLog }> = ({ log }) => {
  const agent = log.agent;

  switch (agent) {
    case 'RetrievalAgent':
      return <RetrievalExpanded data={log.data || {}} />;
    case 'EvaluationAgent':
      return <EvaluationExpanded data={log.data || {}} />;
    case 'CodeGenerationAgent':
      return <CodeGenExpanded log={log} />;
    case 'ExecutionAgent':
      return <ExecutionExpanded log={log} />;
    default:
      return <FallbackExpanded data={log.data || {}} />;
  }
};

// ── Main component ──

const ProcessTimeline: React.FC<ProcessTimelineProps> = ({ logs }) => {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const prevLogCountRef = useRef(0);

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  useEffect(() => {
    if (logs.length > prevLogCountRef.current && logs.length > 0) {
      const latest = logs[logs.length - 1];
      if (isExpandable(latest)) {
        setExpandedIds(prev => new Set(prev).add(latest.id));
      }
    }
    prevLogCountRef.current = logs.length;
  }, [logs]);

  if (!logs.length) return null;

  return (
    <section className="process-timeline" aria-label="运行过程">
      <div className="process-header">
        <div>
          <h2>运行过程</h2>
          <p>{logs.length} 个实时事件</p>
        </div>
      </div>

      <div className="process-list">
        {logs.map(log => {
          const inputImage = log.input_image_base64 || log.data?.input_image_base64;
          const outputImage = log.output_image_base64 || log.data?.output_image_base64;
          const expanded = expandedIds.has(log.id);
          const expandable = isExpandable(log);

          return (
            <article className={`process-item status-${log.status}`} key={log.id}>
              <div className="process-line">
                <span className="process-dot" />
              </div>
              <div className={`process-card ${expanded ? 'expanded' : ''}`}>
                <div
                  className={`process-card-header ${expandable ? 'clickable' : ''}`}
                  onClick={() => expandable && toggleExpand(log.id)}
                  role={expandable ? 'button' : undefined}
                  tabIndex={expandable ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (expandable && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      toggleExpand(log.id);
                    }
                  }}
                  title={expandable ? (expanded ? '点击收起' : '点击展开详情') : undefined}
                >
                  <div>
                    <div className="process-agent">{log.agent}</div>
                    <div className="process-action">{readableAction(log.action)}</div>
                  </div>
                  <div className="process-meta">
                    <span className="process-status">{statusText[log.status] || log.status}</span>
                    <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                    {expandable && (
                      <span className={`process-expand-toggle ${expanded ? 'expanded' : ''}`}>
                        {expanded ? '▾' : '▸'}
                      </span>
                    )}
                  </div>
                </div>

                <div className="process-data">
                  {renderDataRows(log)}
                </div>

                {expanded && <ExpandedContent log={log} />}

                {(inputImage || outputImage) && (
                  <div className="process-images">
                    {inputImage && (
                      <figure>
                        <img src={inputImage} alt="输入图片" />
                        <figcaption>输入图片</figcaption>
                      </figure>
                    )}
                    {outputImage && (
                      <figure>
                        <img src={outputImage} alt="输出图片" />
                        <figcaption>输出图片</figcaption>
                      </figure>
                    )}
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
};

export default ProcessTimeline;
