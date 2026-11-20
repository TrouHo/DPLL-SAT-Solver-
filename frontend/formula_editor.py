"""Caret-aware propositional formula editor built with Streamlit Components v2."""

from __future__ import annotations

from typing import Any

import streamlit as st


_EDITOR_HTML = """
<div class="formula-editor" data-revision="">
  <label class="sr-only" for="formula-textarea">Propositional formula</label>
  <div class="editor-row">
    <textarea
      id="formula-textarea"
      aria-label="Propositional formula editor"
      maxlength="1000"
      spellcheck="false"
    ></textarea>
    <div class="keypad-stack">
      <div class="formula-keypad" role="toolbar" aria-label="Logical symbol keypad">
        <button type="button" data-symbol="¬" aria-label="Insert not">¬</button>
        <button type="button" data-symbol="∧" aria-label="Insert and">∧</button>
        <button type="button" data-symbol="∨" aria-label="Insert or">∨</button>
        <button type="button" data-symbol="→" aria-label="Insert implication">→</button>
        <button type="button" data-symbol="↔" aria-label="Insert equivalence">↔</button>
        <button type="button" data-symbol="(" aria-label="Insert opening parenthesis">(</button>
        <button type="button" data-symbol=")" aria-label="Insert closing parenthesis">)</button>
        <button type="button" data-symbol="A">A</button>
        <button type="button" data-symbol="B">B</button>
        <button type="button" data-symbol="C">C</button>
        <button type="button" data-action="clear" class="clear-button">Clear</button>
      </div>
      <div class="editor-meta">
        <span class="editor-note">Symbols insert at the caret and replace selections.</span>
        <span class="editor-counter">0 / 1000</span>
      </div>
    </div>
  </div>
</div>
"""


_EDITOR_CSS = """
:host {
  color: var(--st-text-color);
  font-family: var(--st-font);
}
.formula-editor {
  width: 100%;
}
.editor-row {
  display: grid;
  grid-template-columns: minmax(300px, 1.15fr) minmax(510px, 1fr);
  gap: 0.8rem;
  align-items: start;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
textarea {
  box-sizing: border-box;
  display: block;
  width: 100%;
  height: 62px;
  min-height: 62px;
  max-height: 150px;
  resize: vertical;
  padding: 0.72rem 0.85rem;
  border: 1px solid var(--st-border-color, #cbd5e1);
  border-radius: var(--st-base-radius, 0.5rem);
  background: var(--st-background-color);
  color: var(--st-text-color);
  font: 500 1.16rem/1.55 var(--st-font-monospace, monospace);
  outline: none;
}
textarea:focus {
  border-color: var(--st-primary-color);
  box-shadow: 0 0 0 1px var(--st-primary-color);
}
.formula-keypad {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
}
button {
  min-width: 2.55rem;
  min-height: 2.55rem;
  padding: 0.32rem 0.62rem;
  border: 1px solid var(--st-border-color, #cbd5e1);
  border-radius: var(--st-base-radius, 0.5rem);
  background: var(--st-secondary-background-color);
  color: var(--st-text-color);
  font: 600 1rem var(--st-font);
  cursor: pointer;
}
button:hover {
  border-color: var(--st-primary-color);
  color: var(--st-primary-color);
}
button:active {
  transform: translateY(1px);
}
.clear-button {
  min-width: 4.4rem;
  font-weight: 500;
}
.editor-meta {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 1rem;
  margin-top: 0.28rem;
  color: var(--st-text-color);
  font-size: 0.75rem;
  opacity: 0.65;
}
.editor-note {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.editor-counter {
  white-space: nowrap;
}
@media (max-width: 900px) {
  .editor-row {
    grid-template-columns: 1fr;
    gap: 0.55rem;
  }
}
"""


_EDITOR_JS = """
export default function(component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component;
  const root = parentElement.querySelector(".formula-editor");
  const textarea = parentElement.querySelector("textarea");
  const counter = parentElement.querySelector(".editor-counter");
  if (!root || !textarea || !counter) return;

  const revision = String(data?.revision ?? 0);
  const updateCounter = () => {
    counter.textContent = `${textarea.value.length} / 1000`;
  };

  if (root.dataset.revision !== revision) {
    textarea.value = String(data?.value ?? "").slice(0, 1000);
    root.dataset.revision = revision;
    updateCounter();
    setStateValue("value", textarea.value);
    setStateValue("revision", revision);
  }

  textarea.oninput = () => {
    updateCounter();
    setStateValue("value", textarea.value);
  };

  for (const button of parentElement.querySelectorAll("button")) {
    button.onpointerdown = (event) => event.preventDefault();
    button.onmousedown = (event) => event.preventDefault();
  }

  for (const button of parentElement.querySelectorAll("button[data-symbol]")) {
    button.onclick = () => {
      const symbol = button.dataset.symbol ?? "";
      const start = textarea.selectionStart ?? textarea.value.length;
      const end = textarea.selectionEnd ?? start;
      const available = 1000 - (textarea.value.length - (end - start));
      const insertion = symbol.slice(0, Math.max(0, available));
      textarea.setRangeText(insertion, start, end, "end");
      textarea.focus({ preventScroll: true });
      updateCounter();
      setStateValue("value", textarea.value);
    };
  }

  const clearButton = parentElement.querySelector("button[data-action='clear']");
  clearButton.onclick = () => {
    textarea.value = "";
    textarea.setSelectionRange(0, 0);
    textarea.focus({ preventScroll: true });
    updateCounter();
    setStateValue("value", "");
    setTriggerValue("cleared", `${revision}:${Date.now()}`);
  };

  updateCounter();
}
"""


_FORMULA_EDITOR = st.components.v2.component(
    "dpll_formula_editor",
    html=_EDITOR_HTML,
    css=_EDITOR_CSS,
    js=_EDITOR_JS,
)


def _state_field(state: Any, name: str, default: Any = None) -> Any:
    if state is None:
        return default
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)


def formula_editor(*, value: str, revision: int, key: str = "formula_editor"):
    """Mount the editor while preserving browser-owned caret and selection state."""
    component_state = st.session_state.get(key)
    state_revision = _state_field(component_state, "revision")
    state_value = _state_field(component_state, "value")
    synchronized_value = (
        state_value
        if state_revision == str(revision) and isinstance(state_value, str)
        else value
    )
    return _FORMULA_EDITOR(
        key=key,
        data={"value": synchronized_value, "revision": revision},
        default={"value": value, "revision": str(revision)},
        on_value_change=lambda: None,
        on_revision_change=lambda: None,
        on_cleared_change=lambda: None,
        width="stretch",
        height="content",
    )

