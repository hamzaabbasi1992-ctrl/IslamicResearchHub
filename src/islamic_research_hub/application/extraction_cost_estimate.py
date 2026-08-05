"""Rough real-dollar cost estimate for event extraction, shown to the
user before any paid API call is made - the first per-click-metered-cost
feature in this app, so a real estimate (not a surprise bill) matters.
"""

_CHARACTERS_PER_TOKEN = 2.5
"""Arabic/Urdu-heavy text tokenizes less efficiently than English -
~2.5 characters per token is a reasonable approximation for this corpus,
not a precise measurement."""

_OVERHEAD_TOKENS_PER_CHUNK = 400
"""Each chunk repeats the system prompt/tool-call scaffolding - a real,
roughly fixed per-call overhead on top of that chunk's own page text
(not a percentage of it, since the overhead itself doesn't grow with
chunk size)."""

_OUTPUT_TO_INPUT_RATIO = 0.20
"""Structured JSON output is typically much smaller than the source text
it's extracted from - ~20% is a reasonable approximation."""

APPROXIMATE_PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "anthropic": (2.0, 10.0),
    "openai": (2.5, 15.0),
    "gemini": (1.0, 6.0),
}
"""(input, output) dollars per million tokens - approximate, current as
of this feature's build date. Provider pricing drifts over time; this is
a rough estimate for the confirmation dialog, never a billing guarantee."""

_DEFAULT_PRICING = (2.5, 15.0)
"""Used for an unrecognized provider code - a conservative (higher-end)
fallback rather than silently estimating $0."""


def estimate_extraction_cost(total_characters: int, chunk_count: int, provider: str) -> float:
    """Return a rough estimated dollar cost for extracting events from
    `total_characters` of real book text, split across `chunk_count`
    chunks, using `provider`'s approximate current pricing."""
    if total_characters <= 0 or chunk_count <= 0:
        return 0.0
    input_price, output_price = APPROXIMATE_PRICING_PER_MILLION_TOKENS.get(provider, _DEFAULT_PRICING)
    base_tokens = total_characters / _CHARACTERS_PER_TOKEN
    input_tokens = base_tokens + (chunk_count * _OVERHEAD_TOKENS_PER_CHUNK)
    output_tokens = base_tokens * _OUTPUT_TO_INPUT_RATIO
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
