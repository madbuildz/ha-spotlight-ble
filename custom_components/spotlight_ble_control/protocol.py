"""Packets for the two tested spotlight families. No network or HA imports."""
import colorsys
import hashlib
import hmac
import re
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PALETTES = dict(zip([
    "Red", "Green", "Blue", "Orange", "Pink", "Aqua", "Gold", "Fuchsia",
    "Lawn green", "Magenta", "Cyan", "Yellow", "Purple", "White 1", "White 2",
    "White 3", "Spring", "Summer", "Autumn", "Winter", "Christmas", "Valentines",
    "Independence", "Thanksgiving", "St Patricks", "Halloween", "Sun", "Earth",
    "Multicolor",
], range(29)))
EFFECTS = dict(zip([
    "Steady", "Blink", "Sparkle", "Alternate", "Fade", "Rolling", "Waves",
    "Fireworks", "Rainbow", "Color band",
], range(1, 11)))
# Mode bytes recovered from Fi Light Android app com.we.glight 1.458.
# The color is part of the effect ID; these are not arbitrary-RGB animations.
FI_EFFECTS = {
    "Pulse rainbow": 0x25, "Pulse red": 0x26, "Pulse green": 0x27,
    "Pulse blue": 0x28, "Pulse yellow": 0x29, "Pulse cyan": 0x2A,
    "Pulse purple": 0x2B, "Pulse RGB white": 0x2C,
    "Pulse red/green": 0x2D, "Pulse red/blue": 0x2E, "Pulse green/blue": 0x2F,
    "Blink rainbow": 0x30, "Blink red": 0x31, "Blink green": 0x32,
    "Blink blue": 0x33, "Blink yellow": 0x34, "Blink cyan": 0x35,
    "Blink purple": 0x36, "Blink RGB white": 0x37, "Jump rainbow": 0x38,
    "Pulse warm white": 0x51, "Pulse cool white": 0x52,
    "Pulse warm/cool white": 0x53, "Blink warm white": 0x54,
    "Blink cool white": 0x55, "Blink warm/cool white": 0x56,
    "Jump warm/cool white": 0x57,
}
FI_EFFECT_ALIASES = {"White pulse": "Pulse warm white", "White blink": "Blink warm white"}
FI_SOLID_MODES = ["Color", "White channel 1", "White channel 2", "Both white channels"]
FI_MODES = FI_SOLID_MODES + list(FI_EFFECTS)


def fi_mode(mode):
    """Keep previously saved helper modes and action callers compatible."""
    return FI_EFFECT_ALIASES.get(mode, mode)


FI_UUID = "0000ffc1-0000-1000-8000-00805f9b34fb"
SHOW_UUIDS = ["c4edc000-9daf-11e3-8003-00025b000b00",
              "c4edc000-9daf-11e3-8004-00025b000b00"]


def fi_packet(state, *, off=False):
    """Scale normalized HS color by brightness, or select white channels."""
    brightness = int(state["b"])
    if not 0 <= brightness <= 255:
        raise ValueError("Brightness must be between 0 and 255")
    mode = fi_mode(state["mode"])
    if mode not in FI_MODES:
        raise ValueError("Unknown Floodlight mode")
    if off:
        return bytes.fromhex("28000000000000f029")
    if mode in FI_EFFECTS:
        speed = state.get("speed", 8)
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 1 <= speed <= 31 or int(speed) != speed:
            raise ValueError("Effect speed must be an integer from 1 to 31")
        return bytes([0xFD, FI_EFFECTS[mode], 32 - int(speed), 0xFC])
    channels = [0] * 5
    if mode == "Color":
        hue, saturation = state["hs"]
        if not 0 <= hue <= 360 or not 0 <= saturation <= 100:
            raise ValueError("Invalid hue or saturation")
        channels[:3] = [round(v * brightness) for v in
                        colorsys.hsv_to_rgb(hue / 360, saturation / 100, 1)]
    else:
        if mode in ("White channel 1", "Both white channels"):
            channels[3] = brightness
        if mode in ("White channel 2", "Both white channels"):
            channels[4] = brightness
    return bytes([0x28, *channels, 0, 0xF0 if mode == "Color" else 0x0F, 0x29])


def show_identity(name):
    """The advertised LA2 name carries the batch and mesh destination."""
    if not re.fullmatch(r"LA2[0-9A-Fa-f]{10}", name):
        raise ValueError("ShowHome advertised name must match LA2000012A1B2 format")
    return int(name[-4:], 16), int(name[7:9], 16)


def show_packet(name, sequence, transaction, preset, effect):
    """Build the observed 27-byte CSRmesh vendor command with fresh counters.

    Wire layout independently implemented from the observed protocol. AES-OFB
    is expressed with its standard ECB feedback construction to avoid the
    deprecated cryptography OFB class. HMAC uses the CSRmesh reversed suffix.
    """
    if not 1 <= sequence <= 0xFFFFFF or not 1 <= transaction <= 15:
        raise ValueError("Invalid mesh sequence or transaction")
    dest, batch = show_identity(name)
    tag = (transaction << 4) | 3
    plain = struct.pack("<H", dest) + bytes([
        0x73, tag, batch, 0, 2, tag, EFFECTS[effect], PALETTES[preset], 0, 0, 0,
    ])
    key = hashlib.sha256(b"686868\x00MCP").digest()[::-1][:16]
    seq = sequence.to_bytes(3, "little")
    source = struct.pack("<H", 0x8000)
    iv = seq + b"\x00" + source + bytes(10)
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    feedback = encryptor.update(iv) + encryptor.finalize()
    encrypted = bytes(a ^ b for a, b in zip(plain, feedback, strict=False))
    mac = hmac.new(key, bytes(8) + seq + source + encrypted, hashlib.sha256).digest()[-8:][::-1]
    return seq + source + encrypted + mac + b"\xff"
