import pytest

import depobs.worker.tasks.start_scan as m


invalid_scan_test_cases = {
    "scan_score_npm_package": (
        dict(
            status=m.ScanStatusEnum["started"],
            params={
                "name": "scan_score_npm_package",
                "args": ["test-pkg", "0.0.0"],
                "kwargs": {},
            },
        ),
        m.ScanStatusEnum["failed"],
    ),
    "scan_score_npm_dep_files": (
        dict(
            status=m.ScanStatusEnum["started"],
            params={
                "name": "scan_score_npm_dep_files",
                "args": [],
                "kwargs": {
                    "dep_file_urls": [
                        {
                            "url": "https://raw.githubusercontent.com/mozilla-services/ip-reputation-js-client/master/package.json",
                            "filename": "package.json",
                        }
                    ]
                },
            },
        ),
        m.ScanStatusEnum["failed"],
    ),
}


# @pytest.mark.asyncio
# @pytest.mark.unit
# @pytest.mark.parametrize(
#     "scan_kwargs, new_scan_status",
#     invalid_scan_test_cases.values(),
#     ids=invalid_scan_test_cases.keys(),
# )
# async def test_finish_scan(app, models, scan_kwargs):
#     scan = await m.finish_scan(models.Scan(**scan_kwargs))
#     assert scan.status == new_scan_status
