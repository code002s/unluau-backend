import unittest

from unluau import descramble

from .helpers import fixture

PLAIN = "v13_basic_O1_g1.luauc"
ENCODED = "v13_basic_O1_g1_roblox_encoded.luauc"
ALL_FIXTURES = [PLAIN, ENCODED, "v13_roblox_like_1.luauc", "v14_extra_O2_g2.luauc"]


class DescrambleTest(unittest.TestCase):
    def test_decodes_roblox_encoding(self):
        self.assertEqual(descramble.decode_roblox(fixture(ENCODED)), fixture(PLAIN))

    def test_encodes_roblox_encoding(self):
        self.assertEqual(descramble.encode_roblox(fixture(PLAIN)), fixture(ENCODED))

    def test_round_trip_on_every_fixture(self):
        for name in ALL_FIXTURES:
            with self.subTest(name):
                data = fixture(name)
                self.assertEqual(descramble.decode_roblox(descramble.encode_roblox(data)), data)

    def test_rejects_non_luau_data(self):
        with self.assertRaises(ValueError):
            descramble.decode_roblox(b"\x63not bytecode")

    def test_rejects_truncated_data(self):
        with self.assertRaises(ValueError):
            descramble.decode_roblox(fixture(PLAIN)[:40])


if __name__ == "__main__":
    unittest.main()
