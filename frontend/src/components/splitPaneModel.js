export const DEFAULT_PANE_WIDTHS = Object.freeze({
  graph: 28,
  source: 36,
  script: 36
});

const MIN_PANE_WIDTH = 18;

export function resizePanePair(widths, leftId, rightId, delta) {
  const pairTotal = widths[leftId] + widths[rightId];
  const leftWidth = clamp(
    widths[leftId] + delta,
    MIN_PANE_WIDTH,
    pairTotal - MIN_PANE_WIDTH
  );

  return {
    ...widths,
    [leftId]: leftWidth,
    [rightId]: pairTotal - leftWidth
  };
}

export function resetPaneWidths() {
  return { ...DEFAULT_PANE_WIDTHS };
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}
