import re
from datetime import datetime, timedelta
from typing import Optional


class QueryProcessor:
    """Parse user queries for semantic search + metadata filtering."""

    TEMPORAL_PATTERNS = [
        (r"\b(last|past)\s+(week|7\s*days?)\b", "last_week"),
        (r"\b(last|past)\s+(month|30\s*days?)\b", "last_month"),
        (r"\b(last|past)\s+(year|365\s*days?|12\s*months?)\b", "last_year"),
        (r"\byesterday\b", "yesterday"),
        (r"\btoday\b", "today"),
        (r"\b(\d+)\s*(days?|weeks?|months?|years?)\s*(ago|back)\b", "relative"),
        (r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b", "month_date"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "iso_date"),
    ]

    TYPE_PATTERNS = {
        r"\b(photos?|pictures?|images?|screenshots?|jpeg|jpg|png|gif|heic|webp)\b": "image",
        r"\b(documents?|reports?|pdf|paper)\b": "pdf",
        r"\b(notes?|memos?|text|txt|markdown|code|py|js|ts|json)\b": "text",
        r"\b(voice|audio|recordings?|mp3|wav|m4a|ogg)\b": "audio",
    }

    SIZE_PATTERNS = [
        (r"\b(large|big)\s+(file|image|photo)s?\b", "large"),
        (r"\b(small|tiny)\s+(file|image|photo)s?\b", "small"),
        (r"\bunder\s+(\d+)\s*mb\b", "under_mb"),
        (r"\bover\s+(\d+)\s*mb\b", "over_mb"),
    ]

    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    # FOR THE EXPANSION QUERY FUNCTION  

    EXPANSION_RULES = [
        (r"\bmeeting\b",        "meeting conversation discussion call"),
        (r"\bphoto[s]?\b",      "photo picture image screenshot"),
        (r"\bnotes?\b",         "note memo document text"),
        (r"\breceipt\b",        "receipt invoice payment bill"),
        (r"\bresume\b",         "resume CV profile portfolio"),
        (r"\bcertificate\b",    "certificate diploma degree award"),
        (r"\binvoice\b",        "invoice bill receipt payment"),
        (r"\bcontract\b",       "contract agreement document"),
        (r"\bpassport\b",       "passport ID identity document"),
        (r"\bscreenshot\b",     "screenshot capture image photo"),
        (r"\brecording\b",      "recording audio voice meeting"),
        (r"\breport\b",         "report document summary analysis"),
        (r"\bpresentation\b",   "presentation slides deck PDF"),
    ]

    def _parse_relative_date(self, match_str: str) -> Optional[dict]:
        match = re.search(r"(\d+)\s*(days?|weeks?|months?|years?)\s*(ago|back)", match_str, re.IGNORECASE)
        if not match:
            return None
        num, unit, _ = match.groups()
        days_map = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30, "year": 365, "years": 365}
        days = days_map.get(unit.lower(), 1) * int(num)
        return {"$gte": (datetime.now() - timedelta(days=days)).timestamp()}

    def _parse_month_date(self, match_str: str) -> Optional[dict]:
        match = re.search(r"(\w+)\s+(\d{1,2})", match_str, re.IGNORECASE)
        if not match:
            return None
        month = self.MONTH_MAP.get(match.group(1).lower())
        if not month:
            return None
        try:
            return {"$gte": datetime(datetime.now().year, month, int(match.group(2))).timestamp()}
        except ValueError:
            return None

    def _parse_size(self, match_str: str, pattern_type: str) -> Optional[dict]:
        if pattern_type == "large":
            return {"$gt": 5 * 1024 * 1024}
        elif pattern_type == "small":
            return {"$lt": 1 * 1024 * 1024}
        elif pattern_type == "under_mb":
            m = re.search(r"(\d+)", match_str)
            return {"$lt": int(m.group(1)) * 1024 * 1024} if m else None
        elif pattern_type == "over_mb":
            m = re.search(r"(\d+)", match_str)
            return {"$gt": int(m.group(1)) * 1024 * 1024} if m else None
        return None

    def process(self, raw_query: str) -> dict:
        clean_query = raw_query
        query_lower = raw_query.lower()
        extracted_temporal = None
        extracted_types = []
        extracted_sizes = None
        negated_types = []

        # --- Temporal ---
        for pattern, pattern_type in self.TEMPORAL_PATTERNS:
            if match := re.search(pattern, query_lower, re.IGNORECASE):
                s = match.group(0)
                if pattern_type == "last_week":
                    extracted_temporal = {"$gte": (datetime.now() - timedelta(days=7)).timestamp()}
                elif pattern_type == "last_month":
                    extracted_temporal = {"$gte": (datetime.now() - timedelta(days=30)).timestamp()}
                elif pattern_type == "last_year":
                    extracted_temporal = {"$gte": (datetime.now() - timedelta(days=365)).timestamp()}
                elif pattern_type == "yesterday":
                    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
                    extracted_temporal = {"$gte": start.timestamp(), "$lt": (start + timedelta(days=1)).timestamp()}
                elif pattern_type == "today":
                    extracted_temporal = {"$gte": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()}
                elif pattern_type == "relative":
                    extracted_temporal = self._parse_relative_date(s)
                elif pattern_type == "month_date":
                    extracted_temporal = self._parse_month_date(s)
                elif pattern_type == "iso_date":
                    try:
                        extracted_temporal = {"$gte": datetime.fromisoformat(s).timestamp()}
                    except ValueError:
                        pass
                clean_query = re.sub(re.escape(s), "", clean_query, flags=re.IGNORECASE)
                break

        # --- Size (before type, so "large images" strips intact before "images" is removed) ---
        for pattern, size_type in self.SIZE_PATTERNS:
            if match := re.search(pattern, query_lower, re.IGNORECASE):
                extracted_sizes = self._parse_size(match.group(0), size_type)
                clean_query = re.sub(re.escape(match.group(0)), "", clean_query, flags=re.IGNORECASE)
                break

        # --- Negation (before type, so we don't double-match) ---
        for neg_pattern in [r"\bnot\s+(pdf|image|text|audio)\b", r"-\s*(pdf|image|text|audio)\b"]:
            if match := re.search(neg_pattern, query_lower, re.IGNORECASE):
                negated_types.append(match.group(1).lower())
                clean_query = re.sub(neg_pattern, "", clean_query, flags=re.IGNORECASE)

        # --- Type ---
        for pattern, ftype in self.TYPE_PATTERNS.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                if ftype not in negated_types:
                    extracted_types.append(ftype)
                clean_query = re.sub(pattern, "", clean_query, flags=re.IGNORECASE)

        # --- Build where_filter ---
        where_filter = {}
        if extracted_temporal:
            where_filter["mtime"] = extracted_temporal
        if extracted_types:
            where_filter["type"] = extracted_types[0] if len(extracted_types) == 1 else {"$in": extracted_types}
        if negated_types:
            where_filter["type"] = {"$nin": negated_types}
        if extracted_sizes:
            where_filter["size"] = extracted_sizes

        return {
            "clean_query": re.sub(r"\s+", " ", clean_query).strip(),
            "where_filter": where_filter if where_filter else None,
            "debug": {
                "extracted_temporal": extracted_temporal,
                "extracted_types": extracted_types,
                "negated_types": negated_types,
                "extracted_sizes": extracted_sizes,
            }
        }


    def expand(self ,query:str)->list[str]:
        """
        Expand a query into 2-3 paraphrased versions for broader semantic search.

        Each paraphrase embeds differently → union of results widens the net.
        """

        queries = [query]
        for pattern , replacement in self.EXPANSION_RULES : 
                if re.search(pattern ,query , re.IGNORECASE):
                    expanded = re.sub(pattern , replacement ,query , flags = re.IGNORECASE)
                    if expanded not in queries : 
                        queries.append(expanded)
                if len(queries) >= 3 : 
                    break 
        return queries


def process_query(raw_query: str) -> dict:
    return QueryProcessor().process(raw_query)

def expand_query(query:str) -> list[str]:
    return QueryProcessor().expand(query)



if __name__ == "__main__":
    tests = [
        "show me photos from last week",
        "pdf reports from january 15",
        "large images under 5mb from yesterday",
        "documents NOT pdf from last month",
        "code files 3 days ago",
        "voice recording from 2026-05-20",
        "small text notes today",
        "screenshots over 10mb this year",
    ]
    for q in tests:
        r = process_query(q)
        print(f"\n📝 {q}")
        print(f"   clean:  {r['clean_query']}")
        print(f"   filter: {r['where_filter']}")
