from kapitan.refs.base import RefController, Revealer
from aiohttp.web import RouteTableDef
from prometheus_client import Counter

REF_CONTROLLER = RefController('/tmp', embed_refs=True)
REVEALER = Revealer(REF_CONTROLLER)

ROUTES = RouteTableDef()

TESORO_COUNTER = Counter('tesoro_requests', 'Tesoro requests')
TESORO_FAILED_COUNTER = Counter('tesoro_requests_failed',
                                'Tesoro failed requests')
REVEAL_COUNTER = Counter('kapitan_reveal_requests',
                         'Kapitan reveal requests')
REVEAL_FAILED_COUNTER = Counter('kapitan_reveal_requests_failed',
                                'Kapitan reveal failed requests ')
