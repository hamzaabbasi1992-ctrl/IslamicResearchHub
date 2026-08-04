"""Split page text into TTS-sized chunks for progressive/streaming narration.

`MmsTtsSpeaker`'s underlying model (`transformers.VitsModel`, a single
non-autoregressive forward pass) has no native streaming/incremental-decode
API - the only real lever for "start playback sooner" is synthesizing
smaller pieces of text instead of a whole page at once. This module owns
the text-splitting side of that; the actual per-chunk synthesis stays in
`PageNarrationService`/`TtsWorker`.
"""

DEFAULT_MAX_CHUNK_CHARACTERS = 320
"""~320 chars synthesizes in ~12-13s at the measured ~3.1x-realtime CPU
speed (a ~250-char sample takes ~10s - see CHANGELOG) - cuts the cold
79s-to-first-sound wait roughly 6x, while the measured 1,978-char worst
case real page still only becomes ~6-7 chunks, not dozens of jarring
transitions."""

_SENTENCE_END_CHARACTERS = ".!?۔؟؛"
"""Latin '.', '!', '?' plus Arabic/Urdu equivalents - '۔' Urdu full stop,
'؟' Arabic question mark, '؛' Arabic semicolon - real sentence-ending
punctuation for this corpus's three languages, not just Latin ones."""

_HEADING_PREFIX = "## "
"""Matches `paragraphs_backfill_cli._HEADING_PREFIX` - the same marker
`strip_html_to_text` promotes a bold span's line to."""


def chunk_narration_text(
    plain_text: str, max_characters: int = DEFAULT_MAX_CHUNK_CHARACTERS
) -> tuple[str, ...]:
    """Split HTML-stripped page text into TTS-sized chunks.

    `plain_text` must still carry its real `"\\n"` line/heading
    boundaries from `strip_html_to_text` - not yet whitespace-collapsed.
    Those boundaries are chunk boundaries first; a long line with none
    (confirmed the majority of the corpus - most real pages are one flat
    block) is split on sentence punctuation, greedily packed up to
    `max_characters`; a single "sentence" still over the cap is hard-cut
    on word boundaries.
    """
    chunks: list[str] = []
    for line in plain_text.split("\n"):
        normalized_line = " ".join(line.split())
        if normalized_line.startswith(_HEADING_PREFIX):
            normalized_line = normalized_line[len(_HEADING_PREFIX):].strip()
        if not normalized_line:
            continue
        chunks.extend(_pack_sentences(_split_sentences(normalized_line), max_characters))
    return tuple(chunks)


def _split_sentences(line: str) -> list[str]:
    """Split one line into sentences, keeping the ending punctuation attached."""
    sentences: list[str] = []
    start = 0
    for index, character in enumerate(line):
        if character in _SENTENCE_END_CHARACTERS:
            sentence = line[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    remainder = line[start:].strip()
    if remainder:
        sentences.append(remainder)
    return sentences


def _pack_sentences(sentences: list[str], max_characters: int) -> list[str]:
    """Greedily pack sentences into chunks no longer than `max_characters`."""
    packed: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(sentence) > max_characters:
            if buffer:
                packed.append(buffer)
                buffer = ""
            packed.extend(_hard_cut(sentence, max_characters))
            continue
        candidate = f"{buffer} {sentence}".strip()
        if buffer and len(candidate) > max_characters:
            packed.append(buffer)
            buffer = sentence
        else:
            buffer = candidate
    if buffer:
        packed.append(buffer)
    return packed


def _hard_cut(text: str, max_characters: int) -> list[str]:
    """Word-boundary greedy pack for one unpunctuated run still over the cap.

    A single "word" alone longer than `max_characters` is sliced by raw
    character count as the absolute last resort, so no chunk is ever
    unbounded.
    """
    pieces: list[str] = []
    buffer = ""
    for word in text.split():
        if len(word) > max_characters:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            pieces.extend(word[i : i + max_characters] for i in range(0, len(word), max_characters))
            continue
        candidate = f"{buffer} {word}".strip()
        if buffer and len(candidate) > max_characters:
            pieces.append(buffer)
            buffer = word
        else:
            buffer = candidate
    if buffer:
        pieces.append(buffer)
    return pieces
