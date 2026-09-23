# Benchmarks

The point of a router is a better quality-per-dollar than a fixed model. That is
a claim you have to measure, not assert.

## Go / no-go

Run the same mixed workload twice:

1. **Routed** — `model: "jev-router"`.
2. **Pinned** — a single baseline model (e.g. the strongest candidate).

Compare, on the same tasks and graders:

| Metric | Why |
| --- | --- |
| Quality (pass rate / score) | The routed run must not be worse beyond a chosen tolerance |
| Cost (USD) | The whole point: routed should be materially cheaper |
| Latency (p50/p90) | Routing adds a Jev round trip; know the overhead |

Verdict: ship only if routed keeps quality within tolerance *and* cuts cost. If a
trivial baseline (cheapest-eligible) matches Jev, the decision model isn't
earning its place.

## Suggested workloads

- A coding-agent task suite (SWE-style) run through a real harness.
- A mixed chat/coding/extraction set for breadth.
- A capability set: image input, tools, long context — to confirm filtering.

Not implemented yet. This is the first thing to build after the proxy is wired.
