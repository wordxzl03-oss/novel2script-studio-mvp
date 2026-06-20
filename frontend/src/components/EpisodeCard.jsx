import React from "react";

export default function EpisodeCard({ card, onOpen }) {
  const sourceTotal = Object.values(card.sourceCounts).reduce(
    (total, count) => total + count,
    0
  );

  return (
    <article className={`episode-card status-${card.status}`}>
      <button className="episode-card__open" type="button" onClick={() => onOpen(card.number)}>
        <header className="episode-card__header">
          <span className="episode-number">E{String(card.number).padStart(2, "0")}</span>
          <span className={`status-badge ${card.status}`}>{statusLabel(card.status)}</span>
        </header>

        <div className="episode-card__title">
          <h3>{card.title}</h3>
          <p>{card.logline}</p>
        </div>

        <dl className="episode-beats">
          <Beat label="Open" value={card.openingHook} />
          <Beat label="Conflict" value={card.mainConflict} />
          <Beat label="Payoff" value={card.emotionalPayoff} />
          <Beat label="Exit" value={card.cliffhanger} />
        </dl>

        <footer className="episode-card__footer">
          <div className="source-summary" aria-label={`${sourceTotal} source links`}>
            {sourceTotal > 0 ? (
              <>
                {card.sourceCounts.literal_quote > 0 && (
                  <span>Quote {card.sourceCounts.literal_quote}</span>
                )}
                {card.sourceCounts.source_based > 0 && (
                  <span>Source {card.sourceCounts.source_based}</span>
                )}
                {card.sourceCounts.invented_for_adaptation > 0 && (
                  <span>Added {card.sourceCounts.invented_for_adaptation}</span>
                )}
              </>
            ) : (
              <span>No source yet</span>
            )}
          </div>

          <div className="risk-summary">
            {card.risks.production && <span className="risk production">Production</span>}
            {card.risks.compliance.length > 0 && (
              <span className="risk compliance">Compliance {card.risks.compliance.length}</span>
            )}
            {card.forkCount > 0 && <span className="fork-badge">Forks {card.forkCount}</span>}
          </div>
        </footer>
      </button>
    </article>
  );
}

function Beat({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function statusLabel(status) {
  if (status === "drafted") return "Drafted";
  if (status === "planned") return "Planned";
  return "Pending";
}
