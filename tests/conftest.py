import os

os.environ.setdefault("RATE_LIMIT_PER_MIN", "100000")
os.environ.pop("ADMIN_TOKEN", None)
os.environ.pop("AGENT_PIN", None)
