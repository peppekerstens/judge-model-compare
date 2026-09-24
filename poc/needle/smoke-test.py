import json, time, needle

DIFF = ("How hard is this request for a language model? Judge the reasoning that the answer "
        "needs, not the length of the text.")
LEVELS = {"simple": "A fact, a definition, a short rewrite, a translation or a greeting.",
          "medium": "A short explanation, a small piece of code, a summary or a comparison.",
          "hard": "A multi-step analysis, a design question, a proof or a trade-off."}
SENS = ("Does the conversation contain personal data or sensitive information? Personal data is a "
        "name, an address, a bank or a medical detail. Sensitive information is a password, an API "
        "key or an internal address.")
CASES = [("simple", "What is the capital of France?"),
         ("hard", "Design a fault-tolerant job queue for a 3-node cluster. Compare at-least-once and "
                  "exactly-once delivery, and explain the trade-offs."),
         ("sensitive", "My colleague Jan de Vries lives at Kerkstraat 12 in Utrecht. Write a "
                       "one-line greeting for his birthday card.")]

def call(tools, system, text):
    agent = needle.Needle(tools=tools, system=system)
    started = time.perf_counter()
    out = agent.complete(text, max_new_tokens=128)
    seconds = time.perf_counter() - started
    agent.close()
    calls = out.get("function_calls") or []
    supp = out.get("suppressed_calls") or []
    return {"seconds": round(seconds, 3), "calls": calls, "suppressed": supp,
            "confidence": out.get("confidence"), "reasoning": (out.get("reasoning") or "")[:70],
            "peak_ram_mb": out.get("peak_ram_mb")}

record_tool = [{"name": "record_decision",
                "description": "Record the answer to this question about the text: " + DIFF,
                "parameters": {"type": "object", "properties": {"decision": {
                    "type": "string", "enum": list(LEVELS),
                    "description": DIFF + " Options: " + "; ".join(f"{k}: {v}" for k, v in LEVELS.items())}},
                    "required": ["decision"]}}]
option_tools = [{"name": k, "description": v,
                 "parameters": {"type": "object", "properties": {}, "required": []}} for k, v in LEVELS.items()]
sens_tool = [{"name": "record_decision",
              "description": "Record the answer to this question about the text: " + SENS,
              "parameters": {"type": "object", "properties": {"decision": {
                  "type": "boolean", "description": SENS}}, "required": ["decision"]}}]

for name, text in CASES:
    print("==", name, "|", text[:45])
    for mode, tools, system in (("record_decision", record_tool, DIFF),
                                ("options_as_tools", option_tools, DIFF),
                                ("sensitive", sens_tool, SENS)):
        r = call(tools, system, text)
        answer = (r["calls"][0].get("name") if mode == "options_as_tools"
                  else (r["calls"][0].get("arguments") or {}).get("decision")) if r["calls"] else None
        print(f"   {mode:17s} answer={str(answer):8s} {r['seconds']:.2f}s conf={r['confidence']} "
              f"supp={len(r['suppressed'])} ram={r['peak_ram_mb']} why={r['reasoning']}")
