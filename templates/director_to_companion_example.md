# Companion fallback / repair usage

The **Prompt Agent**, not Companion, is the normal path for packaging Director assignments.

Use Streamlit Companion only when an otherwise valid Director/Prompt Agent result needs normalization or repair into Agent Manager JSON. Companion must preserve intent exactly and must not add assignments, technical decisions, repository state or feature changes.

Paste the repaired `agent_manager_run` JSON into **Import / Returns → Import packaged run**.
