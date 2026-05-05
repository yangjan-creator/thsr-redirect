from api.r.thsr import _normalize_tdx_station_name


def test_normalize_all_thsr_station_names_for_tdx():
    expected = {
        "南港": "南港",
        "臺北": "台北",
        "台北": "台北",
        "板橋": "板橋",
        "桃園": "桃園",
        "新竹": "新竹",
        "苗栗": "苗栗",
        "臺中": "台中",
        "台中": "台中",
        "彰化": "彰化",
        "雲林": "雲林",
        "嘉義": "嘉義",
        "臺南": "台南",
        "台南": "台南",
        "左營": "左營",
        "新左營": "左營",
    }

    for raw, normalized in expected.items():
        assert _normalize_tdx_station_name(raw) == normalized


def test_unknown_station_passthrough_for_fail_loud_fallback():
    assert _normalize_tdx_station_name("不存在") == "不存在"
