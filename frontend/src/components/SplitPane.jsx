import React, { useRef } from "react";

import { resizePanePair } from "./splitPaneModel.js";

export default function SplitPane({
  panes,
  widths,
  collapsed,
  onResize,
  onReset,
  onTogglePane
}) {
  const frameRef = useRef(null);
  const visiblePanes = panes.filter((pane) => !collapsed[pane.id]);
  const columns = visiblePanes
    .flatMap((pane, index) => [
      `minmax(260px, ${widths[pane.id]}fr)`,
      ...(index < visiblePanes.length - 1 ? ["10px"] : [])
    ])
    .join(" ");

  function startResize(event, leftId, rightId) {
    if (window.matchMedia("(max-width: 1000px)").matches) return;

    event.preventDefault();
    const startX = event.clientX;
    const startWidths = { ...widths };
    const frameWidth = frameRef.current?.getBoundingClientRect().width || 1;

    function move(moveEvent) {
      const delta = ((moveEvent.clientX - startX) / frameWidth) * 100;
      onResize(resizePanePair(startWidths, leftId, rightId, delta));
    }

    function stop() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      document.body.classList.remove("pane-resizing");
    }

    document.body.classList.add("pane-resizing");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  }

  function resizeWithKeyboard(event, leftId, rightId) {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      const delta = event.key === "ArrowLeft" ? -2 : 2;
      onResize(resizePanePair(widths, leftId, rightId, delta));
    }
    if (event.key === "Home") {
      event.preventDefault();
      onReset();
    }
  }

  return (
    <div className="split-pane-frame">
      <div className="pane-visibility" aria-label="Visible workbench panels">
        {panes.map((pane) => (
          <button
            aria-pressed={!collapsed[pane.id]}
            className={!collapsed[pane.id] ? "active" : ""}
            key={pane.id}
            type="button"
            onClick={() => onTogglePane(pane.id)}
          >
            {pane.label}
          </button>
        ))}
        <button type="button" onClick={onReset}>Reset widths</button>
      </div>

      <div
        className="split-pane"
        ref={frameRef}
        style={{ "--pane-columns": columns }}
      >
        {visiblePanes.map((pane, index) => (
          <React.Fragment key={pane.id}>
            <section className={`workbench-pane tone-${pane.tone}`} data-pane={pane.id}>
              <header className="workbench-pane__header">
                <div>
                  <span>{pane.kicker}</span>
                  <strong>{pane.label}</strong>
                </div>
                <button
                  aria-label={`Hide ${pane.label}`}
                  disabled={visiblePanes.length === 1}
                  title={`Hide ${pane.label}`}
                  type="button"
                  onClick={() => onTogglePane(pane.id)}
                >
                  Hide
                </button>
              </header>
              <div className="workbench-pane__body">{pane.content}</div>
            </section>

            {index < visiblePanes.length - 1 && (
              <div
                aria-label={`Resize ${pane.label} and ${visiblePanes[index + 1].label}`}
                className="split-divider"
                role="separator"
                tabIndex="0"
                onDoubleClick={onReset}
                onKeyDown={(event) =>
                  resizeWithKeyboard(event, pane.id, visiblePanes[index + 1].id)
                }
                onPointerDown={(event) =>
                  startResize(event, pane.id, visiblePanes[index + 1].id)
                }
              >
                <span aria-hidden="true">...</span>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

