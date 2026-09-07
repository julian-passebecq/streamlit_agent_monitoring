# Director → Companion usage

Paste the Director's complete natural-language dispatch into the Streamlit Companion conversation after installing its bootstrap.

The Companion must return **only** an `agent_manager_run` JSON object. Paste that JSON into **Import / Returns → Import Director run**.

The JSON may update the Git snapshot and dispatch any existing agent. It must not invent repository state or technical decisions.
