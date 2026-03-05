#!/usr/bin/env python3
"""
Multi-source paper search for the start-literature-research skill.

Sources:
  1. arXiv  — recent preprints in statistics/genomics categories
  2. bioRxiv / medRxiv — genetics, genomics, epidemiology preprints
  3. PubMed (journal sweep) — published papers in target journals
  4. PubMed (author sweep) — papers by priority authors
  5. Semantic Scholar — high-citation papers (optional, off by default)
"""

import xml.etree.ElementTree as ET
import json
import re
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests library not found, using urllib")

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------
ARXIV_NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom',
}

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = (
    "title,abstract,publicationDate,citationCount,"
    "influentialCitationCount,url,authors,externalIds"
)

PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIORXIV_BASE_URL = "https://api.biorxiv.org/details"

PUBMED_REQUEST_INTERVAL = 0.4   # max ~3 requests/s without API key
BIORXIV_REQUEST_INTERVAL = 1.0

# bioRxiv/medRxiv subject categories to retain (client-side filter)
BIORXIV_KEEP_CATEGORIES = {
    "genetics", "genomics", "bioinformatics", "epidemiology",
    "genetic and genomic medicine", "evolutionary biology",
    "systems biology", "neuroscience",
}

ARXIV_CATEGORY_KEYWORDS = {
    "stat.ME": "statistical methodology genetics genomics",
    "stat.AP": "statistical applications genetics epidemiology",
    "stat.CO": "statistical computation genomics",
    "q-bio.GN": "genomics genetics sequencing",
    "q-bio.QM": "quantitative methods biology genomics",
    "cs.LG":   "machine learning",
}

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
SCORE_MAX = 3.0

RELEVANCE_CATEGORY_MATCH_BOOST  = 1.0

# Keyword weight tiers: (title_boost, abstract_boost)
# high   — core method/concept terms; a single title match passes MIN_RELEVANCE_SCORE
# medium — important but broader terms
# low    — supporting vocabulary (legacy default)
KEYWORD_WEIGHT_TIERS = {
    'high':   (2.0, 1.2),
    'medium': (1.0, 0.5),
    'low':    (0.5, 0.3),
}
# Keep these as aliases for the low tier (used elsewhere for clarity)
RELEVANCE_TITLE_KEYWORD_BOOST   = KEYWORD_WEIGHT_TIERS['low'][0]
RELEVANCE_SUMMARY_KEYWORD_BOOST = KEYWORD_WEIGHT_TIERS['low'][1]

RECENCY_THRESHOLDS = [
    (7,  3.0),   # within last week
    (14, 2.0),   # 1–2 weeks
    (30, 1.0),   # 2–4 weeks
]
RECENCY_DEFAULT = 0.0

POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE = 100

WEIGHTS_NORMAL = {'relevance': 0.40, 'recency': 0.20, 'popularity': 0.30, 'quality': 0.10}
WEIGHTS_HOT    = {'relevance': 0.35, 'recency': 0.10, 'popularity': 0.45, 'quality': 0.10}

S2_RATE_LIMIT_WAIT        = 30
S2_CATEGORY_REQUEST_INTERVAL = 3

# Recommendation-score thresholds
THRESHOLD_HIGH     = 7.5
THRESHOLD_MODERATE = 6.5
THRESHOLD_LOW      = 5.5

# Priority-author boost: papers by a priority author AND relevance >= threshold
# get this bonus added to their recommendation score (capped at 10).
PRIORITY_AUTHOR_RELEVANCE_THRESHOLD = 1.5
PRIORITY_AUTHOR_SCORE_BOOST         = 2.0

# Source boost for bioRxiv/medRxiv: these servers are biology-specific so
# their papers are inherently more relevant than generic arXiv stat.ME/stat.AP.
BIORXIV_SOURCE_BOOST = 0.5

# Minimum relevance score for a paper to be considered at all.
# Requires at least one category match (1.0) or two title keyword matches
# (2 × 0.5 = 1.0). Filters out papers that only weakly mention a keyword
# once in the abstract (0.3), which tend to be off-topic.
MIN_RELEVANCE_SCORE = 1.0


# ===========================================================================
# Config loading
# ===========================================================================

def load_research_config(config_path: str) -> Dict:
    import yaml
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error("Error loading config: %s", e)
        return {
            "research_domains": {
                "Statistical Genetics": {
                    "keywords": ["GWAS", "fine-mapping", "eQTL", "PRS"],
                    "arxiv_categories": ["stat.ME", "q-bio.GN"],
                    "priority": 5,
                }
            }
        }


# ===========================================================================
# Date utilities
# ===========================================================================

