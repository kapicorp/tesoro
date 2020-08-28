from asyncio import get_running_loop
from tesoro import REVEALER
from sys import exc_info
import logging

logger = logging.getLogger(__name__)


def kapicorp_labels(req_uid, req_obj):
    "returns kapicorp labels dict for req_obj"
    labels = {}
    try:
        for label_key, label_value in req_obj["metadata"]["labels"].items():
            if label_key.startswith("tesoro.kapicorp.com"):
                labels[label_key] = label_value
    except KeyError:
        logger.error("request_id=%s Tesoro label not found", req_uid)
        return labels

    return labels


async def run_blocking(func):
    "run blocking funcion in async executor"
    loop = get_running_loop()
    return await loop.run_in_executor(None, func)


def kapitan_reveal_json(req_uid, json_doc, retries=3):
    "return revealed object, total revealed tags (TODO)"
    for retry in range(retries):
        try:
            return REVEALER.reveal_obj(json_doc)
        except Exception as e:
            exc_type, exc_value, _ = exc_info()
            if retry + 1 <= retries:
                logger.error("message=\"Kapitan reveal failed, retrying\", request_uid=%s, "
                             "retry=\"%d of %d\", exception_type=%s, error=\"%s\"",
                             req_uid, retry + 1, retries, exc_type, exc_value)
                continue
            raise


def setup_logging(level=logging.INFO, kapitan_debug=False):
    "setup logging, set kapitan_debug to True for kapitan debug logging (dangerous)"
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith("kapitan."):
            logger.disabled = not kapitan_debug

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", level=level, datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.getLogger("tesoro").setLevel(level)


class KapitanRevealFail(Exception):
    pass
