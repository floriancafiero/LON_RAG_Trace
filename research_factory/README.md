# TRACE Research Factory

A runnable, resumable multi-agent research workflow adapted to **TRACE / TRACE-lite** and this repository's League of Nations bilingual source-discovery transfer case. It follows the broad architecture in Engzell & Wilmers' *The Paper Factory* (2026)—fresh narrow agents, parallel findings streams, critic/revision loops, hard gates, competing paper architectures and late audits—but the implementation and TRACE-specific prompts here are independent.

The factory is deliberately small and dependency-free beyond Python itself. It uses DeepSeek through OpenRouter by default, matching the existing TRACE workflow choice, and can also call a local coding-agent wrapper.

## TRACE-specific streams

The six independent findings streams cover retrieval-channel ablations; agentic-vs-non-agentic comparisons under matched compute; EN/FR bilingual transfer; quality–latency–token/cost trade-offs and stopping; error/calibration analysis; and robustness/reproducibility. Extensions include a **JEV-style controller** for continue/stop/escalate or retrieval granularity. JEV remains optional: without callable JEV code the agent must produce an integration/experiment specification, not results.

The scientific gates explicitly check benchmark/gold validity before expensive runs, exact traceability of every number, and final claim calibration. Gold IDs/excerpts/source URLs/evaluation-only metadata are prohibited from retrieval decisions; final-test tuning, silent parse-failure dropping, and unmatched compute comparisons are explicitly audited.

## Quick start

First prepare the LoN benchmark using the main repository README so these exist:

\`\`\`text
data/trace_inputs/trace_documents.jsonl
data/trace_inputs/trace_questions.jsonl
\`\`\`

Then, from the repository root:

\`\`\`bash
export OPENROUTER_API_KEY=...

python research_factory/trace_factory.py init runs/trace_lon_paper \
  --data data/trace_inputs/trace_documents.jsonl \
  --data data/trace_inputs/trace_questions.jsonl \
  --data configs \
  --data scripts

# If outputs/ already contains TRACE/BM25 runs, include: --data outputs

python research_factory/trace_factory.py plan
python research_factory/trace_factory.py run runs/trace_lon_paper
\`\`\`

\`init\` creates a detailed TRACE-specific \`checkpoint.md\` and a \`factory.json\`. Review both before spending API credits. The default model is configurable:

\`\`\`json
{"backend": {"kind": "openrouter", "model": "deepseek/deepseek-chat-v3.1"}}
\`\`\`

Keep the model string synchronized with the DeepSeek version used in the main TRACE experiments. \`--model\` overrides it for a run.

## Smoke test

\`\`\`bash
python research_factory/trace_factory.py init /tmp/trace_factory_smoke --backend mock
python research_factory/trace_factory.py run /tmp/trace_factory_smoke --backend mock
python research_factory/trace_factory.py status /tmp/trace_factory_smoke
\`\`\`

A full mock run should finish at \`awaiting_human_review\` with 67 completed stages. Every stage is checkpointed in \`state.json\`; prompts/responses are stored under \`logs/\` and the event stream under \`provenance/events.jsonl\`.

## Files

- \`trace_factory.py\` — orchestration, hard gates and CLI.
- \`runtime.py\` — workspace, OpenRouter/DeepSeek backend, shell/file tools and mock backend.
- \`prompts.py\` — TRACE-specific research heuristics, six findings directions and seven extensions.

## Security

Agents can run shell commands because evaluation may require Python and external TRACE scripts. A small list of obviously destructive commands is blocked, but this is **not a hardened sandbox**. Use a disposable environment for untrusted code/data.
