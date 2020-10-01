import pytest

import depobs.worker.tasks.start_scan as m


invalid_scan_test_cases = {
    "no_params": (
        dict(status=m.ScanStatusEnum["queued"]),
        dict(
            status=m.ScanStatusEnum["failed"],
        ),
    ),
    "invalid_scan_name": (
        dict(
            status=m.ScanStatusEnum["queued"],
            params={"name": "scan_score_unsupported", "args": [], "kwargs": {}},
        ),
        dict(
            status=m.ScanStatusEnum["failed"],
        ),
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scan_kwargs, expected",
    invalid_scan_test_cases.values(),
    ids=invalid_scan_test_cases.keys(),
)
async def test_start_scan_fails_for_invalid_config(app, models, scan_kwargs, expected):
    started_scan = await m.start_scan(models.Scan(**scan_kwargs))
    assert started_scan.status == m.ScanStatusEnum["failed"]


scan_test_cases = {
    "scan_score_npm_package": dict(
        status=m.ScanStatusEnum["queued"],
        params={
            "name": "scan_score_npm_package",
            "args": ["ip-reputation-js-client", "latest"],
            "kwargs": {},
        },
    ),
    "scan_score_npm_dep_files": dict(
        status=m.ScanStatusEnum["queued"],
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
}


# @pytest.mark.asyncio
# @pytest.mark.unit
# @pytest.mark.parametrize(
#     "scan_kwargs",
#     scan_test_cases.values(),
#     ids=scan_test_cases.keys(),
# )
# async def test_start_scan_starts_job(mocker, app, models, scan_kwargs):
#     # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
#     k8s_mock = mocker.patch("depobs.worker.tasks.start_scan.k8s")
#     scan_cfg_mocks = [
#         mocker.patch("depobs.worker.tasks.start_scan.NPMDepFilesScan"),
#         mocker.patch("depobs.worker.tasks.start_scan.NPMPackageScan"),
#     ]

#     started_scan = await m.start_scan(models.Scan(**scan_kwargs))
#     assert started_scan.status == m.ScanStatusEnum["started"]

#     k8s_mock.create_job.assert_called()
#     # for scan_cfg_mock in scan_cfg_mocks:
#     #     assert scan_cfg_mock.assert_called()
