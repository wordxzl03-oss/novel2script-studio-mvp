export const ANNOTATION_FLAGS = ["高潮", "起", "承", "转", "合", "待改"];

export function annotationCountLabel(count) {
  return `${count} ${count === 1 ? "note" : "notes"}`;
}

export function annotationForNode(annotations = [], nodeId) {
  return annotations.find((annotation) => annotation.node_id === nodeId) || null;
}

export function filterNodesByAnnotation(nodes, annotations = [], filter = "all") {
  if (filter === "all") return nodes;
  const matchingNodeIds = new Set(
    annotations
      .filter((annotation) => annotation.flag === filter)
      .map((annotation) => annotation.node_id)
  );
  return nodes.filter((node) => matchingNodeIds.has(node.id));
}
