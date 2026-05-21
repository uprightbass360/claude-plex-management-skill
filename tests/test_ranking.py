from tests.conftest import make_version, make_item
from scripts.ranking import resolution_rank, rank_versions, choose_keeper, plan_pruning


def test_resolution_rank_orders_known_values():
    assert resolution_rank("4k") > resolution_rank("1080")
    assert resolution_rank("1080") > resolution_rank("720")
    assert resolution_rank("720") > resolution_rank("sd")
    assert resolution_rank("unknown-label") == 0


def test_rank_versions_sorts_by_resolution_then_bitrate_then_size():
    v_lo = make_version(resolution="720", bitrate=3000, size=1_000)
    v_hi = make_version(resolution="1080", bitrate=8000, size=9_000)
    v_mid = make_version(resolution="1080", bitrate=8000, size=2_000)
    ranked = rank_versions([v_lo, v_hi, v_mid])
    assert ranked == [v_hi, v_mid, v_lo]  # 1080>720; tie->bitrate; tie->size


def test_choose_keeper_returns_top_ranked():
    v_lo = make_version(resolution="720")
    v_hi = make_version(resolution="4k")
    item = make_item(versions=[v_lo, v_hi])
    keeper, removals = choose_keeper(item)
    assert keeper is v_hi
    assert removals == [v_lo]


def test_plan_pruning_excludes_exempt_items():
    keep_me = make_item(rating_key="100", versions=[make_version("1080"),
                                                    make_version("720")])
    prune_me = make_item(rating_key="200", versions=[make_version("1080"),
                                                     make_version("720")])
    plan = plan_pruning([keep_me, prune_me], exempt_keys={"100"})
    assert [g["ratingKey"] for g in plan["prunable"]] == ["200"]
    assert [g["ratingKey"] for g in plan["exempt"]] == ["100"]
    assert len(plan["prunable"][0]["removals"]) == 1