def parse_date(date_str: str) -> datetime:
    """Parse YYYYMMDD string into a datetime."""
    return datetime.strptime(date_str, '%Y%m%d')


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation — used for deduplication."""
    return re.sub(r'[^a-z0-9 ]', '', title.lower()).strip()


# ===========================================================================
# arXiv search
# ===========================================================================

def search_arxiv_by_date_range(
    categories: List[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 200,
    max_retries: int = 3,
) -> List[Dict]:
    category_query = "+OR+".join([f"cat:{cat}" for cat in categories])
    date_query = (
        f"submittedDate:[{start_date.strftime('%Y%m%d')}0000"
        f"+TO+{end_date.strftime('%Y%m%d')}2359]"
    )
    full_query = f"({category_query})+AND+{date_query}"
    url = (
        f"https://export.arxiv.org/api/query?"
        f"search_query={full_query}&"
        f"max_results={max_results}&"
        f"sortBy=submittedDate&sortOrder=descending"
    )

    logger.info("[arXiv] Searching %s to %s", start_date.date(), end_date.date())

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                xml_content = response.read().decode('utf-8')
                papers = parse_arxiv_xml(xml_content)
                logger.info("[arXiv] Found %d papers", len(papers))
                return papers
        except Exception as e:
            logger.warning("[arXiv] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
    logger.error("[arXiv] Failed after %d attempts", max_retries)
    return []


def parse_arxiv_xml(xml_content: str) -> List[Dict]:
    papers = []
    try:
        root = ET.fromstring(xml_content)
        for entry in root.findall('atom:entry', ARXIV_NS):
            paper: Dict = {}

            id_elem = entry.find('atom:id', ARXIV_NS)
            if id_elem is not None:
                paper['id'] = id_elem.text
                m = re.search(r'arXiv:(\d+\.\d+)', paper['id']) or \
                    re.search(r'/(\d+\.\d+)$', paper['id'])
                paper['arxiv_id'] = m.group(1) if m else None

            title_elem = entry.find('atom:title', ARXIV_NS)
            if title_elem is not None:
                paper['title'] = title_elem.text.strip()

            summary_elem = entry.find('atom:summary', ARXIV_NS)
            if summary_elem is not None:
                paper['abstract'] = summary_elem.text.strip()

            authors = []
            for author in entry.findall('atom:author', ARXIV_NS):
                name_elem = author.find('atom:name', ARXIV_NS)
                if name_elem is not None:
                    authors.append(name_elem.text)
            paper['authors'] = authors

            published_elem = entry.find('atom:published', ARXIV_NS)
            if published_elem is not None:
                paper['published'] = published_elem.text
                try:
                    paper['published_date'] = datetime.fromisoformat(
                        paper['published'].replace('Z', '+00:00')
                    )
                except (ValueError, TypeError):
                    paper['published_date'] = None

            cats = []
            for cat in entry.findall('atom:category', ARXIV_NS):
                t = cat.get('term')
                if t:
                    cats.append(t)
            paper['categories'] = cats

            if 'id' in paper:
                paper['url'] = paper['id']
            paper['source'] = 'arxiv'
            papers.append(paper)

    except ET.ParseError as e:
        logger.error("Error parsing arXiv XML: %s", e)
    return papers


# ===========================================================================
# bioRxiv / medRxiv search
# ===========================================================================

def search_biorxiv_by_date_range(
    start_date: datetime,
    end_date: datetime,
    max_results: int = 200,
) -> List[Dict]:
    """Fetch recent preprints from bioRxiv and medRxiv, filtered by subject."""
    papers: List[Dict] = []
    start_str = start_date.strftime('%Y-%m-%d')
    end_str   = end_date.strftime('%Y-%m-%d')

    for server in ('biorxiv', 'medrxiv'):
        cursor = 0
        fetched = 0
        while fetched < max_results:
            url = f"{BIORXIV_BASE_URL}/{server}/{start_str}/{end_str}/{cursor}/json"
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                logger.warning("[%s] Error at cursor %d: %s", server, cursor, e)
                break

            collection = data.get('collection', [])
            if not collection:
                break

            for item in collection:
                category = (item.get('category') or '').lower()
                if not any(kw in category for kw in BIORXIV_KEEP_CATEGORIES):
                    continue

                doi = item.get('doi', '')
                pub_date_str = item.get('date', '')
                try:
                    pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
                except (ValueError, TypeError):
                    pub_date = None

                author_str = item.get('authors', '')
                author_list = [a.strip() for a in author_str.split(';') if a.strip()]

                paper = {
                    'title': item.get('title', '').strip(),
                    'abstract': item.get('abstract', '').strip(),
                    'authors': author_list,
                    'published_date': pub_date,
                    'url': f"https://www.{server}.org/content/{doi}v1" if doi else '',
                    'doi': doi,
                    'source': server,
                    'categories': [item.get('category', '')],
                }
                papers.append(paper)
                fetched += 1

            messages = data.get('messages', [])
            total = int(messages[0].get('total', 0)) if messages else 0
            cursor += len(collection)
            if cursor >= total or cursor >= max_results:
                break
            time.sleep(BIORXIV_REQUEST_INTERVAL)

        logger.info("[%s] Collected %d papers (subject-filtered)", server, fetched)

    return papers


# ===========================================================================
# PubMed search
# ===========================================================================

def _pubmed_fetch(url: str, max_retries: int = 3) -> Optional[str]:
    """Fetch a URL with retries, return content as string or None."""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return resp.read().decode('utf-8')
        except Exception as e:
            logger.warning("[PubMed] HTTP error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
    return None


def _build_journal_filter(journals: List[str]) -> str:
    """Build a PubMed journal OR query term."""
    parts = [f'"{j}"[Journal]' for j in journals]
    return '(' + ' OR '.join(parts) + ')'


def _build_author_filter(authors: List[str]) -> str:
    """Format priority author names for PubMed author query.

    Each name generates two terms to handle middle-name variants:
      "Alkes Price"       → "Price A"[Author]   (first initial only)
      "Alkes L Price"     → "Price A"[Author] OR "Price AL"[Author]
    Using OR of both ensures we catch "Price A", "Price AL", etc.
    """
    terms = []
    for full_name in authors:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            first_parts = parts[:-1]          # everything before last name
            first_initial = first_parts[0][0] # first letter of first name
            # Always add "Last F" (catches all variants)
            terms.append(f'"{last} {first_initial}"[Author]')
            # If there are middle names, also add "Last FM" initials
            if len(first_parts) >= 2:
                initials = ''.join(p[0] for p in first_parts)
                terms.append(f'"{last} {initials}"[Author]')
        else:
            terms.append(f'"{full_name}"[Author]')
    return '(' + ' OR '.join(terms) + ')'


def parse_pubmed_xml(xml_content: str) -> List[Dict]:
    """Parse PubMed efetch XML into a list of paper dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error("[PubMed] XML parse error: %s", e)
        return []

    for article in root.findall('.//PubmedArticle'):
        paper: Dict = {'source': 'pubmed'}

        # Title
        title_elem = article.find('.//ArticleTitle')
        paper['title'] = (title_elem.text or '').strip() if title_elem is not None else ''

        # Abstract
        abstract_parts = article.findall('.//AbstractText')
        paper['abstract'] = ' '.join(
            (p.text or '') for p in abstract_parts if p.text
        ).strip()

        # Authors
        authors = []
        for author in article.findall('.//Author'):
            last = author.find('LastName')
            fore = author.find('ForeName')
            if last is not None:
                name = last.text or ''
                if fore is not None and fore.text:
                    name = f"{fore.text} {name}"
                authors.append(name.strip())
        paper['authors'] = authors

        # Journal
        journal_elem = article.find('.//Journal/Title')
        paper['journal'] = journal_elem.text.strip() if journal_elem is not None and journal_elem.text else ''

        # Publication date
        pub_date = article.find('.//PubDate')
        if pub_date is not None:
            year_elem  = pub_date.find('Year')
            month_elem = pub_date.find('Month')
            day_elem   = pub_date.find('Day')
            year  = year_elem.text  if year_elem  is not None else ''
            month = month_elem.text if month_elem is not None else '01'
            day   = day_elem.text   if day_elem   is not None else '01'
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
            }
            month = month_map.get(month, month.zfill(2))
            day   = day.zfill(2) if day.isdigit() else '01'
            if year:
                try:
                    paper['published_date'] = datetime.strptime(
                        f"{year}-{month}-{day}", '%Y-%m-%d'
                    )
                except ValueError:
                    paper['published_date'] = None
            else:
                paper['published_date'] = None
        else:
            paper['published_date'] = None

        # PMID & DOI
        pmid_elem = article.find('.//PMID')
        pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ''
        paper['pmid'] = pmid
        paper['url']  = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ''

        doi = ''
        for id_elem in article.findall('.//ArticleId'):
            if id_elem.get('IdType') == 'doi':
                doi = (id_elem.text or '').strip()
                break
        paper['doi'] = doi

        if paper.get('title'):
            papers.append(paper)

    return papers


