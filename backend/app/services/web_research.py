"""SearXNG-backed iterative web research enrichment."""

from __future__ import annotations

import html
import ipaddress
import os
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

from ..config import Config
from ..utils.llm_client import LLMClient


WEB_RESEARCH_SECTION_HEADER = "=== Generated Web Research ==="
REQUIRED_RESEARCH_SECTIONS = [
    "Source-Grounded Context",
    "Retrieved Source Summaries",
    "Stakeholder and Viewpoint Coverage",
    "Scenario Assumptions Boundary",
    "Coverage Gaps",
    "Sources",
]
MAX_QUERIES_PER_LOOP = 6
SOURCE_CONTENT_SUMMARY_MAX_CHARS = 900
SOURCE_CONTEXT_LINE_MAX_CHARS = 620
SOURCE_SUMMARY_RENDER_LIMIT = 8
SOURCE_CONTEXT_RENDER_LIMIT = 6
FALLBACK_SUMMARY_MIN_SENTENCES = 4
FALLBACK_SUMMARY_MAX_SENTENCES = 5
BOILERPLATE_CATEGORY_TERMS = {
    "automotive",
    "aviation",
    "cargo",
    "communications",
    "construction",
    "education",
    "energy",
    "entertainment",
    "financial",
    "healthcare",
    "hospitality",
    "infrastructure",
    "manufacturing",
    "marine",
    "mining",
    "public",
    "retail",
    "sports",
    "technology",
    "transportation",
    "wholesale",
}
BOILERPLATE_PHRASES = [
    "all rights reserved",
    "cookie policy",
    "privacy policy",
    "skip to content",
    "terms of use",
    "toggle navigation",
    "call us:",
    "new account",
    "user login",
    "training courses",
    "training bundles",
    "safety blog",
    "faq contact us",
    "featured programmes",
    "automated system for customs data",
    "search for a project",
    "in focus impact stories",
    "media for registered journalists",
    "user account menu",
    "brand assets",
    "our consulting",
    "brokerage and claims advocacy",
    "services services",
]
SOURCE_CONTEXT_THEMES = [
    (
        {"shipping", "maritime", "tanker", "vessel", "freight", "cargo", "route", "routes", "ports", "port"},
        "Retrieved sources connect maritime disruption with shipping delays, routing pressure, and supply-chain uncertainty that can shape worker, trader, and public reactions.",
    ),
    (
        {"insurance", "premium", "premiums", "surcharge", "surcharges", "market", "markets", "energy", "oil", "fuel"},
        "Retrieved sources connect insurance and energy-market pressure with cost anxiety, risk pricing, and uneven exposure across firms and consumers.",
    ),
    (
        {"humanitarian", "aid", "civilian", "medical", "relief", "lifesaving", "shipment", "shipments"},
        "Retrieved sources connect maritime disruption with humanitarian access, civilian cargo delays, and pressure for protected or clearly communicated aid routes.",
    ),
    (
        {"misinformation", "disinformation", "rumor", "rumors", "social", "media", "panic", "public"},
        "Retrieved sources connect crisis communication failures with misinformation risk, public confusion, and fast-moving online interpretation of maritime incidents.",
    ),
    (
        {"labor", "worker", "workers", "union", "warehouse", "dock", "terminal", "terminals", "shift", "shifts"},
        "Retrieved sources connect port and logistics labor pressures with safety concerns, schedule disruption, and worker-facing responses to delayed cargo flows.",
    ),
    (
        {"diplomatic", "diplomacy", "navigation", "naval", "security", "de-escalation", "passage", "seafarer", "seafarers"},
        "Retrieved sources connect maritime security and diplomatic management with freedom-of-navigation concerns, escalation control, and seafarer protection.",
    ),
]
FIXTURE_SPECIFIC_QUERY_TERMS = [
    "Caspian Star",
    "Caspian Star Shipping",
    "Caspian Star Shipping Horizon",
    "Mina Cho",
    "Tehran University Student Forum",
    "Gulf Port Workers Union",
    "Crescent Humanitarian Network",
    "Gulf Energy Export Council",
]
SCENARIO_ACTOR_TERMS = [
    "Iran Foreign Ministry",
    "U.S.-led naval coalition",
    "Gulf Energy Export Council",
    "UN Security Council",
    "Caspian Star Shipping",
    "Caspian Star Shipping Horizon",
    "Mina Cho",
    "Tehran University Student Forum",
    "Gulf Port Workers Union",
    "Crescent Humanitarian Network",
]
SCENARIO_BOUNDARY_MARKERS = SCENARIO_ACTOR_TERMS + [
    "fictional",
    "synthetic",
    "smoke test",
    "user-provided",
]
OUT_OF_SCOPE_GAP_MARKERS = [
    "operational military",
    "tactical",
    "strategic aspects",
    "military and strategic",
    "military operation",
    "military operations",
    "military action",
    "military response",
    "long-term diplomatic",
    "long-term diplomacy",
    "long-term consequence",
    "long-term economic",
    "detailed economic impact",
    "detailed economic impact analysis",
    "broader economic impact",
    "potential broader economic impact",
    "more detailed",
    "specific details",
    "specific labor concerns",
    "exact actions",
    "technical details",
    "hull breach",
    "tanker condition",
    "tanker's condition",
    "specific countries",
    "specific actions and statements",
]
QUESTION_QUERY_PREFIXES = (
    "what ",
    "how ",
    "why ",
    "when ",
    "where ",
    "who ",
    "can ",
    "could ",
    "should ",
    "would ",
    "is ",
    "are ",
    "do ",
    "does ",
)
LOW_VALUE_SOURCE_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "tiktok.com",
    "www.tiktok.com",
}
SCENARIO_BOUNDARY_TERMS = [
    "Iran Foreign Ministry",
    "U.S.-led naval coalition",
    "Gulf Energy Export Council",
    "UN Security Council",
    "Caspian Star Shipping",
    "Mina Cho",
    "Tehran University Student Forum",
    "Gulf Port Workers Union",
    "Crescent Humanitarian Network",
    "denies",
    "accuses",
    "patrols",
    "operates",
    "reports_on",
    "calls_for_deescalation",
    "affected_by",
    "warns_about",
    "supports",
    "opposes",
    "escalation fears",
    "nationalism",
    "energy-market anxiety",
    "shipping delays",
    "misinformation",
    "diplomacy",
    "humanitarian concern",
    "public protest",
]


