from scripts.dup_tags import classify_version, tag_group


def _v(file="/m/movie.mkv", size=5_000_000_000, resolution="1080", bitrate=8000):
    return {"file": file, "size": size, "resolution": resolution, "bitrate": bitrate}


def test_classify_sample_by_path():
    assert classify_version(_v(file="/m/Sample.mkv")) == "SAMPLE"
    assert classify_version(_v(file="/m/movie-sample.mkv")) == "SAMPLE"


def test_classify_extra_by_path():
    assert classify_version(_v(file="/m/Film/0 Extras/Commentary.mkv")) == "EXTRA"
    assert classify_version(_v(file="/m/Film/Extras/Featurette.mkv")) == "EXTRA"
    assert classify_version(_v(file="/m/Film/movie[TRAILER-x].mkv")) == "EXTRA"


def test_classify_multitrack_by_path():
    assert classify_version(_v(file="/m/Disc/Disc 2 - Track 3.mkv")) == "MULTITRACK"


def test_classify_main_default():
    assert classify_version(_v(file="/m/Real.Movie.1080p.mkv")) == "MAIN"


def test_tag_group_marks_each_version_and_suggests_keeper():
    versions = [
        _v(file="/m/Sample.mkv", size=300_000_000, bitrate=9000),  # SAMPLE (small)
        _v(file="/m/Movie.1080p.mkv", size=9_000_000_000, bitrate=8000),  # MAIN, biggest main
        _v(file="/m/0 Extras/Bonus.mkv", size=200_000_000),  # EXTRA
    ]
    tagged = tag_group(versions)
    tags = [t["tag"] for t in tagged]
    assert tags == ["SAMPLE", "MAIN", "EXTRA"]
    # exactly one suggested keeper, and it is the MAIN one
    keepers = [t for t in tagged if t["suggested_keeper"]]
    assert len(keepers) == 1
    assert keepers[0]["file"] == "/m/Movie.1080p.mkv"


def test_tag_group_keeper_is_none_when_no_main():
    versions = [_v(file="/m/Sample.mkv", size=1), _v(file="/m/0 Extras/x.mkv", size=2)]
    tagged = tag_group(versions)
    assert all(not t["suggested_keeper"] for t in tagged)  # nothing auto-suggested