def search_pubmed_recent(
    keywords: List[str],
    start_date: datetime,
    end_date: datetime,
    journals: Optional[List[str]] = None,
    max_results: int = 100,
) -> List[Dict]:
    """Search PubMed by keyword + optional journal filter + date range."""
    keyword_query = ' OR '.join([f'"{kw}"' for kw in keywords])  # all keywords; URL stays well under limits
    # Use [EPDT] (electronic publication date) for day-precision filtering.
    # [EDAT] (Entrez/indexing date) lags the actual online publication by 2–3 days,
    # causing recently published papers to be missed in narrow date windows.
    # [PDAT] (print publication date) often has only year+month precision.
    # [EPDT] matches the date the article was made available online, which is what
    # we want when surveying papers published on a specific date.
    date_range    = f'{start_date.strftime("%Y/%m/%d")}:{end_date.strftime("%Y/%m/%d")}[EPDT]'

    if journals:
        journal_query = _build_journal_filter(journals)
        query = f'({keyword_query}) AND {journal_query} AND {date_range}'
    else:
        query = f'({keyword_query}) AND {date_range}'

    # Step 1: esearch — get PMIDs
    search_url = (
        f"{PUBMED_BASE_URL}/esearch.fcgi?"
        f"db=pubmed&term={urllib.parse.quote(query)}"
        f"&retmax={max_results}&retmode=json"
    )
    logger.info("[PubMed] Searching (journal sweep): %d journals", len(journals) if journals else 0)

    content = _pubmed_fetch(search_url)
    if not content:
        return []

    try:
        search_data = json.loads(content)
        pmids = search_data.get('esearchresult', {}).get('idlist', [])
    except (json.JSONDecodeError, KeyError):
        return []

    if not pmids:
        logger.info("[PubMed] No PMIDs found")
        return []

    logger.info("[PubMed] Found %d PMIDs, fetching details...", len(pmids))
    time.sleep(PUBMED_REQUEST_INTERVAL)

    # Step 2: efetch — get full records
    fetch_url = (
        f"{PUBMED_BASE_URL}/efetch.fcgi?"
        f"db=pubmed&id={','.join(pmids)}"
        f"&retmode=xml&rettype=abstract"
    )
    xml_content = _pubmed_fetch(fetch_url)
    if not xml_content:
        return []

    papers = parse_pubmed_xml(xml_content)
    logger.info("[PubMed] Parsed %d papers", len(papers))
    return papers


