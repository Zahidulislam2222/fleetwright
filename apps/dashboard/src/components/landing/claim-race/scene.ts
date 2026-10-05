import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { claimScene as cfg, PHASE } from "./config";

function tokenColor(name: string) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) throw new Error(`Missing colour token ${name}`);
  return new THREE.Color(value);
}

/** 0..1 progress of x inside [a, b], smoothstepped. */
function phase(x: number, a: number, b: number) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

type Racer = {
  pane: THREE.Mesh<THREE.BoxGeometry, THREE.MeshBasicMaterial>;
  beam: THREE.Mesh<THREE.CylinderGeometry, THREE.MeshBasicMaterial>;
  origin: THREE.Vector3;
  speed: number;
  role: "winner" | "loser" | "stale" | "idle";
  bob: number;
};

const ORIGIN = new THREE.Vector3(0, 0, 0);

/**
 * The claim race: a ring of worker panes around one job beacon. Progress (0..1) is driven by scroll;
 * the scene renders only when asked (render loop owned by the React wrapper).
 */
export class ClaimRaceScene {
  private renderer: THREE.WebGLRenderer;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private racers: Racer[] = [];
  private job: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  private halo: THREE.Sprite;
  private pulse: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>;
  private shield: THREE.Mesh<THREE.TorusGeometry, THREE.MeshBasicMaterial>;
  private confirmRing: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>;
  private water: THREE.Points;
  private narrow = false;
  private disposables: { dispose: () => void }[] = [];
  // Colours come from the CSS design tokens, so the scene and the page can never drift apart.
  private colors = {
    idle: tokenColor(cfg.colors.idle),
    hot: tokenColor(cfg.colors.hot),
    beacon: tokenColor(cfg.colors.beacon),
    reject: tokenColor(cfg.colors.reject),
    ok: tokenColor(cfg.colors.ok),
  };

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.setClearColor(0x000000, 1);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, cfg.maxPixelRatio));

    this.scene.fog = new THREE.FogExp2(0x000000, cfg.fogDensity);
    this.camera = new THREE.PerspectiveCamera(cfg.camera.fov, 1, 0.1, 100);

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), cfg.bloom.strength, cfg.bloom.radius, cfg.bloom.threshold);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    // Job beacon
    const jobGeo = new THREE.SphereGeometry(0.32, 32, 16);
    this.job = new THREE.Mesh(jobGeo, new THREE.MeshBasicMaterial({ color: this.colors.beacon }));
    this.scene.add(this.job);

    const haloTex = this.makeGlowTexture();
    this.halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex, color: this.colors.beacon, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.halo.scale.setScalar(3.2);
    this.scene.add(this.halo);

    const pulseGeo = new THREE.RingGeometry(0.5, 0.56, 96);
    this.pulse = new THREE.Mesh(pulseGeo, new THREE.MeshBasicMaterial({ color: this.colors.beacon, transparent: true, side: THREE.DoubleSide, depthWrite: false }));
    this.pulse.rotation.x = -Math.PI / 2;
    this.scene.add(this.pulse);

    const shieldGeo = new THREE.TorusGeometry(1.25, 0.03, 12, 120);
    this.shield = new THREE.Mesh(shieldGeo, new THREE.MeshBasicMaterial({ color: this.colors.reject, transparent: true, opacity: 0 }));
    this.shield.rotation.x = -Math.PI / 2;
    this.scene.add(this.shield);

    const confirmGeo = new THREE.RingGeometry(0.62, 0.7, 96);
    this.confirmRing = new THREE.Mesh(confirmGeo, new THREE.MeshBasicMaterial({ color: this.colors.ok, transparent: true, opacity: 0, side: THREE.DoubleSide }));
    this.confirmRing.rotation.x = -Math.PI / 2;
    this.scene.add(this.confirmRing);

    // Worker panes on two rings; a deterministic subset races.
    const paneGeo = new THREE.BoxGeometry(0.46, 0.28, 0.03);
    const beamGeo = new THREE.CylinderGeometry(0.018, 0.018, 1, 8, 1, true);
    beamGeo.rotateX(Math.PI / 2); // align length with +Z so lookAt() aims the beam
    this.disposables.push(paneGeo, beamGeo, jobGeo, pulseGeo, shieldGeo, confirmGeo, haloTex);

    const rand = mulberry32(cfg.seed);
    const total = cfg.rings.reduce((n, r) => n + r.count, 0);
    const racing = new Set<number>();
    while (racing.size < cfg.racerCount) racing.add(Math.floor(rand() * total));
    const racingList = [...racing];
    const winner = racingList[0];
    const stale = racingList[1];

    let index = 0;
    for (const ring of cfg.rings) {
      for (let i = 0; i < ring.count; i++, index++) {
        const angle = (i / ring.count) * Math.PI * 2 + ring.offset;
        const origin = new THREE.Vector3(Math.cos(angle) * ring.radius, ring.height, Math.sin(angle) * ring.radius);
        const pane = new THREE.Mesh(paneGeo, new THREE.MeshBasicMaterial({ color: this.colors.idle.clone() }));
        pane.position.copy(origin);
        pane.lookAt(ORIGIN.x, ring.height, ORIGIN.z);
        this.scene.add(pane);

        const beam = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({ color: this.colors.hot.clone(), transparent: true, opacity: 0 }));
        beam.visible = false;
        this.scene.add(beam);

        const role: Racer["role"] = index === winner ? "winner" : index === stale ? "stale" : racing.has(index) ? "loser" : "idle";
        this.racers.push({ pane, beam, origin, role, speed: 0.6 + rand() * 0.35, bob: rand() * Math.PI * 2 });
      }
    }

    // Faint dotted "water" plane for depth.
    const pts: number[] = [];
    for (let x = -cfg.water.extent; x <= cfg.water.extent; x += cfg.water.step) {
      for (let z = -cfg.water.extent; z <= cfg.water.extent; z += cfg.water.step) pts.push(x, cfg.water.y, z);
    }
    const waterGeo = new THREE.BufferGeometry();
    waterGeo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    const waterMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.03, transparent: true, opacity: 0.22, depthWrite: false });
    this.water = new THREE.Points(waterGeo, waterMat);
    this.scene.add(this.water);
    this.disposables.push(waterGeo, waterMat);
  }

  resize(width: number, height: number) {
    this.renderer.setSize(width, height, false);
    this.composer.setSize(width, height);
    this.bloom.setSize(width, height);
    this.camera.aspect = width / height;
    // Narrow screens pull the camera back so both rings stay in frame.
    this.narrow = width / height < 1;
    this.camera.updateProjectionMatrix();
  }

  /** Draw one frame. p = scroll progress 0..1, t = seconds (idle motion only). */
  render(p: number, t: number) {
    const detected = phase(p, PHASE.detected[0], PHASE.detected[1]);
    const race = phase(p, PHASE.queued[0], PHASE.queued[1]);
    const lease = phase(p, PHASE.leased[0], PHASE.leased[1]);
    const fence = phase(p, PHASE.acting[0], PHASE.acting[1]);
    const confirm = phase(p, PHASE.confirmed[0], PHASE.confirmed[1]);

    // Camera: slow orbit + rise as the story progresses.
    const orbit = cfg.camera.orbitStart + p * cfg.camera.orbitSweep;
    const dist = this.narrow ? cfg.camera.distanceNarrow : cfg.camera.distance;
    this.camera.position.set(Math.sin(orbit) * dist, cfg.camera.height - p * cfg.camera.heightDrop, Math.cos(orbit) * dist);
    this.camera.lookAt(0, 0, 0);

    // Job beacon
    const pulseT = (t * 0.6) % 1;
    this.job.scale.setScalar(0.2 + detected * 0.8 + Math.sin(t * 3) * 0.03 * detected);
    this.job.material.color.copy(this.colors.beacon).lerp(this.colors.ok, confirm);
    this.halo.material.opacity = detected * (0.75 + 0.25 * Math.sin(t * 2.4));
    this.halo.material.color.copy(this.colors.beacon).lerp(this.colors.ok, confirm);
    this.pulse.scale.setScalar(1 + pulseT * 6 * detected);
    this.pulse.material.opacity = detected * (1 - pulseT) * 0.7 * (1 - confirm);
    this.confirmRing.material.opacity = confirm;
    this.confirmRing.scale.setScalar(1 + (1 - confirm) * 0.6);

    // Fencing shield flashes while the stale worker is rejected.
    const flash = Math.sin(Math.min(1, fence) * Math.PI);
    this.shield.material.opacity = flash * 0.9;
    this.shield.scale.setScalar(1 + flash * 0.08);

    for (const r of this.racers) {
      const bobY = Math.sin(t * 1.2 + r.bob) * 0.04;
      r.pane.position.y = r.origin.y + bobY;
      const mat = r.pane.material;

      if (r.role === "idle") {
        mat.color.copy(this.colors.idle).multiplyScalar(0.55 + 0.45 * (1 - race * 0.5));
        r.beam.visible = false;
        continue;
      }

      // Beam reach: racers advance at different speeds; the winner arrives first.
      const full = r.origin.length() - 0.4;
      // Losers stall short of the job: only the winner ever touches it.
      let reach = r.role === "winner" ? Math.min(1, race * cfg.winnerSpeed) : Math.min(cfg.loserMaxReach, race * r.speed);
      if (r.role !== "winner") reach *= 1 - lease; // losers retract once the lease is granted
      if (r.role === "winner") reach = Math.max(reach, lease);

      let beamColor = this.colors.hot;
      let paneColor = this.colors.hot;
      if (r.role === "winner") {
        beamColor = lease > 0.5 ? (confirm > 0.5 ? this.colors.ok : this.colors.beacon) : this.colors.hot;
        paneColor = beamColor;
      } else if (lease > 0.15) {
        beamColor = this.colors.reject;
        paneColor = this.colors.reject;
      }

      // The stale worker tries again during ACTING and is stopped at the shield.
      if (r.role === "stale" && fence > 0 && fence < 1) {
        reach = Math.min(1, fence * 2.2) * ((full - 1.25) / full);
        beamColor = this.colors.reject;
      }

      const settle = r.role === "winner" ? 0 : confirm;
      mat.color.copy(paneColor).lerp(this.colors.idle, settle);

      const length = full * reach;
      r.beam.visible = length > 0.02;
      if (r.beam.visible) {
        const dir = ORIGIN.clone().setY(r.pane.position.y).sub(r.pane.position).normalize();
        r.beam.position.copy(r.pane.position).addScaledVector(dir, length / 2);
        r.beam.lookAt(r.pane.position.clone().addScaledVector(dir, length));
        r.beam.scale.set(r.role === "winner" && lease > 0.5 ? 2.2 : 1, r.role === "winner" && lease > 0.5 ? 2.2 : 1, length);
        r.beam.material.color.copy(beamColor);
        r.beam.material.opacity = 0.95 * (1 - settle);
      }
    }

    this.water.rotation.y = t * 0.01;
    this.composer.render();
  }

  dispose() {
    this.racers.forEach((r) => {
      r.pane.material.dispose();
      r.beam.material.dispose();
    });
    [this.job.material, this.halo.material, this.pulse.material, this.shield.material, this.confirmRing.material].forEach((m) => m.dispose());
    this.disposables.forEach((d) => d.dispose());
    // EffectComposer.dispose() frees only its own targets; every pass owns render targets too.
    this.composer.passes.forEach((pass) => pass.dispose());
    this.composer.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  private makeGlowTexture() {
    const size = 128;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const ctx = c.getContext("2d");
    if (ctx) {
      const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.25, "rgba(255,255,255,0.45)");
      g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, size, size);
    }
    return new THREE.CanvasTexture(c);
  }
}

/** Small deterministic PRNG so the race looks the same on every visit. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
