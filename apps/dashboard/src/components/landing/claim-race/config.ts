/** Scene parameters for the claim-race visual. Presentation data, not business logic. */
export const claimScene = {
  seed: 7,
  racerCount: 12,
  winnerSpeed: 1.25,
  loserMaxReach: 0.8,
  /** Scroll smoothing: higher = snappier. Time-based, so 60 Hz and 120 Hz screens feel the same. */
  followRate: 7,
  maxPixelRatio: 1.75,
  fogDensity: 0.045,
  rings: [
    { count: 18, radius: 4.6, height: 0.15, offset: 0 },
    { count: 26, radius: 7, height: 0.15, offset: 0.12 },
  ],
  water: { extent: 11, step: 0.55, y: -0.25 },
  camera: {
    fov: 38,
    distance: 15,
    distanceNarrow: 23,
    height: 9.5,
    heightDrop: 3,
    orbitStart: -0.35,
    orbitSweep: 0.7,
  },
  bloom: { strength: 1.15, radius: 0.55, threshold: 0.12 },
  colors: { idle: "--scene-idle", hot: "--scene-hot", beacon: "--beacon", reject: "--signal-bad", ok: "--signal-ok" },
} as const;

/** Scroll-progress windows for each claim state; the DOM step list uses the same boundaries. */
export const PHASE = {
  detected: [0.0, 0.14],
  queued: [0.16, 0.36],
  leased: [0.38, 0.54],
  acting: [0.56, 0.74],
  confirmed: [0.76, 0.92],
} as const;

export const STEP_STARTS = [0, PHASE.queued[0], PHASE.leased[0], PHASE.acting[0], PHASE.confirmed[0]] as const;
