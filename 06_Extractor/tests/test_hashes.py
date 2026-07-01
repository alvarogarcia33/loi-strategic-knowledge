from src.utils.hashes import sha256_text


def test_sha256_text_is_stable() -> None:
    assert sha256_text("loi") == sha256_text("loi")
