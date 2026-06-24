from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class Account:
    platform: str
    email: str
    username: str
    password: str
    token: Optional[str] = None
    user_id: Optional[str] = None
    proxy: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_combo(self, fmt: str = "user:pass:token") -> str:
        mapping = {
            "user": self.username,
            "email": self.email,
            "pass": self.password,
            "token": self.token or "",
            "id": self.user_id or "",
        }
        parts = [mapping.get(p, p) for p in fmt.split(":")]
        return ":".join(parts)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
