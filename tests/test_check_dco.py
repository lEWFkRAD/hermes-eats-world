from scripts.check_dco import Commit, missing_signoffs


def test_accepts_a_standard_dco_trailer():
    commits = [
        Commit(
            sha="a" * 40,
            message="feat: safe change\n\nSigned-off-by: Ada Lovelace <ada@example.com>",
        )
    ]

    assert missing_signoffs(commits) == []


def test_accepts_case_insensitive_trailer_name():
    commits = [
        Commit(
            sha="b" * 40,
            message="fix: safe change\n\nsigned-off-by: Grace Hopper <grace@example.com>",
        )
    ]

    assert missing_signoffs(commits) == []


def test_rejects_missing_or_malformed_signoffs():
    commits = [
        Commit(sha="c" * 40, message="docs: no trailer"),
        Commit(sha="d" * 40, message="test: malformed\n\nSigned-off-by: No Email"),
    ]

    assert missing_signoffs(commits) == commits

