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
    "standby": "–",
    "blocked": "!",
    "idle": "○",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { --am-border: #E2E6EA; --am-muted:#667085; --am-panel:#F8F9FB; --am-soft:#F3F5F7; }
        .stApp { background: #FFFFFF; color:#15171A; }
        [data-testid="stSidebar"] { background: #F7F8FA; border-right: 1px solid var(--am-border); }
        [data-testid="stHeader"] { background: rgba(255,255,255,.92); }
        .block-container { max-width: 1540px; padding-top: 1.25rem; padding-bottom: 4rem; }
        h1, h2, h3 { letter-spacing: -0.025em; color:#15171A; }
        .am-kicker { color: #7A828D; text-transform: uppercase; font-size: .70rem; letter-spacing: .13em; margin-bottom: .25rem; }
        .am-card { border: 1px solid var(--am-border); background: #FFFFFF; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; box-shadow:0 1px 2px rgba(16,24,40,.03); }
        .am-card strong { font-weight: 600; }
        .am-muted { color: var(--am-muted); }
        .am-meta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #59616B; font-size: .8rem; }
        .am-status { display:inline-block; border:1px solid var(--am-border); border-radius:999px; padding:2px 8px; font-size:.76rem; color:#475467; background:#FAFBFC; }
        .am-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
        .am-title { font-size: 1.02rem; font-weight: 600; }
        .am-model { color:#727B86; font-size:.78rem; }
        .am-node { border:1px solid #D9DEE5; border-radius:12px; padding:10px 12px; background:#FFF; text-align:center; min-height:68px; display:flex; flex-direction:column; justify-content:center; }
        .am-node.active { border-color:#98A2B3; box-shadow:0 0 0 2px #EEF1F4 inset; }
        .am-node.standby { background:#F7F8FA; color:#7A828D; }
        .am-arrow { text-align:center; color:#98A2B3; font-size:18px; padding:2px 0; }
        div[data-testid="stTabs"] button { font-size: .9rem; }
        div[data-testid="stExpander"] { border-color: var(--am-border); background:#FBFCFD; }
        .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div { background:#FFFFFF; }
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


def org_node(agent: dict[str, Any], active: bool, status: str = "idle") -> None:
    state = "active" if active else "standby"
    glyph = STATUS_GLYPH.get(status, "○")
    st.markdown(
        f"""
        <div class="am-node {state}">
          <strong>{html.escape(str(agent.get('name','')))}</strong>
          <span style="font-size:.76rem;color:#667085">{html.escape(str(agent.get('role','')))}</span>
          <span style="font-size:.72rem;color:#98A2B3">{glyph} {html.escape(status)} · {html.escape(str(agent.get('model_label','')))}</span>
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
          body {{ margin:0; font-family: Inter, system-ui, sans-serif; background:transparent; color:#1D2939; }}
          .wrap {{ display:flex; gap:8px; align-items:center; }}
          button {{ border:1px solid #D0D5DD; background:#FFFFFF; color:#1D2939; border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:600; }}
          button.secondary {{ background:#F7F8FA; font-weight:500; }}
          button:disabled {{ color:#98A2B3; cursor:not-allowed; }}
          .msg {{ font-size:12px; color:#667085; min-width:70px; }}
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
