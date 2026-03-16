"""Exhaustive tests for app/compass_svc.py — CompassService."""
import json
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

# conftest installs stubs before this import resolves
from app.compass_svc import CompassService
from tests.conftest import FakeAbility, FakeAdversary


# ===================================================================
# Helpers
# ===================================================================

def _make_request(body: dict | bytes | None = None, content_type="application/json"):
    """Build a minimal mock aiohttp request carrying *body*."""
    req = AsyncMock()
    if isinstance(body, bytes):
        raw = body
    elif body is not None:
        raw = json.dumps(body).encode()
    else:
        raw = b""
    req.read = AsyncMock(return_value=raw)
    req.content_type = content_type
    return req


def _make_multipart_request(body_bytes: bytes):
    """Build a mock request whose multipart reader yields *body_bytes* in one field."""
    field = AsyncMock()
    chunks = [body_bytes, b""]  # second call signals EOF
    field.read_chunk = AsyncMock(side_effect=chunks)

    reader = AsyncMock()
    fields = [field, None]  # second call signals no more fields
    reader.next = AsyncMock(side_effect=fields)

    req = AsyncMock()
    req.multipart = AsyncMock(return_value=reader)
    return req


def _make_multipart_request_multi_chunk(chunks_list: list[bytes]):
    """Multipart reader that yields multiple chunks then EOF."""
    field = AsyncMock()
    field.read_chunk = AsyncMock(side_effect=chunks_list + [b""])

    reader = AsyncMock()
    reader.next = AsyncMock(side_effect=[field, None])

    req = AsyncMock()
    req.multipart = AsyncMock(return_value=reader)
    return req


# ===================================================================
# __init__
# ===================================================================

class TestCompassServiceInit:
    def test_stores_services(self, mock_services, compass_svc):
        assert compass_svc.services is mock_services

    def test_auth_svc_resolved(self, mock_services, compass_svc):
        assert compass_svc.auth_svc is mock_services["auth_svc"]

    def test_data_svc_resolved(self, mock_services, compass_svc):
        assert compass_svc.data_svc is mock_services["data_svc"]

    def test_rest_svc_resolved(self, mock_services, compass_svc):
        assert compass_svc.rest_svc is mock_services["rest_svc"]

    def test_missing_service_key_returns_none(self):
        svc = CompassService({})
        assert svc.auth_svc is None
        assert svc.data_svc is None
        assert svc.rest_svc is None


# ===================================================================
# _get_layer_boilerplate
# ===================================================================

