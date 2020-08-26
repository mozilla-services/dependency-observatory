document.getElementById("histScoringView").onchange = function () {
  updateHistogram();
};
document.getElementById("distScoringView").onchange = function () {
  updateDist();
};

function updateHistogram() {
  var spec;
  var scoring_algorithm = document.getElementById("histScoringView").value;
  var img = document.getElementById("histogram_image");
  var table_latest = document.getElementById("score_table_latest");
  var table_v0 = document.getElementById("score_table_v0");

  if (scoring_algorithm == "v0") {
    spec = "/statistics/histogram_v0.vg.json";
    table_latest.hidden = true;
    table_v0.hidden = false;
  } else {
    spec = "/statistics/histogram.vg.json";
    table_latest.hidden = false;
    table_v0.hidden = true;
  }
  vegaEmbed("#score_code_histogram", spec, { ast: true })
    .then(function (result) {
      // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
    })
    .catch(console.error);
}

function updateDist() {
  var spec;
  var scoring_algorithm = document.getElementById("distScoringView").value;
  var img = document.getElementById("distribution_image");
  if (scoring_algorithm == "v0") {
    spec = "/statistics/distribution_v0.vg.json";
  } else {
    spec = "/statistics/distribution.vg.json";
  }
  vegaEmbed("#score_distribution", spec, { ast: true })
    .then(function (result) {
      // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
    })
    .catch(console.error);
}

updateHistogram();
updateDist();