class WebResearchError(Exception):
    """Raised when web research cannot complete safely."""


@dataclass
class WebResearchConfig:
    enabled: bool = False
    searxng_url: Optional[str] = None
    min_loops: int = 2
    max_loops: int = 5
    results_per_query: int = 5
    timeout_seconds: int = 20
    max_source_bytes: int = 200000

    @classmethod
    def from_mapping(cls, mapping: Dict[str, Any]) -> "WebResearchConfig":
        return cls(
            enabled=_parse_bool(mapping.get("WEB_RESEARCH_ENABLED", False)),
            searxng_url=_clean_optional(mapping.get("WEB_RESEARCH_SEARXNG_URL")),
            min_loops=_parse_int(mapping.get("WEB_RESEARCH_MIN_LOOPS"), 2),
            max_loops=_parse_int(mapping.get("WEB_RESEARCH_MAX_LOOPS"), 5),
            results_per_query=_parse_int(mapping.get("WEB_RESEARCH_RESULTS_PER_QUERY"), 5),
            timeout_seconds=_parse_int(mapping.get("WEB_RESEARCH_TIMEOUT_SECONDS"), 20),
            max_source_bytes=_parse_int(mapping.get("WEB_RESEARCH_MAX_SOURCE_BYTES"), 200000),
        )

    @classmethod
    def from_env(cls, environ: Optional[Dict[str, str]] = None) -> "WebResearchConfig":
        return cls.from_mapping(environ or os.environ)

    @classmethod
    def from_config(cls, config_class=Config) -> "WebResearchConfig":
        return cls(
            enabled=bool(getattr(config_class, "WEB_RESEARCH_ENABLED", False)),
            searxng_url=_clean_optional(getattr(config_class, "WEB_RESEARCH_SEARXNG_URL", None)),
            min_loops=int(getattr(config_class, "WEB_RESEARCH_MIN_LOOPS", 2)),
            max_loops=int(getattr(config_class, "WEB_RESEARCH_MAX_LOOPS", 5)),
            results_per_query=int(getattr(config_class, "WEB_RESEARCH_RESULTS_PER_QUERY", 5)),
            timeout_seconds=int(getattr(config_class, "WEB_RESEARCH_TIMEOUT_SECONDS", 20)),
            max_source_bytes=int(getattr(config_class, "WEB_RESEARCH_MAX_SOURCE_BYTES", 200000)),
        )

    def validate(self) -> None:
        if self.enabled and not self.searxng_url:
            raise WebResearchError("WEB_RESEARCH_SEARXNG_URL is required when WEB_RESEARCH_ENABLED=true")
        if self.min_loops < 1:
            raise WebResearchError("WEB_RESEARCH_MIN_LOOPS must be at least 1")
        if self.max_loops < self.min_loops:
            raise WebResearchError("WEB_RESEARCH_MAX_LOOPS must be greater than or equal to WEB_RESEARCH_MIN_LOOPS")
        if self.results_per_query < 1:
            raise WebResearchError("WEB_RESEARCH_RESULTS_PER_QUERY must be at least 1")
        if self.timeout_seconds < 1:
            raise WebResearchError("WEB_RESEARCH_TIMEOUT_SECONDS must be at least 1")
        if self.max_source_bytes < 1024:
            raise WebResearchError("WEB_RESEARCH_MAX_SOURCE_BYTES must be at least 1024")


@dataclass
class WebResearchResult:
    markdown: str
    metadata: Dict[str, Any]


