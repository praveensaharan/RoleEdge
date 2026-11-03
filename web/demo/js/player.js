// Plays a list of steps in order on the stage: play, pause, and start again with load().

import { wait } from "./dom.js";

export function createPlayer({ stage, onStep, onDone }) {
  let steps = [], index = 0, playing = false, running = false, token = 0, resume = null;

  async function loop(myToken) {
    while (index < steps.length) {
      if (!playing) await new Promise((done) => { resume = done; });
      if (myToken !== token) return;
      const step = steps[index];
      onStep(index, step);
      await stage.run(step);
      if (myToken !== token) return;
      await wait(step.hold ?? 1100);
      if (myToken !== token) return;
      index += 1;
    }
    playing = false;
    onDone();
  }

  function start() {
    if (running) return;
    running = true;
    const myToken = token;
    loop(myToken).finally(() => { if (myToken === token) running = false; });
  }

  return {
    load(next) {
      token += 1; // stops the old loop at its next check
      steps = next;
      index = 0;
      playing = false;
      running = false;
      resume?.();
      resume = null;
    },
    play() {
      playing = true;
      const go = resume;
      resume = null;
      if (go) go(); else start();
    },
    pause() { playing = false; },
    isPlaying: () => playing,
    isDone: () => index >= steps.length,
  };
}
