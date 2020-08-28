function updateHistogram() {
  var spec = "/statistics/histogram.vg.json";
  vegaEmbed("#score_code_histogram", spec, { ast: true })
    .then(function (result) {
      // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
    })
    .catch(console.error);
}

function updateDist() {
  var spec = "/statistics/distribution.vg.json";
  vegaEmbed("#score_distribution", spec, { ast: true })
    .then(function (result) {
      // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
    })
    .catch(console.error);
}

updateHistogram();
updateDist();
