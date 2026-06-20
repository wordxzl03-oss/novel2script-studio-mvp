export const LAYER_OPTIONS = [
  { id: "screenwriting", label: "Screenwriting", disabled: false, note: null },
  { id: "audiovisual", label: "Audiovisual", disabled: true, note: "W7" },
  { id: "production", label: "Production", disabled: true, note: "W7" }
];

export const DEFAULT_LAYER_VISIBILITY = {
  screenwriting: true
};

export function toggleLayer(visibility, layerId) {
  if (layerId !== "screenwriting") return visibility;
  return {
    ...visibility,
    screenwriting: !visibility.screenwriting
  };
}
