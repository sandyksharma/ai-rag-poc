import json

from utils.log_parser import load_logs


def test_load_logs_reads_json_file(tmp_path):
    log_file = tmp_path / "logs.json"
    expected = [{"log_id": "1", "message": "failure"}]
    log_file.write_text(json.dumps(expected))

    assert load_logs(log_file) == expected
