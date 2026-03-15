from app.services.shortener import ALPHABET, generate_short_code


def test_generate_short_code_has_expected_length_and_alphabet():
    code = generate_short_code()
    assert len(code) == 7
    assert all(ch in ALPHABET for ch in code)


def test_generate_short_code_custom_length():
    code = generate_short_code(length=12)
    assert len(code) == 12


def test_generate_short_code_smoke_uniqueness():
    # это не математическая гарантия уникальности, но для smoke-теста нормально.
    samples = {generate_short_code() for _ in range(300)}
    assert len(samples) > 295
