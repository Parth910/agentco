from agentco.launch import name_from_idea, short


def test_name_from_idea_uses_first_words():
    assert name_from_idea("Campus feed: post updates, like posts and more") == "Campus feed post updates, like posts"


def test_short_collapses_whitespace_and_truncates():
    assert short("a\n  b") == "a b"
    assert short("x" * 20, limit=10) == "xxxxxxxxx…"
    assert short({"ok": True}) == '{"ok": true}'
