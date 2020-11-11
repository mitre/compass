import json
import uuid

from aiohttp import web
from aiohttp_jinja2 import template
from collections import defaultdict
from enum import Enum

from app.service.auth_svc import for_all_public_methods, check_authorization


class _HeatmapColors(Enum):
    SUCCESS = '#44AA99'  # Green
    PARTIAL_SUCCESS = '#FFB000'  # Orange
    FAILURE = '#CC3311'  # Red
    NOT_RUN = '#555555'  # Dark grey


@for_all_public_methods(check_authorization)
class CompassService:
    def __init__(self, services):
        self.services = services
        self.auth_svc = self.services.get('auth_svc')
        self.data_svc = self.services.get('data_svc')
        self.rest_svc = self.services.get('rest_svc')

    @template('compass.html')
    async def splash(self, request):
        adversaries = [a.display for a in await self.data_svc.locate('adversaries')]
        operations = [o.display for o in await self.data_svc.locate('operations')]
        return dict(
            adversaries=sorted(adversaries, key=lambda a: a['name']),
            operations=operations,
        )

    @staticmethod
    def _get_adversary_layer_boilerplate(name, description):
        return dict(
            version='3.0',
            name=name,
            description=description,
            domain='mitre-enterprise',
            techniques=[],
            legendItems=[],
            showTacticRowBackground=True,
            tacticRowBackground='#205b8f',
            selectTechniquesAcrossTactics=True,
            selectSubtechniquesWithParent=True,
            gradient=dict(
                colors=[
                    '#ffffff',
                    '#66ff66'
                ],
                minValue=0,
                maxValue=1
            )
        )

    @staticmethod
    def _get_operation_layer_boilerplate(name, description):
        return dict(
            name=name,
            versions=dict(
                attack="8",
                navigator="4.0",
                layer="4.0",
            ),
            domain="enterprise-attack",
            description=description,
            filters={
               "platforms": [
                   "Linux",
                   "macOS",
                   "Windows",
                   "Office 365",
                   "Azure AD",
                   "AWS",
                   "GCP",
                   "Azure",
                   "SaaS",
                   "Network"
               ]
            },
            sorting=0,
            hideDisabled=False,
            techniques=[],
            gradient=dict(
                colors=[
                    _HeatmapColors.NOT_RUN.value,
                    _HeatmapColors.FAILURE.value,
                    _HeatmapColors.PARTIAL_SUCCESS.value,
                    _HeatmapColors.SUCCESS.value,
                ],
                minValue=0,
                maxValue=3
            ),
            legendItems=[
                {
                    "label": "All ran procedures succeeded",
                    "color": _HeatmapColors.SUCCESS.value
                },
                {
                    "label": "None of the ran procedures succeeded",
                    "color": _HeatmapColors.FAILURE.value
                },
                {
                    "label": "Some of the ran procedures succeeded",
                    "color": _HeatmapColors.PARTIAL_SUCCESS.value
                },
                {
                    "label": "All procedures skipped",
                    "color": _HeatmapColors.NOT_RUN.value
                }
            ],
            metadata=[],
            showTacticRowBackground=False,
            tacticRowBackground="#dddddd",
            selectTechniquesAcrossTactics=True,
            selectSubtechniquesWithParent=False,
        )

    async def _get_all_abilities(self):
        return 'All-Abilities', 'full set of techniques available', [ability.display for ability in await self.services.get('data_svc').locate('abilities')]

    async def _get_adversary_abilities(self, request_body):
        adversary = (await self.rest_svc.display_objects(object_name='adversaries', data=dict(adversary_id=request_body.get('adversary_id'))))[0]
        return adversary['name'], adversary['description'], adversary['atomic_ordering']

    async def generate_adversary_layer(self, request):
        request_body = json.loads(await request.read())

        ability_functions = dict(
            adversary=lambda d: self._get_adversary_abilities(d),
            all=lambda d: self._get_all_abilities()
        )
        display_name, description, abilities = await ability_functions[request_body['index']](request_body)

        layer = self._get_adversary_layer_boilerplate(name=display_name, description=description)
        for ability in abilities:
            technique = dict(
                techniqueID=ability['technique_id'],
                tactic=ability['tactic'],
                score=1,
                color='',
                comment='',
                enabled=True,
                showSubtechniques=False
            )
            layer['techniques'].append(technique)

        return web.json_response(layer)

    async def generate_operation_layer(self, request):
        request_body = json.loads(await request.read())
        operation = (await self.data_svc.locate('operations', match=dict(id=int(request_body.get('id')))))[0]
        display_name = operation.name
        description = 'Operation {name} was conducted using adversary profile {adv_profile}'.format(
            name=operation.name,
            adv_profile=operation.adversary.name
        )
        layer = self._get_operation_layer_boilerplate(name=display_name, description=description)
        success_counter = defaultdict(int)
        technique_counter = defaultdict(int)
        no_success_counter = defaultdict(int)
        skipped_counter = defaultdict(int)
        technique_tactic_map = dict()
        technique_dicts = dict()  # Map technique ID to corresponding dict object.
        to_process = []  # list of (ability, status) tuples

        # Get links from operation chain
        for link in operation.chain:
            to_process.append((link.ability, link.status))

        # Get automatically skipped links
        skipped_abilities = await operation.get_skipped_abilities_by_agent(self.data_svc)
        for skipped_by_agent in skipped_abilities:
            for _, skipped in skipped_by_agent.items():
                for skipped_info in skipped:
                    status = skipped_info.get('reason_id')
                    ability_id = skipped_info.get('ability_id')
                    if status is not None:
                        ability = (await self.data_svc.locate('abilities', match=dict(ability_id=ability_id)))[0]
                        if ability:
                            to_process.append((ability, status))

        # Count success, failures, no-runs for links.
        for (ability, status) in to_process:
            technique_id = ability.technique_id
            technique_counter[technique_id] += 1
            technique_tactic_map[technique_id] = ability.tactic
            if status == 0:
                success_counter[technique_id] += 1
            elif status in (1, 124, -3, -4):
                # Did not succeed if status was failure, timeout, untrusted, or collected (in the
                # case of collected/untrusted/timeout, the command may have run successfully, but
                # we don't know for sure due to lack of timely response from the agent).
                no_success_counter[technique_id] += 1
            else:
                # Ability either queued, manually discarded, or visibility threshold was surpassed.
                skipped_counter[technique_id] += 1

        for technique_id, num_procedures in technique_counter.items():
            # case 1: all ran procedures succeeded
            # case 2: all ran procedures failed
            # case 3: none of the procedures ran
            # case 4: some procedures ran, but not all of them succeeded

            # Default case: none of the procedures for this technique were run.
            score = 0
            if skipped_counter[technique_id] < num_procedures:
                if success_counter[technique_id] == 0:
                    # None of the procedures that ran for this technique succeeded
                    score = 1
                elif no_success_counter[technique_id] == 0:
                    # All of the procedures that ran for this technique succeeded.
                    score = 3
                else:
                    # Some of the procedures that ran failed
                    score = 2
            technique_dicts[technique_id] = dict(
                techniqueID=technique_id,
                tactic=technique_tactic_map[technique_id],
                score=score,
                color='',
                comment='',
                enabled=True,
                metadata=[],
                showSubtechniques=False,
            )

        for technique_id, num_procedures in technique_counter.items():
            # Check if we need to expand the parent technique.
            if '.' in technique_id:
                parent_id = technique_id.split('.')[0]

                # Check if the parent technique was already processed
                if parent_id in technique_dicts:
                    technique_dicts.get(parent_id)['showSubtechniques'] = True
                else:
                    technique_dicts[parent_id] = dict(
                        techniqueID=parent_id,
                        tactic=technique_tactic_map[technique_id],
                        color='',
                        comment='',
                        enabled=True,
                        metadata=[],
                        showSubtechniques=True,
                    )

        for _, technique_dict in technique_dicts.items():
            layer['techniques'].append(technique_dict)
        return web.json_response(layer)

    @staticmethod
    def _extract_techniques(request_body):
        techniques = request_body.get('techniques')
        adversary_techniques = set()
        for technique in techniques:
            if technique.get('score', 0) > 0:
                adversary_techniques.add((technique.get('techniqueID'), technique.get('tactic')))
        return adversary_techniques

    async def _build_adversary(self, adversary_techniques):
        atomic_order = []
        unmatched_techniques = []
        for technique_id, tactic in adversary_techniques:
            if tactic:
                abilities = await self.data_svc.locate('abilities', match=dict(technique_id=technique_id,
                                                                               tactic=tactic))
            else:
                abilities = await self.data_svc.locate('abilities', match=dict(technique_id=technique_id))

            if not abilities:
                unmatched_techniques.append(dict(technique_id=technique_id, tactic=tactic))
            for ab in abilities:
                ability = dict(id=ab.ability_id)
                if ability not in atomic_order:
                    atomic_order.append(ability)
        return atomic_order, unmatched_techniques

    @staticmethod
    async def _read_layer(request):
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

    async def create_adversary_from_layer(self, request):
        """
        Takes a layer file and generates an adversary that matches the selected tactics and techniques.
        Adversary will be constructed into a single atomic list of techniques
        :param request:
        :return:
        """
        try:
            request_body = await self._read_layer(request)
        except json.decoder.JSONDecodeError:
            return web.HTTPBadRequest()
        try:
            adversary_data = dict(id=str(uuid.uuid4()),
                                  name=request_body.get('name'),
                                  description=request_body.get('description', '') + ' (created by compass)')
            adversary_techniques = self._extract_techniques(request_body)
            adversary_data['atomic_ordering'], unmatched_techniques = await self._build_adversary(adversary_techniques)
            adversary = await self.rest_svc.persist_adversary(dict(access=[self.rest_svc.Access.RED]), adversary_data)
            if adversary:
                return web.json_response(dict(unmatched_techniques=sorted(unmatched_techniques, key=lambda x: x['tactic']),
                                              name=request_body.get('name'),
                                              description=request_body.get('description')))
        except Exception as e:
            print(e)
            raise web.HTTPBadRequest()
