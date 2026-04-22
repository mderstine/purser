from purser.cli import dispatch


def test_dispatch_init_help_smoke() -> None:
    try:
        dispatch(["init", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