def search_pubmed_by_authors(
    authors: List[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 50,
) -> List[Dict]:
    """Search PubMed for papers by priority authors in the date range."""
    author_query = _build_author_filter(authors)
    # Use [EPDT] — see journal-sweep function for rationale.
    date_range   = f'{start_date.strftime("%Y/%m/%d")}:{end_date.strftime("%Y/%m/%d")}[EPDT]'
    query        = f'{author_query} AND {date_range}'

    search_url = (
        f"{PUBMED_BASE_URL}/esearch.fcgi?"
        f"db=pubmed&term={urllib.parse.quote(query)}"
        f"&retmax={max_results}&retmode=json"
    )
    logger.info("[PubMed] Author sweep: %d priority authors", len(authors))

    content = _pubmed_fetch(search_url)
    if not content:
        return []

    try:
        pmids = json.loads(content).get('esearchresult', {}).get('idlist', [])
    except (json.JSONDecodeError, KeyError):
        return []

    if not pmids:
        logger.info("[PubMed] No author papers found")
        return []

    logger.info("[PubMed] Found %d author PMIDs, fetching details...", len(pmids))
    time.sleep(PUBMED_REQUEST_INTERVAL)

    fetch_url = (
        f"{PUBMED_BASE_URL}/efetch.fcgi?"
        f"db=pubmed&id={','.join(pmids)}"
        f"&retmode=xml&rettype=abstract"
    )
    xml_content = _pubmed_fetch(fetch_url)
    if not xml_content:
        return []

    papers = parse_pubmed_xml(xml_content)
    # Flag all as priority-author papers
    for p in papers:
        p['priority_author'] = True
    logger.info("[PubMed] Parsed %d author papers", len(papers))
    return papers


# ===========================================================================
# Semantic Scholar (optional hot papers)
# ===========================================================================

def search_semantic_scholar_hot_papers(
    query: str,
    start_date: datetime,
    end_date: datetime,
    top_k: int = 20,
    max_retries: int = 3,
) -> List[Dict]:
    date_range = f"{start_date.strftime('%Y-%m-%d')}:{end_date.strftime('%Y-%m-%d')}"
    params = {
        "query": query,
        "publicationDateOrYear": date_range,
        "limit": 100,
        "fields": SEMANTIC_SCHOLAR_FIELDS,
    }
    headers = {"User-Agent": "LiteratureResearch-PaperFetcher/2.0"}

    logger.info("[S2] Hot papers %s to %s | query: '%s'", start_date.date(), end_date.date(), query)

    for attempt in range(max_retries):
        try:
            if HAS_REQUESTS:
                response = requests.get(
                    SEMANTIC_SCHOLAR_API_URL, params=params, headers=headers, timeout=15
                )
                response.raise_for_status()
                data = response.json()
            else:
                qs = urllib.parse.urlencode(params)
                req = urllib.request.Request(f"{SEMANTIC_SCHOLAR_API_URL}?{qs}", headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

            papers = data.get("data", [])
            valid = []
            for p in papers:
                if not p.get("title") or not p.get("abstract"):
                    continue
                p["influentialCitationCount"] = p.get("influentialCitationCount") or 0
                p["citationCount"]            = p.get("citationCount") or 0
                p["source"]     = "semantic_scholar"
                p["hot_score"]  = p["influentialCitationCount"]
                # Normalise field names for downstream processing
                p["abstract"]   = p.get("abstract", "")
                author_objects  = p.get("authors", [])
                p["authors"]    = [a.get("name", "") for a in author_objects]
                p["arxiv_id"]   = (p.get("externalIds") or {}).get("ArXiv")
                pub_str = p.get("publicationDate") or ""
                try:
                    p["published_date"] = datetime.strptime(pub_str, '%Y-%m-%d') if pub_str else None
                except ValueError:
                    p["published_date"] = None
                valid.append(p)

            valid.sort(key=lambda x: x["influentialCitationCount"], reverse=True)
            logger.info("[S2] Found %d valid papers, returning top %d", len(valid), top_k)
            return valid[:top_k]

        except Exception as e:
            err = str(e)
            logger.warning("[S2] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                wait = S2_RATE_LIMIT_WAIT if ("429" in err or "Too Many Requests" in err) else (2 ** attempt) * 2
                time.sleep(wait)

    return []


def search_hot_papers_from_categories(
    categories: List[str],
    start_date: datetime,
    end_date: datetime,
    top_k_per_category: int = 5,
) -> List[Dict]:
    all_hot: List[Dict] = []
    seen_arxiv_ids: Set[str] = set()

    for cat in categories:
        query = ARXIV_CATEGORY_KEYWORDS.get(cat, cat)
        papers = search_semantic_scholar_hot_papers(
            query=query, start_date=start_date, end_date=end_date, top_k=top_k_per_category
        )
        for p in papers:
            aid = p.get("arxiv_id")
            if aid and aid in seen_arxiv_ids:
                continue
            if aid:
                seen_arxiv_ids.add(aid)
            all_hot.append(p)
        time.sleep(S2_CATEGORY_REQUEST_INTERVAL)

    all_hot.sort(key=lambda x: x.get("influentialCitationCount", 0), reverse=True)
    return all_hot


# ===========================================================================
# Scoring
# ===========================================================================

def _normalize_keywords(keywords_raw) -> Dict[str, List[str]]:
    """Normalize the keywords field from research_interests.yaml.

    Accepts two formats:
      - flat list  → treated as all 'low' weight (legacy)
      - dict       → expected keys 'high', 'medium', 'low' (new tiered format)
    """
    if isinstance(keywords_raw, list):
        return {'high': [], 'medium': [], 'low': keywords_raw}
    if isinstance(keywords_raw, dict):
        return {
            'high':   keywords_raw.get('high', []),
            'medium': keywords_raw.get('medium', []),
            'low':    keywords_raw.get('low', []),
        }
    return {'high': [], 'medium': [], 'low': []}


def calculate_relevance_score(
    paper: Dict,
    domains: Dict,
) -> Tuple[float, Optional[str], List[str]]:
    title    = paper.get('title', '').lower()
    abstract = paper.get('abstract', '').lower()
    cats     = set(paper.get('categories', []))

    max_score     = 0.0
    best_domain   = None
    matched_kws: List[str] = []

    for domain_name, domain_config in domains.items():
        score = 0.0
        domain_matched: List[str] = []

        kws = _normalize_keywords(domain_config.get('keywords', []))
        for tier, (title_boost, abs_boost) in KEYWORD_WEIGHT_TIERS.items():
            for kw in kws.get(tier, []):
                kw_lower = kw.lower()
                if kw_lower in title:
                    score += title_boost
                    domain_matched.append(kw)
                elif kw_lower in abstract:
                    score += abs_boost
                    domain_matched.append(kw)

        for cat in domain_config.get('arxiv_categories', []):
            if cat in cats:
                score += RELEVANCE_CATEGORY_MATCH_BOOST
                domain_matched.append(cat)

        if score > max_score:
            max_score   = score
            best_domain = domain_name
            matched_kws = domain_matched

    return max_score, best_domain, matched_kws


def calculate_recency_score(published_date: Optional[datetime], reference_date: Optional[datetime] = None) -> float:
    if published_date is None:
        return 0.0
    if reference_date is None:
        reference_date = datetime.now(published_date.tzinfo) if published_date.tzinfo else datetime.now()
    else:
        # Align timezone awareness
        if published_date.tzinfo and reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=published_date.tzinfo)
        elif published_date.tzinfo is None and reference_date.tzinfo:
            published_date = published_date.replace(tzinfo=reference_date.tzinfo)
    days_diff = (reference_date - published_date).days
    for max_days, score in RECENCY_THRESHOLDS:
        if days_diff <= max_days:
            return score
    return RECENCY_DEFAULT


def calculate_quality_score(paper: Dict, config: Dict) -> float:
    """Score how comprehensively a paper aligns with research_interests.yaml.

    Accumulates keyword matches across ALL domains (weighted by domain priority),
    plus a bonus if the paper appears in a target journal. This rewards papers
    that span multiple high-priority research areas over papers that only
    incidentally mention a single keyword.
    """
    domains       = config.get('research_domains', {})
    target_journals = [j.lower() for j in config.get('target_journals', [])]

    title    = paper.get('title', '').lower()
    abstract = paper.get('abstract', '').lower()
    cats     = set(paper.get('categories', []))
    journal  = paper.get('journal', '').lower()

    total = 0.0
    for domain_conf in domains.values():
        priority = domain_conf.get('priority', 1)   # 1–5
        weight   = priority / 5.0                   # normalise to 0–1

        domain_score = 0.0
        kws = _normalize_keywords(domain_conf.get('keywords', []))
        for tier, (title_boost, abs_boost) in KEYWORD_WEIGHT_TIERS.items():
            for kw in kws.get(tier, []):
                kl = kw.lower()
                if kl in title:
                    domain_score += title_boost
                elif kl in abstract:
                    domain_score += abs_boost
        for cat in domain_conf.get('arxiv_categories', []):
            if cat in cats:
                domain_score += RELEVANCE_CATEGORY_MATCH_BOOST

        total += weight * domain_score

    # Bonus for publication in a target journal
    if journal and any(j in journal for j in target_journals):
        total += 0.5

    return min(total, SCORE_MAX)


def calculate_recommendation_score(
    relevance: float,
    recency: float,
    popularity: float,
    quality: float,
    is_hot: bool = False,
) -> float:
    normalized = {k: (v / SCORE_MAX) * 10 for k, v in
                  [('relevance', relevance), ('recency', recency),
                   ('popularity', popularity), ('quality', quality)]}
    weights = WEIGHTS_HOT if is_hot else WEIGHTS_NORMAL
    return round(sum(normalized[k] * weights[k] for k in weights), 2)


def _normalize_name(name: str) -> str:
    """Lowercase, strip non-alpha chars for fuzzy author matching."""
    return re.sub(r'[^a-z ]', '', name.lower()).strip()


def check_priority_author_match(paper: Dict, priority_authors: List[str]) -> List[str]:
    """Return list of priority author names whose last name + first name prefix
    appear in the paper's author list.

    Matching rules:
    - Last names must match exactly (after normalisation).
    - First names are compared using a prefix of length min(3, min(len_a, len_b)).
      If either side is a single initial (length 1), a 1-char match is accepted.
      This prevents e.g. 'Siwei' from matching 'Sizhe' while still accepting
      abbreviated author names like 'S Chen' for 'Siwei Chen'.
    """
    paper_authors_norm = [_normalize_name(a) for a in paper.get('authors', [])]
    matched: List[str] = []
    for pa in priority_authors:
        pa_norm  = _normalize_name(pa)
        pa_parts = pa_norm.split()
        if len(pa_parts) < 2:
            continue
        last       = pa_parts[-1]
        first_name = pa_parts[0]   # first name (or first initial) of priority author
        for pap in paper_authors_norm:
            pap_parts = pap.split()
            if last not in pap_parts:
                continue
            other = [p for p in pap_parts if p != last]
            for candidate in other:
                if len(first_name) == 1 or len(candidate) == 1:
                    # One side is a bare initial — accept single-char match
                    if candidate[0] == first_name[0]:
                        matched.append(pa)
                        break
                else:
                    # Require at least 3-char prefix match to avoid collisions
                    # like 'Siwei' vs 'Sizhe'
                    n = min(3, min(len(first_name), len(candidate)))
                    if first_name[:n] == candidate[:n]:
                        matched.append(pa)
                        break
            else:
                continue
            break   # already appended pa; move to next priority author
    return matched


def filter_and_score_papers(
    papers: List[Dict],
    config: Dict,
    is_hot_paper_batch: bool = False,
    end_date: Optional[datetime] = None,
    priority_authors: Optional[List[str]] = None,
) -> List[Dict]:
    domains = config.get('research_domains', {})
    scored: List[Dict] = []

    for paper in papers:
        relevance, matched_domain, matched_kws = calculate_relevance_score(paper, domains)
        if relevance < MIN_RELEVANCE_SCORE:
            continue

        # Recency — computed relative to the search end_date so historical
        # searches are not penalised by datetime.now()
        pub_date = paper.get('published_date')
        if isinstance(pub_date, str):
            try:
                pub_date = datetime.strptime(pub_date, '%Y-%m-%d')
            except ValueError:
                pub_date = None
        recency = calculate_recency_score(pub_date, reference_date=end_date)

        # Popularity
        if is_hot_paper_batch:
            inf_cit = paper.get('influentialCitationCount', 0) or 0
            popularity = min(inf_cit / (POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE / SCORE_MAX), SCORE_MAX)
        else:
            popularity = calculate_quality_score(paper, config)

        quality = calculate_quality_score(paper, config)
        rec_score = calculate_recommendation_score(relevance, recency, popularity, quality, is_hot_paper_batch)

        # Source boost: bioRxiv/medRxiv papers are biology-specific, so they are
        # inherently more on-topic than generic arXiv stat papers.
        source = paper.get('source', '')
        if source in ('biorxiv', 'medrxiv'):
            rec_score = min(rec_score + BIORXIV_SOURCE_BOOST, 10.0)

        # Priority-author boost: reward papers that are both relevant and by a
        # priority author, pushing them toward (or into) the high-priority bucket.
        matched_authors: List[str] = []
        if priority_authors and relevance >= PRIORITY_AUTHOR_RELEVANCE_THRESHOLD:
            matched_authors = check_priority_author_match(paper, priority_authors)
            if matched_authors:
                rec_score = min(rec_score + PRIORITY_AUTHOR_SCORE_BOOST, 10.0)

        paper['scores'] = {
            'relevance':      round(relevance, 2),
            'recency':        round(recency, 2),
            'popularity':     round(popularity, 2),
            'quality':        round(quality, 2),
            'recommendation': round(rec_score, 2),
        }
        paper['matched_domain']   = matched_domain
        paper['matched_keywords'] = matched_kws
        paper['matched_authors']  = matched_authors
        paper['is_hot_paper']     = is_hot_paper_batch
        scored.append(paper)

    scored.sort(key=lambda x: x['scores']['recommendation'], reverse=True)
    return scored


# ===========================================================================
# Deduplication
# ===========================================================================

def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    """Deduplicate by DOI first, then by normalised title."""
    seen_dois:   Set[str] = set()
    seen_titles: Set[str] = set()
    unique: List[Dict] = []

    for p in papers:
        doi = (p.get('doi') or '').strip().lower()
        if doi and doi in seen_dois:
            continue

        norm_title = normalize_title(p.get('title', ''))
        if norm_title and norm_title in seen_titles:
            continue

        if doi:
            seen_dois.add(doi)
        if norm_title:
            seen_titles.add(norm_title)
        unique.append(p)

    return unique


# ---------------------------------------------------------------------------
# Within-section ordering: published journals first, then bioRxiv/medRxiv,
# then arXiv; within each source group papers are ordered by score (desc).
# ---------------------------------------------------------------------------
_SOURCE_ORDER = {'pubmed': 0, 'biorxiv': 1, 'medrxiv': 1, 'arxiv': 2, 'semantic_scholar': 3}


def sort_by_source_then_score(papers: List[Dict]) -> List[Dict]:
    return sorted(
        papers,
        key=lambda p: (
            _SOURCE_ORDER.get(p.get('source', 'arxiv'), 99),
            -p.get('scores', {}).get('recommendation', 0),
        ),
    )


# ===========================================================================
# Main
# ===========================================================================

def main():
    import argparse

    # Default config: prefer config.local.yaml (private, gitignored) over config.yaml
    _repo_root = Path(__file__).resolve().parent.parent.parent
    _local = _repo_root / 'config.local.yaml'
    _default = _repo_root / 'config.yaml'
    default_config = str(_local) if _local.exists() else (str(_default) if _default.exists() else '')

    parser = argparse.ArgumentParser(
        description='Multi-source paper search: arXiv, bioRxiv, PubMed, Semantic Scholar'
    )
    parser.add_argument('--config', type=str, default=default_config or None,
                        help='Path to research_interests.yaml (or set OBSIDIAN_VAULT_PATH)')
    parser.add_argument('--output', type=str, default='papers_results.json',
                        help='Output JSON file path')
    parser.add_argument('--start', type=str, required=True,
                        help='Start date YYYYMMDD (inclusive)')
    parser.add_argument('--end', type=str, required=True,
                        help='End date YYYYMMDD (inclusive)')
    parser.add_argument('--max-results', type=int, default=200,
                        help='Max papers per source')
    parser.add_argument('--categories', type=str,
                        default='stat.ME,stat.AP,stat.CO,q-bio.GN,q-bio.QM',
                        help='Comma-separated arXiv categories')
    parser.add_argument('--skip-biorxiv', action='store_true',
                        help='Skip bioRxiv/medRxiv search')
    parser.add_argument('--skip-pubmed', action='store_true',
                        help='Skip PubMed journal sweep')
    parser.add_argument('--skip-author-search', action='store_true',
                        help='Skip PubMed priority-author search')
    parser.add_argument('--include-hot-papers', action='store_true',
                        help='Include Semantic Scholar hot papers (off by default)')
    parser.add_argument('--hot-lookback-days', type=int, default=60,
                        help='Days to look back for Semantic Scholar hot papers')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    if not args.config:
        logger.error(
            "No config path. Use --config or set OBSIDIAN_VAULT_PATH."
        )
        return 1

    logger.info("Loading config from: %s", args.config)
    config = load_research_config(args.config)

    try:
        start_date = parse_date(args.start)
        end_date   = parse_date(args.end)
    except ValueError as e:
        logger.error("Invalid date: %s", e)
        return 1

    categories = args.categories.split(',')
    domains    = config.get('research_domains', {})
    journals   = config.get('target_journals', [])
    pr_authors = config.get('priority_authors', [])

    all_scored: List[Dict] = []
    priority_author_papers: List[Dict] = []

    stats = {'arxiv': 0, 'biorxiv': 0, 'pubmed': 0, 'priority_authors': 0, 'semantic_scholar': 0}

    # ── Step 1: arXiv ──────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("Step 1: arXiv search (%s → %s)", args.start, args.end)
    logger.info("=" * 70)

    arxiv_papers = search_arxiv_by_date_range(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        max_results=args.max_results,
    )
    if arxiv_papers:
        scored = filter_and_score_papers(
            arxiv_papers, config, is_hot_paper_batch=False, end_date=end_date, priority_authors=pr_authors
        )
        stats['arxiv'] = len(scored)
        all_scored.extend(scored)
        logger.info("arXiv: %d scored papers", len(scored))

    # ── Step 2: bioRxiv / medRxiv ──────────────────────────────────────────
    if not args.skip_biorxiv:
        logger.info("=" * 70)
        logger.info("Step 2: bioRxiv / medRxiv search")
        logger.info("=" * 70)
        biorxiv_papers = search_biorxiv_by_date_range(
            start_date=start_date, end_date=end_date, max_results=args.max_results
        )
        if biorxiv_papers:
            scored = filter_and_score_papers(
                biorxiv_papers, config, is_hot_paper_batch=False, end_date=end_date, priority_authors=pr_authors
            )
            stats['biorxiv'] = len(scored)
            all_scored.extend(scored)
            logger.info("bioRxiv/medRxiv: %d scored papers", len(scored))
    else:
        logger.info("Step 2: bioRxiv search skipped")

    # ── Step 3: PubMed journal sweep ───────────────────────────────────────
    if not args.skip_pubmed and journals:
        logger.info("=" * 70)
        logger.info("Step 3: PubMed journal sweep (%d journals)", len(journals))
        logger.info("=" * 70)

        all_domain_keywords: List[str] = []
        for d in domains.values():
            kws = _normalize_keywords(d.get('keywords', []))
            for tier in ('high', 'medium', 'low'):  # high-weight keywords first so [:20] keeps them
                all_domain_keywords.extend(kws.get(tier, []))
        all_domain_keywords = list(dict.fromkeys(all_domain_keywords))  # deduplicate, preserve order

        pubmed_papers = search_pubmed_recent(
            keywords=all_domain_keywords,
            start_date=start_date,
            end_date=end_date,
            journals=journals,
            max_results=args.max_results,
        )
        if pubmed_papers:
            scored = filter_and_score_papers(
                pubmed_papers, config, is_hot_paper_batch=False, end_date=end_date, priority_authors=pr_authors
            )
            stats['pubmed'] = len(scored)
            all_scored.extend(scored)
            logger.info("PubMed journals: %d scored papers", len(scored))
    else:
        logger.info("Step 3: PubMed journal sweep skipped")

    # ── Step 4: PubMed priority-author search ─────────────────────────────
    if not args.skip_author_search and pr_authors:
        logger.info("=" * 70)
        logger.info("Step 4: PubMed author sweep (%d priority authors)", len(pr_authors))
        logger.info("=" * 70)

        author_papers = search_pubmed_by_authors(
            authors=pr_authors,
            start_date=start_date,
            end_date=end_date,
            max_results=50,
        )
        if author_papers:
            stats['priority_authors'] = len(author_papers)
            # Score with priority-author boost; add to the main pool.
            # Store the scored list separately — after bucketing we will keep
            # only papers that did NOT make it into the main scored buckets.
            scored_author = filter_and_score_papers(
                author_papers, config, is_hot_paper_batch=False, end_date=end_date, priority_authors=pr_authors
            )
            all_scored.extend(scored_author)
            priority_author_papers = scored_author
            logger.info("Priority authors: %d papers", len(author_papers))
    else:
        logger.info("Step 4: Priority author search skipped")

    # ── Step 5: Semantic Scholar hot papers (optional) ─────────────────────
    if args.include_hot_papers:
        logger.info("=" * 70)
        logger.info("Step 5: Semantic Scholar hot papers (last %d days)", args.hot_lookback_days)
        logger.info("=" * 70)

        hot_start = end_date - timedelta(days=args.hot_lookback_days)
        hot_end   = start_date - timedelta(days=1)

        hot_papers = search_hot_papers_from_categories(
            categories=categories,
            start_date=hot_start,
            end_date=hot_end,
            top_k_per_category=5,
        )
        if hot_papers:
            scored = filter_and_score_papers(
                hot_papers, config, is_hot_paper_batch=True, end_date=end_date, priority_authors=pr_authors
            )
            stats['semantic_scholar'] = len(scored)
            all_scored.extend(scored)
            logger.info("Semantic Scholar: %d scored hot papers", len(scored))
    else:
        logger.info("Step 5: Semantic Scholar search skipped (use --include-hot-papers to enable)")

    # ── Step 6: Merge, deduplicate, bucket ────────────────────────────────
    logger.info("=" * 70)
    logger.info("Step 6: Merge, deduplicate, bucket")
    logger.info("=" * 70)

    all_scored.sort(key=lambda x: x['scores']['recommendation'], reverse=True)
    unique = deduplicate_papers(all_scored)
    logger.info("Total unique scored papers: %d", len(unique))

    high_priority     = [p for p in unique if p['scores']['recommendation'] >= THRESHOLD_HIGH]
    moderate_priority = [p for p in unique if THRESHOLD_MODERATE <= p['scores']['recommendation'] < THRESHOLD_HIGH]
    low_priority      = [p for p in unique if THRESHOLD_LOW <= p['scores']['recommendation'] < THRESHOLD_MODERATE]

    # Priority-author section: papers by priority authors that did NOT make it
    # into the main scored buckets (either too low relevance or score too low
    # even after the boost).  Papers that were boosted into the main buckets
    # already appear there and should not be repeated here.
    main_titles = {normalize_title(p.get('title', '')) for p in high_priority + moderate_priority + low_priority}
    priority_author_papers = deduplicate_papers([
        p for p in priority_author_papers
        if normalize_title(p.get('title', '')) not in main_titles
    ])

    # Within each bucket sort: PubMed first, then bioRxiv/medRxiv, then arXiv;
    # within each source group papers are ordered by score descending.
    high_priority     = sort_by_source_then_score(high_priority)
    moderate_priority = sort_by_source_then_score(moderate_priority)
    low_priority      = sort_by_source_then_score(low_priority)
    priority_author_papers = sort_by_source_then_score(priority_author_papers)

    logger.info(
        "Buckets — high: %d, moderate: %d, low: %d, priority authors: %d",
        len(high_priority), len(moderate_priority), len(low_priority), len(priority_author_papers)
    )

    output = {
        'target_date': args.end,
        'date_windows': {
            'recent': {'start': args.start, 'end': args.end},
            'hot': {
                'start': (end_date - timedelta(days=args.hot_lookback_days)).strftime('%Y-%m-%d'),
                'end':   (start_date - timedelta(days=1)).strftime('%Y-%m-%d'),
            } if args.include_hot_papers else {},
        },
        'stats': stats,
        'high_priority':          high_priority,
        'moderate_priority':      moderate_priority,
        'low_priority':           low_priority,
        'priority_author_papers': priority_author_papers,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Results saved to: %s", args.output)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
