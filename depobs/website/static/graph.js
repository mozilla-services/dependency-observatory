document.getElementById("histScoringView").onchange = function() {setHistPicture()};
document.getElementById("distScoringView").onchange = function() {setDistPicture()};

function setHistPicture() {
  var scoring_algorithm = document.getElementById("histScoringView").value;
  var img = document.getElementById("histogram_image");
  if (scoring_algorithm == "v0") {
    img.src = "/histogram_v0.png";
  } else {
    img.src = "/histogram.png";
  }
}

function setDistPicture() {
  var scoring_algorithm = document.getElementById("distScoringView").value;
  var img = document.getElementById("distribution_image");
  if (scoring_algorithm == "v0") {
    img.src = "/distribution_v0.png";
  } else {
    img.src = "/distribution.png";
  }
}
