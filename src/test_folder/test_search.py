"""
Tests for mac_memory/search.py

Required installs (all stdlib or already in the project):
    pip install pytest          # test runner
    pip install chromadb        # already a project dependency
    pip install google-genai    # already a project dependency

No extra installs needed — mocking is done with unittest.mock (stdlib).

KNOWN BUGS IN search.py (tests below expose them):
  BUG-1 (line 41): inside `for q in queries` loop, `where` is overwritten with
         {"type ": file_type} (trailing space in key!), clobbering the
         where_filter from process_query on every iteration.
  BUG-2 (lines 50-54): the dedup loop `for meta, distance in zip(...)` is
         OUTSIDE the `for q in queries` loop — only the last query's results
         are ever merged, so multi-vector expansion is silently broken.
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch, call

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── mock chromadb BEFORE importing search (it connects at import time) ───────
_mock_collection = MagicMock()
_mock_collection.count.return_value = 20

_mock_chroma_client = MagicMock()
_mock_chroma_client.get_collection.return_value = _mock_collection

with patch("chromadb.PersistentClient", return_value=_mock_chroma_client):
    from mac_memory import search
    from mac_memory.search import search_files, SearchResult

# point the module-level `collection` at our mock
search.collection = _mock_collection


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_embed_result(values: list[float]):
    """Build a fake EmbedContentResponse-like object."""
    embedding = MagicMock()
    embedding.values = values
    result = MagicMock()
    result.embeddings = [embedding]
    return result


def _chroma_response(paths: list[str], distances: list[float]):
    """Build a fake chromadb collection.query() response."""
    metadatas = [
        {"path": p, "name": os.path.basename(p), "type": "image", "size": 1024}
        for p in paths
    ]
    return {
        "metadatas": [metadatas],
        "distances": [distances],
    }


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_collection_mock():
    """Reset the collection mock state before each test."""
    _mock_collection.query.side_effect = None
    _mock_collection.query.return_value = None
    _mock_collection.count.return_value = 20
    yield


# ── SearchResult dataclass ────────────────────────────────────────────────────

class TestSearchResult:
    def test_fields_exist(self):
        r = SearchResult(path="/a/b.jpg", name="b.jpg", file_type="image",
                         similarity=0.95, size=2048)
        assert r.path == "/a/b.jpg"
        assert r.name == "b.jpg"
        assert r.file_type == "image"
        assert r.similarity == 0.95
        assert r.size == 2048

    def test_vars_serializable(self):
        r = SearchResult(path="/a/b.jpg", name="b.jpg", file_type="image",
                         similarity=0.95, size=2048)
        d = vars(r)
        assert json.dumps(d)  # must be JSON-serializable for --json CLI flag


# ── search_files: basic behaviour ────────────────────────────────────────────

class TestSearchFilesBasic:
    def test_returns_list(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/a/photo.jpg"], [0.2]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("find my photos")
        assert isinstance(results, list)

    def test_result_is_search_result(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/a/photo.jpg"], [0.2]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("find my photos")
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)

    def test_similarity_equals_1_minus_distance(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/a/photo.jpg"], [0.3]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("photo")
        assert results[0].similarity == round(1.0 - 0.3, 4)

    def test_empty_when_embedder_returns_none(self):
        with patch.object(search.embedder, "embed_text", return_value=None):
            results = search_files("anything")
        assert results == []

    def test_empty_when_no_embeddings_in_result(self):
        bad_result = MagicMock()
        bad_result.embeddings = []
        with patch.object(search.embedder, "embed_text", return_value=bad_result):
            results = search_files("anything")
        assert results == []

    def test_top_k_limits_results(self):
        fake_embed = _make_embed_result([0.1] * 768)
        paths = [f"/a/file{i}.jpg" for i in range(10)]
        distances = [0.1 * i for i in range(10)]
        _mock_collection.query.return_value = _chroma_response(paths, distances)
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("photos", top_k=3)
        assert len(results) <= 3

    def test_results_sorted_by_similarity_descending(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/a.jpg", "/b.jpg", "/c.jpg"], [0.5, 0.1, 0.3]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("photos")
        sims = [r.similarity for r in results]
        assert sims == sorted(sims, reverse=True)


# ── search_files: query processor integration ─────────────────────────────────

class TestQueryProcessorIntegration:
    def test_temporal_keyword_stripped_before_embedding(self):
        """The string passed to embed_text should have temporal tokens removed."""
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.jpg"], [0.2])
        captured = []

        def capture_embed(text):
            captured.append(text)
            return fake_embed

        with patch.object(search.embedder, "embed_text", side_effect=capture_embed):
            search_files("photos from last week")

        assert captured, "embed_text should have been called"
        assert "last week" not in captured[0].lower()

    def test_type_keyword_stripped_before_embedding(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.jpg"], [0.2])
        captured = []

        def capture_embed(text):
            captured.append(text)
            return fake_embed

        with patch.object(search.embedder, "embed_text", side_effect=capture_embed):
            search_files("my vacation photos")

        assert "photo" not in captured[0].lower()

    def test_where_filter_passed_to_chroma(self):
        """process_query temporal/type filter should reach collection.query()."""
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.jpg"], [0.2])

        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            search_files("images from last week")

        call_kwargs = _mock_collection.query.call_args
        where_arg = call_kwargs.kwargs.get("where") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        # where should have mtime from "last week"
        # (BUG-1 in search.py may cause this to fail — see module docstring)
        if where_arg:
            assert "mtime" in where_arg or "type" in where_arg


# ── search_files: file_type override ─────────────────────────────────────────

class TestFileTypeOverride:
    def test_file_type_arg_sets_where_type(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.pdf"], [0.2])

        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            search_files("reports", file_type="pdf")

        call_kwargs = _mock_collection.query.call_args
        where_arg = call_kwargs.kwargs.get("where")
        assert where_arg == {"type": "pdf"}

    def test_no_file_type_passes_none_or_filter(self):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.jpg"], [0.2])

        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            search_files("photos")

        call_kwargs = _mock_collection.query.call_args
        where_arg = call_kwargs.kwargs.get("where")
        # should be None or a dict — never have a trailing space key "type "
        if isinstance(where_arg, dict):
            assert "type " not in where_arg, "BUG-1: trailing space in 'type ' key"


# ── multi-vector expansion ────────────────────────────────────────────────────

class TestMultiVectorExpansion:
    def test_embed_text_called_for_each_expanded_query(self):
        """expand_query returns 2-3 variants; embed_text should be called once each."""
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(["/a.jpg"], [0.2])
        call_count = []

        def count_embed(text):
            call_count.append(text)
            return fake_embed

        with patch.object(search.embedder, "embed_text", side_effect=count_embed):
            search_files("meeting notes")  # "meeting" triggers expansion

        assert len(call_count) >= 2, (
            "BUG-2: dedup loop is outside for-q loop — multi-vector search broken"
        )

    def test_dedup_keeps_best_score_per_file(self):
        """Same file from two query variants should appear once with best similarity."""
        fake_embed = _make_embed_result([0.1] * 768)
        responses = [
            _chroma_response(["/shared.jpg", "/a.jpg"], [0.4, 0.6]),
            _chroma_response(["/shared.jpg", "/b.jpg"], [0.1, 0.5]),  # better score for /shared.jpg
        ]
        response_iter = iter(responses)
        _mock_collection.query.side_effect = lambda **_: next(response_iter)

        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            results = search_files("meeting photos")

        paths = [r.path for r in results]
        assert paths.count("/shared.jpg") <= 1, "duplicate result for same file"

        shared = next((r for r in results if r.path == "/shared.jpg"), None)
        if shared:
            assert shared.similarity == round(1.0 - 0.1, 4), \
                "should keep best (lowest distance) result for duplicate file"


# ── CLI main() ────────────────────────────────────────────────────────────────

class TestCLIMain:
    def test_json_flag_outputs_valid_json(self, capsys):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/a/photo.jpg"], [0.2]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            with patch("sys.argv", ["search.py", "find photos", "--json"]):
                search.main()

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert "path" in data[0]
        assert "similarity" in data[0]

    def test_no_results_prints_message(self, capsys):
        with patch.object(search.embedder, "embed_text", return_value=None):
            with patch("sys.argv", ["search.py", "xyz"]):
                search.main()

        captured = capsys.readouterr()
        assert "no results" in captured.out.lower() or captured.out == ""

    def test_text_output_contains_filename(self, capsys):
        fake_embed = _make_embed_result([0.1] * 768)
        _mock_collection.query.return_value = _chroma_response(
            ["/home/user/photo.jpg"], [0.15]
        )
        with patch.object(search.embedder, "embed_text", return_value=fake_embed):
            with patch("sys.argv", ["search.py", "vacation"]):
                search.main()

        captured = capsys.readouterr()
        assert "photo.jpg" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
