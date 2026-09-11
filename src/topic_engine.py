"""Deterministic, niche-specific topic selection."""
from __future__ import annotations
import hashlib, re
from .repository import load, save, now

PILLARS = ["Website design fundamentals","Landing page design","UI/UX design","Responsive web design","HTML and CSS tutorials","JavaScript for websites","WordPress websites","Webflow websites","Framer websites","Shopify storefront design","Website redesigns","Website accessibility","Website SEO","Website speed optimization","Conversion-rate optimization","AI website creation","No-code web design","Web-design freelancing","Web-design agency systems","Website troubleshooting","Content marketing","Email marketing","Social media marketing","Local marketing","Brand messaging","Marketing funnels","Lead generation","Analytics and attribution","Paid advertising fundamentals","E-commerce marketing"]
SEEDS = [
    "How to design a high-converting landing page that gets more leads",
    "7 homepage mistakes that make potential customers leave",
    "How to build a small business website that earns trust",
    "Website redesign checklist for entrepreneurs who want more enquiries",
    "How to write a website headline that turns visitors into leads",
    "The best website structure for a local service business",
    "How to add trust signals that increase website conversions",
    "Website SEO basics for a new business that needs local customers",
    "How to design a mobile website that customers can use instantly",
    "How to improve website speed and stop losing impatient buyers",
    "Content marketing strategy for a small business with no audience",
    "How to create a content calendar that brings consistent leads",
    "Email marketing welcome sequence that turns subscribers into customers",
    "How to write a weekly newsletter people actually want to read",
    "Social media content ideas that drive website visits and enquiries",
    "How to turn one blog post into a month of marketing content",
    "Local marketing checklist for service businesses that want more calls",
    "Google Business Profile optimization for local customer discovery",
    "How to clarify your brand message so customers choose you faster",
    "Marketing funnel explained: turn attention into qualified enquiries",
    "Lead magnet ideas that grow an email list for entrepreneurs",
    "How to track website leads with simple analytics and attribution",
    "Paid advertising landing page mistakes that waste your budget",
    "E-commerce product page copy that helps shoppers decide",
]

def words(value): return set(re.findall(r"[a-z0-9]+", value.lower())) - {"how","to","the","a","for","and","website","design"}
def similarity(a,b):
    x,y=words(a),words(b); return len(x&y)/max(1,len(x|y))
def topic_id(title): return hashlib.sha1(title.lower().encode()).hexdigest()[:12]
PILLAR_KEYWORDS = {
    "Content marketing": ("content", "blog", "calendar", "repurpos"),
    "Email marketing": ("email", "newsletter", "subscriber"),
    "Social media marketing": ("social media", "social content"),
    "Local marketing": ("local", "google business", "nearby"),
    "Brand messaging": ("brand", "headline", "message"),
    "Marketing funnels": ("funnel", "lead magnet", "journey"),
    "Lead generation": ("lead", "enquir", "calls"),
    "Analytics and attribution": ("analytics", "attribution", "track"),
    "Paid advertising fundamentals": ("paid", "advertising", "budget"),
    "E-commerce marketing": ("e-commerce", "ecommerce", "shopper", "product page"),
}

def score(title, pillar):
    normalized = title.lower()
    intent = 90 if any(x in normalized for x in ("how to", "checklist", "mistakes", "guide", "fix", "best", "why")) else 72
    answer_intent = 92 if any(x in normalized for x in ("how to", "what", "why", "best", "checklist")) else 70
    local_or_entity_intent = 88 if any(x in normalized for x in ("local", "small business", "wordpress", "shopify", "webflow")) else 68
    return round(.25 * intent + .20 * 88 + .20 * 92 + .15 * answer_intent + .10 * local_or_entity_intent + .10 * 82)
def candidates(existing):
    titles=[x.get("title","") for x in existing]
    result=[]
    for seed in SEEDS:
        if any(similarity(seed,t) >= .55 for t in titles+ [x["title"] for x in result]): continue
        normalized_seed = seed.lower()
        pillar = next((name for name, keywords in PILLAR_KEYWORDS.items() if any(keyword in normalized_seed for keyword in keywords)), None)
        pillar = pillar or next((p for p in PILLARS if any(k in normalized_seed for k in p.lower().split()[:2])), "Website design fundamentals")
        result.append({"id":topic_id(seed),"title":seed,"pillar":pillar,"cluster":pillar.lower().replace(" ","-"),"format":"tutorial","difficulty":"beginner","search_intent":"practical solution","audience":"entrepreneurs, founders and service businesses","evergreen_score":92,"demand_score":88,"problem_score":90,"monetization_score":84,"production_score":82,"seo_score":88,"geo_score":78,"aeo_score":90,"priority_score":score(seed,pillar),"selection_reason":"Persistent business problem with search, answer and entity intent.","status":"pending","created_at":now(),"published_at":None,"youtube_id":None,"parent_topic_id":None,"related_topic_ids":[],"decay_score":0,"update_candidate":False})
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
    marketing_pillars = set(PILLAR_KEYWORDS)
    marketing_pending = sum(x.get("status") == "pending" and x.get("pillar") in marketing_pillars for x in existing)
    if pending >= min_pending and marketing_pending >= 8:
        save("topics", existing)
        return existing
    additions=candidates(existing)
    if marketing_pending < 8:
        marketing_additions = [item for item in additions if item["pillar"] in marketing_pillars]
        existing.extend(marketing_additions[:8 - marketing_pending])
        additions = [item for item in additions if item not in marketing_additions[:8 - marketing_pending]]
    existing.extend(additions[:max(0, min(batch, min_pending - pending))]); save("topics",existing); return existing

def select_next(topics):
    pending=[x for x in topics if x.get("status")=="pending"]
    return max(pending,key=lambda x:x.get("priority_score",0),default=None)
