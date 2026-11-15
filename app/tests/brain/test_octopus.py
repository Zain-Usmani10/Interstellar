"""Fabricated packets and mocked BLE only: no hardware or wearer validation."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.brain.acquisition import SyntheticAdapter
from app.brain.octopus import OctopusAdapter, OctopusStream, UV_PER_COUNT, decode_notification
from app.brain.selection import SelectionGate
from app.backend.runtime.stores import load_validators
from test_selection import Clock, context, stimulus


def packet(counter, values=None):
    values = [100] * 16 if values is None else values
    return b'\xa0' + bytes([counter % 256]) + b''.join(
        int(value).to_bytes(3, 'big', signed=True) for value in values) + b'\xc0'


def test_signed_values_units_channels_and_counter_wrap():
    values = [0, 1, -1, 8388606, -8388607] + [123] * 11
    decoded = decode_notification(packet(255, values))
    np.testing.assert_allclose(decoded[0][1], np.array(values) * UV_PER_COUNT)
    stream = OctopusStream((4, 1))
    batch = stream.ingest(packet(255, values) + packet(0, values))
    assert batch.source == 'live_eeg'
    np.testing.assert_array_equal(batch.sample_indices, [0, 1])
    np.testing.assert_allclose(batch.samples_uv[:, 0], np.array([-8388607, 1]) * UV_PER_COUNT)


@pytest.mark.parametrize('payload', [b'', packet(0)[:-1], b'\x00' + packet(0)[1:],
                                     packet(0) + b'\x00', packet(0, [8388607] * 16),
                                     packet(0, [-8388608] * 16)])
def test_corrupt_packet_invalidates_stream(payload):
    stream = OctopusStream()
    with pytest.raises(ValueError):
        stream.ingest(payload)
    with pytest.raises(RuntimeError):
        stream.ingest(packet(0))


@pytest.mark.parametrize('counter', [0, 2, 255])
def test_loss_duplicate_restart_rejected(counter):
    stream = OctopusStream()
    stream.ingest(packet(0))
    with pytest.raises(ValueError):
        stream.ingest(packet(counter))


def test_receive_stall_rejected_even_with_contiguous_counter():
    clock = Clock()
    stream = OctopusStream(clock=clock)
    stream.ingest(packet(0))
    clock.advance(0.51)
    with pytest.raises(ValueError):
        stream.ingest(packet(1))


@pytest.mark.parametrize('frequency,target', [(10, 'planet.399'), (15, 'planet.499')])
def test_fabricated_packets_use_same_selection_intent(frequency, target):
    clock = Clock()
    stream = OctopusStream(clock=clock)
    generator = SyntheticAdapter(clock)
    generator.start({'frequency_hz': frequency})
    gate = SelectionGate(source='live_eeg', clock=clock)
    gate.configure(context(), ['planet.399', 'planet.499'], [10, 15])
    intents = []
    for n in range(60):
        clock.advance()
        synthetic = generator.read_batch()
        wire = b''.join(packet(index, list(np.rint(sample / UV_PER_COUNT).astype(int)) + [100]*14)
                        for index, sample in zip(synthetic.sample_indices, synthetic.samples_uv.T))
        gate.stimulus(stimulus(gate, n))
        intent = gate.feed(stream.ingest(wire))
        if intent:
            intents.append(intent)
    assert len(intents) == 1
    assert intents[0]['target_id'] == target
    assert intents[0]['source'] == 'live_eeg'  # exercises labeling, NOT real EEG evidence
    load_validators()['selection_intent'].validate(intents[0])


@pytest.mark.parametrize('config', [dict(address=''), dict(address='test-device', channels=(0, 0)),
                                   dict(address='test-device', channels=(16,)),
                                   dict(address='test-device', sample_rate_hz=float('nan')),
                                   dict(address='test-device', sample_rate_hz=100)])
def test_bad_configuration_rejected_before_connect(config):
    adapter = OctopusAdapter()
    with pytest.raises(ValueError):
        adapter.start(config)
    assert adapter.thread is None


@pytest.fixture
def ble(monkeypatch):
    state = SimpleNamespace(found=True, service=True, silent=False, disconnected=False,
                            stopped=False, client=None)

    class Scanner:
        @staticmethod
        async def find_device_by_address(address, timeout):
            assert address == 'test-device'
            return object() if state.found else None

    class Client:
        def __init__(self, device, disconnected_callback):
            state.client = self
            self.disconnect = disconnected_callback
            self.services = SimpleNamespace(get_service=lambda _: object() if state.service else None)
            self.is_connected = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            state.disconnected = True
            self.is_connected = False

        async def start_notify(self, uuid, callback):
            self.callback = callback
            if not state.silent:
                for i in range(25):
                    callback(None, packet(i))

        async def stop_notify(self, uuid):
            state.stopped = True

    monkeypatch.setitem(sys.modules, 'bleak', SimpleNamespace(BleakClient=Client, BleakScanner=Scanner))
    return state


def test_adapter_metadata_batch_and_cleanup(ble):
    adapter = OctopusAdapter()
    try:
        info = adapter.start({'address': 'test-device', 'channels': (2, 7)})
        assert info.source == 'live_eeg' and info.channels == ('CH3', 'CH8')
        batch = adapter.read_batch()
        assert batch.samples_uv.shape == (2, 25)
        np.testing.assert_array_equal(batch.sample_indices, np.arange(25))
        assert batch.batch_id == 1
    finally:
        adapter.stop()
    assert ble.stopped and ble.disconnected
    adapter.stop()
    with pytest.raises(RuntimeError):
        adapter.read_batch()


@pytest.mark.parametrize('fault', ['found', 'service'])
def test_missing_device_or_service_fails_without_fallback(ble, fault):
    setattr(ble, fault, False)
    adapter = OctopusAdapter()
    with pytest.raises(RuntimeError):
        adapter.start({'address': 'test-device'})
    assert adapter.thread is None and not adapter.running


@pytest.mark.parametrize('fault', ['disconnect', 'overflow', 'stale', 'corrupt'])
def test_queued_samples_cannot_survive_fault(ble, fault):
    clock = Clock()
    adapter = OctopusAdapter(clock)
    try:
        adapter.start({'address': 'test-device'})
        if fault == 'disconnect':
            adapter._disconnected(None)
        elif fault == 'overflow':
            for i in range(25, 160):
                adapter._receive(None, packet(i))
        elif fault == 'corrupt':
            adapter._receive(None, b'bad')
        else:
            clock.advance(0.6)
        with pytest.raises(RuntimeError):
            adapter.read_batch()
    finally:
        adapter.stop()


def test_silent_device_times_out_and_cleans_up(ble):
    ble.silent = True
    adapter = OctopusAdapter()
    try:
        adapter.start({'address': 'test-device'})
        with pytest.raises(RuntimeError):
            adapter.read_batch()
    finally:
        adapter.stop()
    assert ble.disconnected