class TestGetLayerBoilerplate:
    def test_returns_dict(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert isinstance(layer, dict)

    def test_name_and_description(self):
        layer = CompassService._get_layer_boilerplate("MyName", "MyDesc")
        assert layer["name"] == "MyName"
        assert layer["description"] == "MyDesc"

    def test_version(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert layer["version"] == "3.0"

    def test_domain(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert layer["domain"] == "mitre-enterprise"

    def test_techniques_empty_list(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert layer["techniques"] == []

    def test_gradient_present(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert "gradient" in layer
        assert layer["gradient"]["minValue"] == 0
        assert layer["gradient"]["maxValue"] == 1
        assert len(layer["gradient"]["colors"]) == 2

    def test_tactic_row_background(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert layer["showTacticRowBackground"] is True
        assert layer["tacticRowBackground"] == "#205b8f"

    def test_select_flags(self):
        layer = CompassService._get_layer_boilerplate("n", "d")
        assert layer["selectTechniquesAcrossTactics"] is True
        assert layer["selectSubtechniquesWithParent"] is True

    def test_empty_strings(self):
        layer = CompassService._get_layer_boilerplate("", "")
        assert layer["name"] == ""
        assert layer["description"] == ""


# ===================================================================
# splash
# ===================================================================

class TestSplash:
    @pytest.mark.asyncio
    async def test_splash_returns_sorted_adversaries(self, compass_svc, mock_services):
        adv_b = FakeAdversary(name="Bravo")
        adv_a = FakeAdversary(name="Alpha")
        mock_services["data_svc"].locate = AsyncMock(return_value=[adv_b, adv_a])

        result = await compass_svc.splash(MagicMock())
        names = [a["name"] for a in result["adversaries"]]
        assert names == ["Alpha", "Bravo"]

    @pytest.mark.asyncio
    async def test_splash_empty(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[])
        result = await compass_svc.splash(MagicMock())
        assert result["adversaries"] == []

    @pytest.mark.asyncio
    async def test_splash_single_adversary(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[FakeAdversary(name="Solo")])
        result = await compass_svc.splash(MagicMock())
        assert len(result["adversaries"]) == 1


# ===================================================================
# _get_all_abilities
# ===================================================================

class TestGetAllAbilities:
    @pytest.mark.asyncio
    async def test_returns_tuple(self, compass_svc, mock_services, sample_abilities):
        mock_services["data_svc"].locate = AsyncMock(return_value=sample_abilities)
        name, desc, abilities = await compass_svc._get_all_abilities()
        assert name == "All-Abilities"
        assert "full set" in desc
        assert len(abilities) == len(sample_abilities)

    @pytest.mark.asyncio
    async def test_empty_abilities(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[])
        name, desc, abilities = await compass_svc._get_all_abilities()
        assert abilities == []


# ===================================================================
# _get_adversary_abilities
# ===================================================================

class TestGetAdversaryAbilities:
    @pytest.mark.asyncio
    async def test_returns_adversary_fields(self, compass_svc, mock_services):
        mock_services["rest_svc"].display_objects = AsyncMock(return_value=[
            {"name": "Adv1", "description": "desc1", "atomic_ordering": [{"technique_id": "T1"}]}
        ])
        name, desc, abilities = await compass_svc._get_adversary_abilities({"adversary_id": "adv-1"})
        assert name == "Adv1"
        assert desc == "desc1"
        assert len(abilities) == 1

    @pytest.mark.asyncio
    async def test_missing_adversary_id_key(self, compass_svc, mock_services):
        """adversary_id defaults to None via .get(); rest_svc still queried."""
        mock_services["rest_svc"].display_objects = AsyncMock(return_value=[
            {"name": "X", "description": "Y", "atomic_ordering": []}
        ])
        name, desc, abilities = await compass_svc._get_adversary_abilities({})
        assert name == "X"


# ===================================================================
# generate_layer
# ===================================================================

class TestGenerateLayer:
    @pytest.mark.asyncio
    async def test_generate_layer_all(self, compass_svc, mock_services, sample_abilities):
        mock_services["data_svc"].locate = AsyncMock(return_value=sample_abilities)
        req = _make_request({"index": "all"})

        resp = await compass_svc.generate_layer(req)
        body = json.loads(resp.body)

        assert body["name"] == "All-Abilities"
        assert len(body["techniques"]) == 3

    @pytest.mark.asyncio
    async def test_generate_layer_adversary(self, compass_svc, mock_services, sample_abilities):
        mock_services["rest_svc"].display_objects = AsyncMock(return_value=[
            {"name": "Adv", "description": "d", "atomic_ordering": [sample_abilities[0].display]}
        ])
        req = _make_request({"index": "adversary", "adversary_id": "adv-1"})

        resp = await compass_svc.generate_layer(req)
        body = json.loads(resp.body)

        assert body["name"] == "Adv"
        assert len(body["techniques"]) == 1
        assert body["techniques"][0]["techniqueID"] == "T1059"

    @pytest.mark.asyncio
    async def test_generate_layer_technique_fields(self, compass_svc, mock_services, sample_abilities):
        mock_services["data_svc"].locate = AsyncMock(return_value=[sample_abilities[0]])
        req = _make_request({"index": "all"})

        resp = await compass_svc.generate_layer(req)
        tech = json.loads(resp.body)["techniques"][0]

        assert tech["score"] == 1
        assert tech["color"] == ""
        assert tech["comment"] == ""
        assert tech["enabled"] is True
        assert tech["showSubtechniques"] is False

    @pytest.mark.asyncio
    async def test_generate_layer_invalid_index_raises(self, compass_svc, mock_services):
        req = _make_request({"index": "bogus"})
        with pytest.raises(KeyError):
            await compass_svc.generate_layer(req)

    @pytest.mark.asyncio
    async def test_generate_layer_missing_index_key(self, compass_svc, mock_services):
        req = _make_request({})
        with pytest.raises(KeyError):
            await compass_svc.generate_layer(req)

    @pytest.mark.asyncio
    async def test_generate_layer_malformed_json(self, compass_svc, mock_services):
        req = _make_request(b"not json at all")
        with pytest.raises(json.JSONDecodeError):
            await compass_svc.generate_layer(req)

    @pytest.mark.asyncio
    async def test_generate_layer_empty_abilities(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[])
        req = _make_request({"index": "all"})
        resp = await compass_svc.generate_layer(req)
        body = json.loads(resp.body)
        assert body["techniques"] == []

    @pytest.mark.asyncio
    async def test_generate_layer_returns_json_response(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[])
        req = _make_request({"index": "all"})
        resp = await compass_svc.generate_layer(req)
        assert isinstance(resp, web.Response)


# ===================================================================
# _extract_techniques
# ===================================================================

class TestExtractTechniques:
    def test_basic_extraction(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 1},
                {"techniqueID": "T1071", "tactic": "c2", "score": 1},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert ("T1059", "execution") in result
        assert ("T1071", "c2") in result

    def test_zero_score_excluded(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 0},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 0

    def test_negative_score_excluded(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": -5},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 0

    def test_missing_score_excluded(self):
        """score defaults to 0 via .get('score', 0)."""
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution"},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 0

    def test_empty_techniques_list(self):
        result = CompassService._extract_techniques({"techniques": []})
        assert result == set()

    def test_missing_techniques_key_raises(self):
        with pytest.raises(TypeError):
            CompassService._extract_techniques({})

    def test_duplicate_techniques_deduplicated(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 1},
                {"techniqueID": "T1059", "tactic": "execution", "score": 1},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 1

    def test_same_technique_different_tactic(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 1},
                {"techniqueID": "T1059", "tactic": "defense-evasion", "score": 1},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 2

    def test_missing_tactic_key(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "score": 1},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert ("T1059", None) in result

    def test_missing_technique_id_key(self):
        body = {
            "techniques": [
                {"tactic": "execution", "score": 1},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert (None, "execution") in result

    def test_high_score(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 999},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 1

    def test_fractional_score_positive(self):
        body = {
            "techniques": [
                {"techniqueID": "T1059", "tactic": "execution", "score": 0.5},
            ]
        }
        result = CompassService._extract_techniques(body)
        assert len(result) == 1


# ===================================================================
# _build_adversary
# ===================================================================

class TestBuildAdversary:
    @pytest.mark.asyncio
    async def test_matched_abilities(self, compass_svc, mock_services):
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])

        order, unmatched = await compass_svc._build_adversary({("T1059", "execution")})
        assert len(order) == 1
        assert order[0] == {"id": "ab-1"}
        assert unmatched == []

    @pytest.mark.asyncio
    async def test_unmatched_technique(self, compass_svc, mock_services):
        mock_services["data_svc"].locate = AsyncMock(return_value=[])

        order, unmatched = await compass_svc._build_adversary({("T9999", "none")})
        assert order == []
        assert len(unmatched) == 1
        assert unmatched[0]["technique_id"] == "T9999"

    @pytest.mark.asyncio
    async def test_no_tactic_uses_technique_only(self, compass_svc, mock_services):
        ab = FakeAbility("ab-2", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])

        order, unmatched = await compass_svc._build_adversary({("T1059", None)})
        assert len(order) == 1
        # Verify locate was called without tactic match
        call_args = mock_services["data_svc"].locate.call_args
        assert "tactic" not in call_args[1].get("match", {})

    @pytest.mark.asyncio
    async def test_empty_tactic_string_is_falsy(self, compass_svc, mock_services):
        """Empty string tactic is falsy, so locate should omit tactic."""
        ab = FakeAbility("ab-3", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])

        order, unmatched = await compass_svc._build_adversary({("T1059", "")})
        assert len(order) == 1

    @pytest.mark.asyncio
    async def test_duplicate_abilities_deduplicated(self, compass_svc, mock_services):
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab, ab])

        order, _ = await compass_svc._build_adversary({("T1059", "execution")})
        assert len(order) == 1

    @pytest.mark.asyncio
    async def test_empty_input(self, compass_svc, mock_services):
        order, unmatched = await compass_svc._build_adversary(set())
        assert order == []
        assert unmatched == []

    @pytest.mark.asyncio
    async def test_multiple_abilities_per_technique(self, compass_svc, mock_services):
        ab1 = FakeAbility("ab-1", "T1059", "execution")
        ab2 = FakeAbility("ab-2", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab1, ab2])

        order, _ = await compass_svc._build_adversary({("T1059", "execution")})
        assert len(order) == 2


# ===================================================================
# _read_layer
# ===================================================================

class TestReadLayer:
    @pytest.mark.asyncio
    async def test_valid_json(self):
        payload = json.dumps({"name": "test"}).encode()
        req = _make_multipart_request(payload)
        result = await CompassService._read_layer(req)
        assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        req = _make_multipart_request(b"not-json")
        with pytest.raises(json.JSONDecodeError):
            await CompassService._read_layer(req)

    @pytest.mark.asyncio
    async def test_empty_body_raises(self):
        req = _make_multipart_request(b"")
        with pytest.raises(json.JSONDecodeError):
            await CompassService._read_layer(req)

    @pytest.mark.asyncio
    async def test_multi_chunk_reassembly(self):
        full = json.dumps({"key": "value"}).encode()
        mid = len(full) // 2
        req = _make_multipart_request_multi_chunk([full[:mid], full[mid:]])
        result = await CompassService._read_layer(req)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_multiple_fields_concatenated(self):
        """If multiple fields exist, their bytes are concatenated."""
        part1 = b'{"na'
        part2 = b'me": "x"}'

        field1 = AsyncMock()
        field1.read_chunk = AsyncMock(side_effect=[part1, b""])
        field2 = AsyncMock()
        field2.read_chunk = AsyncMock(side_effect=[part2, b""])

        reader = AsyncMock()
        reader.next = AsyncMock(side_effect=[field1, field2, None])

        req = AsyncMock()
        req.multipart = AsyncMock(return_value=reader)

        result = await CompassService._read_layer(req)
        assert result == {"name": "x"}


# ===================================================================
# create_adversary_from_layer
# ===================================================================

class TestCreateAdversaryFromLayer:
    @pytest.mark.asyncio
    async def test_success(self, compass_svc, mock_services, valid_layer_json):
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(valid_layer_json).encode())
        resp = await compass_svc.create_adversary_from_layer(req)

        body = json.loads(resp.body)
        assert body["name"] == "TestLayer"
        assert "unmatched_techniques" in body

    @pytest.mark.asyncio
    async def test_malformed_json_returns_400(self, compass_svc, mock_services):
        """PR #45 bug: should *return* HTTPBadRequest, not raise it."""
        req = _make_multipart_request(b"<<<not json>>>")
        resp = await compass_svc.create_adversary_from_layer(req)
        # Current code returns HTTPBadRequest (which is also a Response)
        assert isinstance(resp, web.HTTPBadRequest)

    @pytest.mark.asyncio
    async def test_empty_body_returns_400(self, compass_svc, mock_services):
        req = _make_multipart_request(b"")
        resp = await compass_svc.create_adversary_from_layer(req)
        assert isinstance(resp, web.HTTPBadRequest)

    @pytest.mark.asyncio
    async def test_empty_techniques_creates_adversary(self, compass_svc, mock_services, empty_layer_json):
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(empty_layer_json).encode())
        resp = await compass_svc.create_adversary_from_layer(req)

        body = json.loads(resp.body)
        assert body["name"] == "EmptyLayer"
        assert body["unmatched_techniques"] == []

    @pytest.mark.asyncio
    async def test_missing_name_field(self, compass_svc, mock_services, layer_missing_fields):
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(layer_missing_fields).encode())
        resp = await compass_svc.create_adversary_from_layer(req)

        body = json.loads(resp.body)
        assert body["name"] is None

    @pytest.mark.asyncio
    async def test_missing_description_uses_default(self, compass_svc, mock_services):
        layer = {"name": "X", "techniques": []}
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(layer).encode())
        resp = await compass_svc.create_adversary_from_layer(req)

        # description should have been '' + ' (created by compass)'
        call_args = mock_services["rest_svc"].persist_adversary.call_args
        assert "(created by compass)" in call_args[0][1]["description"]

    @pytest.mark.asyncio
    async def test_persist_returns_none(self, compass_svc, mock_services, valid_layer_json):
        """When persist_adversary returns falsy, no json_response is returned."""
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=None)

        req = _make_multipart_request(json.dumps(valid_layer_json).encode())
        resp = await compass_svc.create_adversary_from_layer(req)
        # When adversary is falsy, the method returns None implicitly
        assert resp is None

    @pytest.mark.asyncio
    async def test_exception_in_build_raises_400(self, compass_svc, mock_services):
        """General exception in adversary building triggers HTTPBadRequest raise."""
        layer = {"name": "X", "techniques": "not-a-list"}
        req = _make_multipart_request(json.dumps(layer).encode())
        with pytest.raises(web.HTTPBadRequest):
            await compass_svc.create_adversary_from_layer(req)

    @pytest.mark.asyncio
    async def test_unmatched_techniques_sorted_by_tactic(self, compass_svc, mock_services):
        layer = {
            "name": "Test",
            "description": "d",
            "techniques": [
                {"techniqueID": "T2000", "tactic": "z-tactic", "score": 1},
                {"techniqueID": "T3000", "tactic": "a-tactic", "score": 1},
            ],
        }
        mock_services["data_svc"].locate = AsyncMock(return_value=[])
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(layer).encode())
        resp = await compass_svc.create_adversary_from_layer(req)

        body = json.loads(resp.body)
        tactics = [t["tactic"] for t in body["unmatched_techniques"]]
        assert tactics == sorted(tactics)

    @pytest.mark.asyncio
    async def test_adversary_id_is_uuid(self, compass_svc, mock_services, empty_layer_json):
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)
        req = _make_multipart_request(json.dumps(empty_layer_json).encode())
        await compass_svc.create_adversary_from_layer(req)

        call_args = mock_services["rest_svc"].persist_adversary.call_args
        adv_id = call_args[0][1]["id"]
        # Should be a valid UUID
        uuid.UUID(adv_id)

    @pytest.mark.asyncio
    async def test_no_tactic_on_technique(self, compass_svc, mock_services, layer_no_tactic):
        ab = FakeAbility("ab-1", "T1059", "execution")
        mock_services["data_svc"].locate = AsyncMock(return_value=[ab])
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(layer_no_tactic).encode())
        resp = await compass_svc.create_adversary_from_layer(req)
        body = json.loads(resp.body)
        assert body["name"] == "NoTactic"

    @pytest.mark.asyncio
    async def test_description_appended_with_compass_tag(self, compass_svc, mock_services):
        layer = {"name": "X", "description": "Original", "techniques": []}
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(layer).encode())
        await compass_svc.create_adversary_from_layer(req)

        call_args = mock_services["rest_svc"].persist_adversary.call_args
        assert call_args[0][1]["description"] == "Original (created by compass)"

    @pytest.mark.asyncio
    async def test_access_red_passed_to_persist(self, compass_svc, mock_services, empty_layer_json):
        mock_services["rest_svc"].persist_adversary = AsyncMock(return_value=True)

        req = _make_multipart_request(json.dumps(empty_layer_json).encode())
        await compass_svc.create_adversary_from_layer(req)

        call_args = mock_services["rest_svc"].persist_adversary.call_args
        access_dict = call_args[0][0]
        assert "access" in access_dict


# ===================================================================
# HTTPBadRequest raise vs return (PR #45 scenario)
# ===================================================================

class TestHTTPBadRequestBehavior:
    """
    The first except block (JSONDecodeError) *returns* HTTPBadRequest.
    The second except block (general Exception) *raises* HTTPBadRequest.
    PR #45 addresses this inconsistency.
    """

    @pytest.mark.asyncio
    async def test_json_decode_error_returns_not_raises(self, compass_svc, mock_services):
        req = _make_multipart_request(b"invalid json")
        # Should NOT raise; should return
        resp = await compass_svc.create_adversary_from_layer(req)
        assert isinstance(resp, web.HTTPBadRequest)

    @pytest.mark.asyncio
    async def test_general_exception_raises(self, compass_svc, mock_services):
        layer = {"name": "X", "description": "d", "techniques": 42}
        req = _make_multipart_request(json.dumps(layer).encode())
        with pytest.raises(web.HTTPBadRequest):
            await compass_svc.create_adversary_from_layer(req)
