const EPISODE_COUNT = 10;
const PRODUCTION_RISK_THRESHOLD = 0.6;

export function buildEpisodeCards(project) {
  const outlines = indexByNumber(project?.series?.outlines);
  const episodes = indexByNumber(
    (project?.series?.episodes || []).filter((episode) => episode.episode_id !== "E000")
  );
  const diagnosis = project?.ip_diagnosis;

  return Array.from({ length: EPISODE_COUNT }, (_, index) => {
    const number = index + 1;
    const outline = outlines.get(number);
    const episode = episodes.get(number);
    const content = episode || outline;
    const sourceLinks = content?.source_ranges || [];
    const productionRisk = productionRiskFor(diagnosis, sourceLinks);
    const complianceRisks = complianceRisksFor(diagnosis, sourceLinks);

    return {
      number,
      episodeId: episode?.episode_id || null,
      status: episode ? "drafted" : outline ? "planned" : "pending",
      title: content?.title || `Episode ${number}`,
      logline: content?.logline || "Awaiting episode outline.",
      openingHook: content?.opening_hook || "Not planned yet.",
      mainConflict: content?.main_conflict || "Not planned yet.",
      emotionalPayoff: content?.emotional_payoff || "Not planned yet.",
      cliffhanger: content?.cliffhanger || "Not planned yet.",
      sourceCounts: countSourceTypes(sourceLinks),
      risks: {
        production: productionRisk,
        compliance: complianceRisks
      },
      forkCount: episode?.forks?.length || 0
    };
  });
}

export function filterEpisodeCards(cards, filter) {
  if (filter === "production") {
    return cards.filter((card) => Boolean(card.risks.production));
  }
  if (filter === "compliance") {
    return cards.filter((card) => card.risks.compliance.length > 0);
  }
  return cards;
}

export function summarizeProjectRisks(project, cards = buildEpisodeCards(project)) {
  const affectedEpisodeCount = cards.filter(
    (card) => card.risks.production || card.risks.compliance.length > 0
  ).length;

  return {
    productionScore: project?.ip_diagnosis?.production_cost_risk?.score ?? null,
    complianceCount: project?.ip_diagnosis?.compliance_risk_notes?.length || 0,
    affectedEpisodeCount
  };
}

function productionRiskFor(diagnosis, sourceLinks) {
  const risk = diagnosis?.production_cost_risk;
  if (!risk || risk.score < PRODUCTION_RISK_THRESHOLD) {
    return null;
  }
  if (!evidenceApplies(risk.rationale, sourceLinks)) {
    return null;
  }
  return {
    score: risk.score,
    text: risk.rationale?.text || "Production cost needs review."
  };
}

function complianceRisksFor(diagnosis, sourceLinks) {
  return (diagnosis?.compliance_risk_notes || [])
    .filter((note) => evidenceApplies(note, sourceLinks))
    .map((note) => note.text);
}

function evidenceApplies(evidenceText, sourceLinks) {
  const evidenceLinks = evidenceText?.evidence?.source_basis || [];
  if (evidenceLinks.length === 0) {
    return true;
  }
  if (sourceLinks.length === 0) {
    return false;
  }
  return evidenceLinks.some((riskLink) =>
    sourceLinks.some((episodeLink) => rangesOverlap(riskLink, episodeLink))
  );
}

function rangesOverlap(firstLink, secondLink) {
  const first = firstLink?.source_range;
  const second = secondLink?.source_range;
  if (!first || !second || first.chapter_id !== second.chapter_id) {
    return false;
  }
  return first.start_para <= second.end_para && second.start_para <= first.end_para;
}

function countSourceTypes(sourceLinks) {
  return sourceLinks.reduce(
    (counts, link) => {
      if (link?.type in counts) {
        counts[link.type] += 1;
      }
      return counts;
    },
    {
      literal_quote: 0,
      source_based: 0,
      invented_for_adaptation: 0
    }
  );
}

function indexByNumber(items = []) {
  return new Map(items.map((item) => [item.number, item]));
}
