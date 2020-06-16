from prometheus_client import Counter, start_http_server as prom_http_server

TESORO_COUNTER = Counter("tesoro_requests", "Tesoro requests")
TESORO_FAILED_COUNTER = Counter("tesoro_requests_failed", "Tesoro failed requests")
REVEAL_COUNTER = Counter("kapitan_reveal_requests", "Kapitan reveal requests")
REVEAL_FAILED_COUNTER = Counter("kapitan_reveal_requests_failed", "Kapitan reveal failed requests ")
