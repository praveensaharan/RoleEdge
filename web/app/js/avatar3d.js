// The 3D talking avatar: a VRM character rendered with three.js. Everything that moves it is plain code, not an AI
// model call (hackathon rule): vowel mouth shapes from the text being spoken (Japanese kana map to their vowel,
// English letters to the nearest one), blinking, breathing, a little head movement, and eyes that follow the camera.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { hush, speakNaturally } from "./voice.js";

const VOWEL_OF = {};
for (const [vowel, kana] of Object.entries({
  aa: "あかさたなはまやらわがざだばぱぁゃアカサタナハマヤラワガザダバパァャ",
  ih: "いきしちにひみりぎじぢびぴぃイキシチニヒミリギジヂビピィ",
  ou: "うくすつぬふむゆるぐずづぶぷぅゅっウクスツヌフムユルグズヅブプゥュッ",
  ee: "えけせてねへめれげぜでべぺぇエケセテネヘメレゲゼデベペェ",
  oh: "おこそとのほもよろをごぞどぼぽぉょオコソトノホモヨロヲゴゾドボポォョ",
})) for (const ch of kana) VOWEL_OF[ch] = vowel;
Object.assign(VOWEL_OF, { a: "aa", e: "ee", i: "ih", o: "oh", u: "ou", y: "ih", w: "ou" });
const VISEMES = ["aa", "ih", "ou", "ee", "oh"];
const PAUSES = /[、。,.!?！？\n]/;

/** Load a VRM into a canvas and start rendering; resolves to a TalkingHead3D, or null if it can't load. */
export async function loadAvatar3D(canvas, url) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(22, 4 / 3, 0.1, 20);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8dbe2, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(0.6, 1.8, 1.6);
  scene.add(key);

  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  let gltf;
  try { gltf = await loader.loadAsync(url); } catch { renderer.dispose(); return null; }
  const vrm = gltf.userData.vrm;
  VRMUtils.removeUnnecessaryVertices(gltf.scene);
  VRMUtils.combineSkeletons?.(gltf.scene);
  VRMUtils.rotateVRM0(vrm); // VRM 0.x models face the other way
  scene.add(vrm.scene);
  return new TalkingHead3D(renderer, scene, camera, vrm, canvas);
}

export class TalkingHead3D {
  constructor(renderer, scene, camera, vrm, canvas) {
    Object.assign(this, { renderer, scene, camera, vrm, canvas });
    this.clock = new THREE.Clock();
    this.speaking = false;
    this.weights = Object.fromEntries(VISEMES.map((v) => [v, 0]));
    this.target = { viseme: null, strength: 0 };
    this.nextBlink = 1.5;
    this.blinkT = -1;
    this.pose();
    this.frame();
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
  }

  bone(name) { return this.vrm.humanoid.getNormalizedBoneNode(name); }

  pose() {
    // arms down from the T-pose, and frame the head and shoulders
    this.bone("leftUpperArm").rotation.z = 1.25;
    this.bone("rightUpperArm").rotation.z = -1.25;
    this.bone("leftLowerArm").rotation.z = 0.12;
    this.bone("rightLowerArm").rotation.z = -0.12;
    this.vrm.update(0);
    const head = new THREE.Vector3();
    this.bone("head").getWorldPosition(head);
    this.lookTarget = new THREE.Object3D();
    this.lookTarget.position.set(0, head.y + 0.02, 2);
    this.scene.add(this.lookTarget);
    if (this.vrm.lookAt) this.vrm.lookAt.target = this.lookTarget;
    this.camera.position.set(0, head.y - 0.02, 1.05);
    this.camera.lookAt(0, head.y - 0.05, 0);
    this.expressions?.setValue?.("relaxed", 0.25);
  }

  get expressions() { return this.vrm.expressionManager; }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  frame() {
    requestAnimationFrame(() => this.frame());
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.elapsedTime;
    // breathing and a little head movement; a bit more while talking
    const lively = this.speaking ? 1.6 : 1;
    this.bone("chest") && (this.bone("chest").rotation.x = Math.sin(t * 1.4) * 0.012);
    this.bone("head").rotation.y = Math.sin(t * 0.7) * 0.05 * lively;
    this.bone("head").rotation.z = Math.sin(t * 0.5 + 1) * 0.025 * lively;
    this.bone("head").rotation.x = Math.sin(t * 0.9 + 2) * 0.02 * lively - 0.03;
    // blinking every few seconds
    this.nextBlink -= dt;
    if (this.nextBlink <= 0 && this.blinkT < 0) { this.blinkT = 0; this.nextBlink = 2.2 + Math.random() * 3.5; }
    let blink = 0;
    if (this.blinkT >= 0) { this.blinkT += dt; blink = Math.sin(Math.min(1, this.blinkT / 0.16) * Math.PI); if (this.blinkT > 0.16) this.blinkT = -1; }
    // mouth: ease each vowel shape towards its target
    for (const v of VISEMES) {
      const goal = this.target.viseme === v ? this.target.strength : 0;
      this.weights[v] += (goal - this.weights[v]) * Math.min(1, dt * 18);
      this.expressions?.setValue(v, this.weights[v]);
    }
    this.expressions?.setValue("blink", blink);
    this.vrm.update(dt);
    this.renderer.render(this.scene, this.camera);
  }

