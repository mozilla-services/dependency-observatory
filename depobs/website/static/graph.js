document.getElementById("histScoringView").onchange = function() {updateHist()};
document.getElementById("distScoringView").onchange = function() {updateDist()};

function updateHist() {
  var scoring_algorithm = document.getElementById("histScoringView").value;
  var img = document.getElementById("histogram_image");
  var table_latest = document.getElementById("score_table_latest")
  var table_v0 = document.getElementById("score_table_v0")

  if (scoring_algorithm == "v0") {
    img.src = "/histogram_v0.png";
    table_latest.hidden = true;
    table_v0.hidden = false;
  } else {
    img.src = "/histogram.png";
    table_latest.hidden = false;
    table_v0.hidden = true;
  }
}

function updateDist() {
  var scoring_algorithm = document.getElementById("distScoringView").value;
  var img = document.getElementById("distribution_image");
  if (scoring_algorithm == "v0") {
    img.src = "/distribution_v0.png";
  } else {
    img.src = "/distribution.png";
  }
}
