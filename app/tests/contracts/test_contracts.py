"""Contract checks: CRC vector, golden frames, protocol JSON vs reference code, schemas vs fixtures.

Run from the repo root:  python -m pytest app/tests/contracts
"""
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from app.contracts import protocol_v1 as p

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
FRAMES = CONTRACTS / "fixtures" / "frames"
MANIFEST = json.loads((FRAMES / "manifest.json").read_text(encoding="utf-8"))
ENTRIES = {e["name"]: e for e in MANIFEST["frames"]}
PROTOCOL = json.loads((CONTRACTS / "protocol_v1.json").read_text(encoding="utf-8"))


def load_schemas():
    schemas = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in (CONTRACTS / "schemas").glob("*.json")}
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas.values())
    return {name: Draft202012Validator(s, registry=registry) for name, s in schemas.items()}


VALIDATORS = load_schemas()

# fixture file prefix -> schema file
FIXTURE_SCHEMAS = {
    "mission_plan_": "mission_plan.schema.json",
    "mission_snapshot_": "mission_snapshot.schema.json",
    "planet_info_": "planet_info.schema.json",
    "input_context_": "input_context.schema.json",
    "selection_intent_": "selection_intent.schema.json",
    "intent_result_": "intent_result.schema.json",
    "input_heartbeat": "input_heartbeat.schema.json",
}


