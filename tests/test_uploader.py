from src.uploader import sanitize_title


def test_sanitize_title_truncates_and_removes_forbidden_markers():
    title = "Building Your First Image Generator with Diffusion Models: From Text to Art (Giving AI a Specific Recipe)"
    cleaned = sanitize_title(title)

    assert cleaned != title
    assert len(cleaned) <= 100
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert cleaned.endswith("...")


def test_sanitize_title_replaces_empty_after_cleanup():
    assert sanitize_title("< >") == "Untitled Video"
