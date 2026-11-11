"""Tests for the LEGO Wireless Protocol helpers."""

from custom_components.lego_power import lego


def test_parse_attached():
    # Port B (0x01), attached, IO type 0x0008 (Light), hw/sw versions.
    msg = bytes.fromhex("0f00040101080000000010000000 10".replace(" ", ""))
    assert lego.parse_message(msg) == lego.AttachedIO(port=1, io_type=0x0008)


def test_parse_attached_virtual():
    msg = bytes.fromhex("0900040202260000 01".replace(" ", ""))
    assert lego.parse_message(msg) == lego.AttachedIO(port=2, io_type=0x0026)


def test_parse_detached():
    assert lego.parse_message(bytes.fromhex("0500040000")) == lego.AttachedIO(0, None)


def test_parse_battery():
    assert lego.parse_message(bytes.fromhex("060001060657")) == lego.BatteryLevel(87)


def test_parse_ignores_other():
    assert lego.parse_message(bytes.fromhex("050082000a")) is None
    assert lego.parse_message(b"\x01") is None


def test_commands():
    assert lego.set_motor_power(0, -50) == bytes.fromhex("0800810011510 0ce".replace(" ", ""))
    assert lego.set_light_brightness(1, 75) == bytes.fromhex("080081011151004b")
    assert lego.enable_battery_updates() == bytes.fromhex("0500010602")


def test_kinds_and_labels():
    assert lego.io_type_kind(0x0008) == lego.KIND_LIGHT
    assert lego.io_type_kind(0x0002) == lego.KIND_MOTOR
    assert lego.io_type_kind(0x0025) is None
    assert lego.port_label(1) == "B"
    assert not lego.is_external_port(0x32)