def fixture(name):
    return json.loads((CONTRACTS / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ protocol

def test_crc_check_vector():
    assert p.crc16_ccitt_false(b"123456789") == 0x29B1
    assert MANIFEST["crc_check"]["value"] == 0x29B1


def test_protocol_json_matches_reference_code():
    for name, spec in PROTOCOL["messages"].items():
        msg_type = p.MsgType[name]
        assert int(spec["type_hex"], 16) == msg_type
        assert spec["payload_length"] == p.PAYLOAD_LEN[msg_type]
    assert len(PROTOCOL["messages"]) == len(p.MsgType)
    for enum_name, cls in (("state", p.State), ("result", p.Result), ("detail", p.Detail), ("safe_reason", p.SafeReason)):
        assert PROTOCOL["enums"][enum_name] == {m.name: m.value for m in cls}
    assert PROTOCOL["frame"]["max_frame"] == p.MAX_FRAME == 142
    assert bytes.fromhex(PROTOCOL["frame"]["magic_hex"]) == p.MAGIC


def test_payload_sizes():
    assert len(p.Plan(1, 1, 2, 3, 2, 1, 1).pack()) == 28
    assert len(p.Ack(0x13, 0, 0, 1, 0, 0).pack()) == 16
    assert len(p.Status().pack()) == 40
    assert len(p.pack_commit(1, 2)) == 6


@pytest.mark.parametrize("name", [n for n, e in ENTRIES.items() if e["valid"] is True])
def test_valid_golden_frame(name):
    entry = ENTRIES[name]
    data = (FRAMES / f"{name}.bin").read_bytes()
    assert data == bytes.fromhex((FRAMES / f"{name}.hex").read_text()) == bytes.fromhex(entry["hex"])
    frame = p.decode_frame(data)
    assert p.shape_ok(frame)
    assert (p.MsgType(frame.msg_type).name, frame.sequence, frame.session_id) == (
        entry["type"], entry["sequence"], entry["session_id"])
    # Re-encoding the decoded frame gives the same bytes.
    assert p.encode_frame(frame.msg_type, frame.sequence, frame.session_id, frame.payload) == data
    if frame.msg_type == p.MsgType.STATUS:
        assert p.Status.unpack(frame.payload).pack() == frame.payload
        assert p.Status.unpack(frame.payload).tick == entry["fields"]["tick"]
    if frame.msg_type == p.MsgType.ACK:
        ack = p.Ack.unpack(frame.payload)
        assert ack.pack() == frame.payload
        assert p.Detail(ack.detail).name == entry["fields"]["detail"]
    if frame.msg_type == p.MsgType.LOAD_PLAN:
        plan = p.Plan.unpack(frame.payload)
        assert plan.problem() is None
        assert plan.crc16() == MANIFEST["plan_crc16"]


@pytest.mark.parametrize("name", [n for n, e in ENTRIES.items() if e["valid"] is False])
def test_invalid_golden_frame_is_rejected(name):
    data = (FRAMES / f"{name}.bin").read_bytes()
    expected = ENTRIES[name]["expected_error"]
    if expected == "BAD_SHAPE":          # integrity is fine; the exact-length/type check must fail
        assert not p.shape_ok(p.decode_frame(data))
    else:
        with pytest.raises(p.FrameError) as err:
            p.decode_frame(data if expected != "OVERSIZE" else data + bytes(131))
        assert err.value.code == expected
    assert p.StreamParser().feed(data) == [] or expected == "BAD_SHAPE"


@pytest.mark.parametrize("name", [n for n, e in ENTRIES.items() if e.get("stream")])
@pytest.mark.parametrize("chunk", [1, 3, 1000])
def test_stream_fixture(name, chunk):
    data = (FRAMES / f"{name}.bin").read_bytes()
    parser, got = p.StreamParser(), []
    for i in range(0, len(data), chunk):
        got += parser.feed(data[i:i + chunk])
    expected = [p.decode_frame((FRAMES / f"{n}.bin").read_bytes()) for n in ENTRIES[name]["expected_frames"]]
    assert got == expected


def test_parser_abandons_incomplete_frame_after_timeout():
    arm = (FRAMES / "11_arm.bin").read_bytes()
    status = (FRAMES / "05_get_status.bin").read_bytes()
    parser = p.StreamParser()
    assert parser.feed(arm[:13], now=0.0) == []       # header complete, body never arrives
    assert parser.feed(status, now=0.2) == [p.decode_frame(status)]
    assert parser.timeouts == 1


def test_plan_rules():
    good = p.Plan(1, 10, 12010, 12610, 300, 200, 100)
    assert good.problem() is None
    for bad in (p.Plan(0, 10, 12010, 12610, 300, 200, 100),      # zero mission id
                p.Plan(1, 0, 12010, 12610, 300, 200, 100),       # departure tick 0
                p.Plan(1, 20, 20, 12610, 300, 200, 100),         # arrival not after departure
                p.Plan(1, 10, 12010, 360001, 300, 200, 100),     # end tick too large
                p.Plan(1, 10, 12010, 12610, 300, 0, 100),        # zero cost
                p.Plan(1, 10, 12010, 12610, 299, 200, 100),      # costs exceed fuel
                p.Plan(1, 10, 12010, 12610, 5, 0xFFFFFFFF, 7)):  # 32-bit sum would wrap
        assert bad.problem() is not None


# ------------------------------------------------------------------ schemas and fixtures

def all_fixture_files():
    return sorted(f.stem for f in (CONTRACTS / "fixtures").glob("*.json") if f.stem != "planets")


@pytest.mark.parametrize("name", all_fixture_files())
def test_fixture_validates(name):
    schema = next(s for prefix, s in FIXTURE_SCHEMAS.items() if name.startswith(prefix))
    errors = list(VALIDATORS[schema].iter_errors(fixture(name)))
    assert not errors, errors[0].message


def test_every_schema_is_well_formed():
    for validator in VALIDATORS.values():
        Draft202012Validator.check_schema(validator.schema)


def rejects(schema, doc):
    return not VALIDATORS[schema].is_valid(doc)


def test_selection_intent_rejections():
    good = fixture("selection_intent_synthetic")
    schema = "selection_intent.schema.json"
    assert rejects(schema, dict(good, target_id="mission.request_start"))   # no mission targets
    assert rejects(schema, dict(good, target_id="planet.299"))              # Venus not supported
    assert rejects(schema, dict(good, source="telepathy"))
    assert rejects(schema, dict(good, schema_version=2))
    assert rejects(schema, dict(good, command="START"))                     # no extra fields
    no_evidence = {k: v for k, v in good.items() if k != "evidence"}
    assert rejects(schema, no_evidence)                                     # EEG-type source needs evidence
    assert not rejects(schema, dict(no_evidence, source="keyboard"))


def test_input_context_only_allows_planet_explore():
    good = fixture("input_context_planet_choice")
    schema = "input_context.schema.json"
    assert rejects(schema, dict(good, capability="mission_control"))
    assert rejects(schema, dict(good, allowed_targets=["mission.request_start"]))


def test_plan_fixture_is_consistent():
    plan = fixture("mission_plan_earth_mars")
    digest = plan.pop("plan_sha256")
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == digest
    wire, ticks = plan["wire"], plan["ticks"]
    assert wire["initial_fuel_g"] == wire["departure_fuel_g"] + wire["capture_fuel_g"]
    assert ticks["seconds_per_tick"] == pytest.approx(plan["tof_s"] / (ticks["arrival_tick"] - ticks["departure_tick"]))
    assert plan["data_mode"] == "synthetic"       # the mock must never pass as NASA data
    # The golden LOAD_PLAN frame carries exactly this plan.
    loaded = p.Plan.unpack(p.decode_frame((FRAMES / "06_load_plan.bin").read_bytes()).payload)
    assert (loaded.departure_tick, loaded.arrival_tick, loaded.end_tick) == (
        ticks["departure_tick"], ticks["arrival_tick"], ticks["end_tick"])
    assert (loaded.initial_fuel_g, loaded.departure_fuel_g, loaded.capture_fuel_g) == (
        wire["initial_fuel_g"], wire["departure_fuel_g"], wire["capture_fuel_g"])


def test_mars_weather_is_unavailable_not_invented():
    mars = fixture("planet_info_499")["conditions"]
    assert mars["availability"] == "unavailable" and mars["items"] == []
