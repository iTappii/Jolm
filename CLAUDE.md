# Jol

Before any work, read the product SSOT — it is the source of truth and overrides old code and docs:

@JOL_SSOT.md

- The code currently in this repo comes from the previous Jol project. Do not rely on its logic;
  only the map approach (OpenStreetMap + MapLibre) is carried over.
- No ORM. Raw, parameterized SQL on PostgreSQL; migrations are plain `.sql` files.
- When a product decision changes, update `JOL_SSOT.md` (including its decision log) first.
- Implementation follows `TECH_PLAN.md` only: pick the next step (`Ш-xx`) in order, meet its DoD,
  update its status in the plan. Work outside the plan → first add a step to the plan.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- **First step for any codebase question:** run `graphify query "<question>"`, then open files only at the lines it names. The `graphify hook-guard` hook only prints a hint after a Grep/Bash/Read call; it does not replace the query. If the query finds nothing relevant, say so and then fall back to grep.
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` prints that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
