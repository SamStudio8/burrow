import pytest
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
