var scoreCodeSpecEl = document.getElementById("deps_score_code_histogram");

vegaEmbed("#deps_score_code_histogram", scoreCodeSpecEl.dataset.src, {
  ast: true,
})
  .then(function (result) {
    // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
  })
  .catch(console.error);

var scoreSpecEl = document.getElementById("deps_score_histogram");

vegaEmbed("#deps_score_histogram", scoreSpecEl.dataset.src, { ast: true })
  .then(function (result) {
    // Access the Vega view instance (https://vega.github.io/vega/docs/api/view/) as result.view
  })
  .catch(console.error);
