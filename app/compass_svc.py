import json
import uuid

from aiohttp import web
from aiohttp_jinja2 import template

from app.service.auth_svc import check_authorization


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

    @staticmethod
    def extract_techniques(request_body):
        techniques = request_body.get('techniques')
        adversary_techniques = set()
        for technique in techniques:
            if technique.get('score') > 0:
                technique_id = technique.get('techniqueID')
                adversary_techniques.add(technique_id)
        return adversary_techniques

    async def build_phases(self, adversary_techniques):
        phases = []
        for technique_id in adversary_techniques:
            abilities = await self.data_svc.locate('abilities', match=dict(technique_id=technique_id))
            for ab in abilities:
                ability = dict(id=ab.ability_id, phase='1')
                if ability not in phases:
                    phases.append(ability)
        return phases

    @staticmethod
    async def read_layer(request):
        body = bytes()
        reader = await request.multipart()
        while True:
            field = await reader.next()
            if not field:
                break
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                body += chunk
        return json.loads(body)

    @check_authorization
    async def create_adversary_from_layer(self, request):
        """
        Takes a layer file and generates an adversary that matches the selected tactics and techniques.
        Adversary will be divided into phases by tactic
        :param request:
        :return:
        """
        try:
            request_body = await self.read_layer(request)
        except json.decoder.JSONDecodeError:
            return web.HTTPBadRequest()

        adversary_data = dict(i=str(uuid.uuid4()),
                              name=request_body.get('name'),
                              description=request_body.get('description'))

        adversary_techniques = self.extract_techniques(request_body)
        adversary_data['phases'] = await self.build_phases(adversary_techniques)
        adversary = await self.rest_svc.persist_adversary(adversary_data)

        if adversary:
            return web.json_response('adversary created')
        raise web.HTTPBadRequest()
