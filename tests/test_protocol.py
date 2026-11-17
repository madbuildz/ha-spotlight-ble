"""Packet tests do not connect to Bluetooth or require Home Assistant."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "protocol", ROOT / "custom_components/spotlight_ble_control/protocol.py"
)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PacketTests(unittest.TestCase):
    def state(self, **changes):
        return {"b": 128, "hs": [0, 100], "mode": "Color"} | changes

    def test_observed_half_red_and_blue(self):
        self.assertEqual(p.fi_packet(self.state()).hex(), "28800000000000f029")
        self.assertEqual(p.fi_packet(self.state(hs=[240, 100])).hex(), "28000080000000f029")

    def test_brightness_scales_color_without_changing_ratio(self):
        self.assertEqual(p.fi_packet(self.state(b=255, hs=[300, 100]))[1:4], bytes([255, 0, 255]))
        self.assertEqual(p.fi_packet(self.state(b=64, hs=[300, 100]))[1:4], bytes([64, 0, 64]))

    def test_neutral_color_and_zero(self):
        self.assertEqual(p.fi_packet(self.state(hs=[0, 0]))[1:4], bytes([128, 128, 128]))
        self.assertEqual(p.fi_packet(self.state(b=0)).hex(), "28000000000000f029")

    def test_white_channel_separation(self):
        for mode, packet in [
            ("White channel 1", "280000008000000f29"),
            ("White channel 2", "280000000080000f29"),
            ("Both white channels", "280000008080000f29"),
        ]:
            self.assertEqual(p.fi_packet(self.state(mode=mode)).hex(), packet)

    def test_confirmed_effect_commands(self):
        self.assertEqual(p.fi_packet(self.state(mode="White pulse")).hex(), "fd5118fc")
        self.assertEqual(p.fi_packet(self.state(mode="White blink")).hex(), "fd5418fc")

    def test_all_app_effect_ids_match_recorded_fixture(self):
        recorded = json.loads((ROOT / 'tests/fixtures/fi_light_effects.json').read_text())
        self.assertEqual(len(p.FI_EFFECTS), 27)
        self.assertEqual(list(p.FI_EFFECTS.values()), [int(e['mode_hex'], 16) for e in recorded['effects']])
        for mode, recorded_effect in zip(p.FI_EFFECTS, recorded['effects'], strict=True):
            expected = bytes([0xFD, int(recorded_effect['mode_hex'], 16), 0x18, 0xFC])
            self.assertEqual(p.fi_packet(self.state(mode=mode)), expected)
            self.assertEqual(p.fi_packet(self.state(mode=mode), off=True).hex(), '28000000000000f029')

    def test_effect_speed_mapping_and_validation(self):
        for speed in range(1, 32):
            self.assertEqual(p.fi_packet(self.state(mode="Pulse red", speed=speed)), bytes([0xFD, 0x26, 32-speed, 0xFC]))
        for speed in (0, 32, -1, 1.5, True, None):
            with self.assertRaises(ValueError):
                p.fi_packet(self.state(mode="Pulse red", speed=speed))

    def test_off_overrides_effect(self):
        self.assertEqual(p.fi_packet(self.state(mode="White pulse"), off=True).hex(), "28000000000000f029")

    def test_invalid_channels_and_mode_fail_before_writing(self):
        for changes in [{"b": 256}, {"b": -1}, {"hs": [1, 101]}, {"mode": "invalid"}]:
            with self.assertRaises(ValueError):
                p.fi_packet(self.state(**changes))

    def test_both_showhome_identities(self):
        self.assertEqual(p.show_identity("LA2000012A1B2"), (0xA1B2, 0x12))
        self.assertEqual(p.show_identity("LA2000034C3D4"), (0xC3D4, 0x34))

    def test_reference_encrypted_packet(self):
        # Independently generated with recsrmesh 0.3.0 for plaintext
        # d4c373f3340002f30100000000, sequence 66051, source 0x8000.
        packet = p.show_packet("LA2000034C3D4", 66051, 15, "Red", "Steady")
        self.assertEqual(packet.hex(), "0302010080a714fe83e6aae8ab3059fc943cc10994033c94eaeeff")
        self.assertEqual((len(packet[:20]), len(packet[20:])), (20, 7))

    def test_fresh_sequences_and_batches_change_packets(self):
        a = p.show_packet("LA2000034C3D4", 66051, 15, "Red", "Steady")
        self.assertNotEqual(a, p.show_packet("LA2000034C3D4", 66052, 1, "Red", "Steady"))
        self.assertNotEqual(a, p.show_packet("LA2000056C3D4", 66051, 15, "Red", "Steady"))

    def test_invalid_mesh_identity_and_counters(self):
        for name in ["C3D4", "LA2000034ZZZZ", "LA2000034C3D4x"]:
            with self.assertRaises(ValueError):
                p.show_identity(name)
        for sequence, transaction in [(0, 1), (0x1000000, 1), (1, 0), (1, 16)]:
            with self.assertRaises(ValueError):
                p.show_packet("LA2000034C3D4", sequence, transaction, "Red", "Steady")


if __name__ == "__main__":
    unittest.main()
