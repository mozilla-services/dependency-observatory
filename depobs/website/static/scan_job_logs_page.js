window.addEventListener("DOMContentLoaded", (event) => {
  console.debug("DOM fully loaded and parsed");

  // when refresh query param is truthy, reload the scan logs page if
  // the scan completes successfully (as indicated by a #report-url
  // element present redirect to the report URL)
  let searchParams = new URLSearchParams(window.location.search);
  console.debug("refresh?", searchParams.get("refresh"));
  if (searchParams.get("refresh")) {
    var refreshURL;
    // unhide the refresh message
    document.getElementById("page-refresh-message").classList.remove("d-none");

    console.debug("report-url?", document.getElementById("report-url"));
    if (document.getElementById("report-url")) {
      console.debug(
        "refreshing to report-url in 5s",
        document.getElementById("report-url").href
      );
      refreshURL = document.getElementById("report-url").href;
    } else {
      console.debug("refreshing scan job logs in 5s", window.location.pathname);
      refreshURL = window.location.href;
    }
    window.setTimeout(
      (refreshURL) => {
        window.location.href = refreshURL;
      },
      5000,
      refreshURL
    );
  }
});
