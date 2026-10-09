from sample import checksum


def test_checksum() -> None:
    assert checksum(b"abc") == "900150983cd24fb0d6963f7d28e17f72"