  /** A still picture of the avatar (for the small faces in the chat). */
  snapshot() { this.renderer.render(this.scene, this.camera); return this.canvas.toDataURL("image/png"); }

  /** Same interface as the 2D TalkingHead: speak ``text`` with the browser voice, moving the mouth as it goes. */
  speak(text, { lang, voiceIndex = 0, rate = 0.92, gender = "", onProgress = () => {} } = {}) {
    this.stop();
    const cps = (lang.startsWith("ja") ? 7.5 : 14) * rate; // characters a second, to move the mouth between word marks
    let pointer = 0;
    let phrase = null; // the phrase being said, or null in a pause (the mouth rests)
    this.speaking = true;
    const timer = setInterval(() => {
      if (phrase) pointer = Math.max(pointer, Math.min(phrase.end, phrase.start + Math.floor((performance.now() - phrase.at) / 1000 * cps * (phrase.rate / rate))));
      onProgress(pointer);
      const ch = (text[pointer] || "").toLowerCase();
      if (!phrase || !ch || PAUSES.test(ch)) this.target = { viseme: null, strength: 0 };
      else this.target = { viseme: VOWEL_OF[ch] || (Math.random() < 0.5 ? "aa" : "ih"), strength: VOWEL_OF[ch] ? 0.85 : 0.35 };
    }, 80);
    this.timer = timer;
    const said = speakNaturally(text, { lang, rate, gender, pick: voiceIndex,
      onState: (s) => { pointer = Math.max(pointer, s.index); phrase = s.talking ? { start: s.phraseStart, end: s.phraseStart + s.phraseLength, at: s.startedAt, rate: s.rate } : null; },
      onBoundary: (i) => { pointer = Math.max(pointer, i); if (phrase) phrase.at = performance.now() - (i - phrase.start) / cps * 1000; } });
    const finish = () => { // only this speech's own timer: a newer speech may already be running
      clearInterval(timer);
      if (this.timer !== timer) return;
      this.speaking = false; this.target = { viseme: null, strength: 0 }; onProgress(text.length);
    };
    this.finish = () => { hush(); finish(); };
    return said.then(() => finish());
  }

  /** Play an audio file (for example a recorded or cloned voice) and move the mouth with its loudness. */
  speakAudio(url, { onProgress = () => {} } = {}) {
    this.stop();
    return new Promise((resolve) => {
      const audio = new Audio(url);
      audio.crossOrigin = "anonymous";
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaElementSource(audio).connect(analyser);
      analyser.connect(ctx.destination);
      const data = new Uint8Array(analyser.fftSize);
      let turn = 0;
      let done = false; // ended, failed or stopped: whichever comes first
      const finish = () => { if (done) return; done = true; this.speaking = false; clearInterval(this.timer); this.target = { viseme: null, strength: 0 }; ctx.close().catch(() => {}); onProgress(1); resolve(); };
      audio.onended = finish;
      audio.onerror = finish;
      this.finish = () => { audio.pause(); finish(); };
      this.speaking = true;
      this.timer = setInterval(() => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const v of data) sum += ((v - 128) / 128) ** 2;
        const loud = Math.min(1, Math.sqrt(sum / data.length) * 6);
        if (loud > 0.08 && turn++ % 2 === 0) this.target = { viseme: VISEMES[Math.floor(Math.random() * VISEMES.length)], strength: loud };
        else if (loud <= 0.08) this.target = { viseme: null, strength: 0 };
        else this.target.strength = loud;
        onProgress(audio.duration ? audio.currentTime / audio.duration : 0);
      }, 70);
      audio.play().catch(finish); // the browser refused (no tap yet): don't hang
    });
  }

  stop() {
    if (this.speaking) { hush(); this.finish?.(); }
    clearInterval(this.timer);
    this.speaking = false;
    this.target = { viseme: null, strength: 0 };
  }
}
