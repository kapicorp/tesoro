#!/usr/bin/env python3

import asyncio
from aiohttp import web
import jsonpatch
from kapitan.refs.base import RefController, Revealer
import logging

logging.basicConfig(level=logging.INFO)

ROUTES = web.RouteTableDef()
ROUTES_METRICS = web.RouteTableDef()

REF_CONTROLLER = RefController('/tmp', embed_refs=True)
REVEALER = Revealer(REF_CONTROLLER)

@ROUTES_METRICS.get('/metrics')
async def metrics_handler(request):
    return web.Response(text="Metrics go here")

@ROUTES.post('/mutate/{resource}')
async def mutate_resource_handler(request):
    resource = request.match_info.get('resource', None)
    if resource is None:
        return web.Response(status=500, reason='Resource not set')

    try:
        req_json = await request.json()
        # TODO get annotations and check 'kapicorp.com/kapitan-controller'
        req_updated = req_json.copy()

        # TODO remove when reveal works
        temp_ref = ("?{base64:eyJkYXRhIjogImNtVm1JREVnWkdGMFlRPT0iLCAiZW5jb2"
                "RpbmciOiAib3JpZ2luYWwiLCAidHlwZSI6ICJiYXNlNjQifQ==:embedded}"
        )
        req_updated["temp_ref"] = temp_ref # TODO remove when reveal works

        reveal_req_func = lambda: kapitan_reveal_json(req_updated)
        req_revealed = await run_blocking(reveal_req_func)
        patch = jsonpatch.make_patch(req_json, req_revealed)
        return web.json_response(patch.patch)
    except json.decode.JSONDecoderError:
        return web.Response(status=500, reason='Request not JSON')

    return web.Response(status=500, reason='Unknown error')

async def run_blocking(func):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)

def kapitan_reveal_json(json_doc):
    "return revealed object, total revealed tags (TODO)"
    return REVEALER.reveal_obj(json_doc)

async def start_site(app, app_runners, address="localhost", port=8080):
    runner = web.AppRunner(app)
    app_runners.append(runner)
    await runner.setup()
    site = web.TCPSite(runner, address, port)
    await site.start()


if __name__ == '__main__':
    app_runners = []
    app = web.Application()
    app.add_routes(ROUTES)
    app_metrics = web.Application()
    app_metrics.add_routes(ROUTES_METRICS)

    loop = asyncio.get_event_loop()
    loop.create_task(start_site(app, app_runners))
    loop.create_task(start_site(app_metrics, app_runners, port=9095))

    try:
        loop.run_forever()
    except:
        pass
    finally:
        for runner in app_runners:
            loop.run_until_complete(runner.cleanup())
