"""Robu.in component enrichment with caching and graceful fallback behavior."""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .utils import cache_key, normalize_text, read_json, write_json


DEFAULT_CACHE = Path(".cache/robu_results.json")
USER_AGENT = "PCB-Sustainability-Academic-Prototype/0.1"


class RobuClient:
    """Small scraper layer for Robu.in search pages.

    The implementation is intentionally defensive: cached results are preferred,
    network errors return structured metadata, and selector failures do not break
    the overall sustainability pipeline.
    """

    def __init__(self, cache_path: str | Path = DEFAULT_CACHE, delay_seconds: float = 1.0, timeout: int = 10):
        self.cache_path = Path(cache_path)
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.cache = read_json(self.cache_path, {})
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def enrich_bom(self, df: pd.DataFrame, enabled: bool = True, limit: int | None = None) -> dict[str, dict]:
        enrichments = {}
        rows = df.head(limit) if limit else df
        for _, row in rows.iterrows():
            query = self._query_from_row(row)
            key = normalize_text(row.get("part_number")) or normalize_text(row.get("description")) or query
            enrichments[key] = self.search(query, enabled=enabled)
        self.save()
        return enrichments

    def search(self, query: str, enabled: bool = True) -> dict:
        query = normalize_text(query)
        if not query:
            return {"query": query, "status": "missing_query", "match_confidence": 0.0}
        key = cache_key(query)
        if key in self.cache:
            result = dict(self.cache[key])
            result["from_cache"] = True
            return result
        if not enabled:
            result = self._offline_guess(query)
            self.cache[key] = result
            return result

        time.sleep(self.delay_seconds)
        url = f"https://robu.in/?s={quote_plus(query)}&post_type=product"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = self._parse_search(query, url, response.text)
        except requests.RequestException as exc:
            result = self._offline_guess(query)
            result.update({"status": "network_error", "error": str(exc), "source_url": url})
        self.cache[key] = result
        return result

    def save(self) -> None:
        write_json(self.cache_path, self.cache)

    def _query_from_row(self, row: pd.Series) -> str:
        fields = [row.get("part_number"), row.get("manufacturer"), row.get("description"), row.get("value")]
        return " ".join(normalize_text(value) for value in fields if normalize_text(value))[:180]

    def _parse_search(self, query: str, url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        product = soup.select_one("li.product, .product-small, .product, .type-product")
        if not product:
            return {
                "query": query,
                "status": "not_found",
                "source_url": url,
                "availability": "Unknown",
                "match_confidence": 0.15,
            }

        title_el = product.select_one(".woocommerce-loop-product__title, .product-title, h2, h3, a")
        price_el = product.select_one(".price, .amount")
        link_el = product.select_one("a[href]")
        stock_el = product.select_one(".stock, .availability")
        category_el = product.select_one(".posted_in, .category")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        href = link_el.get("href", "") if link_el else url

        metadata = {
            "query": query,
            "status": "ok",
            "title": title,
            "category": category_el.get_text(" ", strip=True) if category_el else _guess_category(title or query),
            "manufacturer": _guess_manufacturer(title or query),
            "package": _guess_package(title or query),
            "datasheet_link": _find_datasheet(product),
            "availability": stock_el.get_text(" ", strip=True) if stock_el else "Available status not shown",
            "price": price_el.get_text(" ", strip=True) if price_el else "",
            "similar_components": _similar_terms(title or query),
            "source_url": href,
            "match_confidence": _match_confidence(query, title),
        }
        return metadata

    def _offline_guess(self, query: str) -> dict:
        return {
            "query": query,
            "status": "offline_fallback",
            "title": query,
            "category": _guess_category(query),
            "manufacturer": _guess_manufacturer(query),
            "package": _guess_package(query),
            "datasheet_link": "",
            "availability": "Unknown; enable online lookup for live Robu.in stock status",
            "price": "",
            "similar_components": _similar_terms(query),
            "match_confidence": 0.35,
        }


def _guess_category(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["resistor", "ohm"]):
        return "Passive resistor"
    if any(term in lowered for term in ["capacitor", "uf", "nf", "pf"]):
        return "Passive capacitor"
    if any(term in lowered for term in ["connector", "header", "terminal"]):
        return "Connector"
    if any(term in lowered for term in ["battery", "cell", "lipo"]):
        return "Battery"
    if any(term in lowered for term in ["arduino", "esp", "mcu", "ic", "module"]):
        return "IC or module"
    return "Electronic component"


def _guess_package(text: str) -> str:
    match = re.search(r"\b(0201|0402|0603|0805|1206|sot-?\d+|soic-?\d+|qfn-?\d+|bga|dip-?\d+|to-?\d+)\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _guess_manufacturer(text: str) -> str:
    known = ["Texas Instruments", "STMicroelectronics", "Microchip", "Arduino", "Espressif", "Vishay", "Murata", "Samsung"]
    lowered = text.lower()
    for manufacturer in known:
        if manufacturer.lower() in lowered:
            return manufacturer
    return ""


def _find_datasheet(product) -> str:
    for link in product.select("a[href]"):
        href = link.get("href", "")
        label = link.get_text(" ", strip=True).lower()
        if "datasheet" in label or href.lower().endswith(".pdf"):
            return href
    return ""


def _similar_terms(text: str) -> list[str]:
    category = _guess_category(text)
    if category == "Battery":
        return ["socketed battery holder", "standard replaceable cell", "RoHS-compliant holder"]
    if category == "Connector":
        return ["through-hole connector", "locking recyclable connector", "standard pitch header"]
    if category == "Passive resistor":
        return ["RoHS 0805 resistor", "larger 1206 serviceable resistor"]
    if category == "Passive capacitor":
        return ["RoHS MLCC", "aluminum electrolytic with clear polarity marking"]
    return ["RoHS equivalent", "halogen-free equivalent", "widely available module"]


def _match_confidence(query: str, title: str) -> float:
    if not title:
        return 0.2
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    title_terms = set(re.findall(r"[a-z0-9]+", title.lower()))
    if not query_terms:
        return 0.2
    overlap = len(query_terms & title_terms) / len(query_terms)
    return round(max(0.2, min(0.95, overlap)), 2)