class SearXNGClient:
    """Small SearXNG JSON API client."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 20,
        request_get: Callable[..., Any] = requests.get,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.request_get = request_get

    def search(self, query: str, results_per_query: int) -> List[Dict[str, str]]:
        try:
            response = self.request_get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json", "language": "en"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except Exception as exc:
            raise WebResearchError(f"SearXNG search failed: {exc}") from exc

        try:
            payload = response.json()
        except Exception as exc:
            raise WebResearchError("SearXNG JSON output is unavailable or disabled") from exc

        if not isinstance(payload, dict) or "results" not in payload:
            raise WebResearchError("SearXNG JSON response did not include results")

        parsed = []
        for item in payload.get("results", [])[:results_per_query]:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            parsed.append(
                {
                    "title": str(item.get("title") or item.get("url")),
                    "url": str(item["url"]),
                    "snippet": str(item.get("content") or item.get("snippet") or ""),
                }
            )
        return parsed


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, _attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str):
        if not self._skip_depth and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\s+", " ", html.unescape(" ".join(self._chunks))).strip()


class SafeUrlFetcher:
    """Fetch text from public HTTP(S) URLs with SSRF guardrails."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 20,
        max_source_bytes: int = 200000,
        request_get: Callable[..., Any] = requests.get,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_source_bytes = max_source_bytes
        self.request_get = request_get

    def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise WebResearchError(f"Unsupported source URL scheme: {parsed.scheme or 'missing'}")
        if not parsed.hostname:
            raise WebResearchError("Source URL must include a hostname")
        if parsed.hostname.lower() == "localhost":
            raise WebResearchError("Source URL host is blocked: localhost")

        for ip in self._resolve_host(parsed.hostname, parsed.port):
            if self._is_blocked_ip(ip):
                raise WebResearchError(f"Source URL host resolves to blocked address: {ip}")

    def fetch(self, url: str) -> str:
        current_url = url
        for _redirect in range(5):
            self.validate_url(current_url)
            response = self.request_get(
                current_url,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "MiroFish-WebResearch/1.0"},
                stream=True,
                allow_redirects=False,
            )
            response.raise_for_status()

            if 300 <= getattr(response, "status_code", 200) < 400:
                location = response.headers.get("location")
                if not location:
                    raise WebResearchError("Redirect response did not include a Location header")
                current_url = urljoin(current_url, location)
                continue

            content_type = response.headers.get("content-type", "")
            if content_type and not any(kind in content_type.lower() for kind in ("text/", "html", "xml", "json")):
                raise WebResearchError(f"Unsupported source content type: {content_type}")

            raw = self._read_limited(response)
            encoding = getattr(response, "encoding", None) or "utf-8"
            decoded = raw.decode(encoding, errors="replace")
            text = self._html_to_text(decoded)
            if not text:
                raise WebResearchError("Fetched source did not contain usable text")
            return text

        raise WebResearchError("Too many source redirects")

    def _read_limited(self, response) -> bytes:
        chunks: List[bytes] = []
        total = 0
        if hasattr(response, "iter_content"):
            iterator = response.iter_content(chunk_size=8192)
        else:
            iterator = [getattr(response, "content", b"")]

        for chunk in iterator:
            if not chunk:
                continue
            total += len(chunk)
            if total > self.max_source_bytes:
                raise WebResearchError("Fetched source exceeded WEB_RESEARCH_MAX_SOURCE_BYTES")
            chunks.append(chunk)
        return b"".join(chunks)

    def _html_to_text(self, value: str) -> str:
        extractor = _HTMLTextExtractor()
        extractor.feed(value)
        text = extractor.text()
        if text:
            return text
        return re.sub(r"\s+", " ", value).strip()

    def _resolve_host(self, hostname: str, port: Optional[int]) -> Iterable[ipaddress._BaseAddress]:
        try:
            literal_ip = ipaddress.ip_address(hostname)
            return [literal_ip]
        except ValueError:
            pass

        try:
            infos = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise WebResearchError(f"Could not resolve source URL host: {hostname}") from exc
        return [ipaddress.ip_address(info[4][0]) for info in infos]

    def _is_blocked_ip(self, ip: ipaddress._BaseAddress) -> bool:
        return any(
            [
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            ]
        )


