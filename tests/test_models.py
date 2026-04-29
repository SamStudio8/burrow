import pytest
from burrow.models import Request


@pytest.mark.rule("comment-body-nonempty")
def test_comment_rejects_whitespace_body(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    (tmp_path / "foo.py").write_text("hello\n")
    with pytest.raises(ValueError):
        request.add_comment(file="foo.py", first_line=1, last_line=1, body="   ")


@pytest.mark.rule("anchor-lines-positive")
def test_comment_rejects_negative_line_numbers(tmp_path):
    request = Request(summary="test", repo_root=tmp_path)
    (tmp_path / "foo.py").write_text("hello\n")
    with pytest.raises(ValueError):
        request.add_comment(file="foo.py", first_line=-1, last_line=1, body="a comment")
