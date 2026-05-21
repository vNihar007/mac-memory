import pytest
from datetime import datetime, timedelta
from mac_memory import query_processor 


# ─── query_processor.process_query tests ────────────────────────────────────────────────────

class TestTemporalFilters:
    def test_last_week(self):
        r = query_processor.process_query("show me photos from last week")
        assert r["where_filter"]["mtime"]["$gte"] is not None
        expected = (datetime.now() - timedelta(days=7)).timestamp()
        assert abs(r["where_filter"]["mtime"]["$gte"] - expected) < 5

    def test_last_month(self):
        r = query_processor.process_query("documents from last month")
        assert "$gte" in r["where_filter"]["mtime"]

    def test_last_year(self):
        r = query_processor.process_query("files from last year")
        assert "$gte" in r["where_filter"]["mtime"]

    def test_today(self):
        r = query_processor.process_query("notes today")
        assert "$gte" in r["where_filter"]["mtime"]
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        assert abs(r["where_filter"]["mtime"]["$gte"] - start_of_day) < 5

    def test_yesterday(self):
        r = query_processor.process_query("screenshots from yesterday")
        mtime = r["where_filter"]["mtime"]
        assert "$gte" in mtime and "$lt" in mtime

    def test_relative_days_ago(self):
        r = query_processor.process_query("code files 3 days ago")
        assert "$gte" in r["where_filter"]["mtime"]
        expected = (datetime.now() - timedelta(days=3)).timestamp()
        assert abs(r["where_filter"]["mtime"]["$gte"] - expected) < 5

    def test_relative_weeks_ago(self):
        r = query_processor.process_query("images 2 weeks ago")
        expected = (datetime.now() - timedelta(days=14)).timestamp()
        assert abs(r["where_filter"]["mtime"]["$gte"] - expected) < 5

    def test_iso_date(self):
        r = query_processor.process_query("voice recording from 2026-05-20")
        assert "$gte" in r["where_filter"]["mtime"]

    def test_month_date(self):
        r = query_processor.process_query("pdf reports from january 15")
        assert "$gte" in r["where_filter"]["mtime"]

    def test_no_temporal(self):
        r = query_processor.process_query("find my resume")
        assert r["where_filter"] is None or "mtime" not in (r["where_filter"] or {})


class TestTypeFilters:
    def test_image_photo(self):
        r = query_processor.process_query("show me my photos")
        assert r["where_filter"]["type"] == "image"

    def test_image_screenshot(self):
        r = query_processor.process_query("find screenshots")
        assert r["where_filter"]["type"] == "image"

    def test_pdf(self):
        r = query_processor.process_query("find documents")
        assert r["where_filter"]["type"] == "pdf"

    def test_audio(self):
        r = query_processor.process_query("voice recording from last week")
        assert r["where_filter"]["type"] == "audio"

    def test_text(self):
        r = query_processor.process_query("show me my notes")
        assert r["where_filter"]["type"] == "text"

    def test_no_type(self):
        r = query_processor.process_query("something from 3 days ago")
        assert r["where_filter"] is None or "type" not in (r["where_filter"] or {})


class TestNegationFilters:
    def test_not_pdf(self):
        r = query_processor.process_query("documents NOT pdf from last month")
        assert r["where_filter"]["type"] == {"$nin": ["pdf"]}

    def test_dash_negation(self):
        r = query_processor.process_query("files -image from today")
        assert r["where_filter"]["type"] == {"$nin": ["image"]}


class TestSizeFilters:
    def test_large_file(self):
        r = query_processor.process_query("large image from yesterday")
        assert r["where_filter"]["size"] == {"$gt": 5 * 1024 * 1024}

    def test_small_file(self):
        r = query_processor.process_query("small files from today")
        assert r["where_filter"]["size"] == {"$lt": 1 * 1024 * 1024}

    def test_under_mb(self):
        r = query_processor.process_query("images under 10mb")
        assert r["where_filter"]["size"] == {"$lt": 10 * 1024 * 1024}

    def test_over_mb(self):
        r = query_processor.process_query("screenshots over 10mb")
        assert r["where_filter"]["size"] == {"$gt": 10 * 1024 * 1024}


class TestCleanQuery:
    def test_temporal_stripped(self):
        r = query_processor.process_query("show me photos from last week")
        assert "last week" not in r["clean_query"].lower()

    def test_type_keyword_stripped(self):
        r = query_processor.process_query("show me my photos from today")
        assert "photo" not in r["clean_query"].lower()

    def test_size_keyword_stripped(self):
        r = query_processor.process_query("large images from yesterday")
        assert "large" not in r["clean_query"].lower()

    def test_no_double_spaces(self):
        r = query_processor.process_query("show me pdf documents from last month")
        assert "  " not in r["clean_query"]

    def test_combined_clean_query(self):
        r = query_processor.process_query("pdf reports from january 15")
        assert r["clean_query"].strip() != ""


class TestCombinedFilters:
    def test_type_and_temporal(self):
        r = query_processor.process_query("images from last week")
        assert "type" in r["where_filter"]
        assert "mtime" in r["where_filter"]

    def test_type_size_temporal(self):
        r = query_processor.process_query("large images under 5mb from yesterday")
        assert "type" in r["where_filter"]
        assert "mtime" in r["where_filter"]
        assert "size" in r["where_filter"]


# ─── expand_query tests ─────────────────────────────────────────────────────

class TestExpandQuery:
    def test_returns_list(self):
        result = query_processor.expand_query("find my meeting notes")
        assert isinstance(result, list)

    def test_original_preserved(self):
        q = "find my passport"
        result = query_processor.expand_query(q)
        assert result[0] == q

    def test_expands_meeting(self):
        result = query_processor.expand_query("notes from the meeting")
        assert len(result) >= 2
        assert any("conversation" in r or "discussion" in r or "call" in r for r in result[1:])

    def test_expands_photo(self):
        result = query_processor.expand_query("my vacation photos")
        assert any("picture" in r or "image" in r or "screenshot" in r for r in result[1:])

    def test_expands_receipt(self):
        result = query_processor.expand_query("grocery receipt")
        assert any("invoice" in r or "bill" in r for r in result[1:])

    def test_expands_resume(self):
        result = query_processor.expand_query("update my resume")
        assert any("CV" in r or "portfolio" in r for r in result[1:])

    def test_no_expansion_for_unmatched(self):
        result = query_processor.expand_query("random unrelated query xyz")
        assert result == ["random unrelated query xyz"]

    def test_max_3_results(self):
        result = query_processor.expand_query("meeting photos recording")
        assert len(result) <= 3

    def test_no_duplicates(self):
        result = query_processor.expand_query("passport photo")
        assert len(result) == len(set(result))

    def test_case_insensitive_expansion(self):
        result = query_processor.expand_query("MEETING notes")
        assert len(result) >= 2


# ─── run directly ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