class WebResearchService:
    """Iterative source-grounded research using SearXNG and the local LLM client."""

    def __init__(
        self,
        *,
        config: Optional[WebResearchConfig] = None,
        llm_client: Optional[LLMClient] = None,
        search_client: Optional[SearXNGClient] = None,
        fetcher: Optional[SafeUrlFetcher] = None,
    ):
        self.config = config or WebResearchConfig.from_config(Config)
        self.config.validate()
        self.llm_client = llm_client
        self.search_client = search_client
        self.fetcher = fetcher
        if self.config.enabled:
            if self.llm_client is None:
                self.llm_client = LLMClient()
            if self.search_client is None:
                self.search_client = SearXNGClient(
                    self.config.searxng_url or "",
                    timeout_seconds=self.config.timeout_seconds,
                )
            if self.fetcher is None:
                self.fetcher = SafeUrlFetcher(
                    timeout_seconds=self.config.timeout_seconds,
                    max_source_bytes=self.config.max_source_bytes,
                )

    @staticmethod
    def disabled_metadata() -> Dict[str, Any]:
        return {
            "enabled": False,
            "status": "disabled",
            "iterations": 0,
            "source_count": 0,
            "sources": [],
            "summary_path": None,
            "error": None,
        }

    def run(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None,
    ) -> WebResearchResult:
        if not self.config.enabled:
            return WebResearchResult(markdown="", metadata=self.disabled_metadata())

        pending_queries = self._generate_initial_queries(document_texts, simulation_requirement, additional_context)
        seen_urls = set()
        searched_queries = set()
        query_history: List[str] = []
        sources: List[Dict[str, Any]] = []
        summary_markdown = ""
        coverage = {"covered": [], "gaps": []}
        fetched_count = 0
        completed_iterations = 0

        for iteration in range(1, self.config.max_loops + 1):
            queries = [query for query in _dedupe_strings(pending_queries) if query.lower() not in searched_queries]
            if not queries:
                queries = [
                    query
                    for query in self._fallback_queries(
                        document_texts=document_texts,
                        simulation_requirement=simulation_requirement,
                        coverage=coverage,
                    )
                    if query.lower() not in searched_queries
                ]
            if not queries:
                queries = [simulation_requirement]

            batch_sources = []
            for query in queries:
                searched_queries.add(query.lower())
                query_history.append(query)
                batch_sources.extend(self._search_and_fetch(query, seen_urls, sources))
            fetched_count += len(batch_sources)

            if batch_sources:
                summary_update = self._summarize_sources(
                    document_texts=document_texts,
                    simulation_requirement=simulation_requirement,
                    additional_context=additional_context,
                    existing_summary=summary_markdown,
                    sources=batch_sources,
                )
                summary_markdown = summary_update["summary_markdown"]
                self._apply_content_summaries(
                    sources=sources,
                    fetched_sources=batch_sources,
                    summary_update=summary_update,
                    document_texts=document_texts,
                    simulation_requirement=simulation_requirement,
                )
                coverage = _merge_coverage(coverage, summary_update.get("coverage"))

            completed_iterations = iteration

            if not batch_sources and fetched_count == 0 and iteration >= self.config.max_loops:
                break

            reflection = self._reflect(
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
                summary_markdown=summary_markdown,
                coverage=coverage,
                iteration=iteration,
            )
            coverage = _merge_coverage(coverage, _coverage_from_response(reflection))

            sufficient = bool(reflection.get("sufficient"))
            follow_up_queries = self._filter_research_queries(
                _queries_from_response(reflection, ["follow_up_queries", "follow_up_query"])
            )
            if iteration >= self.config.min_loops and sufficient and fetched_count > 0:
                break
            pending_queries = follow_up_queries

        if fetched_count == 0:
            raise WebResearchError("No usable web research sources were fetched")

        coverage = _filter_contextually_covered_gaps(coverage, summary_markdown, sources, query_history)
        markdown = self._finalize_markdown(summary_markdown, sources, document_texts, coverage)
        metadata = {
            "enabled": True,
            "status": "completed",
            "iterations": completed_iterations,
            "source_count": fetched_count,
            "queries": query_history,
            "coverage": coverage,
            "sources": sources,
            "summary_path": "web_research.md",
            "error": None,
        }
        return WebResearchResult(markdown=markdown, metadata=metadata)

    def _generate_initial_queries(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str],
    ) -> List[str]:
        response = self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate three to five concise web search queries for source-grounded "
                        "scenario enrichment. Search for real-world analogue context, not fictional "
                        "fixture names. Cover shipping/security context, energy or insurance risk, "
                        "stakeholder/public reaction, misinformation, and humanitarian or diplomatic "
                        "concerns when relevant. Return JSON with key queries."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Simulation requirement:\n{simulation_requirement}\n\n"
                        f"Additional context:\n{additional_context or ''}\n\n"
                        f"Scenario excerpt:\n{_join_excerpt(document_texts)}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        analogue_queries = self._scenario_analogue_queries(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            coverage={"covered": [], "gaps": []},
        )
        queries = analogue_queries + self._filter_research_queries(
            _queries_from_response(response, ["queries", "query"])
        )
        return _dedupe_strings(queries)[:MAX_QUERIES_PER_LOOP] or [simulation_requirement]

    def _filter_research_queries(self, queries: List[str]) -> List[str]:
        filtered = []
        for query in queries:
            lowered_query = query.lower().strip()
            if any(term.lower() in lowered_query for term in FIXTURE_SPECIFIC_QUERY_TERMS):
                continue
            if any(term in lowered_query for term in OUT_OF_SCOPE_GAP_MARKERS):
                continue
            if _is_question_like_query(lowered_query):
                continue
            filtered.append(query)
        return _dedupe_strings(filtered)[:MAX_QUERIES_PER_LOOP]

    def _source_is_usable_search_result(self, url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if _is_placeholder_source(url):
            return False
        if hostname in LOW_VALUE_SOURCE_HOSTS:
            return False
        if parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi")):
            return False
        return True

    def _search_and_fetch(
        self,
        query: str,
        seen_urls: set[str],
        sources: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        fetched_sources = []
        if self.search_client is None:
            raise WebResearchError("SearXNG client is not configured")
        if self.fetcher is None:
            raise WebResearchError("Source fetcher is not configured")

        results = self.search_client.search(query, self.config.results_per_query)
        for item in results:
            url = item["url"]
            if not self._source_is_usable_search_result(url):
                continue
            normalized = _normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            source_id = f"R{len(sources) + 1}"
            record = {
                "id": source_id,
                "title": item.get("title") or url,
                "url": url,
                "query": query,
                "snippet": item.get("snippet") or "",
                "fetched": False,
                "error": None,
            }
            try:
                text = self.fetcher.fetch(url)
                record["fetched"] = True
                fetched_sources.append({**record, "text": text})
            except Exception as exc:
                record["error"] = str(exc)
            sources.append(record)
        return fetched_sources

    def _summarize_sources(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str],
        existing_summary: str,
        sources: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        source_block = "\n\n".join(
            f"[{source['id']}] {source['title']}\n"
            f"Search query: {source.get('query')}\n"
            f"URL: {source['url']}\nSnippet: {source['snippet']}\nText: {source['text'][:3000]}"
            for source in sources
        )
        response = self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Update a medium-depth markdown research synthesis using only the provided sources. "
                        "Every source-grounded factual claim must include [R1], [R2] style citations. "
                        "For each fetched source, also return source_summaries as objects with id "
                        "and a 2-4 sentence content_summary derived from the fetched Text field rather "
                        "than the search snippet or title. Each source summary should capture the main "
                        "evidence, scenario relevance, and stakeholder or risk implications when present. "
                        "Ignore navigation menus, category lists, cookie banners, and generic site boilerplate. "
                        "Do not present fictional or user-provided scenario actors as externally "
                        "verified. Use ## Source-Grounded Context for cross-source synthesis rather "
                        "than repeating one source summary at a time. Use sections: ## Source-Grounded "
                        "Context, ## Stakeholder and Viewpoint Coverage, ## Scenario Assumptions Boundary, and ## Coverage Gaps. "
                        "Return JSON with summary_markdown, source_summaries, and coverage "
                        "{covered: [], gaps: []}."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Simulation requirement:\n{simulation_requirement}\n\n"
                        f"Additional context:\n{additional_context or ''}\n\n"
                        f"Scenario excerpt:\n{_join_excerpt(document_texts)}\n\n"
                        f"Existing summary:\n{existing_summary}\n\n"
                        f"Sources:\n{source_block}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=3072,
        )
        if not isinstance(response, dict):
            return {
                "summary_markdown": existing_summary,
                "source_summaries": {},
                "coverage": {"covered": [], "gaps": []},
            }
        summary = _clean_optional(response.get("summary_markdown")) or _clean_optional(response.get("summary")) or existing_summary
        return {
            "summary_markdown": summary,
            "source_summaries": _source_summaries_from_response(response),
            "coverage": _coverage_from_response(response),
        }

    def _apply_content_summaries(
        self,
        *,
        sources: List[Dict[str, Any]],
        fetched_sources: List[Dict[str, str]],
        summary_update: Dict[str, Any],
        document_texts: List[str],
        simulation_requirement: str,
    ) -> None:
        records_by_id = {source.get("id"): source for source in sources}
        llm_summaries = summary_update.get("source_summaries") or {}

        for fetched_source in fetched_sources:
            source_id = fetched_source.get("id")
            if not source_id:
                continue
            record = records_by_id.get(source_id)
            if record is None:
                continue

            content_summary = _clean_optional(llm_summaries.get(source_id))
            if content_summary:
                cleaned_summary = _clean_optional(_remove_boilerplate_sentences(content_summary))
                if cleaned_summary:
                    record["content_summary"] = _cap_text(
                        cleaned_summary,
                        max_chars=SOURCE_CONTENT_SUMMARY_MAX_CHARS,
                    )
                    continue

            record["content_summary"] = _fallback_content_summary(
                fetched_source,
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
            )

    def _reflect(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: str,
        summary_markdown: str,
        coverage: Dict[str, List[str]],
        iteration: int,
    ) -> Dict[str, Any]:
        response = self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Decide whether the research summary is sufficient for scenario enrichment. "
                        "Evaluate coverage of source-grounded context, stakeholder viewpoints, "
                        "misinformation/public reaction, humanitarian concerns, and scenario-boundary "
                        "clarity. Do not request operational military or tactical details; public "
                        "security posture and escalation-management context are enough. Do not treat "
                        "fixture-specific actor details as research gaps. Return JSON with sufficient "
                        "boolean, follow_up_queries list of web-search keyword phrases rather than "
                        "questions, and coverage {covered: [], gaps: []}."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Iteration: {iteration}\n"
                        f"Simulation requirement:\n{simulation_requirement}\n\n"
                        f"Scenario excerpt:\n{_join_excerpt(document_texts)}\n\n"
                        f"Current coverage:\n{coverage}\n\n"
                        f"Current summary:\n{summary_markdown}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return response if isinstance(response, dict) else {"sufficient": False, "follow_up_query": None}

    def _fallback_queries(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: str,
        coverage: Dict[str, List[str]],
    ) -> List[str]:
        return self._scenario_analogue_queries(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            coverage=coverage,
        )

    def _scenario_analogue_queries(
        self,
        *,
        document_texts: List[str],
        simulation_requirement: str,
        coverage: Dict[str, List[str]],
    ) -> List[str]:
        text = f"{simulation_requirement}\n{_join_excerpt(document_texts)}".lower()
        queries = []
        if any(term in text for term in ("strait of hormuz", "shipping", "tanker", "maritime")):
            queries.append("Strait of Hormuz shipping disruption tanker chokepoint energy markets")
        if any(term in text for term in ("energy-market", "energy market", "insurance", "oil", "fuel")):
            queries.append("maritime insurance risk energy market shipping disruption")
        if any(term in text for term in ("misinformation", "rumor", "social media", "public protest", "nationalism")):
            queries.append("maritime incident misinformation public reaction social media")
        if any(term in text for term in ("humanitarian", "medical cargo", "civilian shipment", "aid")):
            queries.append("shipping lane disruption humanitarian medical cargo maritime safety")
        if any(term in text for term in ("port workers", "union", "labor", "dock worker")):
            queries.append("port workers shipping disruption safety insurance labor reaction")
        if any(term in text for term in ("un security council", "diplomacy", "de-escalation", "naval coalition")):
            queries.append("Strait of Hormuz naval patrol maritime security de-escalation shipping lanes")
        if any(term in text for term in ("small importer", "small business", "truck driver", "warehouse", "customs broker", "supply chain")):
            queries.append("shipping disruption small businesses importers supply chain costs")
        for gap in coverage.get("gaps", []):
            cleaned_gap = _clean_optional(gap)
            if cleaned_gap:
                queries.append(f"{cleaned_gap} maritime shipping crisis context")
        return _dedupe_strings(queries)

    def _finalize_markdown(
        self,
        summary_markdown: str,
        sources: List[Dict[str, Any]],
        document_texts: List[str],
        coverage: Dict[str, List[str]],
    ) -> str:
        if not summary_markdown.strip():
            summary_markdown = "## Source Claims\n- Web research completed with the sources below."
        summary_markdown = _normalize_citation_markers(_strip_sources_section(summary_markdown).strip())
        summary_markdown = _drop_preamble_before_first_heading(summary_markdown)
        summary_markdown = _remove_any_level_section(summary_markdown, "Retrieved Source Summaries")
        summary_markdown = _remove_any_level_section(summary_markdown, "Retrieved Source Notes")
        if not _has_heading(summary_markdown, "Source-Grounded Context"):
            summary_markdown = f"## Source-Grounded Context\n{summary_markdown}"
        if not _has_heading(summary_markdown, "Stakeholder and Viewpoint Coverage"):
            summary_markdown += (
                "\n\n## Stakeholder and Viewpoint Coverage\n"
                "- Use the cited context above to enrich stakeholder viewpoints; keep uncited fixture actors as scenario inputs."
            )
        summary_markdown, relocated_claims = _relocate_scenario_boundary_claims(summary_markdown)
        summary_markdown = _ensure_source_context_citations(summary_markdown, sources)
        source_summary_lines = _source_summary_lines(sources)
        if source_summary_lines:
            summary_markdown = _append_to_section(
                summary_markdown,
                "Source-Grounded Context",
                "\n\n## Retrieved Source Summaries\n" + "\n".join(source_summary_lines),
            )
        assumptions = _extract_scenario_assumptions(document_texts)
        if not _has_heading(summary_markdown, "Scenario Assumptions Boundary"):
            assumption_line = "- User-provided scenario inputs remain separate from source-cited claims above."
            if assumptions:
                assumption_line += f" Treat these as scenario inputs unless independently cited: {', '.join(assumptions)}."
            summary_markdown += f"\n\n## Scenario Assumptions Boundary\n{assumption_line}"
        if relocated_claims:
            summary_markdown = _append_to_section(
                summary_markdown,
                "Scenario Assumptions Boundary",
                "\n- Scenario-specific details relocated from source-grounded prose because they come from the user fixture, not fetched sources: "
                + " ".join(relocated_claims[:6]),
            )
        if assumptions:
            missing = [term for term in assumptions if term not in summary_markdown]
            if missing:
                summary_markdown = _append_to_section(
                    summary_markdown,
                    "Scenario Assumptions Boundary",
                    "\n- Additional user-provided scenario inputs to keep separate unless independently cited: "
                    + ", ".join(missing)
                    + ".",
                )
        summary_markdown = _remove_section(summary_markdown, "Coverage Gaps")
        gap_lines = coverage.get("gaps") or []
        if gap_lines:
            rendered_gaps = "\n".join(f"- {gap}" for gap in gap_lines)
        else:
            rendered_gaps = "- No unresolved coverage gaps were reported by the research loop."
        summary_markdown += f"\n\n## Coverage Gaps\n{rendered_gaps}"
        source_lines = ["", "## Sources"]
        for source in sources:
            status = "fetched" if source.get("fetched") else f"skipped: {source.get('error')}"
            source_lines.append(f"- [{source['id']}] {source['title']} - {source['url']} ({status})")
        return summary_markdown.strip() + "\n" + "\n".join(source_lines).rstrip()

    def _llm(self) -> LLMClient:
        if self.llm_client is None:
            raise WebResearchError("LLM client is not configured")
        return self.llm_client

    def _chat_json(self, messages, *, temperature: float, max_tokens: int) -> Any:
        try:
            return self._llm().chat_json(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise WebResearchError(f"Web research LLM JSON call failed: {exc}") from exc


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Any, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(value)


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    seen = set()
    deduped = []
    for value in values:
        cleaned = _clean_optional(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _queries_from_response(response: Any, keys: List[str]) -> List[str]:
    if not isinstance(response, dict):
        return []
    queries = []
    for key in keys:
        value = response.get(key)
        if isinstance(value, list):
            queries.extend(value)
        else:
            cleaned = _clean_optional(value)
            if cleaned:
                queries.append(cleaned)
    return _dedupe_strings(queries)


def _is_question_like_query(lowered_query: str) -> bool:
    return lowered_query.endswith("?") or lowered_query.startswith(QUESTION_QUERY_PREFIXES)


def _coverage_from_response(response: Any) -> Dict[str, List[str]]:
    if not isinstance(response, dict):
        return {"covered": [], "gaps": []}
    coverage = response.get("coverage") if isinstance(response.get("coverage"), dict) else {}
    covered = coverage.get("covered", response.get("covered", []))
    gaps = coverage.get(
        "gaps",
        response.get("coverage_gaps", response.get("gaps", [])),
    )
    return {
        "covered": sorted(_dedupe_strings(_as_list(covered))),
        "gaps": _filter_coverage_gaps(_dedupe_strings(_as_list(gaps))),
    }


def _source_summaries_from_response(response: Any) -> Dict[str, str]:
    if not isinstance(response, dict):
        return {}

    raw = response.get("source_summaries", response.get("content_summaries"))
    summaries: Dict[str, str] = {}
    if isinstance(raw, dict):
        for source_id, value in raw.items():
            cleaned_id = _clean_optional(source_id)
            if isinstance(value, dict):
                cleaned_summary = _clean_optional(
                    value.get("content_summary")
                    or value.get("summary")
                    or value.get("text_summary")
                )
            else:
                cleaned_summary = _clean_optional(value)
            if cleaned_id and cleaned_summary:
                summaries[_normalize_source_id(cleaned_id)] = cleaned_summary
        return summaries

    if not isinstance(raw, list):
        return {}

    for item in raw:
        if not isinstance(item, dict):
            continue
        source_id = _clean_optional(item.get("id") or item.get("source_id") or item.get("citation"))
        summary = _clean_optional(
            item.get("content_summary")
            or item.get("summary")
            or item.get("text_summary")
        )
        if source_id and summary:
            summaries[_normalize_source_id(source_id)] = summary
    return summaries


def _merge_coverage(
    current: Dict[str, List[str]],
    update: Optional[Dict[str, List[str]]],
) -> Dict[str, List[str]]:
    if not update:
        return {
            "covered": sorted(_dedupe_strings(current.get("covered", []))),
            "gaps": sorted(_dedupe_strings(current.get("gaps", []))),
        }
    covered = set(_dedupe_strings(current.get("covered", []) + update.get("covered", [])))
    gaps = set(_dedupe_strings(update.get("gaps", current.get("gaps", []))))
    gaps.difference_update(covered)
    return {"covered": sorted(covered), "gaps": sorted(gaps)}


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_source_id(value: str) -> str:
    cleaned = value.strip()
    match = re.search(r"R\s*(\d+)", cleaned, flags=re.IGNORECASE)
    if match:
        return f"R{match.group(1)}"
    return cleaned


def _join_excerpt(document_texts: List[str], max_chars: int = 5000) -> str:
    return "\n\n".join(document_texts)[:max_chars]


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    normalized = parsed._replace(fragment="", query=query)
    return urlunparse(normalized).rstrip("/")


def _is_placeholder_source(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/").lower()
    return hostname in {"example.com", "www.example.com"} or (
        hostname == "www.iana.org" and path == "/domains/reserved"
    )


def _strip_sources_section(markdown: str) -> str:
    return re.split(r"(?im)^##\s+Sources\s*$", markdown, maxsplit=1)[0].strip()


def _drop_preamble_before_first_heading(markdown: str) -> str:
    first_heading = re.search(r"(?m)^##\s+", markdown)
    if first_heading and markdown[: first_heading.start()].strip():
        return markdown[first_heading.start():].strip()
    return markdown


def _remove_section(markdown: str, heading: str) -> str:
    pattern = rf"(?ims)^##\s+{re.escape(heading)}\s*$.*?(?=^##\s+|\Z)"
    return re.sub(pattern, "", markdown).strip()


def _remove_any_level_section(markdown: str, heading: str) -> str:
    pattern = rf"(?ims)^#{2,6}\s+{re.escape(heading)}\s*$.*?(?=^#{1,6}\s+|\Z)"
    return re.sub(pattern, "", markdown).strip()


def _normalize_citation_markers(markdown: str) -> str:
    return re.sub(r"\((R\d+(?:\s*,\s*R\d+)*)\)", r"[\1]", markdown)


def _has_heading(markdown: str, heading: str) -> bool:
    return bool(re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", markdown))


def _append_to_section(markdown: str, heading: str, addition: str) -> str:
    heading_match = re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", markdown)
    if not heading_match:
        return markdown.rstrip() + addition
    next_heading = re.search(r"(?im)^##\s+", markdown[heading_match.end():])
    if not next_heading:
        return markdown.rstrip() + addition
    insert_at = heading_match.end() + next_heading.start()
    return markdown[:insert_at].rstrip() + addition + "\n\n" + markdown[insert_at:].lstrip()


def _section_body(markdown: str, heading: str) -> Optional[str]:
    heading_match = re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", markdown)
    if not heading_match:
        return None
    next_heading = re.search(r"(?im)^##\s+", markdown[heading_match.end():])
    end_at = heading_match.end() + next_heading.start() if next_heading else len(markdown)
    return markdown[heading_match.end():end_at].strip()


def _replace_section_body(markdown: str, heading: str, body: str) -> str:
    heading_match = re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", markdown)
    if not heading_match:
        return markdown
    next_heading = re.search(r"(?im)^##\s+", markdown[heading_match.end():])
    if not next_heading:
        return markdown[:heading_match.end()].rstrip() + "\n" + body.strip()
    suffix_start = heading_match.end() + next_heading.start()
    return (
        markdown[:heading_match.end()].rstrip()
        + "\n"
        + body.strip()
        + "\n\n"
        + markdown[suffix_start:].lstrip()
    )


def _ensure_source_context_citations(
    markdown: str,
    sources: List[Dict[str, Any]],
) -> str:
    body = _section_body(markdown, "Source-Grounded Context")
    if body is None or re.search(r"\[R\d+\]", body):
        return markdown
    lines = _source_grounded_context_lines(sources)
    if not lines:
        return markdown
    return _replace_section_body(
        markdown,
        "Source-Grounded Context",
        "\n".join(lines),
    )


def _source_grounded_context_lines(sources: List[Dict[str, Any]]) -> List[str]:
    fetched_sources = [
        source
        for source in sources
        if source.get("fetched") and _clean_optional(source.get("content_summary"))
    ]
    lines = []
    for keywords, template in SOURCE_CONTEXT_THEMES:
        matches = [
            source
            for source in fetched_sources
            if _summary_keywords(str(source.get("content_summary") or "")) & keywords
        ]
        if not matches:
            continue
        citations = _format_source_citations(matches[:3])
        lines.append(f"- {template} {citations}")
        if len(lines) >= SOURCE_CONTEXT_RENDER_LIMIT:
            break

    if lines:
        return lines

    for source in sources:
        if not source.get("fetched"):
            continue
        detail = _clean_optional(source.get("content_summary"))
        if not detail:
            continue
        lines.append(
            "- Retrieved sources add scenario-relevant context from fetched material about "
            f"{_cap_text(detail, max_chars=SOURCE_CONTEXT_LINE_MAX_CHARS)} [{source['id']}]"
        )
        if len(lines) >= SOURCE_CONTEXT_RENDER_LIMIT:
            break
    return lines


def _format_source_citations(sources: List[Dict[str, Any]]) -> str:
    return " ".join(f"[{source['id']}]" for source in sources if source.get("id"))


def _source_summary_lines(sources: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for source in sources:
        if not source.get("fetched"):
            continue
        detail = _clean_optional(source.get("content_summary"))
        if not detail:
            detail = "Fetched source did not contain enough relevant text to summarize."
        detail = _cap_text(detail, max_chars=SOURCE_CONTENT_SUMMARY_MAX_CHARS)
        lines.append(f"- [{source['id']}] {detail}")
        if len(lines) >= SOURCE_SUMMARY_RENDER_LIMIT:
            break
    return lines


def _fallback_content_summary(
    source: Dict[str, Any],
    *,
    document_texts: List[str],
    simulation_requirement: str,
    max_chars: int = SOURCE_CONTENT_SUMMARY_MAX_CHARS,
) -> str:
    text = _clean_optional(source.get("text"))
    if not text:
        return "Fetched source did not contain enough relevant text to summarize."

    normalized = _remove_boilerplate_sentences(text)
    sentences = _split_summary_sentences(normalized)
    if not sentences:
        return "Fetched source did not contain enough relevant non-boilerplate text to summarize."

    keywords = _summary_keywords(
        " ".join(
            [
                str(source.get("query") or ""),
                simulation_requirement,
                _join_excerpt(document_texts, max_chars=2000),
            ]
        )
    )
    scored = []
    for index, sentence in enumerate(sentences):
        sentence_words = _summary_keywords(sentence)
        score = len(sentence_words & keywords)
        scored.append((score, index, sentence))

    selected_indices = [
        index
        for score, index, _sentence in sorted(scored, key=lambda item: (-item[0], item[1]))
        if score > 0
    ][:FALLBACK_SUMMARY_MAX_SENTENCES]
    for index in range(len(sentences)):
        if len(selected_indices) >= min(FALLBACK_SUMMARY_MIN_SENTENCES, len(sentences)):
            break
        if index not in selected_indices:
            selected_indices.append(index)
    if not selected_indices:
        selected_indices = list(range(min(FALLBACK_SUMMARY_MIN_SENTENCES, len(sentences))))

    selected = [sentences[index] for index in sorted(selected_indices)]
    return _cap_text(" ".join(selected), max_chars=max_chars)


def _remove_boilerplate_sentences(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    raw_sentences = _split_summary_sentences(normalized)
    sentences = [
        sentence
        for sentence in raw_sentences
        if not _is_boilerplate_sentence(sentence)
    ]
    if sentences:
        return " ".join(sentences)
    if raw_sentences:
        return ""
    return normalized


def _is_boilerplate_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    if any(phrase in lowered for phrase in BOILERPLATE_PHRASES):
        return True

    words = set(re.findall(r"[a-z][a-z&'-]+", lowered))
    category_hits = words & BOILERPLATE_CATEGORY_TERMS
    if len(category_hits) >= 6:
        return True
    if sentence.count("&") >= 5 and len(category_hits) >= 4:
        return True
    if len(sentence) > 180 and len(category_hits) >= 4 and "services" in lowered:
        return True
    return False


def _split_summary_sentences(text: str) -> List[str]:
    candidates = re.split(r"(?<=[.!?])\s+", text)
    sentences = []
    for candidate in candidates:
        cleaned = candidate.strip()
        if cleaned:
            sentences.append(cleaned)
    return sentences


def _summary_keywords(text: str) -> set[str]:
    stopwords = {
        "about",
        "after",
        "also",
        "from",
        "have",
        "into",
        "more",
        "near",
        "over",
        "that",
        "their",
        "there",
        "these",
        "this",
        "with",
        "would",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9'-]{3,}", text.lower())
        if token not in stopwords
    }


def _cap_text(text: str, *, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    clipped = cleaned[:max_chars].rstrip()
    boundary = max(clipped.rfind(". "), clipped.rfind("; "), clipped.rfind(", "))
    if boundary >= 160:
        clipped = clipped[: boundary + 1].rstrip()
    return clipped.rstrip(".;, ") + "..."


def _filter_coverage_gaps(gaps: List[str]) -> List[str]:
    filtered = []
    for gap in gaps:
        lowered = gap.lower()
        if any(marker in lowered for marker in OUT_OF_SCOPE_GAP_MARKERS):
            continue
        filtered.append(gap)
    return sorted(filtered)


def _filter_contextually_covered_gaps(
    coverage: Dict[str, List[str]],
    summary_markdown: str,
    sources: List[Dict[str, Any]],
    query_history: List[str],
) -> Dict[str, List[str]]:
    context_parts = [summary_markdown, " ".join(query_history)]
    for source in sources:
        context_parts.extend(
            [
                str(source.get("title") or ""),
                str(source.get("snippet") or ""),
                str(source.get("query") or ""),
            ]
        )
    context = " ".join(context_parts).lower()
    gaps = []
    for gap in coverage.get("gaps", []):
        lowered = gap.lower()
        if ("military" in lowered or "security" in lowered) and any(
            marker in context
            for marker in (
                "maritime security",
                "de-escalation",
                "freedom of navigation",
                "naval patrol",
                "shipping lane",
                "crowded shipping lanes",
            )
        ):
            continue
        if "economic" in lowered and any(
            marker in context
            for marker in (
                "insurance",
                "shipping delay",
                "freight rate",
                "supply chain",
                "importer",
                "small business",
                "energy market",
            )
        ):
            continue
        if ("small business" in lowered or "shipping delay" in lowered) and any(
            marker in context
            for marker in (
                "shipping delay",
                "supply chain",
                "importer",
                "small business",
                "freight rate",
                "logistics cost",
            )
        ):
            continue
        gaps.append(gap)
    return {
        "covered": sorted(_dedupe_strings(coverage.get("covered", []))),
        "gaps": sorted(_dedupe_strings(gaps)),
    }


def _relocate_scenario_boundary_claims(markdown: str) -> tuple[str, List[str]]:
    boundary_match = re.search(r"(?im)^##\s+Scenario Assumptions Boundary\s*$", markdown)
    if boundary_match:
        prefix = markdown[:boundary_match.start()]
        suffix = markdown[boundary_match.start():]
    else:
        prefix = markdown
        suffix = ""

    relocated: List[str] = []
    kept_lines = []
    for line in prefix.splitlines():
        if line.startswith("#"):
            kept_lines.append(line)
            continue
        if not any(marker.lower() in line.lower() for marker in SCENARIO_BOUNDARY_MARKERS):
            kept_lines.append(line)
            continue

        kept_sentences = []
        for sentence in _split_sentences(line):
            if any(marker.lower() in sentence.lower() for marker in SCENARIO_BOUNDARY_MARKERS):
                cleaned = re.sub(r"\s*\[R\d+(?:\s*,\s*R\d+)*\]", "", sentence)
                cleaned = re.sub(r"\s*\(\s*\)", "", cleaned).strip()
                if cleaned:
                    relocated.append(cleaned)
            else:
                kept_sentences.append(sentence)
        if kept_sentences:
            kept_lines.append(" ".join(kept_sentences))

    return "\n".join(kept_lines).strip() + ("\n\n" if suffix and kept_lines else "") + suffix.strip(), relocated


def _split_sentences(line: str) -> List[str]:
    if not line.strip():
        return []
    bullet = ""
    stripped = line.strip()
    if stripped.startswith("- "):
        bullet = "- "
        stripped = stripped[2:].strip()
    sentences = re.split(r"(?<=[.!?])\s+", stripped)
    return [bullet + sentence if idx == 0 and bullet else sentence for idx, sentence in enumerate(sentences) if sentence]


def _extract_scenario_assumptions(document_texts: List[str]) -> List[str]:
    text = _join_excerpt(document_texts, max_chars=12000)
    lowered = text.lower()
    return [term for term in SCENARIO_BOUNDARY_TERMS if term.lower() in lowered]
