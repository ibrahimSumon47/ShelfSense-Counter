# Chat evaluation: not measured yet; pipeline demonstration only

Status: **not measured yet; pipeline demonstration only**. The earlier version of this file
reported "30/30 (100%)". That number was misleading and has been withdrawn.

What actually exists:

- A rule-based router (`apps/web/src/lib/chat-tools.ts`) that picks one of three database
  tools by keyword and formats a fixed sentence. No language model is involved.
- A unit test (`apps/web/src/lib/shelfsense.test.ts`) that runs 30 questions through that
  router against a tiny fixture. The expected answers were written by the same author as
  the router, so passing it is a regression check of the code, not an accuracy measurement.
- A script that called a free hosted LLM got HTTP 503, and a fallback then printed the
  deterministic result as if it were the live result. That script was deleted.

What is needed before any number is reported:

1. Run the 30 questions (15 English, 15 Bangla) against the real free LLM with tool calling.
2. Check each answer's numbers against the tool output and record the true pass rate,
   including failures, together with the command and the model name.

Until then the wording "tool-call and numeric grounding checks" applies only to the unit
test described above.
