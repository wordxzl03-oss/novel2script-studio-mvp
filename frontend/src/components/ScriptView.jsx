import React, { useMemo } from "react";

import { buildScriptDocument } from "../views/scriptViewModel.js";
import SourceBadge from "./SourceBadge.jsx";

export default function ScriptView({
  badgeNotice,
  elementBadges,
  episode,
  registry,
  selectedLabel,
  selectedSceneId,
  onActivateBadge
}) {
  const document = useMemo(
    () => buildScriptDocument({
      episode,
      registry,
      elementBadges,
      selectedSceneId
    }),
    [elementBadges, episode, registry, selectedSceneId]
  );

  return (
    <article className="script-view">
      <header className="script-view__title">
        <span>Screenwriting layer</span>
        <strong>{selectedLabel}</strong>
      </header>
      {badgeNotice && <div className="badge-notice">{badgeNotice}</div>}
      {document.length > 0 ? document.map((scene) => (
        <ScriptScene
          key={scene.sceneId}
          scene={scene}
          onActivateBadge={onActivateBadge}
        />
      )) : (
        <div className="provenance-empty">No screenplay content matches this selection.</div>
      )}
    </article>
  );
}

function ScriptScene({ scene, onActivateBadge }) {
  return (
    <section className="script-scene">
      <header className="script-scene__heading">
        <span>{scene.sceneId}</span>
        <h3>{scene.title}</h3>
      </header>
      {scene.beats.map((beat) => (
        <section className="script-beat" key={beat.beatId}>
          <header className="script-beat__heading">
            <span>{beat.beatId}</span>
            {beat.summary && <p>{beat.summary}</p>}
          </header>
          <div className="script-elements">
            {beat.elements.map((element) => (
              <ScriptElement
                element={element}
                key={element.elementId}
                onActivateBadge={onActivateBadge}
              />
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}

function ScriptElement({ element, onActivateBadge }) {
  return (
    <div className={`script-element type-${element.kind}`}>
      <div className="script-element__content">
        {element.kind === "dialogue" ? (
          <DialogueElement element={element} />
        ) : (
          <StandardElement element={element} />
        )}
      </div>
      <div className="element-badges">
        {element.badges.map((badge, index) => (
          <SourceBadge
            badge={badge}
            key={`${element.elementId}-${index}`}
            onActivate={onActivateBadge}
          />
        ))}
      </div>
    </div>
  );
}

function DialogueElement({ element }) {
  return (
    <div className="script-dialogue">
      <strong>{element.speakerName}</strong>
      {element.performanceHint && (
        <span className="performance-hint">({element.performanceHint})</span>
      )}
      <p>{element.text}</p>
    </div>
  );
}

function StandardElement({ element }) {
  return (
    <>
      <span className="script-element__label">{element.label}</span>
      <p>{element.text}</p>
    </>
  );
}
