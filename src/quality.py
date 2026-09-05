"""Content quality firewall."""
import re

def score_content(content):
    slides=content.get("long_form_slides",[]); text=" ".join(str(x.get("content","")) for x in slides)
    score=0
    score += 25 if len(text.split()) >= 180 else 10
    score += 20 if len(slides) >= 6 else 8
    score += 15 if any(k in text.lower() for k in ("step", "example", "checklist")) else 5
    score += 15 if content.get("short_form_highlight") else 0
    score += 10 if len(set(re.findall(r"\b\w+\b", text.lower()))) > 80 else 4
    score += 10 if not re.search(r"hello and welcome|ai for developers", text, re.I) else 0
    score += 5 if content.get("hashtags") else 0
    return score

def validate_content(content):
    score=score_content(content)
    if score < 75: raise ValueError(f"Script QA score {score}/100 is below the 75 threshold")
    return score
