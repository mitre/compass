from app.utility.base_world import BaseWorld
from plugins.compass.app.compass_svc import CompassService

name = 'Compass'
description = 'Use the compass to Navigate CALDERA'
address = '/plugin/compass/gui'
access = BaseWorld.Access.RED


async def enable(services):
    app = services.get('app_svc').application
    compass_svc = CompassService(services)
    app.router.add_static('/compass', 'plugins/compass/static/', append_version=True)
    app.router.add_route('POST', '/plugin/compass/layer', compass_svc.generate_layer)
    app.router.add_route('POST', '/plugin/compass/adversary', compass_svc.create_adversary_from_layer)
    app.router.add_route('GET', '/plugin/compass/gui', compass_svc.splash)
