import React, { useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const SAMPLE_NOVEL = `第1章 雨夜来信

雨从傍晚开始落下，老街巷口的路灯被水雾晕成一团。
林砚把伞压低，发现门缝里夹着一只没有署名的信封。
信纸上只有半行字：三年前的案子，不该就这么结束。

第2章 旧案卷宗

档案室的灯坏了一半，只剩最里面一排冷白色的光。
陈叔把钥匙放在桌上，没有看林砚。
林砚翻开旧案卷宗，发现一页证词被黑笔划去了半个名字。

第3章 巷口重逢

巷口的路灯亮得很迟，雨停以后，地面还反着碎光。
周南站在阴影里，像是早就知道林砚会来。
林砚举起那页复印件，问：被划掉的名字，是你，对吗？`;

function App() {
  const [title, setTitle] = useState("雨夜旧案");
  const [logline, setLogline] = useState("一封匿名信迫使刑警重新面对三年前的失踪案。");
  const [profile, setProfile] = useState("film");
  const [novelText, setNovelText] = useState(SAMPLE_NOVEL);
  const [result, setResult] = useState(null);
  const [rawJsonVisible, setRawJsonVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const scenes = result?.screenplay?.scenes || [];
  const characters = result?.global_scan?.characters || [];
  const locations = result?.global_scan?.locations || [];
  const findings = result?.lint_findings || [];
  const metrics = result?.metrics || {};

  const errorFindings = useMemo(
    () => findings.filter((item) => item.severity === "error"),
    [findings]
  );

  const warningFindings = useMemo(
    () => findings.filter((item) => item.severity === "warning"),
    [findings]
  );

  async function handleGenerate() {
    setError("");
    setResult(null);

    if (!novelText.trim()) {
      setError("请先粘贴至少 3 章小说文本。");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          novel_text: novelText,
          title,
          logline,
          profile,
          max_json_repair_attempts: 1,
          max_schema_repair_attempts: 1
        })
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = data?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || JSON.stringify(detail, null, 2);
        throw new Error(message || `HTTP ${response.status}`);
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "生成失败。");
    } finally {
      setLoading(false);
    }
  }

  function downloadJson() {
    if (!result) return;

    const blob = new Blob([JSON.stringify(result.screenplay, null, 2)], {
      type: "application/json;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title || "screenplay"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="app">
      <header className="hero">
        <div>
          <p className="eyebrow">Novel2Script Studio</p>
          <h1>AI 小说转剧本工作台</h1>
          <p className="subtitle">
            粘贴 3 章以上小说文本，调用真实后端流水线，生成可校验、可溯源、可继续打磨的结构化剧本。
          </p>
        </div>
        <div className="status-card">
          <span className="status-dot" />
          <div>
            <strong>真实 API 闭环</strong>
            <p>POST {API_BASE}/api/generate</p>
          </div>
        </div>
      </header>

      <section className="grid">
        <section className="panel input-panel">
          <div className="panel-header">
            <h2>输入小说</h2>
            <button type="button" onClick={() => setNovelText(SAMPLE_NOVEL)}>
              填入示例文本
            </button>
          </div>

          <label>
            项目标题
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          <label>
            Logline
            <input value={logline} onChange={(event) => setLogline(event.target.value)} />
          </label>

          <label>
            剧种 Profile
            <select value={profile} onChange={(event) => setProfile(event.target.value)}>
              <option value="film">film</option>
              <option value="series">series</option>
              <option value="short_drama">short_drama</option>
            </select>
          </label>

          <label className="textarea-label">
            小说正文
            <textarea
              value={novelText}
              onChange={(event) => setNovelText(event.target.value)}
              spellCheck="false"
            />
          </label>

          <button className="primary" type="button" onClick={handleGenerate} disabled={loading}>
            {loading ? "生成中：正在调用后端流水线..." : "生成结构化剧本"}
          </button>

          {error && <div className="error-box">{error}</div>}
        </section>

        <section className="panel">
          <h2>生成指标</h2>
          {result ? (
            <div className="metrics">
              <Metric label="章节数" value={metrics.chapter_count} />
              <Metric label="场景数" value={metrics.scene_count} />
              <Metric label="JSON 修复" value={metrics.json_repair_attempts} />
              <Metric label="Schema 修复" value={metrics.schema_repair_attempts} />
              <Metric label="Schema 最终通过" value={String(metrics.final_schema_ok)} />
              <Metric label="Lint 错误" value={metrics.lint_error_count} />
              <Metric label="Lint 警告" value={metrics.lint_warning_count} />
              <Metric label="LLM 调用" value={metrics.llm_calls_used} />
            </div>
          ) : (
            <EmptyState text="生成后将在这里显示通过率、修复次数与 Linter 统计。" />
          )}

          {result && (
            <div className="actions">
              <button type="button" onClick={downloadJson}>下载 Screenplay JSON</button>
              <button type="button" onClick={() => setRawJsonVisible((value) => !value)}>
                {rawJsonVisible ? "隐藏原始 JSON" : "查看原始 JSON"}
              </button>
            </div>
          )}
        </section>
      </section>

      <section className="columns">
        <section className="panel">
          <h2>角色注册表</h2>
          {characters.length > 0 ? (
            <div className="card-list">
              {characters.map((character) => (
                <article className="mini-card" key={character.character_id}>
                  <strong>{character.character_id}｜{character.name}</strong>
                  <p>{character.description || "无描述"}</p>
                  <small>别名：{(character.aliases || []).join("、") || "无"}</small>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState text="暂无角色注册表。" />
          )}
        </section>

        <section className="panel">
          <h2>地点注册表</h2>
          {locations.length > 0 ? (
            <div className="card-list">
              {locations.map((location) => (
                <article className="mini-card" key={location.location_id}>
                  <strong>{location.location_id}｜{location.name}</strong>
                  <p>{location.description || "无描述"}</p>
                  <small>别名：{(location.aliases || []).join("、") || "无"}</small>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState text="暂无地点注册表。" />
          )}
        </section>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>剧本场景</h2>
          <span>{scenes.length} scenes</span>
        </div>

        {scenes.length > 0 ? (
          <div className="scene-list">
            {scenes.map((scene) => (
              <SceneCard scene={scene} key={scene.scene_id} />
            ))}
          </div>
        ) : (
          <EmptyState text="点击生成后，场景级剧本会显示在这里。" />
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Linter 检查结果</h2>
          <span>
            {errorFindings.length} errors · {warningFindings.length} warnings · {findings.length} total
          </span>
        </div>

        {findings.length > 0 ? (
          <div className="finding-list">
            {findings.map((finding, index) => (
              <article className={`finding ${finding.severity}`} key={`${finding.rule_id}-${index}`}>
                <strong>{finding.rule_id}｜{finding.severity}</strong>
                <p>{finding.message}</p>
                <small>{finding.path}</small>
                {finding.suggestion && <em>{finding.suggestion}</em>}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState text={result ? "当前没有 Linter findings。" : "生成后将在这里显示结构错误、质量警告与优化提示。"} />
        )}
      </section>

      {rawJsonVisible && result && (
        <section className="panel">
          <h2>原始返回 JSON</h2>
          <pre className="json-view">{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="empty">{text}</div>;
}

function SceneCard({ scene }) {
  return (
    <article className="scene-card">
      <div className="scene-head">
        <div>
          <strong>{scene.scene_id}｜{scene.title || "未命名场景"}</strong>
          <p>
            {scene.heading?.int_ext} · {scene.heading?.location_id} · {scene.heading?.time_of_day}
          </p>
        </div>
        <small>
          {scene.source?.chapter} · P{scene.source?.para_range?.start}–P{scene.source?.para_range?.end}
        </small>
      </div>

      <div className="scene-meta">
        <span>角色：{(scene.characters || []).join("、") || "无"}</span>
        <span>估时：{scene.estimated_seconds ?? "—"}s</span>
      </div>

      <div className="scene-objective">
        <p><b>目标：</b>{scene.objective || "无"}</p>
        <p><b>冲突：</b>{scene.conflict || "无"}</p>
      </div>

      <div className="elements">
        {(scene.elements || []).map((element, index) => (
          <ElementBlock element={element} key={index} />
        ))}
      </div>

      {scene.source?.quote && (
        <blockquote>原文锚点：{scene.source.quote}</blockquote>
      )}
    </article>
  );
}

function ElementBlock({ element }) {
  if (element.type === "dialogue") {
    return (
      <div className="element dialogue">
        <span>{element.speaker_id}</span>
        <p>{element.line}</p>
      </div>
    );
  }

  if (element.type === "action") {
    return (
      <div className="element action">
        <span>动作</span>
        <p>{element.text}</p>
      </div>
    );
  }

  return (
    <div className="element other">
      <span>{element.type}</span>
      <p>{element.text || element.line || JSON.stringify(element)}</p>
    </div>
  );
}

export default App;