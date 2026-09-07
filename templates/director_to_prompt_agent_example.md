# Director → Prompt Agent usage

1. Director decides the cycle objective, selected roles, assignments, dependencies, acceptance criteria, QA policy and Audit/history requirements.
2. In Agent Manager, select active/standby workers on **Organization**.
3. Paste Director's orchestration brief into **Prompt Studio**.
4. Agent Manager prepends current model labels, role contracts, technical stack and Git metadata and produces the packet for Prompt Agent.
5. Prompt Agent improves clarity without changing Director decisions and returns strict `agent_manager_run` JSON for selected workers only.
6. Paste/apply that JSON in Prompt Studio.
7. Use Control Room to copy/open each worker conversation.
