from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4


@dataclass
class Comment:
    id: UUID
    file: str
    first_line: int
    last_line: int
    body: str


@dataclass
class Request:
    summary: str
    repo_root: Path
    comments: list[Comment] = field(default_factory=list)

    def add_comment(self, file, first_line, last_line, body):
        if not body.strip():
            raise ValueError("body must not be empty or whitespace")
        if first_line < 0 or last_line < 0:
            raise ValueError("line numbers must not be negative")
        comment = Comment(
            id=uuid4(),
            file=file,
            first_line=first_line,
            last_line=last_line,
            body=body,
        )
        self.comments.append(comment)
        return comment
