from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4


@dataclass
class Comment:
    file: str
    first_line: int
    last_line: int
    body: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not self.body.strip():
            raise ValueError("body must not be empty or whitespace")
        if self.first_line < 0 or self.last_line < 0:
            raise ValueError("line numbers must not be negative")
        if (self.first_line == 0) != (self.last_line == 0):
            raise ValueError("first_line and last_line must both be zero or neither")


@dataclass
class Request:
    summary: str
    repo_root: Path
    comments: list[Comment] = field(default_factory=list)

    def add_comment(self, file, first_line, last_line, body):
        comment = Comment(file=file, first_line=first_line, last_line=last_line, body=body)
        self.comments.append(comment)
        return comment
