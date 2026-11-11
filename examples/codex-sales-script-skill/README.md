# SCTCamp product video script skill practice

The SKU, product facts, and requests in this practice project are fictional. The expected JSON is a hand-written example.

## Run the practice

1. Open this extracted folder as a project in Codex. The hidden `.agents` folder holds the project-local skill.
2. Send the prompt below. Save the returned JSON as `drafts.json`.
3. Run `python3 checks/check-drafts.py drafts.json`. Read the three scripts or blockers beside `fixtures/product.md` and verify each claim.

```text
Use $sales-script-evidence with fixtures/product.md and fixtures/requests.json.
Return a single JSON object for all three requests. Use Chinese for normal-zh
and English for normal-en. Keep the provided case IDs.
```

You can run `python3 checks/check-drafts.py examples/expected.json` immediately to check the hand-written reference. The checker verifies the three cases, fields, and fact IDs. A reviewer still compares the wording and proposed shots with the source facts.

[Guide in Chinese](https://sctcamp.com/posts/codex-sales-script-skill) · [Guide in English](https://sctcamp.com/en/posts/codex-sales-script-skill)
