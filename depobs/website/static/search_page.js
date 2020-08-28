function formDataToDepFilesScanBody(formData) {
  console.debug("converting formData to dep files scan:", formData);
  let body = {
    scan_type: "scan_score_npm_dep_files",
    package_manager: formData.package_manager,
    manifest_url: formData.manifest_url,
  };
  if (formData.lockfile_url) {
    console.debug("adding lockfile_url to body");
    body.lockfile_url = formData.lockfile_url;
  }
  if (formData.shrinkwrap_url) {
    console.debug("adding shrinkwrap_url to body");
    body.shrinkwrap_url = formData.shrinkwrap_url;
  }
  return body;
}

function formDataToPackageScanBody(formData) {
  console.debug("converting formData to package scan:", formData);
  let body = {
    scan_type: "scan_score_npm_package",
    package_manager: formData.package_manager,
    package_name: formData.package_name,
    package_versions_type: formData.package_versions_type,
  };
  if (formData.package_versions_type === "specific-version") {
    console.debug("adding package_version to body");
    body.package_version = formData.package_version;
  }
  return body;
}

async function startScan(body) {
  let scanURI = "/api/v1/scans";
  console.debug("starting scan with req body:", body);

  let response = await fetch(scanURI, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }).catch((err) => {
    console.error(`error POSTing to ${scanURI}: ${err}`);
    throw err;
  });
  if (response.status !== 202) {
    let err = new Error(`${response.status} from ${scanURI}`);
    err.response = response;
    throw err;
  }
  console.log("start scan response: ", response);
  let responseJSON = await response.json();

  console.log("start scan response JSON: ", responseJSON);
  return responseJSON;
}

async function checkReportExists(formDataObj) {
  // check for a package report
  let queryParams = new URLSearchParams({
    package_name: formDataObj.package_name,
    package_version: formDataObj.package_version,
    package_manager: formDataObj.package_manager,
  });
  let reportURI = `/package_report?${queryParams}`;
  let response = await fetch(reportURI, {
    method: "HEAD",
  });
  return response;
}

async function checkChangelogExists(formDataObj) {
  // check for a package report
  let queryParams = new URLSearchParams({
    package_name: formDataObj.package_name,
    package_manager: formDataObj.package_manager,
  });
  let reportURI = `/package_changelog?${queryParams}`;
  let response = await fetch(reportURI, {
    method: "HEAD",
  });
  return response;
}

// view / UI code

const formEl = document.getElementById("package-form");
const formFieldsetEls = formEl.querySelectorAll("fieldset");
const formPackageVersionTypeEl = document.getElementById(
  "package-versions-type"
);
const formPackageVersionEl = document.getElementById("packageVersion");
const depFilesFormEl = document.getElementById("dep-files-form");

function updateSearchError(err, errContextMessage) {
  // takes an Error with an optional .response property set and
  // displays errContextMessage
  const errorEl = document.getElementById("search-error");
  const errorContextMessageEl = document.getElementById("error-context");
  const errorReqIDEl = document.getElementById("error-request-id");
  const errorIssueLinkEl = document.querySelector(".error-issue-link");

  if (errContextMessage) {
    errorContextMessageEl.textContent = errContextMessage;
  } else {
    errorContextMessageEl.textContent = "";
  }
  if (err) {
    errorEl.classList.remove("d-none");
  } else {
    errorEl.classList.add("d-none");
  }
  if (
    err &&
    err.response &&
    err.response.headers &&
    err.response.headers.get("x-request-id")
  ) {
    let requestID = err.response.headers.get("x-request-id");
    errorReqIDEl.textContent = requestID;
    errorIssueLinkEl.href = `https://github.com/mozilla-services/dependency-observatory/issues/new?title=error making request&body=request id: ${requestID}`;
  } else {
    errorReqIDEl.textContent = "";
    errorIssueLinkEl.href = `https://github.com/mozilla-services/dependency-observatory/issues/new?title=error making request&body=request id: replaceme`;
  }
}

function updateSearchForm(disable) {
  if (disable) {
    console.debug("disabling search form");
    formFieldsetEls.forEach((fieldsetEl) =>
      fieldsetEl.setAttribute("disabled", "")
    );
  } else {
    console.debug("enabling search form");
    formFieldsetEls.forEach((fieldsetEl) =>
      fieldsetEl.removeAttribute("disabled")
    );
  }
}

async function scanAndScore(body) {
  console.debug("starting scan with data:", body);
  let startScanResponseJSON = await startScan(body);
  let scanID = startScanResponseJSON.id;
  console.log(
    `created scan with name: ${scanID} and URL: ${window.location.origin}/api/v1/scans/${scanID}`
  );
  return scanID;
}

