import unittest
from types import SimpleNamespace

from guardian.classifier import (
    POLICIES,
    SafetyDecision,
    classify_content,
    parse_specialized_decision,
    resolve_guardian_mode,
)


class _SpecializedCompletions:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content=self.response)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _PromptedCompletions:
    def __init__(self, decision):
        self.decision = decision
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(parsed=self.decision)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class GuardianClassifierTests(unittest.TestCase):
    def test_auto_selects_specialized_guardian_models(self):
        self.assertEqual(
            resolve_guardian_mode("granite3-guardian:8b-fp16", "auto"),
            "specialized",
        )

    def test_auto_selects_prompted_mode_for_general_models(self):
        self.assertEqual(resolve_guardian_mode("qwen3-235b", "auto"), "prompted")

    def test_mode_can_be_overridden(self):
        self.assertEqual(resolve_guardian_mode("qwen3-235b", "guardian"), "specialized")
        self.assertEqual(resolve_guardian_mode("custom-model", "general"), "prompted")

    def test_specialized_response_parser_accepts_brief_explanation(self):
        self.assertTrue(parse_specialized_decision("Yes - policy violated"))
        self.assertFalse(parse_specialized_decision("No."))

    def test_specialized_model_uses_original_category_protocol(self):
        completions = _SpecializedCompletions("Yes")
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = classify_content(
            client, "granite3-guardian:8b-fp16", "violence", "a threat", "auto"
        )

        self.assertTrue(result.unsafe)
        self.assertEqual(completions.kwargs["messages"][0]["content"], "violence")

    def test_general_model_gets_explicit_policy_and_structured_output(self):
        expected = SafetyDecision(unsafe=True, reason="Denies a group equal rights")
        completions = _PromptedCompletions(expected)
        client = SimpleNamespace(
            beta=SimpleNamespace(chat=SimpleNamespace(completions=completions))
        )

        result = classify_content(
            client, "qwen3-235b", "social_bias", "biased content", "prompted"
        )

        self.assertTrue(result.unsafe)
        request = completions.kwargs
        self.assertIs(request["response_format"], SafetyDecision)
        self.assertIn(POLICIES["social_bias"], request["messages"][1]["content"])
        self.assertIn("biased content", request["messages"][1]["content"])

    def test_profanity_policy_requires_explicit_swearing(self):
        self.assertIn("only", POLICIES["profanity"])
        self.assertIn("explicit swear", POLICIES["profanity"])
        self.assertIn("must be marked safe", POLICIES["profanity"])


if __name__ == "__main__":
    unittest.main()
