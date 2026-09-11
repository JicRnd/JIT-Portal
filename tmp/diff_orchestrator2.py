import difflib

with open(r'c:\Users\Kane\.copilot\agents\ai-orchestrator.agent.md', 'r', encoding='utf-8') as f:
    new_content = f.read()

# Revert changes to produce the original content
original = new_content

# Remove the two inserted sections between Context budget and Cost & verification discipline
start_marker = "- Do not ask workers to return unchanged source.\n\n## Deterministic discovery order (rg, git, CRG, AppMap)"
end_marker = "## Cost & verification discipline\n"
idx_start = original.find(start_marker)
idx_end = original.find(end_marker)
if idx_start != -1 and idx_end != -1:
    original = original[:idx_start] + "- Do not ask workers to return unchanged source.\n\n" + original[idx_end:]

# Revert the two bullets in Cost & verification discipline
old_bullets = """- Prefer the cheapest verifier that actually proves correctness, in order: (a) a deterministic check — `rg`, `git status`/`diff`/`log`, file timestamps, or a checked-in architecture map confirmed current; (b) a Lightweight Worker read-check; (c) a Coding Worker review; (d) a full redo. Stop at the first level that answers the question.
- Do not assume `docs/ARCHITECTURE_MAP.md`, `docs/business-rules.md`, or any architecture/index doc exists — have a worker confirm it exists and is current before citing it. If it exists and is current, have the worker consult or update it instead of re-deriving routes, models, services, or templates from scratch."""

new_bullets = """- Prefer the cheapest verifier that actually proves correctness, in order: (a) a static/deterministic check such as the existing test suite, schema/route introspection, or a checked-in architecture map; (b) a Lightweight Worker read-check; (c) a Coding Worker review; (d) a full redo. Stop at the first level that answers the question.
- Before delegating discovery, check whether the repository already has a checked-in architecture or index doc (e.g., `docs/ARCHITECTURE_MAP.md`, `appmap.yml`/AppMap output, or similar). If it does, have the worker consult or update it instead of re-deriving routes, models, services, or templates from scratch."""

original = original.replace(old_bullets, new_bullets)

orig_lines = original.splitlines(keepends=True)
new_lines = new_content.splitlines(keepends=True)

if orig_lines and not orig_lines[-1].endswith('\n'):
    orig_lines[-1] += '\n'
if new_lines and not new_lines[-1].endswith('\n'):
    new_lines[-1] += '\n'

diff = list(difflib.unified_diff(
    orig_lines, new_lines,
    fromfile='c:/Users/Kane/.copilot/agents/ai-orchestrator.agent.md.before',
    tofile='c:/Users/Kane/.copilot/agents/ai-orchestrator.agent.md'
))
print(''.join(diff), end='')
