from kapitan.refs.base import RefController, Revealer

REF_CONTROLLER = RefController("/tmp", embed_refs=True, cache_session=False)
REVEALER = Revealer(REF_CONTROLLER)
