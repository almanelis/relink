from datetime import UTC, datetime, timedelta
import random
import string

from locust import HttpUser, between, task


def _random_alias(prefix: str = "loc") -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}{suffix}"


class RelinkUser(HttpUser):
    # слегка "человеческая" пауза между запросами.
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.created_codes: list[str] = []

    @task(5)
    def create_short_link(self):
        alias = _random_alias()
        payload = {
            "original_url": "https://example.com",
            "custom_alias": alias,
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).replace(
                second=0, microsecond=0
            ).isoformat(),
        }
        resp = self.client.post("/links/shorten", json=payload, name="/links/shorten")
        if resp.status_code == 201:
            self.created_codes.append(alias)

    @task(3)
    def open_existing_link(self):
        if not self.created_codes:
            self.create_short_link()
            return
        code = random.choice(self.created_codes)
        self.client.get(
            f"/links/{code}",
            name="/links/{short_code}",
            allow_redirects=False,
        )

    @task(2)
    def read_stats(self):
        if not self.created_codes:
            self.create_short_link()
            return
        code = random.choice(self.created_codes)
        self.client.get(f"/links/{code}/stats", name="/links/{short_code}/stats")
