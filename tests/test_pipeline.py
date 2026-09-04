import json
from src.topic_engine import similarity, candidates
from src.quality import score_content

def test_similarity_detects_overlap():
    assert similarity("How to design a landing page", "Landing page design guide") > 0.2

def test_candidates_are_unique():
    items=candidates([])
    assert len(items) == len({x["id"] for x in items})
    assert all(x["status"] == "pending" for x in items)

def test_quality_scores_actionable_content():
    content={"long_form_slides":[{"content":"Step example checklist " + "useful " * 200} for _ in range(7)],"short_form_highlight":"one idea","hashtags":"#webdesign"}
    assert score_content(content) >= 75
