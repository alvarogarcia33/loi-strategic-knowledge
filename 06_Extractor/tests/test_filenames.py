from src.utils.filenames import safe_filename


def test_safe_filename_removes_spaces() -> None:
    assert safe_filename("Hola Mundo") == "Hola-Mundo"
