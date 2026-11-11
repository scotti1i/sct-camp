---
name: sales-script-evidence
description: Draft three-part product video scripts from approved product facts and flag requested claims that lack evidence.
---

# Product video scripts with source facts

Read the supplied product facts and requests. In the SCTCamp practice folder, use `fixtures/product.md` and `fixtures/requests.json`.

For each request:

1. Use only facts about the requested SKU. If a requested claim needs missing evidence, return `needs-evidence`, list each missing field by its source key, and leave the script empty.
2. Otherwise write a short opening, a product demo, and a close. Give each a spoken line and a filmable shot. Ground both in one or more approved fact IDs. Keep the requested language and omit prices, timelines, performance, and materials absent from the facts.
3. Return one JSON object with a `cases` array. Each case has `case_id`, `status`, `lines`, and `missing`. A `draft` has three lines in order with `part` values `opening`, `demo`, and `close`, plus `text`, `shot`, and `fact_ids` for each line. Its `missing` array is empty. A `needs-evidence` case has an empty `lines` array. Return plain JSON without a Markdown fence.