function redirectToScanLogs(scanID) {
  let scanLogsURI = `/scans/${scanID}/logs?refresh=1`;
  console.log(
    `redirecting to tail logs at ${window.location.origin}${scanLogsURI}`
  );
  window.location.assign(scanLogsURI);
}

function getFormDataObj() {
  let formDataObj = Object.fromEntries(new FormData(formEl));
  return formDataObj;
}

function onSubmit(event) {
  console.debug(`package scan form submitted! timestamp: ${event.timeStamp}`);
  event.preventDefault();
  updateSearchError(null); // clear error display

  let formDataObj = getFormDataObj();
  console.debug("have package scan formdata", formDataObj);

  if (formDataObj.force_rescan === "on") {
    console.debug("skipping report check since rescan requested");
    scanAndScore(formDataToPackageScanBody(formDataObj))
      .then(redirectToScanLogs)
      .catch((err) => {
        console.error(`error starting rescan: ${err}`);
        updateSearchError(err, "rescanning a package");
      });
  } else if (!formDataObj.package_version) {
    console.debug(
      "checking for package changelog since package version not specified"
    );
    updateSearchForm(true); // disable the search form
    checkChangelogExists(formDataObj)
      .catch((err) => {
        updateSearchForm(false); // enable the search form
        console.error(`error checking changelog exists: ${err}`);
        updateSearchError(err, "checking a package changelog exists");
      })
      .then((response) => {
        updateSearchForm(false); // enable the search form
        if (response.status === 200) {
          // redirect to changelog if it exists
          console.debug(`changelog exists redirecting to ${response.url}`);
          window.location.assign(response.url);
        } else if (response.status !== 404) {
          // something unexpected display an error for non-404 errors
          let err = new Error();
          err.response = response;
          updateSearchError(err, "checking a package changelog exists");
        } else {
          scanAndScore(formDataToPackageScanBody(formDataObj))
            .then(redirectToScanLogs)
            .catch((err) => {
              console.error(`error starting scan: ${err}`);
              updateSearchError(err, "scanning a package");
            });
        }
      });
  } else {
    updateSearchForm(true); // disable the search form
    checkReportExists(formDataObj)
      .catch((err) => {
        updateSearchForm(false); // enable the search form
        console.error(`error checking report exists: ${err}`);
        updateSearchError(err, "checking a package report exists");
      })
      .then((response) => {
        updateSearchForm(false); // enable the search form

        if (response.status === 200) {
          // redirect to report if it exists
          console.debug(`report exists redirecting to ${response.url}`);
          window.location.assign(response.url);
          // } else if (response.status === 422) {
          //   // TODO: display the error message for malformed requests
          //   // updateSearchError(true, "checking a package report exists", response.headers.get("x-request-id"));
        } else if (response.status !== 404) {
          // something unexpected display an error for non-404 errors
          let err = new Error();
          err.response = response;
          updateSearchError(err, "checking a package report exists");
        } else {
          scanAndScore(formDataToPackageScanBody(formDataObj))
            .then(redirectToScanLogs)
            .catch((err) => {
              console.error(`error starting scan: ${err}`);
              updateSearchError(err, "scanning a package");
            });
        }
      });
  }
}

function updatePackageVersionInput(e) {
  // enable the package version text input when package versions type is specific-version
  if (e.target.value === "specific-version") {
    formPackageVersionEl.removeAttribute("disabled");
  } else {
    formPackageVersionEl.setAttribute("disabled", "");
  }
}

function onDepFilesFormSubmit(e) {
  console.debug(`dep files scan form submitted! timestamp: ${event.timeStamp}`);
  event.preventDefault();

  let formDataObj = Object.fromEntries(new FormData(depFilesFormEl));
  console.debug("have dep files scan formdata", formDataObj);
  scanAndScore(formDataToDepFilesScanBody(formDataObj))
    .then(redirectToScanLogs)
    .catch((err) => {
      console.error(`error starting dep files scan: ${err}`);
      updateSearchError(err, "scanning a dep files");
    });
}

window.addEventListener("DOMContentLoaded", (event) => {
  console.debug("DOM fully loaded and parsed");

  formPackageVersionTypeEl.addEventListener(
    "change",
    updatePackageVersionInput
  );
  // browser can preserve form data
  let formDataObj = getFormDataObj();
  if (formDataObj.package_versions_type === "specific-version") {
    formPackageVersionEl.removeAttribute("disabled");
  }
  formEl.addEventListener("submit", onSubmit);

  depFilesFormEl.addEventListener("submit", onDepFilesFormSubmit);
});
