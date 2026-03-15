from backend.scripts import smoke_rag_pipeline


def test_citations_valid_accepts_matching_indices():
    answer = "Key finding [1]. Extra support [2]."
    citations = [{"index": 1}, {"index": 2}]
    assert smoke_rag_pipeline.citations_valid(answer, citations) is True


def test_citations_valid_rejects_missing_or_out_of_range():
    assert smoke_rag_pipeline.citations_valid("No refs here", [{"index": 1}]) is False
    assert smoke_rag_pipeline.citations_valid("Bad ref [9]", [{"index": 1}]) is False


def test_build_url_normalizes_trailing_slash():
    assert smoke_rag_pipeline.build_url("http://127.0.0.1:8000", "/health") == "http://127.0.0.1:8000/health"
    assert smoke_rag_pipeline.build_url("http://127.0.0.1:8000/", "/health") == "http://127.0.0.1:8000/health"
