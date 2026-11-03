"""SAM 3.1 box records are read correctly, and voice features are measured from a reply's audio."""

import array
import io
import math
import wave

from roleedge.llm.meta_media import _BOX, _box
from roleedge.replies.voice import measure


def test_sam_box_records_are_parsed_by_key():
    text = "<0f>7,<|box;x1=682;y1=922;x2=923;y2=994;w=1600;h=1600|><|mask;x=0;y=0;data=4,4,~abc|>"
    boxes = [_box(m.group(1)) for m in _BOX.finditer(text)]
    assert len(boxes) == 1
    assert (boxes[0].x1, boxes[0].y2, boxes[0].width) == (682, 994, 1600)
    assert boxes[0].center == (802.5, 958.0)


def _wav(pattern: list[tuple[float, bool]], rate: int = 16000) -> bytes:
    samples = array.array("h")
    for seconds, loud in pattern:
        for i in range(int(seconds * rate)):
            samples.append(int(8000 * math.sin(2 * math.pi * 220 * i / rate)) if loud else 0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def test_voice_features_measure_span_pauses_and_pace():
    wav = _wav([(0.5, False), (2.0, True), (1.0, False), (2.0, True), (0.5, False)])  # 5 s of speech, 1 s pause
    features = measure(wav, "one two three four five six seven eight nine ten", "en")
    assert 4.8 <= features.seconds <= 5.2
    assert 0.17 <= features.pause_ratio <= 0.23
    assert 110 <= features.pace <= 130  # 10 words in about 5 s


def test_japanese_pace_counts_characters():
    wav = _wav([(3.0, True)])
    assert measure(wav, "今日は誰とも話してない。", "ja").pace > measure(wav, "today", "en").pace
