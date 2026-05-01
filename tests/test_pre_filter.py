from pathlib import Path

from scripts.pre_filter import should_flush, FilterReason

FIXTURES = Path(__file__).parent / "fixtures"


def test_short_transcript_skipped():
    text = (FIXTURES / "transcript_short.md").read_text()
    decision = should_flush(text, char_threshold=1000)
    assert decision.proceed is False
    assert decision.reason == FilterReason.TOO_SHORT


def test_meaningful_transcript_proceeds():
    text = (FIXTURES / "transcript_meaningful.md").read_text()
    decision = should_flush(text, char_threshold=1000)
    assert decision.proceed is True
    assert decision.reason == FilterReason.OK


def test_empty_text_skipped():
    decision = should_flush("", char_threshold=1000)
    assert decision.proceed is False
    assert decision.reason == FilterReason.EMPTY


def test_only_bash_commands_skipped():
    text = (
        "**User:** ls -la\n\n"
        "**Assistant:** [Bash output]\n\n"
        "**User:** pwd\n\n"
        "**Assistant:** [Bash output]\n\n"
    ) * 5
    decision = should_flush(text, char_threshold=100)
    assert decision.proceed is False
    assert decision.reason == FilterReason.TRIVIAL_OPS
