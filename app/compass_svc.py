import json

from aiohttp import web
from aiohttp_jinja2 import template


class CompassService:

    def __init__(self, services):
        self.services = services
        self.auth_svc = self.services.get('auth_svc')
        self.data_svc = self.services.get('data_svc')

    @template('compass.html')
    async def splash(self, request):
        await self.auth_svc.check_permissions(request)
        adversaries = [a.display for a in await self.data_svc.locate('adversaries')]
        return dict(adversaries=sorted(adversaries, key=lambda a: a['name']))

    @staticmethod
    def _get_layer_boilerplate(name, description):
        return dict(
            version='2.2',
            name=name,
            description=description,
            domain='mitre-enterprise',
            techniques=[],
            legendItems=[],
            showTacticRowBackground=True,
            tacticRowBackground='#205b8f',
            selectTechniquesAcrossTactics=True,
            gradient=dict(
                colors=[
                    '#ffffff',
                    '#66ff66'
                ],
                minValue=0,
                maxValue=1
            )
        )

    async def _get_all_abilities(self):
        return 'All-Abilities', 'full set of techniques available', await self.services.get('data_svc').locate('abilities')

    async def _get_adversary_abilities(self, request_body):
        abilities = []
        adversary = (await self.data_svc.locate('adversaries', match=dict(adversary_id=request_body.get('adversary_id'))))[0]
        for _, v in adversary.phases.items():
            for a in v:
                abilities.append(a)
        return adversary.name, adversary.description, abilities

    async def generate_layer(self, request):
        await self.services.get('auth_svc').check_permissions(request)
        request_body = json.loads(await request.read())

        ability_functions = dict(
            adversary=lambda d: self._get_adversary_abilities(d),
            all=lambda d: self._get_all_abilities()
        )
        display_name, description, abilities = await ability_functions[request_body['index']](request_body)

        layer = self._get_layer_boilerplate(name=display_name, description=description)
        for ability in abilities:
            technique = dict(
                techniqueID=ability.technique_id,
                score=1,
                color='',
                comment='',
                enabled=True
            )
            layer['techniques'].append(technique)

        return web.json_response(layer)
