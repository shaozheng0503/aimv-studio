"""MusicAnalyzer — Extracts structured metadata from audio for driving MV generation.

Components:
1. BPM / beat detection (librosa)
2. Song structure segmentation (intro/verse/chorus/bridge/outro)
3. Vocal separation (htdemucs via CLI)
4. Lyrics alignment (faster-whisper)
5. Mood/energy curve extraction
"""

import subprocess
import tempfile
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class Beat:
    time: float  # seconds
    strength: float  # 0-1


@dataclass
class Section:
    label: str  # intro / verse / chorus / bridge / outro / instrumental
    start: float
    end: float
    energy: float  # average energy 0-1


@dataclass
class LyricLine:
    text: str
    start: float
    end: float


@dataclass
class MusicAnalysis:
    bpm: float = 0.0
    duration: float = 0.0
    beats: list[Beat] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    lyrics: list[LyricLine] = field(default_factory=list)
    energy_curve: list[float] = field(default_factory=list)
    vocal_path: str = ""
    instrumental_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_beat_map(self) -> list[float]:
        """Returns list of beat timestamps for video cut point alignment."""
        return [b.time for b in self.beats]

    def to_srt(self) -> str:
        """Convert transcribed lyrics to SRT subtitle format."""
        def _fmt(s: float) -> str:
            h, rem = divmod(int(s), 3600)
            m, sec = divmod(rem, 60)
            ms = int((s % 1) * 1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        blocks: list[str] = []
        for i, line in enumerate(self.lyrics, 1):
            blocks.append(f"{i}\n{_fmt(line.start)} --> {_fmt(line.end)}\n{line.text}")
        return "\n\n".join(blocks)


class MusicAnalyzer:
    def __init__(self, audio_path: str):
        self.audio_path = Path(audio_path)
        self._analysis = MusicAnalysis()
        # Cached audio data — loaded once in _load(), reused by all analysis methods
        self._y = None
        self._sr: int = 22050
        # Temp dir created internally by separate_vocals; caller must call cleanup()
        self._owned_temp_dir: str | None = None

    def _load(self):
        """Load audio file once; subsequent calls are no-ops."""
        if self._y is not None:
            return
        import librosa
        self._y, self._sr = librosa.load(str(self.audio_path), sr=22050)
        self._analysis.duration = float(librosa.get_duration(y=self._y, sr=self._sr))

    def analyze(self) -> MusicAnalysis:
        """Run full analysis pipeline. Audio is loaded only once.

        Each stage degrades gracefully: a failure (e.g. audio too short for the
        recurrence window, or silent audio) leaves that field empty instead of
        crashing the caller's planning pipeline.
        """
        self._load()
        try:
            self._detect_bpm_and_beats()
        except Exception:
            self._analysis.bpm = 0.0
            self._analysis.beats = []
        try:
            self._segment_structure()
        except Exception:
            self._analysis.sections = []
        try:
            self._extract_energy_curve()
        except Exception:
            pass
        return self._analysis

    def cleanup(self) -> None:
        """Remove any temp directory created internally by separate_vocals."""
        if self._owned_temp_dir:
            import shutil
            shutil.rmtree(self._owned_temp_dir, ignore_errors=True)
            self._owned_temp_dir = None

    def separate_vocals(self, output_dir: str | None = None) -> tuple[str, str]:
        """Separate vocals from instrumental using htdemucs."""
        if output_dir is None:
            out = tempfile.mkdtemp()
            self._owned_temp_dir = out
        else:
            out = output_dir
        try:
            subprocess.run(
                ["python3", "-m", "demucs", "--two-stems", "vocals", "-o", out, str(self.audio_path)],
                check=True,
                capture_output=True,
            )
            stem_dir = Path(out) / "htdemucs" / self.audio_path.stem
            vocal = str(stem_dir / "vocals.wav")
            instrumental = str(stem_dir / "no_vocals.wav")
            self._analysis.vocal_path = vocal
            self._analysis.instrumental_path = instrumental
            return vocal, instrumental
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Demucs not installed, return original
            return str(self.audio_path), ""

    def transcribe_lyrics(self, audio_path: str | None = None) -> list[LyricLine]:
        """Transcribe lyrics with timestamps using faster-whisper."""
        target = audio_path or self._analysis.vocal_path or str(self.audio_path)
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", compute_type="int8")
            segments, _ = model.transcribe(target, word_timestamps=True)
            lyrics = []
            for seg in segments:
                lyrics.append(LyricLine(text=seg.text.strip(), start=seg.start, end=seg.end))
            self._analysis.lyrics = lyrics
            return lyrics
        except ImportError:
            return []

    def _detect_bpm_and_beats(self):
        import librosa
        self._load()
        y, sr = self._y, self._sr
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        self._analysis.bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        # Guard against silent audio where onset_env.max() == 0 → division by zero.
        onset_peak = float(onset_env.max()) or 1.0
        self._analysis.beats = [
            Beat(time=float(t), strength=min(1.0, float(onset_env[f]) / onset_peak))
            for t, f in zip(beat_times, beat_frames)
            if f < len(onset_env)
        ]

    def _segment_structure(self):
        """Segment song structure using MFCC+chroma recurrence matrix + agglomerative clustering.

        Boundaries are detected from audio feature similarity (not fixed windows).
        Labels are assigned by energy: intro/outro for first/last, chorus for high-energy
        segments, bridge for the mid-song low-energy segment, verse for the rest.
        """
        import librosa
        import numpy as np

        self._load()
        y, sr = self._y, self._sr
        duration = self._analysis.duration
        hop_length = 512

        # Too-short audio can't be segmented reliably — leave sections empty so
        # the planner falls back to uniform shot timing rather than crashing.
        if duration < 10.0:
            return

        # --- Feature extraction ---
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12, hop_length=hop_length)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
        features = librosa.util.normalize(
            np.vstack([mfcc, chroma]), norm=2, axis=0
        )
        n_frames = features.shape[1]
        if n_frames < 8:
            return

        # --- Recurrence matrix + agglomerative boundary detection ---
        # width must stay below the frame count or librosa raises.
        width = min(43, max(3, n_frames // 4))
        R = librosa.segment.recurrence_matrix(
            features, width=width, mode="affinity", sym=True
        )
        # Number of segments: ~1 per 20 s, clamped to [4, 10] and never more than
        # the available frames allow.
        k = max(4, min(10, int(duration / 20)))
        k = min(k, n_frames - 1)
        bounds = librosa.segment.agglomerative(R, k)
        bound_times = librosa.frames_to_time(bounds, sr=sr, hop_length=hop_length)
        # agglomerative already emits frame 0 as its first boundary, so the explicit
        # 0.0 prepended below would duplicate it. Dedupe and drop sub-0.5 s slivers
        # so we never emit a zero-length intro that shifts every later label.
        bound_times = np.concatenate([[0.0], bound_times, [duration]])
        bound_times = np.unique(np.round(bound_times, 2))
        merged = [float(bound_times[0])]
        for t in bound_times[1:]:
            if float(t) - merged[-1] >= 0.5:
                merged.append(float(t))
        if merged[-1] < duration:
            merged.append(duration)
        bound_times = np.array(merged)
        # Degenerate result (collapsed to <2 segments) → fall back to ~8 s uniform
        # slices, matching the documented degradation path.
        if len(bound_times) - 1 < 2:
            n_uniform = max(2, int(round(duration / 8.0)))
            bound_times = np.linspace(0.0, duration, n_uniform + 1)

        # --- Per-segment RMS energy for label assignment ---
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        n_frames = len(rms)

        energies: list[float] = []
        for i in range(len(bound_times) - 1):
            f0 = min(int(librosa.time_to_frames(bound_times[i], sr=sr, hop_length=hop_length)), n_frames)
            f1 = min(int(librosa.time_to_frames(bound_times[i + 1], sr=sr, hop_length=hop_length)), n_frames)
            seg_energy = float(np.mean(rms[f0:f1])) if f1 > f0 else 0.0
            energies.append(seg_energy)

        if not energies:
            return

        energy_high = float(np.percentile(energies, 65))
        n = len(energies)
        mid = n // 2

        sections: list[Section] = []
        for i, energy in enumerate(energies):
            if i == 0:
                label = "intro"
            elif i == n - 1:
                label = "outro"
            elif energy >= energy_high:
                label = "chorus"
            elif i == mid and n > 5:
                label = "bridge"
            else:
                label = "verse"

            sections.append(Section(
                label=label,
                start=round(float(bound_times[i]), 2),
                end=round(float(bound_times[i + 1]), 2),
                energy=round(energy, 4),
            ))
        self._analysis.sections = sections

    def _extract_energy_curve(self):
        """Extract per-second energy for mood/intensity visualization."""
        import numpy as np
        self._load()
        y, sr = self._y, self._sr
        hop = sr  # 1 second windows
        curve = []
        for i in range(0, len(y), hop):
            chunk = y[i:i + hop]
            if len(chunk) < sr // 2:
                break
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            curve.append(round(rms, 4))
        # Normalize to 0-1
        if curve:
            max_val = max(curve)
            if max_val > 0:
                curve = [round(v / max_val, 3) for v in curve]
        self._analysis.energy_curve = curve
