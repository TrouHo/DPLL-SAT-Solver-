from frontend import formula_editor


def test_editor_uses_selection_aware_insertion_and_refocuses():
    javascript = formula_editor._EDITOR_JS
    assert "selectionStart" in javascript
    assert "selectionEnd" in javascript
    assert "setRangeText" in javascript
    assert "textarea.focus" in javascript
    assert "onpointerdown" in javascript


def test_editor_syncs_only_when_revision_changes():
    javascript = formula_editor._EDITOR_JS
    assert "root.dataset.revision !== revision" in javascript
    assert 'setStateValue("revision", revision)' in javascript
    assert 'setStateValue("value", textarea.value)' in javascript


def test_editor_keeps_static_markup_and_1000_character_limit():
    assert 'maxlength="1000"' in formula_editor._EDITOR_HTML
    assert "0 / 1000" in formula_editor._EDITOR_HTML
    assert ".slice(0, 1000)" in formula_editor._EDITOR_JS
    assert "const available = 1000" in formula_editor._EDITOR_JS
    assert "height: 62px" in formula_editor._EDITOR_CSS
    assert "grid-template-columns" in formula_editor._EDITOR_CSS
    assert "@media (max-width: 900px)" in formula_editor._EDITOR_CSS
    assert formula_editor._EDITOR_HTML.count('data-symbol="') == 10
    assert 'data-action="clear"' in formula_editor._EDITOR_HTML
    assert "Symbols insert at the caret and replace selections." in formula_editor._EDITOR_HTML
    assert "ⓘ" not in formula_editor._EDITOR_HTML

