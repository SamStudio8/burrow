import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4


def _serialise(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"cannot serialise {type(obj)}")


class Status(StrEnum):
    TODO = "todo"
    DONE = "done"
    PARTIAL = "partial"
    REFUSED = "refused"
    BLOCKED = "blocked"


@dataclass
class Comment:
    file: str
    first_line: int
    last_line: int
    body: str
    id: UUID = field(default_factory=uuid4)
    status: Status = Status.TODO
    reply: str | None = None

    def __post_init__(self):
        self.status = Status(self.status)
        if not self.body.strip():
            raise ValueError("body must not be empty or whitespace")
        if self.first_line < 0 or self.last_line < 0:
            raise ValueError("line numbers must not be negative")
        if (self.first_line == 0) != (self.last_line == 0):
            raise ValueError("first_line and last_line must both be zero or neither")
        if self.last_line < self.first_line:
            raise ValueError("last_line must not be less than first_line")
        if (self.status == Status.TODO) != (self.reply is None):
            raise ValueError("reply must be None if status is todo")


@dataclass
class Request:
    summary: str
    repo_root: Path
    comments: list[Comment] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_comment(self, file, first_line, last_line, body):
        path = self.repo_root / file
        if not path.is_file():
            raise ValueError(f"{file} does not exist in repo")
        line_count = len(path.read_text().splitlines())
        if last_line > line_count:
            raise ValueError(f"last_line {last_line} exceeds file length {line_count}")
        comment = Comment(file=file, first_line=first_line, last_line=last_line, body=body)
        self.comments.append(comment)
        return comment

    @classmethod
    def load(cls, repo_root):
        data = json.loads((repo_root / ".burrow" / "request.json").read_text())
        comments = [
            Comment(
                file=c["file"],
                first_line=c["first_line"],
                last_line=c["last_line"],
                body=c["body"],
                id=UUID(c["id"]),
            )
            for c in data["comments"]
        ]
        return cls(
            summary=data["summary"],
            repo_root=Path(data["repo_root"]),
            comments=comments,
            id=UUID(data["id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def save(self):
        session_dir = self.repo_root / ".burrow"
        session_dir.mkdir(exist_ok=True)
        data = {
            "id": self.id,
            "created_at": self.created_at,
            "summary": self.summary,
            "repo_root": self.repo_root,
            "comments": [
                {"id": c.id, "file": c.file, "first_line": c.first_line, "last_line": c.last_line, "body": c.body}
                for c in self.comments
            ],
        }
        (session_dir / "request.json").write_text(json.dumps(data, default=_serialise, indent=2))
