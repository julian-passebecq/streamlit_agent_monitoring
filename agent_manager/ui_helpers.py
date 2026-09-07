from __future__ import annotations

import html
import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

STATUS_GLYPH = {
    "draft": "○",
    "ready": "◉",
    "sent": "↗",
    "working": "●",
    "returned": "◆",
    "reviewed": "✓",
    "closed": "✓",
    "waiting": "◌",
    "blocked": "!",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { --am-border: rgba(128,128,128,.24); }
        .stApp { background: #111315; }
        [data-testid="stSidebar"] { background: #17191c; border-right: 1px solid var(--am-border); }
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        .block-container { max-width: 1500px; padding-top: 1.35rem; padding-bottom: 4rem; }
        h1, h2, h3 { letter-spacing: -0.02em; }
        .am-kicker { color: #8f969f; text-transform: uppercase; font-size: .72rem; letter-spacing: .12em; margin-bottom: .25rem; }
        .am-card { border: 1px solid var(--am-border); background: #17191c; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }
        .am-card strong { font-weight: 600; }
        .am-muted { color: #9198a1; }
        .am-meta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #aeb4bc; font-size: .8rem; }
        .am-status { display:inline-block; border:1px solid var(--am-border); border-radius:999px; padding:2px 8px; font-size:.76rem; color:#c7ccd2; }
        .am-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
        .am-title { font-size: 1.02rem; font-weight: 600; }
        .am-model { color:#9aa1aa; font-size:.78rem; }
        div[data-testid="stTabs"] button { font-size: .9rem; }
        div[data-testid="stExpander"] { border-color: var(--am-border); background:#15171a; }
        .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div { background:#17191c; }
        .stButton button, .stDownloadButton button { border-radius:8px; }
        code { font-size: .84rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def agent_card(agent: dict[str, Any], status: str, subtitle: str = "") -> None:
    glyph = STATUS_GLYPH.get(status, "○")
    st.markdown(
        f"""
        <div class="am-card">
          <div class="am-row">
            <div>
              <div class="am-title">{html.escape(str(agent.get('name','')))}</div>
              <div class="am-model">{html.escape(str(agent.get('role','')))} · {html.escape(str(agent.get('model_label','')))}</div>
            </div>
            <span class="am-status">{glyph} {html.escape(status)}</span>
          </div>
          {f'<div class="am-muted" style="margin-top:8px">{html.escape(subtitle)}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def copy_open_controls(text: str, url: str = "", label: str = "Copy + Open") -> None:
    text_js = json.dumps(text)
    url_js = json.dumps(url or "")
    safe_label = html.escape(label)
    components.html(
        f"""
        <style>
          body {{ margin:0; font-family: Inter, system-ui, sans-serif; background:transparent; color:#e6e8eb; }}
          .wrap {{ display:flex; gap:8px; align-items:center; }}
          button {{ border:1px solid rgba(150,150,150,.35); background:#202327; color:#eef0f2; border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:600; }}
          button.secondary {{ background:#17191c; font-weight:500; }}
          .msg {{ font-size:12px; color:#9ca3ab; min-width:70px; }}
        </style>
        <div class="wrap">
          <button onclick="copyText(false)">Copy prompt</button>
          <button class="secondary" onclick="copyText(true)" {'disabled' if not url else ''}>{safe_label}</button>
          <span class="msg" id="msg"></span>
        </div>
        <script>
          const payload = {text_js};
          const target = {url_js};
          async function copyText(openToo) {{
            const msg = document.getElementById('msg');
            try {{
              await navigator.clipboard.writeText(payload);
              msg.textContent = 'Copied';
            }} catch (e) {{
              msg.textContent = 'Use code copy';
            }}
            if (openToo && target) window.open(target, '_blank', 'noopener,noreferrer');
            setTimeout(() => msg.textContent = '', 1800);
          }}
        </script>
        """,
        height=46,
    )


def json_download(label: str, data: dict[str, Any], filename: str) -> None:
    st.download_button(
        label,
        data=json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        file_name=filename,
        mime="application/json",
        use_container_width=True,
    )
