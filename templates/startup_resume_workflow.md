# Startup / Resume workflow

Use **Start / Resume** when returning to a project whose repository/agent state may have changed.

1. Copy the generated audit prompt.
2. Open the most knowledgeable existing chat in the ChatGPT Project (or dedicated Startup Agent conversation).
3. Ask it to inspect the available Project history/files and repositories it can actually access.
4. It returns `project_bootstrap_audit` JSON only.
5. Paste it into Agent Manager and review the proposed stack, Git state, agent organization, feature board and next cycle before applying.
6. Stable agent IDs preserve stored chat links. Agents not needed now can be placed on standby rather than deleted.
7. Director then owns the cycle. Prompt Agent packages worker prompts only for agents selected active in Organization.
