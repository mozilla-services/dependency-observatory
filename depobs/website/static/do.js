const PACKAGE_PREFIX = '/package';
const PARENTS_PREFIX = '/parents';

window.onload = function() {
    let urlParams = new URLSearchParams(window.location.search);
    let pkg = urlParams.get('package');
    let ver = urlParams.get('version');
    // TODO do some sanity checking here?
    getPackageInfo(pkg, ver);
}

function getPackageInfo(pkg, ver) {
    fetch(PACKAGE_PREFIX + '?' + 'package_name=' + encodeURIComponent(pkg) + '&package_version=' + encodeURIComponent(ver))
        .then((response) => {
            if (response.status == 200) {
                response.json().then(function(pkgInfo) {
                    gotPackageInfo(pkgInfo);
                });
            } else if (response.status == 404) {
                document.getElementById('scan-started').className = "";
            } else {
                console.log(response);
            }
         })
        .then((data) => {
            console.log(data);
         });
}

function gotPackageInfo(pkgInfo) {
    document.getElementById('scan-results').className = "";
    setElement(pkgInfo, 'package');
    setElement(pkgInfo, 'version');
    setElement(pkgInfo, 'npmsio_score');
    setElement(pkgInfo, 'authors');
    setElement(pkgInfo, 'contributors');
    setElement(pkgInfo, 'immediate_deps');
    setElement(pkgInfo, 'all_deps');
    setElement(pkgInfo, 'directVulnsCritical_score');
    setElement(pkgInfo, 'directVulnsHigh_score');
    setElement(pkgInfo, 'directVulnsMedium_score');
    setElement(pkgInfo, 'directVulnsLow_score');
    setElement(pkgInfo, 'indirectVulnsCritical_score');
    setElement(pkgInfo, 'indirectVulnsHigh_score');
    setElement(pkgInfo, 'indirectVulnsMedium_score');
    setElement(pkgInfo, 'indirectVulnsLow_score');


    let score = calculate_score(pkgInfo);
    document.getElementById('top_score').innerText = score;
    let grade = get_grade(score);
    document.getElementById("scan-grade-letter").innerText = grade;
    document.getElementById("scan-grade-container").className += " grade-" + grade.toLowerCase();

    let table = document.getElementById("deps");
    let depJson = pkgInfo['dependencies'];
    for(let i = 0; i < depJson.length; i++) {
        let pkg = depJson[i]['package'];
        let ver = depJson[i]['version'];
        let score = calculate_score(depJson[i]);
        let grade = get_grade(score);

        let row = table.insertRow(i+1);
        let cell = row.insertCell(0);
        let linkUrl = 'results.html?manager=npm&package=' + pkg + '&version=' + ver;
        let a = document.createElement('a');
        let linkText = document.createTextNode(pkg);
        a.appendChild(linkText);
        a.title = "See package / version details";
        a.href = linkUrl;
        cell.appendChild(a);

        cell = row.insertCell(1);
        a = document.createElement('a');
        linkText = document.createTextNode(ver);
        a.appendChild(linkText);
        a.title = "See package / version details";
        a.href = linkUrl;
        cell.appendChild(a);

        cell = row.insertCell(2);
        cell.innerText = grade + " (" + score + ")";
        cell = row.insertCell(3);
        cell.innerText = depJson[i]['immediate_deps'];
        cell = row.insertCell(4);
        cell.innerText = depJson[i]['all_deps'];
    }
}

function calculate_score(json) {
    let score = json["npmsio_score"] * 100;
    let all_deps = json["all_deps"];
    if (all_deps <= 5) {
        score +=20;
    } else if (all_deps <= 20) {
        score +=10;
    } else if (all_deps >= 500) {
        score -=20;
    } else if (all_deps >= 100) {
        score -=10;
    }
    if (json["directVulnsCritical_score"] > 0) {
        score -=20;
    }
    if (json["directVulnsHigh_score"] > 0) {
        score -=10;
    }
    if (json["directVulnsModerate_score"] > 0) {
        score -=5;
    }
    if (json["indirectVulnsCritical_score"] > 0) {
        score -=10;
    }
    if (json["indirectVulnsHigh_score"] > 0) {
        score -=7;
    }
    if (json["indirectVulnsModerate_score"] > 0) {
        score -=3;
    }
    return parseInt(score);
}

function get_grade(score) {
    let grade;
    if (score >= 80) {
        grade = "A";
    } else if (score >= 60) {
        grade = "B";
    } else if (score >= 40) {
        grade = "C";
    } else if (score >= 20) {
        grade = "D";
    } else {
        grade = "E";
    }
    return grade;
}

function toggleParents() {
    let table = document.getElementById("parenttable");
    if (table.rows.length === 0) {
        let urlParams = new URLSearchParams(window.location.search);
        let pkg = urlParams.get('package');
        let ver = urlParams.get('version');
	    fetch(PARENTS_PREFIX + '?' + 'package_name=' + encodeURIComponent(pkg) + '&package_version=' + encodeURIComponent(ver))
	        .then((response) => {
	            if (response.status == 200) {
	                console.log(response);
                    response.json().then(function(parInfo) {
    	                gotParentsInfo(parInfo);
                    });
	            } else {
	                console.log(response);
	            }
	         })
	        .then((data) => {
	            console.log(data);
	         });


    } else {
        while(table.hasChildNodes()) {
           table.removeChild(table.firstChild);
        }
    }
}

function gotParentsInfo(parInfo) {
    let table = document.getElementById("parenttable");
    let parentsJson = parInfo['parents'];
    for(let i = 0; i < parentsJson.length; i++) {
        let pkg = parentsJson[i]['package'];
        let ver = parentsJson[i]['version'];

        let row = table.insertRow(i);
        let cell = row.insertCell(0);
        let linkUrl = 'results.html?manager=npm&package=' + pkg + '&version=' + ver;
        let a = document.createElement('a');
        let linkText = document.createTextNode(pkg);
        a.appendChild(linkText);
        a.title = "See package / version details";
        a.href = linkUrl;
        cell.appendChild(a);

        cell = row.insertCell(1);
        a = document.createElement('a');
        linkText = document.createTextNode(ver);
        a.appendChild(linkText);
        a.title = "See package / version details";
        a.href = linkUrl;
        cell.appendChild(a);
    }
}

function setElement(json, elem) {
    document.getElementById(elem).innerText = json[elem];
}
