const PACKAGE_PREFIX = '/package';
const PARENTS_PREFIX = '/parents';

function getLinkURL(name, version) {
    return '/?manager=npm&package=' + encodeURIComponent(name) + '&version=' + encodeURIComponent(version);
}

function getPrefixedURL(prefix, name, version) {
    return prefix + '?package_name=' + encodeURIComponent(name) + '&package_version=' + encodeURIComponent(version);
}

window.onload = function() {
    let urlParams = new URLSearchParams(window.location.search);
    let pkg = urlParams.get('package');
    let ver = urlParams.get('version');
    // TODO do some more sanity checking here?
    if (pkg == null) {
        // No request, show the form
        document.getElementById('no-scan').className = "";
    } else {
        getPackageInfo(pkg, ver);
    }
}

function getPackageInfo(pkg, ver) {
    fetch(getPrefixedURL(PACKAGE_PREFIX, pkg, ver))
        .then((response) => {
            if (response.status == 200) {
                response.json().then(function(pkgInfo) {
                    gotPackageInfo(pkgInfo);
                });
            } else if (response.status == 202) {
                document.getElementById('scan-started').className = "";
            } else if (response.status == 404) {
                // Show an error an the form
                document.getElementById('no-package').className = "";
                document.getElementById('no-scan').className = "";
            } else {
                document.getElementById('scan-error').className = "";
            }
         })
        .then((data) => {
            console.log(data);
         });
}

function gotPackageInfo(pkgInfo) {
    document.getElementById('scan-results').className = "";
    let fail = 0;
    let warn = 0;
    setElement(pkgInfo, 'package');
    setElement(pkgInfo, 'version');
    setElement(pkgInfo, 'npmsio_score');
    setElement(pkgInfo, 'authors');
    setElement(pkgInfo, 'contributors');
    setElement(pkgInfo, 'immediate_deps');
    setElement(pkgInfo, 'all_deps');
    fail += setElement(pkgInfo, 'directVulnsCritical_score');
    fail += setElement(pkgInfo, 'directVulnsHigh_score');
    warn += setElement(pkgInfo, 'directVulnsMedium_score');
    warn += setElement(pkgInfo, 'directVulnsLow_score');
    fail += setElement(pkgInfo, 'indirectVulnsCritical_score');
    fail += setElement(pkgInfo, 'indirectVulnsHigh_score');
    warn += setElement(pkgInfo, 'indirectVulnsMedium_score');
    warn += setElement(pkgInfo, 'indirectVulnsLow_score');

    const vulnHeader = document.getElementById("vuln-header");
    console.log('Fail ' + fail + ' warn ' + warn);
    if (fail > 0) {
        vulnHeader.className += " bg-danger text-white";
    } else if (warn > 0) {
        vulnHeader.className += " bg-warning text-dark";
    } else {
        vulnHeader.className += " bg-success text-white";
    }

    let score = calculate_score(pkgInfo, document.getElementById("scoring"));
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
        let linkUrl = getLinkURL(pkg, ver);
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

function calculate_element_score(json, total, score, scoringElem, i, descText) {
    total += score;
    if (scoringElem) {
        row = scoringElem.insertRow(i);
        cell = row.insertCell(0);
        cell.appendChild(document.createTextNode(descText));
        cell = row.insertCell(1);
        cell.className = "text-right";
        if (score > 0) {
            cell.appendChild(document.createTextNode('+' + score));
        } else {
            cell.appendChild(document.createTextNode(score));
        }
    }
    return total;
}

function calculate_score(json, scoringElem) {
    let i = 0;
    let row;
    let cell;
    let total = calculate_element_score(json, 0, parseInt(json["npmsio_score"] * 100), scoringElem, i++, 'NPMSIO Score x 100')
    let all_deps = json["all_deps"];
    if (all_deps <= 5) {
        total = calculate_element_score(json, total, 20, scoringElem, i++, 'All dependencies <= 5')
    } else if (all_deps <= 20) {
        total = calculate_element_score(json, total, 10, scoringElem, i++, 'All dependencies <= 20')
    } else if (all_deps >= 500) {
        total = calculate_element_score(json, total, -20, scoringElem, i++, 'All dependencies >= 500')
    } else if (all_deps >= 100) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'All dependencies >= 100')
    }

    if (json["directVulnsCritical_score"] > 0) {
        total = calculate_element_score(json, total, -20, scoringElem, i++, 'Critical vulnerability in package')
    }
    if (json["directVulnsHigh_score"] > 0) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'High vulnerability in package')
    }
    if (json["directVulnsMedium_score"] > 0) {
        total = calculate_element_score(json, total, -5, scoringElem, i++, 'Medium vulnerability in package')
    }
    if (json["indirectVulnsCritical_score"] > 0) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'Critical vulnerability in dependency')
    }
    if (json["indirectVulnsHigh_score"] > 0) {
        total = calculate_element_score(json, total, -7, scoringElem, i++, 'High vulnerability in dependency')
    }
    if (json["indirectVulnsMedium_score"] > 0) {
        total = calculate_element_score(json, total, -3, scoringElem, i++, 'Medium vulnerability in dependency')
    }
    if (scoringElem) {
        calculate_element_score(json, 0, total, scoringElem, i++, 'Total')
    }
    return total;
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
    // Hide 'show parents' link
    document.getElementById('parents').className = "d-none";
    let table = document.getElementById("parenttable");
    if (table.rows.length === 0) {
        let urlParams = new URLSearchParams(window.location.search);
        let pkg = urlParams.get('package');
        let ver = urlParams.get('version');
        fetch(getPrefixedURL(PARENTS_PREFIX, pkg, ver))
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
    return false;
}

function gotParentsInfo(parInfo) {
    let table = document.getElementById("parenttable");
    let parentsJson = parInfo['parents'];
    if (parentsJson.length == 0) {
        document.getElementById('no-parents').className = "";
    } else {
        for(let i = 0; i < parentsJson.length; i++) {
            let pkg = parentsJson[i]['package'];
            let ver = parentsJson[i]['version'];
    
            let row = table.insertRow(i);
            let cell = row.insertCell(0);
            let linkUrl = getLinkURL(pkg, ver);
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
}

function setElement(json, elem) {
    const el = document.getElementById(elem);
    const val = json[elem];
    if (el) {
        el.innerText = val;
    } else {
        console.log('No element for id: ' + elem);
    }
    return val;
}
