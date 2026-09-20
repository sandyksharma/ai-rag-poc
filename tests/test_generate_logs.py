import runpy
from pathlib import Path
from unittest.mock import mock_open


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "utils" / "generate_logs.py"


def run_generate_logs(monkeypatch):
    dumped = {}
    opened = []
    printed = []

    def fake_dump(data, file_obj, indent):
        dumped["data"] = data
        dumped["file_obj"] = file_obj
        dumped["indent"] = indent

    def fake_choice(options):
        return options[0]

    def fake_print(*args, **kwargs):
        printed.append((args, kwargs))

    mocked_open = mock_open()
    monkeypatch.setattr("json.dump", fake_dump)
    monkeypatch.setattr("random.choice", fake_choice)
    monkeypatch.setattr("builtins.print", fake_print)
    monkeypatch.setattr(
        "builtins.open",
        lambda *args, **kwargs: opened.append((args, kwargs)) or mocked_open(*args, **kwargs),
    )

    namespace = runpy.run_path(str(SCRIPT_PATH), run_name="__test__")
    return namespace, dumped, opened, printed


def test_fill_template_replaces_known_placeholders(monkeypatch):
    namespace, _dumped, _opened, _printed = run_generate_logs(monkeypatch)

    result = namespace["fill_template"](
        "ORA-06502 numeric or value error in procedure {proc}"
    )

    assert result == "ORA-06502 numeric or value error in procedure LOAD_CUSTOMER"


def test_script_generates_and_writes_expected_logs(monkeypatch):
    namespace, dumped, opened, printed = run_generate_logs(monkeypatch)

    assert opened[0][0][0] == namespace["log_file"]
    assert opened[0][0][1] == "w"
    assert dumped["indent"] == 2
    assert len(dumped["data"]) == 10000
    assert dumped["data"][0] == {
        "log_id": "1",
        "message": "ORA-06502 numeric or value error in procedure LOAD_CUSTOMER",
        "service": "customer_etl",
        "severity": "ERROR",
    }
    assert dumped["data"][-1]["log_id"] == "10000"
    assert printed == [(( "Generated 10,000 log entries!",), {})]
