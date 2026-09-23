import json
import unittest

from jev_router.deciders import (
    Candidate,
    JevDecider,
    RulesDecider,
    eligible,
    has_image,
    requested_max_output,
    summarize,
)

CANDIDATES = [
    Candidate(name="cheap", description="cheap", price_in=0.1, price_out=0.5),
    Candidate(name="mid", description="mid", price_in=1.0, price_out=3.0),
    Candidate(
        name="vision",
        description="vision",
        vision=True,
        max_output=200000,
        price_in=5.0,
        price_out=15.0,
    ),
    Candidate(
        name="small",
        description="small",
        max_output=1000,
        price_in=0.05,
        price_out=0.2,
    ),
]


def image_messages():
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is this?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AAAA"},
                },
            ],
        }
    ]


class SummarizeTests(unittest.TestCase):
    def test_detects_images_only_in_user_messages(self):
        self.assertTrue(has_image(image_messages()))
        self.assertFalse(
            has_image([{"role": "assistant", "content": image_messages()[0]["content"]}])
        )

    def test_minimizes_and_flags_signals(self):
        summary = summarize(image_messages(), tools=[{"type": "function"}], max_output=42)
        self.assertTrue(summary.has_image)
        self.assertTrue(summary.has_tools)
        self.assertEqual(summary.requested_max_output, 42)
        self.assertEqual(summary.message_count, 1)
        self.assertIn("[image]", summary.messages[0]["text"])

    def test_reads_max_completion_tokens_first(self):
        self.assertEqual(
            requested_max_output({"max_tokens": 10, "max_completion_tokens": 20}), 20
        )


class EligibilityTests(unittest.TestCase):
    def test_excludes_non_vision_when_image_present(self):
        names = {c.name for c in eligible(CANDIDATES, summarize(image_messages()))}
        self.assertEqual(names, {"vision"})

    def test_excludes_models_with_too_small_output(self):
        summary = summarize([{"role": "user", "content": "hi"}], max_output=5000)
        names = {c.name for c in eligible(CANDIDATES, summary)}
        self.assertNotIn("small", names)


class RulesDeciderTests(unittest.TestCase):
    def test_picks_cheapest_eligible(self):
        summary = summarize([{"role": "user", "content": "hi"}])
        chosen = asyncio_run(RulesDecider("mid").decide(summary, CANDIDATES))
        self.assertEqual(chosen, "small")

    def test_falls_back_when_nothing_eligible(self):
        summary = summarize(image_messages(), max_output=999999)
        chosen = asyncio_run(RulesDecider("mid").decide(summary, eligible(CANDIDATES, summary)))
        self.assertEqual(chosen, "mid")


def jev_response(choice):
    return json.dumps({"answers": {"model": {"type": "choice", "choice": choice, "confidence": 0.8}}}).encode()


class JevDeciderTests(unittest.IsolatedAsyncioTestCase):
    def decider(self, fetch, fallback="mid"):
        return JevDecider(api_key="test", fallback=fallback, fetch=fetch)

    async def test_returns_choice(self):
        async def run():
            summary = summarize([{"role": "user", "content": "hi"}])
            return await self.decider(lambda *_: (200, jev_response("mid"))).decide(
                summary, eligible(CANDIDATES, summary)
            )

        self.assertEqual(await run(), "mid")

    async def test_falls_back_on_error(self):
        def boom(*_):
            raise RuntimeError("network down")

        summary = summarize([{"role": "user", "content": "hi"}])
        chosen = await self.decider(boom).decide(summary, eligible(CANDIDATES, summary))
        self.assertEqual(chosen, "mid")

    async def test_falls_back_on_out_of_set_choice(self):
        summary = summarize([{"role": "user", "content": "hi"}])
        chosen = await self.decider(
            lambda *_: (200, jev_response("unknown-model"))
        ).decide(summary, eligible(CANDIDATES, summary))
        self.assertEqual(chosen, "mid")

    async def test_sends_only_eligible_criteria(self):
        captured = {}

        def capture(_url, _headers, body, _timeout):
            captured["criteria"] = set(
                json.loads(body)["questions"]["model"]["criteria"]
            )
            return 200, jev_response("vision")

        summary = summarize(image_messages())
        await self.decider(capture).decide(summary, eligible(CANDIDATES, summary))
        self.assertEqual(captured["criteria"], {"vision"})


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
