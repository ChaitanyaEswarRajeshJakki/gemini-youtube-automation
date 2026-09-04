"""Deterministic, niche-specific topic selection."""
from __future__ import annotations
import hashlib, re
from .repository import load, save, now

PILLARS = ["Website design fundamentals","Landing page design","UI/UX design","Responsive web design","HTML and CSS tutorials","JavaScript for websites","WordPress websites","Webflow websites","Framer websites","Shopify storefront design","Website redesigns","Website accessibility","Website SEO","Website speed optimization","Conversion-rate optimization","AI website creation","No-code web design","Web-design freelancing","Web-design agency systems","Website troubleshooting"]
SEEDS = ["How to design a high-converting landing page that gets more leads", "7 homepage mistakes that make potential customers leave", "How to build a small business website that earns trust", "Website redesign checklist for entrepreneurs who want more enquiries", "How to write a website headline that turns visitors into leads", "The best website structure for a local service business", "How to add trust signals that increase website conversions", "Website SEO basics for a new business that needs local customers", "How to design a mobile website that customers can use instantly", "How to improve website speed and stop losing impatient buyers"]

def words(value): return set(re.findall(r"[a-z0-9]+", value.lower())) - {"how","to","the","a","for","and","website","design"}
def similarity(a,b):
    x,y=words(a),words(b); return len(x&y)/max(1,len(x|y))
def topic_id(title): return hashlib.sha1(title.lower().encode()).hexdigest()[:12]
def score(title, pillar):
    intent = 90 if any(x in title.lower() for x in ("how to","checklist","mistakes","guide","fix")) else 72
    return round(.25*intent + .20*88 + .20*92 + .15*80 + .10*85 + .10*82)
def candidates(existing):
    titles=[x.get("title","") for x in existing]
    result=[]
    for seed in SEEDS:
        if any(similarity(seed,t) >= .55 for t in titles+ [x["title"] for x in result]): continue
        pillar=next((p for p in PILLARS if any(k in seed.lower() for k in p.lower().split()[:2])), "Website design fundamentals")
        result.append({"id":topic_id(seed),"title":seed,"pillar":pillar,"cluster":pillar.lower().replace(" ","-"),"format":"tutorial","difficulty":"beginner","search_intent":"practical solution","audience":"beginners, business owners and freelancers","evergreen_score":92,"demand_score":88,"problem_score":90,"monetization_score":84,"production_score":82,"priority_score":score(seed,pillar),"selection_reason":"Persistent website problem with clear search intent and actionable follow-up opportunities.","status":"pending","created_at":now(),"published_at":None,"youtube_id":None,"parent_topic_id":None,"related_topic_ids":[],"decay_score":0,"update_candidate":False})
    return result

def archive_off_brand_topics(topics):
    """Keep legacy AI topics from resurfacing after the channel repositioning."""
    business_terms = ("website", "landing", "homepage", "conversion", "seo", "customer", "business", "entrepreneur", "mobile", "shopify", "wordpress", "webflow", "framer")
    off_brand_terms = ("nlp", "llm", "transformer", "vector database", "agent", "reinforcement learning", "rlhf", "multimodal", "tokenization", "embeddings", "langgraph", "prompt engineering")
    for topic in topics:
        title = topic.get("title", "").lower()
        off_brand = any(term in title for term in off_brand_terms) or ("ai" in title and not any(term in title for term in business_terms))
        if topic.get("status") == "pending" and off_brand:
            topic["status"] = "archived"
            topic["archive_reason"] = "Off-brand after repositioning to entrepreneur-focused web design."
    return topics

def replenish(min_pending=20, batch=50):
    existing=archive_off_brand_topics(load("topics",[])); pending=sum(x.get("status")=="pending" for x in existing)
    if pending >= min_pending:
        save("topics", existing)
        return existing
    additions=candidates(existing)
    existing.extend(additions[:batch]); save("topics",existing); return existing

def select_next(topics):
    pending=[x for x in topics if x.get("status")=="pending"]
    return max(pending,key=lambda x:x.get("priority_score",0),default=None)
