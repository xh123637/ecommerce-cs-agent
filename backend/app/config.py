"""Runtime configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
DB_PATH = Path(os.getenv("TICKET_DB_PATH", str(DATA_DIR / "tickets.db")))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / ".chroma")))

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://tokenrhythm.studio/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "24"))

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "512"))
RERANK_BACKEND = os.getenv("RERANK_BACKEND", "heuristic")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
REDIS_URL = os.getenv("REDIS_URL", "")

KUAI100_CUSTOMER = os.getenv("KUAI100_CUSTOMER", "")
KUAI100_KEY = os.getenv("KUAI100_KEY", "")
KUAI100_QUERY_URL = os.getenv(
    "KUAI100_QUERY_URL",
    "https://poll.kuaidi100.com/poll/query.do",
)
