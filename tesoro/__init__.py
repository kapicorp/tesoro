from kapitan.refs.base import RefController, Revealer
from aiohttp.web import RouteTableDef

REF_CONTROLLER = RefController('/tmp', embed_refs=True)
REVEALER = Revealer(REF_CONTROLLER)

ROUTES = RouteTableDef()
