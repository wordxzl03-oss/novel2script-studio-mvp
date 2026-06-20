import React, { useMemo, useState } from "react";

import EpisodeCard from "../components/EpisodeCard.jsx";
import RiskFilter from "../components/RiskFilter.jsx";
import {
  buildEpisodeCards,
  filterEpisodeCards,
  summarizeProjectRisks
} from "./episodeBoardModel.js";

export default function EpisodeBoard({ project, profileId, stageLabel, onOpenEpisode }) {
  const [filter, setFilter] = useState("all");
  const cards = useMemo(() => buildEpisodeCards(project), [project]);
  const visibleCards = useMemo(() => filterEpisodeCards(cards, filter), [cards, filter]);
  const riskSummary = useMemo(() => summarizeProjectRisks(project, cards), [project, cards]);
  const counts = {
    all: cards.length,
    production: filterEpisodeCards(cards, "production").length,
    compliance: filterEpisodeCards(cards, "compliance").length
  };
  const draftedCount = cards.filter((card) => card.status === "drafted").length;

  return (
    <section className="episode-board" aria-labelledby="episode-board-title">
      <header className="board-header">
        <div>
          <p className="eyebrow">Episode runway / E01-E10</p>
          <h2 id="episode-board-title">{project?.series?.title || project?.novel?.title || "Episode board"}</h2>
          <p className="board-intro">
            Ten episode beats, their source footprint, and diagnosis-backed risk signals.
          </p>
        </div>
        <div className="board-context" aria-label="Board context">
          <span>{profileId}</span>
          <span>{stageLabel}</span>
        </div>
      </header>

      <div className="board-summary" aria-label="Episode board summary">
        <Summary label="Drafted" value={`${draftedCount}/10`} />
        <Summary
          label="Production score"
          value={riskSummary.productionScore == null ? "Not scored" : `${Math.round(riskSummary.productionScore * 100)}%`}
        />
        <Summary label="Compliance notes" value={riskSummary.complianceCount} />
        <Summary label="Episodes flagged" value={riskSummary.affectedEpisodeCount} />
      </div>

      <RiskFilter value={filter} counts={counts} onChange={setFilter} />

      {visibleCards.length > 0 ? (
        <div className="episode-grid">
          {visibleCards.map((card) => (
            <EpisodeCard card={card} key={card.number} onOpen={onOpenEpisode} />
          ))}
        </div>
      ) : (
        <div className="board-empty">
          No episodes match this risk filter. Diagnosis risk is only attached when its evidence
          overlaps an episode source range.
        </div>
      )}
    </section>
  );
}

function Summary({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
