from app.scripts.seed_demo import parse_args


def test_seed_demo_parse_args_supports_reset_only(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["seed_demo", "--reset-only"])

    args = parse_args()

    assert args.reset_only is True
    assert args.skip_work_orders is False


def test_seed_demo_parse_args_keeps_skip_work_order_alias(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["seed_demo", "--skip-work-order"])

    args = parse_args()

    assert args.reset_only is False
    assert args.skip_work_orders is True
