"""Generate SPEC-Topical-Authority.pdf — a scoping specification for the
'Topical Authority' evolution of Topic Coverage. Run: python docs/build_authority_spec.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "SPEC-Topical-Authority.pdf"

INK = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
GREEN = colors.HexColor("#15803d")
GREENBG = colors.HexColor("#f0fdf4")
ORANGE = colors.HexColor("#c2410c")
HEADBG = colors.HexColor("#1e293b")
ZEBRA = colors.HexColor("#f8fafc")

styles = getSampleStyleSheet()


def S(name, **kw):
    styles.add(ParagraphStyle(name=name, **kw))


S("Cover", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=30,
  leading=34, textColor=INK, spaceAfter=6)
S("CoverSub", fontName="Helvetica", fontSize=13, leading=18, textColor=MUTED,
  spaceAfter=4)
S("Meta", fontName="Helvetica", fontSize=9.5, leading=14, textColor=MUTED)
S("H1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK,
  spaceBefore=16, spaceAfter=6)
S("H2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=SLATE,
  spaceBefore=10, spaceAfter=3)
S("Body", fontName="Helvetica", fontSize=9.7, leading=14.2, textColor=INK,
  spaceAfter=6, alignment=TA_LEFT)
S("Bul", fontName="Helvetica", fontSize=9.7, leading=13.6, textColor=INK)
S("Small", fontName="Helvetica", fontSize=8.6, leading=11.6, textColor=MUTED,
  spaceAfter=4)
S("Cell", fontName="Helvetica", fontSize=8.2, leading=10.6, textColor=INK)
S("CellB", fontName="Helvetica-Bold", fontSize=8.2, leading=10.6, textColor=INK)
S("CellH", fontName="Helvetica-Bold", fontSize=8.3, leading=10.8,
  textColor=colors.white)
S("Callout", fontName="Helvetica", fontSize=9.5, leading=13.6, textColor=SLATE)
S("Mono", fontName="Courier", fontSize=8.2, leading=11, textColor=INK)

story = []


def h1(t): story.append(Paragraph(t, styles["H1"]))
def h2(t): story.append(Paragraph(t, styles["H2"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def small(t): story.append(Paragraph(t, styles["Small"]))
def sp(h=6): story.append(Spacer(1, h))


def bullets(items, style="Bul"):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, styles[style]), leftIndent=10, value="•")
         for i in items],
        bulletType="bullet", start="•", leftIndent=12, spaceBefore=1, spaceAfter=6,
    ))


def cell(t, b=False):
    return Paragraph(t, styles["CellB" if b else "Cell"])


def table(headers, rows, widths, zebra=True):
    data = [[Paragraph(h, styles["CellH"]) for h in headers]]
    for r in rows:
        data.append([c if hasattr(c, "wrap") else cell(str(c)) for c in r])
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADBG),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, HEADBG),
        ("GRID", (0, 1), (-1, -1), 0.4, LINE),
    ]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(st))
    story.append(t)
    sp(8)


def callout(title, body, bg=GREENBG, bar=GREEN):
    inner = [Paragraph(f"<b>{title}</b>", styles["Callout"]),
             Paragraph(body, styles["Callout"])]
    t = Table([[inner]], colWidths=[6.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t)
    sp(8)


# ---------------------------------------------------------------- COVER
sp(70)
story.append(Paragraph("Topical Authority", styles["Cover"]))
story.append(Paragraph("Build &amp; Scoping Specification", styles["CoverSub"]))
sp(10)
story.append(Paragraph(
    "The demand + authority evolution of <b>Topic Coverage</b> — turning a "
    "content-coverage comparison into a measure of who actually <b>owns</b> the "
    "topics in a market, and where to invest to win.", styles["CoverSub"]))
sp(24)
story.append(Table([[Paragraph(
    "<b>Status:</b> Draft for scoping &nbsp;·&nbsp; <b>Builds on:</b> Topic "
    "Coverage (existing) &nbsp;·&nbsp; <b>Audience:</b> product + eng scoping "
    "the next phase", styles["Meta"])]], colWidths=[6.6 * inch],
    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
                      ("LINEBEFORE", (0, 0), (0, -1), 3, SLATE),
                      ("LEFTPADDING", (0, 0), (-1, -1), 10),
                      ("TOPPADDING", (0, 0), (-1, -1), 8),
                      ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])))
sp(16)
small("Grounded in: Google topical-authority signals (site focus score, content "
      "coverage, internal linking, E-E-A-T, off-site brand/backlinks); DataForSEO "
      "(SERP, Keywords Data, Labs, Backlinks, On-Page) and Apify (Website Content "
      "Crawler, Google Search Results Scraper). Sources listed on the final page.")
story.append(PageBreak())

# ---------------------------------------------------------------- 0
h1("0 · Context — what exists, what this adds")
p("<b>Topic Coverage</b> (already built) crawls a brand and its competitors, "
  "clusters the crawled content into topics, and shows — as a radial map — "
  "<i>who has content on what, and who has more</i>. It is a pure <b>content "
  "comparison</b>: topics are discovered only from content that actually exists, "
  "and there is deliberately no demand and no authority signal.")
p("<b>Topical Authority</b> is the next layer. It keeps the coverage engine and "
  "adds the three signals that separate \"has content\" from \"is the recognized "
  "authority\": <b>demand</b> (what the market searches for), <b>visibility</b> "
  "(who actually ranks / is cited), and <b>off-site trust</b> (backlinks, brand "
  "mentions) — plus the on-site structure Google rewards (site focus, internal "
  "link graph, E-E-A-T markers).")
table(
    ["Dimension", "Topic Coverage (today)", "Topical Authority (this spec)"],
    [
        [cell("Core question", True),
         cell("Who has content on which topics, and who has more?"),
         cell("For the topics that matter in my market, how strong is my authority vs competitors, and where do I invest to win?")],
        [cell("Topic source", True), cell("Content-driven (crawled pages only)"),
         cell("Content-driven <b>+</b> demand-driven (keywords, related questions, SERP entities)")],
        [cell("Demand / white space", True), cell("None by design"),
         cell("Yes — search volume + intent unlock true opportunity gaps")],
        [cell("Off-site signals", True), cell("None"),
         cell("Backlinks, referring domains, anchors, brand mentions")],
        [cell("Visibility", True), cell("None"),
         cell("Rankings, SERP features, AI-overview presence, share of voice, ETV")],
        [cell("Output", True), cell("A diagnosis / mirror of content"),
         cell("A prioritised authority scorecard + where to act")],
    ],
    [1.15, 2.35, 3.1])
callout("The one-line difference",
        "Coverage says <i>“here is who has content on what.”</i> Topical "
        "Authority says <i>“here is who the market and Google treat as the "
        "authority on each topic — and the highest-leverage gaps to close.”</i>")

# ---------------------------------------------------------------- 1
h1("1 · What this is (and is not)")
p("Topical Authority answers a single strategic question:")
callout("Question it answers",
        "“Across the topics in my category, how strong is my topical authority "
        "relative to competitors — weighted by real search demand — and which "
        "topics are the best opportunities to invest in next?”", bg=ZEBRA, bar=SLATE)
h2("It IS")
bullets([
    "A <b>composite, weighted estimate</b> of authority per (domain, topic): coverage depth × demand × visibility × off-site trust × site focus.",
    "<b>Demand-aware</b>: it can finally surface white space (high demand, low coverage/visibility) that Coverage structurally cannot.",
    "<b>Comparative</b>: every metric is computed for you and each competitor, so the map shows relative standing and share of voice.",
    "<b>Actionable</b>: each topic gets a priority (opportunity / defend / maintain / deprioritise) derived from deterministic rules over the signals.",
])
h2("It is NOT")
bullets([
    "<b>Not Google's actual authority signal.</b> It is a transparent, defensible <i>approximation</i> built from public + third-party data. We never claim to reproduce Google's internal score.",
    "<b>Not a content writer.</b> It diagnoses and prioritises; generation stays out of scope.",
    "<b>Not free to run.</b> Demand, SERP and backlink data come from paid APIs (DataForSEO) and/or metered scraping (Apify). Cost is a first-class design constraint (§9).",
])

# ---------------------------------------------------------------- 2
h1("2 · What's new vs Topic Coverage — five added signal layers")
p("Everything in Topic Coverage is reused unchanged (crawl → extract → chunk → "
  "embed → cluster → per-topic coverage). Topical Authority adds five layers on "
  "top, each mapped to concrete data sources in §6.")
table(
    ["#", "New layer", "What it adds", "Primary source"],
    [
        ["1", cell("Demand", True), cell("Search volume, keyword difficulty, intent, related questions / “people also ask”, seasonal trend per topic."), cell("DataForSEO Keywords Data + Labs; Apify SERP")],
        ["2", cell("Visibility", True), cell("Where each domain ranks for the topic's keywords, SERP features owned (snippets, AI overviews, PAA), estimated traffic value (ETV), share of voice."), cell("DataForSEO Labs ranked_keywords + SERP")],
        ["3", cell("Off-site authority", True), cell("Backlinks, referring domains, anchor-text relevance, domain/URL authority, topical link overlap vs competitors, brand mentions."), cell("DataForSEO Backlinks")],
        ["4", cell("Site focus &amp; internal graph", True), cell("Site focus score (topical concentration via embeddings — we already have these), internal link structure, pillar/cluster coherence."), cell("Local (reuse embeddings) + On-Page")],
        ["5", cell("E-E-A-T markers", True), cell("Author/entity presence, content freshness, structured data, trust pages — approximated from crawl + entities."), cell("Local crawl + DataForSEO On-Page")],
    ],
    [0.25, 1.35, 3.4, 1.65])

# ---------------------------------------------------------------- 3
h1("3 · Core concepts &amp; definitions")
bullets([
    "<b>Topic</b> — reused from Coverage: a cluster of semantically similar chunks across all domains, with a human-readable label.",
    "<b>Topic keyword set</b> — the real search keywords mapped to a topic (from the domains' ranked keywords + keyword-idea expansion), each with volume, difficulty, intent.",
    "<b>Topic demand</b> D(t) — aggregate real search demand for a topic = Σ volume over its keyword set (optionally intent-weighted).",
    "<b>Coverage depth</b> C(d,t) — reused Coverage strength: how much on-topic content domain d has (chunks × similarity).",
    "<b>Visibility / Share of Voice</b> V(d,t) — d's share of ranking + SERP-feature presence for the topic's keywords, ETV-weighted.",
    "<b>Off-site authority</b> A(d,t) — topical link strength: referring domains / authority of pages ranking for the topic, anchor relevance.",
    "<b>Site focus</b> F(d,t) — how central the topic is to d (embedding distance of the topic centroid to d's site centroid). Approximates Google's “site focus score”.",
    "<b>Topical Authority score</b> TA(d,t) — the composite (§5), normalised 0–1 across domains per topic.",
    "<b>Opportunity</b> — deterministic label per topic from demand vs your authority (high demand + low TA = invest; this is the white space Coverage can't show).",
])

# ---------------------------------------------------------------- 4
h1("4 · Inputs &amp; outputs")
h2("Input (one run)")
story.append(Paragraph(
    "{ own_domain, competitor_domains[], market_language, location, "
    "max_pages_per_domain, providers:{ serp, keywords, backlinks, enabled },  "
    "budget_usd_cap }", styles["Mono"]))
sp(4)
p("<b>location</b> and <b>market_language</b> now matter (search data is "
  "geo/lang-specific). <b>budget_usd_cap</b> is a hard ceiling on paid-API spend "
  "for the run (§9). Providers are config-gated so the tool still runs in a "
  "coverage-only mode with no keys.")
h2("Output")
p("A stored <b>authority map</b>: categories → topics, and per topic: the "
  "Topical Authority score (you vs each competitor), demand, coverage, "
  "visibility/SoV, off-site authority, site-focus, an <b>opportunity/priority</b> "
  "label, and the evidence behind each (ranking keywords, SERP snapshot, top "
  "referring domains, matched content). Rendered as the radial map — now "
  "colour/size-encoded by authority and opportunity, not just coverage.")

# ---------------------------------------------------------------- 5
h1("5 · The Topical Authority score (model)")
p("For each (domain d, topic t), normalise each component to 0–1 across the "
  "domains in the run, then combine with configurable weights (all weights live "
  "in config — never hardcoded):")
story.append(Paragraph(
    "TA(d,t) = w_c·C' + w_v·V' + w_a·A' + w_f·F'&nbsp;&nbsp; (C=coverage depth, "
    "V=visibility/SoV, A=off-site authority, F=site focus; X' = per-topic "
    "min-max normalised)", styles["Mono"]))
sp(4)
p("Demand D(t) is a <b>topic-level weight</b>, not a per-domain term: it scales "
  "how much a topic matters in roll-ups and drives the opportunity rule, but it "
  "is the same for every domain, so it never distorts the head-to-head TA "
  "comparison on a single topic.")
h2("Per-topic authority state (colour) — extends Coverage's 5 states")
table(
    ["State", "Rule (deterministic)", "Meaning"],
    [
        [cell("You own it", True), cell("TA(you) &gt; max(TA(comp)) + δ"), cell("You are the clear topical authority")],
        [cell("You lead", True), cell("TA(you) highest but within δ of a competitor"), cell("Narrow lead — defend")],
        [cell("Contested", True), cell("Top domains within δ of each other"), cell("No clear owner — winnable")],
        [cell("Competitor leads / owns", True), cell("A competitor &gt; you (+δ / clear)"), cell("You are behind")],
        [cell("Opportunity ★", True, ), cell("D(t) high AND TA(you) low AND no competitor owns"), cell("High-demand gap — best ROI (the true white space)")],
    ],
    [1.35, 2.85, 2.4])
callout("Why this needs the demand layer",
        "Coverage could only compare content volume. With demand D(t), the model "
        "can separate <i>“a topic nobody should care about”</i> from <i>“a "
        "high-demand topic you're losing”</i> — the single most valuable output "
        "Coverage cannot produce.", bg=ZEBRA, bar=ORANGE)

# ---------------------------------------------------------------- 6  (the ask)
story.append(PageBreak())
h1("6 · Data sources &amp; APIs — the data we need")
p("Two complementary providers. <b>DataForSEO</b> is the SEO-metrics layer "
  "(search volume, rankings, backlinks) — structured, priced per row, the "
  "cheapest path to the demand/visibility/authority signals. <b>Apify</b> is the "
  "scraping/crawl layer (content extraction at scale on JS-heavy sites, and an "
  "alternative SERP source) — priced per compute/result. Our existing local "
  "crawler + embeddings stay as the free default and cover site-focus and "
  "content depth without any API.")

h2("6.1 · DataForSEO — endpoints mapped to signals")
table(
    ["API · endpoint", "Data returned (key fields)", "Used for", "≈ Cost"],
    [
        [cell("Keywords Data › Search Volume / Google Ads", True),
         cell("search_volume, cpc, competition, monthly trend (Google Ads + clickstream)"),
         cell("Demand D(t); keyword weighting"), cell("~$0.05 / 1k kw (bulk)")],
        [cell("Labs › Keyword Ideas / Related Keywords / Suggestions", True),
         cell("expanded keywords in the same category, related & PAA-style terms, volume, difficulty"),
         cell("Build the topic keyword set; expand demand beyond what domains already target"), cell("$0.01/task + $0.0001/item")],
        [cell("Labs › Ranked Keywords", True),
         cell("every keyword a domain/URL ranks for: rank_group, rank_absolute, search_volume, keyword_difficulty, ETV, SERP item_types, is_up/down/new/lost"),
         cell("Visibility V(d,t); map keywords→topics via ranking URLs; share of voice"), cell("$0.01/task + $0.0001/item")],
        [cell("Labs › Competitors Domain / Domain Intersection", True),
         cell("competitor overlap of ranking keywords, shared vs unique terms, traffic split"),
         cell("Competitor set validation; contested vs unique topics"), cell("$0.01/task + $0.0001/item")],
        [cell("Labs › Relevant Pages / Historical Rank Overview", True),
         cell("top ranking pages per domain w/ traffic; historical rank & traffic trend"),
         cell("Which page owns a topic; momentum (rising/declining authority)"), cell("$0.01/task + $0.0001/item")],
        [cell("SERP API (Google, live/standard)", True),
         cell("organic results, featured snippet, People-Also-Ask, AI overview, local pack, ads — per keyword"),
         cell("SERP-feature ownership, AI-overview presence, intent, PAA questions"), cell("~$0.0006–0.002 / SERP")],
        [cell("Backlinks API › summary / referring_domains / anchors / bulk", True),
         cell("backlinks, referring_domains, rank, spam_score, anchor text, dofollow ratio; bulk by URL"),
         cell("Off-site authority A(d,t) at the topic's ranking-page level; anchor relevance"), cell("priced per row returned")],
        [cell("On-Page API", True),
         cell("internal links, indexability, structured data, duplicate content, Lighthouse, raw HTML"),
         cell("Internal link graph, E-E-A-T/technical markers (optional; local crawl can substitute)"), cell("per page crawled")],
    ],
    [1.55, 2.35, 1.85, 0.9])
small("Prices are indicative from DataForSEO's published model (Labs: ~$0.01 per "
      "task + ~$0.0001 per returned item; SERP and Backlinks priced separately). "
      "Treat as order-of-magnitude for budgeting, not a quote.")

h2("6.2 · Apify — actors mapped to needs")
table(
    ["Actor", "Data returned", "Used for", "≈ Cost"],
    [
        [cell("Website Content Crawler", True),
         cell("clean main content at scale, JS-rendered pages, handles proxies/anti-bot, sitemap+crawl"),
         cell("Content depth on JS-heavy sites our local crawler struggles with; scale beyond one host"), cell("compute-unit based")],
        [cell("Google Search Results Scraper / SERP", True),
         cell("organic, ads, PAA, AI overviews, related queries; per country/language/location"),
         cell("SERP + visibility as an alternative / cross-check to DataForSEO SERP"), cell("~$0.5 / 1k SERPs (≈$0.002/query)")],
        [cell("SEO Content Orchestrator (or compose actors)", True),
         cell("pipeline: keyword volume → SERP → competitor content crawl → brief"),
         cell("Optional turnkey enrichment if we prefer Apify over DataForSEO for demand+SERP"), cell("per-run / event based")],
    ],
    [1.7, 2.3, 1.85, 0.85])
callout("Provider strategy (recommended)",
        "Use <b>DataForSEO</b> as the primary structured signal source (demand, "
        "ranked keywords, backlinks) — it's cheaper per data point and returns "
        "clean metrics. Use <b>Apify</b> for (a) content extraction on sites our "
        "local Playwright crawler can't handle, and (b) as a SERP cross-check. "
        "Keep both behind a provider interface so either can be swapped or "
        "disabled; the tool must still run coverage-only with no keys.")

h2("6.3 · Signal → source quick map")
table(
    ["Signal in the model", "Free / local", "Paid source"],
    [
        [cell("Coverage depth C", True), cell("✓ local crawl + embeddings (built)"), cell("— (Apify crawler for scale)")],
        [cell("Site focus F", True), cell("✓ embeddings (built)"), cell("—")],
        [cell("Demand D", True), cell("✗"), cell("DataForSEO Keywords Data + Labs")],
        [cell("Visibility / SoV V", True), cell("✗"), cell("DataForSEO Labs ranked_keywords + SERP")],
        [cell("Off-site authority A", True), cell("✗"), cell("DataForSEO Backlinks")],
        [cell("Internal graph / E-E-A-T", True), cell("~ partial (local crawl)"), cell("DataForSEO On-Page")],
    ],
    [2.4, 2.3, 2.0])

# ---------------------------------------------------------------- 7
story.append(PageBreak())
h1("7 · Architecture — pipeline extension")
p("Stages 1–4 are the existing Topic Coverage pipeline, reused as-is. Stages 5–9 "
  "are new and each is independently skippable (config / budget-gated).")
story.append(Paragraph(
    "[1] crawl+extract → [2] chunk+embed → [3] cluster→topics → [4] coverage "
    "(EXISTING)<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
    "[5] keyword mapping&nbsp;&nbsp;— topic ↔ real keywords (Labs ranked_keywords + keyword ideas)<br/>"
    "[6] demand enrich&nbsp;&nbsp;&nbsp;&nbsp;— volume/difficulty/intent per keyword (Keywords Data)<br/>"
    "[7] visibility fetch&nbsp;&nbsp;&nbsp;— rankings, SERP features, ETV, SoV (Labs + SERP)<br/>"
    "[8] authority fetch&nbsp;&nbsp;&nbsp;— backlinks / referring domains for ranking pages (Backlinks)<br/>"
    "[9] score + state&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;— site focus (local) + composite TA + opportunity rules<br/>"
    "&nbsp;&nbsp;&nbsp;&nbsp;↓<br/>"
    "STORE (SQLite, cached) → API → radial map (authority/opportunity encoded)",
    styles["Mono"]))
sp(6)
p("A <b>caching + rate-limit layer</b> wraps every paid call (keyed by "
  "provider+endpoint+params, TTL in config) so re-runs and overlapping topics "
  "don't re-buy the same data — essential for cost control.")

# ---------------------------------------------------------------- 8
h1("8 · Data model additions (SQLite)")
story.append(Paragraph(
    "keywords( id, run_id, keyword, volume, difficulty, cpc, intent, source )<br/>"
    "topic_keywords( topic_id, keyword_id, weight )&nbsp;&nbsp;— topic ↔ keyword map<br/>"
    "rankings( id, run_id, domain_id, keyword_id, rank_absolute, url, etv, serp_features_json, trend )<br/>"
    "serp_features( id, run_id, keyword_id, feature, owner_domain )&nbsp;— snippet/PAA/AI-overview<br/>"
    "backlinks_domain( id, run_id, domain_id, topic_id, referring_domains, backlinks, rank, spam_score )<br/>"
    "internal_links( id, run_id, domain_id, from_url, to_url, anchor )&nbsp;— optional<br/>"
    "topic_authority( id, run_id, topic_id, domain_id, coverage, demand, visibility, "
    "authority_offsite, site_focus, ta_score, state, opportunity )<br/>"
    "api_cache( key, provider, endpoint, response_json, cost_usd, fetched_at )",
    styles["Mono"]))
sp(6)
p("All existing tables (runs, domains, pages, chunks, topics, categories, "
  "topic_coverage, topic_state) are unchanged; the above are additive.")

# ---------------------------------------------------------------- 9
h1("9 · Cost model &amp; budget (the new hard constraint)")
p("Unlike Coverage, a run now spends real money on APIs. Cost must be estimable "
  "<i>before</i> the run and capped <i>during</i> it.")
h2("Rough per-run estimate")
p("For N domains, T topics, ~K keywords/topic:")
bullets([
    "<b>Keyword set + demand</b>: N × (ranked-keywords tasks) + one bulk volume call ≈ small, dominated by item counts (T·K items × ~$0.0001).",
    "<b>Visibility</b>: reuse ranked-keywords items; add SERP calls only for the top keywords per topic you want feature-level detail on (T × top-k × ~$0.001).",
    "<b>Backlinks</b>: only for the specific ranking pages that own each topic (N × T rows) — the biggest cost lever; sample, don't fetch everything.",
])
p("Worked ballpark: 4 domains × 20 topics × 25 keywords ≈ 2,000 keyword-items "
  "(~$0.20) + ~400 SERP lookups (~$0.40–0.80) + a few hundred backlink summaries "
  "→ typically <b>low single-digit dollars per run</b> with sampling; more if you "
  "fetch full backlink profiles. Every cap below lives in config.")
h2("Cost controls (all config)")
bullets([
    "<b>budget_usd_cap</b> per run — stop enrichment when hit; degrade to what's already fetched.",
    "Caps: max_keywords_per_topic, max_serp_lookups_per_topic, backlink sampling (top-k ranking pages only).",
    "Aggressive <b>api_cache</b> with TTL; dedupe overlapping keywords across topics.",
    "Provider toggles: run demand-only, or demand+visibility, or full, per budget.",
])

# ---------------------------------------------------------------- 10
h1("10 · Milestones (build order)")
table(
    ["#", "Milestone", "Deliverable", "Acceptance check"],
    [
        ["A0", cell("Provider layer + cache", True), cell("DataForSEO + Apify clients behind one interface; SQLite api_cache; budget cap; all keys/caps in config"), cell("Mock + one live call cached; re-run makes 0 paid calls; coverage-only still works keyless")],
        ["A1", cell("Keyword mapping", True), cell("Topic ↔ real keyword sets via ranked_keywords + keyword ideas"), cell("Each topic has a keyword set; keywords map back to ranking URLs")],
        ["A2", cell("Demand enrichment", True), cell("Volume/difficulty/intent per keyword; topic demand D(t)"), cell("topic_keywords populated; D(t) sane vs known-popular topics")],
        ["A3", cell("Visibility", True), cell("Rankings, SERP features, ETV, share of voice per (domain,topic)"), cell("rankings populated; SoV sums to ~100% per topic across domains")],
        ["A4", cell("Off-site authority", True), cell("Backlink/referring-domain strength for topic-owning pages"), cell("backlinks_domain populated for sampled pages; spot-checks reasonable")],
        ["A5", cell("Authority scoring", True), cell("Site focus (local) + composite TA + states + opportunity rules"), cell("Every topic has TA per domain, one state, one opportunity label")],
        ["A6", cell("UI + report", True), cell("Radial map encoded by authority/opportunity; per-topic detail w/ keywords, SERP, backlinks, cost summary"), cell("Opening a run shows authority map; clicking a topic shows the evidence + run cost")],
    ],
    [0.3, 1.35, 2.75, 2.05])

# ---------------------------------------------------------------- 11
h1("11 · Tech stack additions")
bullets([
    "<b>Providers</b>: DataForSEO REST (httpx), Apify client — both behind a <code>Provider</code> interface, config-gated, keyless-degradable.",
    "<b>Cache/rate-limit</b>: SQLite-backed response cache (cost + TTL), per-provider concurrency + backoff (reuse the crawl politeness pattern).",
    "<b>Scoring</b>: numpy for per-topic normalisation; deterministic rule function for state + opportunity (unit-tested, like coverage_state today).",
    "<b>Config</b>: new weights (w_c/w_v/w_a/w_f), δ, demand intent weights, all caps, budget_usd_cap, provider keys — every threshold in config.py.",
    "<b>Secrets</b>: DATAFORSEO_LOGIN/PASSWORD, APIFY_TOKEN via .env (git-ignored), same pattern as the optional LLM labels.",
])

# ---------------------------------------------------------------- 12
h1("12 · Risks, honesty &amp; guardrails")
bullets([
    "<b>Approximation, not ground truth.</b> TA is a transparent estimate of authority, not Google's internal score. Every component is inspectable; never present it as “Google's number”.",
    "<b>Cost runaway.</b> Paid APIs make a naïve run expensive. The budget cap, caches and sampling are mandatory, not optional.",
    "<b>Data freshness &amp; geo.</b> Rankings/volume are location/language/time specific; store the location + fetch date with every metric.",
    "<b>Keyword↔topic mapping is the hard part.</b> Getting real keywords onto the right content-derived topic is the core research risk — validate A1 carefully before building on it.",
    "<b>Still not content generation.</b> Recommendations are prioritisation (“invest here”), not drafts. Writing remains out of scope.",
])

# ---------------------------------------------------------------- 13
h1("13 · Acceptance criteria (whole system)")
bullets([
    "Given an own domain + ≥1 competitor + a location/language, a run reuses coverage, enriches with demand/visibility/authority within the budget cap, and completes with no manual steps.",
    "Every topic has real search demand attached, a share-of-voice per domain summing to ~100%, and off-site authority for the topic-owning pages (sampled).",
    "Every topic has exactly one composite Topical Authority score per domain, one authority state, and one opportunity/priority label from deterministic rules.",
    "The map renders authority + opportunity; the detail panel shows the evidence (keywords, SERP snapshot, top referring domains, matched content) and the run's API cost.",
    "The whole thing degrades gracefully: with no keys it runs as today's coverage tool; with a budget cap it never overspends.",
])

# ---------------------------------------------------------------- SOURCES
h1("Sources (research)")
small(
    "DataForSEO — APIs overview &amp; docs: dataforseo.com/apis, docs.dataforseo.com/v3, "
    "Labs ranked_keywords &amp; overview endpoints, DataForSEO Labs product page. "
    "Apify — apify.com/apify/google-search-scraper, Website Content Crawler, SEO "
    "Content Orchestrator, use-apify.com SEO tools 2026. Topical authority signals "
    "— ahrefs.com/blog/topical-authority (site focus score, content coverage, "
    "internal linking, E-E-A-T, off-site), growth-memo.com (measuring topical "
    "authority), entity-based SEO guides 2026. Retrieved Jul 2026; treat pricing as "
    "indicative.")

doc = SimpleDocTemplate(
    str(OUT), pagesize=LETTER,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    topMargin=0.8 * inch, bottomMargin=0.7 * inch,
    title="Topical Authority — Build & Scoping Specification",
    author="Topic Coverage project",
)


def footer(canvas, d):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, 0.45 * inch, "Topical Authority — scoping spec")
    canvas.drawRightString(7.6 * inch, 0.45 * inch, "Page %d" % d.page)
    canvas.setStrokeColor(LINE)
    canvas.line(0.9 * inch, 0.6 * inch, 7.6 * inch, 0.6 * inch)
    canvas.restoreState()


doc.build(story, onLaterPages=footer, onFirstPage=lambda c, d: None)
print("wrote", OUT)
