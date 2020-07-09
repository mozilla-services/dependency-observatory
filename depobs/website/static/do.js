async function startJob(args) {
  let jobURI = "/api/v1/jobs";
  let body = {
    name: "scan_score_npm_package",
    args: [args["package_name"], args["package_version"]],
  };
  console.debug("starting job with req body:", body);

  let response = await fetch(jobURI, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }).catch((err) => {
    console.error(`error POSTing to ${jobURI}: ${err}`);
    throw err;
  });
  if (response.status !== 200) {
    let err = new Error(`${response.status} from ${jobURI}`);
    err.response = response;
    throw err;
  }
  console.log("start job response: ", response);
  let responseJSON = await response.json();

  console.log("start job response JSON: ", responseJSON);
  return responseJSON;
}

async function checkReportExists(formData) {
  // check for a package report
  let queryParams = new URLSearchParams(formData);
  let reportURI = `/package_report?${queryParams}`;
  let response = await fetch(reportURI, {
    method: "HEAD",
  });
  return response;
}

// view / UI code

const formEl = document.getElementById("search-form");
const formFieldsetEls = formEl.querySelectorAll("fieldset");

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
      fieldsetEl.setAttribute("disabled", "disabled")
    );
  } else {
    console.debug("enabling search form");
    formFieldsetEls.forEach((fieldsetEl) =>
      fieldsetEl.removeAttribute("disabled")
    );
  }
}

async function scanAndScorePackage(formDataObj) {
  console.debug("starting job with data:", formDataObj);
  let startJobResponseJSON = await startJob(formDataObj);
  let jobName = startJobResponseJSON.metadata.labels["job-name"];
  console.log(
    `created job with name: ${jobName} and URL: ${window.location.origin}/api/v1/jobs/${jobName}`
  );
  return jobName;
}

function redirectToJobLogs(jobName) {
  let jobLogsURI = `/jobs/${jobName}/logs`;
  console.log(
    `redirecting to tail logs at ${window.location.origin}${jobLogsURI}`
  );
  window.location.assign(jobLogsURI);
}

function onSubmit(event) {
  console.debug(`form submitted! timestamp: ${event.timeStamp}`);
  event.preventDefault();
  updateSearchError(null); // clear error display

  let formData = new FormData(formEl);
  let formDataObj = Object.fromEntries(formData);
  console.debug("have formdata", formDataObj);

  if (formDataObj.force_rescan === "on") {
    console.debug("skipping report check since rescan requested");
    scanAndScorePackage(formDataObj)
      .then(redirectToJobLogs)
      .catch((err) => {
        console.error(`error starting rescan: ${err}`);
        updateSearchError(err, "rescanning a package");
      });
  } else {
    updateSearchForm(true); // disable the search form
    checkReportExists(formData)
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
          scanAndScorePackage(formDataObj)
            .then(redirectToJobLogs)
            .catch((err) => {
              console.error(`error starting scan: ${err}`);
              updateSearchError(err, "scanning a package");
            });
        }
      });
  }
}

window.addEventListener("DOMContentLoaded", (event) => {
  console.debug("DOM fully loaded and parsed");

  // bind
  formEl.addEventListener("submit", onSubmit);
});
