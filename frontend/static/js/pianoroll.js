/**
 * piano-roll.js
 *
 * Falling-note visual tutorial ("keys light up as they're played"),
 * synced to an <audio> element's playback position. Pure canvas, no deps.
 *
 * Usage:
 *   const roll = new PianoRoll(canvasEl, audioEl, notes, {
 *     lookaheadSeconds: 4,   // how many seconds of "incoming" notes are visible above the keyboard
 *   });
 *   roll.start();
 *   // later, e.g. on view teardown:
 *   roll.destroy();
 *
 * `notes` is exactly transcriber.py's output shape:
 *   [{ pitch: 60, start: 0.0, end: 0.5, velocity: 80 }, ...]
 *
 * The canvas resizes itself to its CSS box (use CSS to size it, e.g.
 * `#tutorial-canvas { width: 100%; height: 420px; }`) — no need to set
 * width/height attributes yourself.
 */

class PianoRoll {
  constructor(canvas, audio, notes, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.audio = audio;
    this.notes = [...notes].sort((a, b) => a.start - b.start);

    this.lookaheadSeconds = opts.lookaheadSeconds ?? 4;
    this.keyboardHeightPx = opts.keyboardHeightPx ?? 90;

    // Pitch range: fit to the piece (with a little headroom) rather than
    // always drawing a full 88-key range the piece doesn't use.
    const pitches = this.notes.map((n) => n.pitch);
    this.minPitch = Math.max(21, Math.min(...pitches) - 2);
    this.maxPitch = Math.min(108, Math.max(...pitches) + 2);

    this._buildKeyLayout();

    this._raf = null;
    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(canvas);
    this._resize();
  }

  start() {
    if (this._raf) return; // already running
    const loop = () => {
      this._draw(this.audio.currentTime || 0);
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }

  stop() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  destroy() {
    this.stop();
    this._resizeObserver.disconnect();
  }

  /** Call this if you swap in a new piece without recreating the whole view. */
  setNotes(notes) {
    this.notes = [...notes].sort((a, b) => a.start - b.start);
    const pitches = this.notes.map((n) => n.pitch);
    this.minPitch = Math.max(21, Math.min(...pitches) - 2);
    this.maxPitch = Math.min(108, Math.max(...pitches) + 2);
    this._buildKeyLayout();
  }

  // ── layout ────────────────────────────────────────────────────────────

  _isBlackKey(pitch) {
    return [1, 3, 6, 8, 10].includes(pitch % 12);
  }

  _buildKeyLayout() {
    // White keys are laid out left-to-right at equal width; black keys are
    // drawn narrower, offset to sit between their neighboring white keys.
    this.whiteKeys = [];
    for (let p = this.minPitch; p <= this.maxPitch; p++) {
      if (!this._isBlackKey(p)) this.whiteKeys.push(p);
    }
    this.pitchToWhiteIndex = new Map(this.whiteKeys.map((p, i) => [p, i]));
  }

  _keyX(pitch, whiteKeyWidth) {
    if (!this._isBlackKey(pitch)) {
      return this.pitchToWhiteIndex.get(pitch) * whiteKeyWidth;
    }
    // Black key: anchor to the white key just below it, shifted right.
    const belowWhite = this.pitchToWhiteIndex.get(pitch - 1);
    return (belowWhite + 1) * whiteKeyWidth - whiteKeyWidth * 0.3;
  }

  _resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.cssWidth = rect.width;
    this.cssHeight = rect.height;
  }

  // ── drawing ───────────────────────────────────────────────────────────

  _draw(t) {
    const ctx = this.ctx;
    const W = this.cssWidth;
    const H = this.cssHeight;
    const rollH = H - this.keyboardHeightPx;
    const whiteKeyWidth = W / this.whiteKeys.length;

    const style = getComputedStyle(this.canvas);
    const bg = style.getPropertyValue("--piano-roll-bg").trim() || "#14161a";
    const bass = style.getPropertyValue("--piano-roll-bass").trim() || "#4fb3a9";
    const treble = style.getPropertyValue("--piano-roll-treble").trim() || "#e0a95e";
    const activeGlow = style.getPropertyValue("--piano-roll-active").trim() || "#ffffff";
    const whiteKeyColor = style.getPropertyValue("--piano-roll-white-key").trim() || "#f2f0eb";
    const blackKeyColor = style.getPropertyValue("--piano-roll-black-key").trim() || "#1c1c1c";

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, rollH);

    // Active notes this frame (for key highlighting). Notes are sorted by
    // start, so this window only ever scans forward from a moving pointer
    // rather than the whole list — cheap even for long pieces.
    if (this._activePointer === undefined) this._activePointer = 0;
    while (
      this._activePointer < this.notes.length - 1 &&
      this.notes[this._activePointer].end < t - 0.05
    ) {
      this._activePointer++;
    }
    const activePitches = new Set();

    // Falling note bars: only draw notes whose start falls within the
    // lookahead window, or that are still sounding.
    const windowStart = t;
    const windowEnd = t + this.lookaheadSeconds;
    for (const note of this.notes) {
      if (note.end < windowStart - 0.05) continue;
      if (note.start > windowEnd) break; // sorted by start — safe to stop
      if (note.start <= t && note.end >= t) activePitches.add(note.pitch);

      const x = this._keyX(note.pitch, whiteKeyWidth);
      const w = this._isBlackKey(note.pitch) ? whiteKeyWidth * 0.6 : whiteKeyWidth * 0.92;
      // y=rollH is "now" (the keyboard line); notes fall downward toward it.
      const yTop = rollH * (1 - (note.end - windowStart) / this.lookaheadSeconds);
      const yBottom = rollH * (1 - (note.start - windowStart) / this.lookaheadSeconds);
      const barH = Math.max(4, yBottom - yTop);

      ctx.fillStyle = note.pitch < 60 ? bass : treble;
      ctx.globalAlpha = note.start <= t && note.end >= t ? 1 : 0.85;
      ctx.beginPath();
      ctx.roundRect(x + w * 0.04, Math.max(0, yTop), w * 0.92, barH, 4);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    this._drawKeyboard(ctx, W, rollH, this.keyboardHeightPx, whiteKeyWidth, {
      whiteKeyColor,
      blackKeyColor,
      activeGlow,
      activePitches,
    });
  }

  _drawKeyboard(ctx, W, top, h, whiteKeyWidth, { whiteKeyColor, blackKeyColor, activeGlow, activePitches }) {
    // White keys first (full height), then black keys on top (shorter).
    for (const pitch of this.whiteKeys) {
      const x = this._keyX(pitch, whiteKeyWidth);
      const active = activePitches.has(pitch);
      ctx.fillStyle = active ? activeGlow : whiteKeyColor;
      ctx.fillRect(x, top, whiteKeyWidth - 1, h);
    }
    for (let p = this.minPitch; p <= this.maxPitch; p++) {
      if (!this._isBlackKey(p)) continue;
      const x = this._keyX(p, whiteKeyWidth);
      const active = activePitches.has(p);
      ctx.fillStyle = active ? activeGlow : blackKeyColor;
      ctx.fillRect(x, top, whiteKeyWidth * 0.6, h * 0.62);
    }
  }
}