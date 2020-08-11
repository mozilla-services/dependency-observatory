document.getElementById("scoringView").onchange = function() {setPicture()};

function setPicture() {
  var scoring_algorithm = document.getElementById("scoringView").value;
  var img = document.getElementById("histogram_image");
  if (scoring_algorithm == "old") {
    img.src = "/histogram_old.png";
  } else {
    img.src = "/histogram.png";
  }
}
