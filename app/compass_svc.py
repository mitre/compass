import json
import uuid

from aiohttp import web
from aiohttp_jinja2 import template


from pprint import pprint # TODO: Remove

def check_authorization(func):
    async def process(func, *args, **params):
        return await func(*args, **params)

    async def helper(*args, **params):
        await args[0].auth_svc.check_permissions(args[1])
        result = await process(func, *args, **params)
        return result
    return helper


class CompassService:

    def __init__(self, services):
        self.services = services
        self.auth_svc = self.services.get('auth_svc')
        self.data_svc = self.services.get('data_svc')
        self.rest_svc = self.services.get('rest_svc')

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

    @check_authorization
    async def generate_layer(self, request):
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

    @check_authorization
    async def create_adversary_from_layer(self, request):
        """
        Takes a layer file and generates an adversary that matches the selected tactics and techniques.
        Adversary will be divided into phases by tactic
        :param request:
        :return:
        """
        try:
            chunks = []
            reader = await request.multipart()
            while True:
                field = await reader.next()
                if not field:
                    break
                filename = field.filename
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    chunks.append(chunk)
            body = b''.join(chunks)
            request_body = json.loads(body)
        except:
            return web.HTTPBadRequest()

        from collections import defaultdict
        adversary_data = dict(i=str(uuid.uuid4()),
                              name=request_body.get('name'),
                              description=request_body.get('description'),
                              phases=defaultdict(list))
        adversary_techniques = []

        techniques = request_body.get('techniques')

        for technique in techniques:
            if technique.get('score') > 0:
                technique_id = technique.get('techniqueID')
                adversary_techniques.append(technique_id)

        for technique_id in set(adversary_techniques):
            abilities = await self.data_svc.locate('abilities', match=dict(technique_id=technique_id))
            print(abilities)
            for ab in abilities:
                if ab.display not in adversary_data['phases']['1']:
                    adversary_data['phases']['1'].append(ab.display)

        adversary_data['phases'] = dict(adversary_data['phases'])
        pprint(adversary_data)
        adversary = await self.rest_svc.persist_adversary(adversary_data)
        print(adversary)

        if adversary:
            return web.json_response('hello')
        raise web.HTTPBadRequest()
