import json

from aiohttp import web
from aiohttp_jinja2 import template


class CompassService:

    def __init__(self, services):
        self.services = services

    @template('compass.html')
    async def splash(self, request):
        await self.services.get('auth_svc').check_permissions(request)
        return dict(test='test')

    @staticmethod
    def get_layer_boilerplate(name, description):
        return {
            'version': '2.2',
            'name': name,
            'description': description,
            'domain': 'mitre-enterprise',
            'techniques': [],
            'legendItems': [],
            'showTacticRowBackground': True,
            'tacticRowBackground': '#205b8f',
            'selectTechniquesAcrossTactics': True,
            'gradient': {
                'colors': [
                    '#ffffff',
                    '#66ff66'
                ],
                'minValue': 0,
                'maxValue': 1
            }
        }

    async def generate_layer(self, request):
        abilities = await self.services.get('data_svc').locate('abilities')

        layer = self.get_layer_boilerplate(name='Library', description='full set of techniques available')
        for ability in abilities:
            technique = {
                'techniqueID': ability.technique_id,
                'score': 1,
                'color': '',
                'comment': '',
                'enabled': True
            }
            layer['techniques'].append(technique)

        return web.json_response(layer)
