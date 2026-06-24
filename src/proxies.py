import itertools
import threading
from pathlib import Path
from typing import Optional, List


class ProxyPool:
    """Round-robin proxy rotation from a file (one proxy per line).

    Accepted line formats:
        host:port
        user:pass@host:port
        host:port:user:pass
    """

    def __init__(self, file: str, scheme: str = "http"):
        self.scheme = scheme
        self.proxies: List[str] = self._load(file) if file else []
        self._cycle = itertools.cycle(self.proxies) if self.proxies else None
        self._lock = threading.Lock()

    def _load(self, file: str) -> List[str]:
        path = Path(file)
        if not path.exists():
            return []
        out = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out.append(self._normalize(line))
        return out

    def _normalize(self, line: str) -> str:
        if "@" in line:
            return f"{self.scheme}://{line}"
        parts = line.split(":")
        if len(parts) == 4:
            host, port, user, pw = parts
            return f"{self.scheme}://{user}:{pw}@{host}:{port}"
        return f"{self.scheme}://{line}"

    def next(self) -> Optional[str]:
        if not self._cycle:
            return None
        with self._lock:
            return next(self._cycle)

    def as_httpx(self, proxy: Optional[str]):
        if not proxy:
            return None
        return {"http://": proxy, "https://": proxy}
