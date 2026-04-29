import json
import pytest
from datetime import datetime, timezone
from burrow.models import Comment, Request


@pytest.mark.rule("comment-body-nonempty")
def test_comment_rejects_whitespace_body():
    with pytest.raises(ValueError):
        Comment(file="foo.py", first_line=1, last_line=1, body="   ")


@pytest.mark.rule("anchor-lines-positive")
def test_comment_rejects_negative_line_numbers():
    with pytest.raises(ValueError):
        Comment(file="foo.py", first_line=-1, last_line=1, body="a comment")


@pytest.mark.rule("anchor-zero-paired")
def test_comment_rejects_partial_zero_anchor():
    with pytest.raises(ValueError):
        Comment(file="foo.py", first_line=0, last_line=1, body="a comment")


@pytest.mark.rule("anchor-range-valid")
def test_comment_rejects_last_line_before_first_line():
    with pytest.raises(ValueError):
        Comment(file="foo.py", first_line=5, last_line=3, body="a comment")


@pytest.mark.rule("anchor-file-exists")
def test_comment_rejects_nonexistent_file(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    with pytest.raises(ValueError):
        request.add_comment(file="nonexistent.py", first_line=1, last_line=1, body="a comment")


@pytest.mark.rule("anchor-range-valid")
def test_comment_rejects_last_line_beyond_eof(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\n")
    with pytest.raises(ValueError):
        request.add_comment(file="foo.py", first_line=1, last_line=10, body="a comment")


@pytest.mark.rule("comment-id-unique")
def test_comments_have_unique_ids(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    (tmp_path / "foo.py").write_text("line1\nline2\n")
    a = request.add_comment(file="foo.py", first_line=1, last_line=1, body="first")
    b = request.add_comment(file="foo.py", first_line=2, last_line=2, body="second")
    assert a.id != b.id


@pytest.mark.rule("request-id-unique")
def test_requests_have_unique_ids(tmp_path):
    a = Request(summary="test", repo_root=tmp_path)
    b = Request(summary="test", repo_root=tmp_path)
    assert a.id != b.id


@pytest.mark.rule("request-created-at")
def test_request_records_creation_timestamp(tmp_path):
    before = datetime.now(timezone.utc)
    request = Request(summary="test", repo_root=tmp_path)
    after = datetime.now(timezone.utc)
    assert before <= request.created_at <= after


@pytest.mark.rule("request-repo-root")
def test_request_records_repo_root(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    assert request.repo_root == tmp_path


@pytest.mark.rule("load-session")
def test_load_reconstructs_request(tmp_path, example_request):
    (tmp_path / ".burrow").mkdir()
    (tmp_path / ".burrow" / "request.json").write_text(json.dumps(example_request))
    request = Request.load(tmp_path)
    assert str(request.id) == example_request["id"]
    assert request.summary == example_request["summary"]
    assert len(request.comments) == len(example_request["comments"])
    assert str(request.comments[0].id) == example_request["comments"][0]["id"]
    assert request.comments[0].body == example_request["comments"][0]["body"]


@pytest.mark.rule("write-session")
def test_save_writes_session_file(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    request.save()
    assert (tmp_path / ".burrow" / "request.json").exists()
