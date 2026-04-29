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
