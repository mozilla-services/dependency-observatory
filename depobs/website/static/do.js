const PACKAGE_PREFIX = '/package';
const PARENTS_PREFIX = '/parents';
const VULNERABILITIES_PREFIX = '/vulnerabilities';

function getLinkURL(name, version) {
    return '/?manager=npm&package=' + encodeURIComponent(name) + '&version=' + encodeURIComponent(version);
}

function getPrefixedURL(prefix, name, version) {
    let url = prefix + '?package_name=' + encodeURIComponent(name);
    if (version !== null) {
	url = url  + '&package_version=' + encodeURIComponent(version);
    }
    return url;
}

window.onload = function() {
    let urlParams = new URLSearchParams(window.location.search);
    let pkg = urlParams.get('package');
    let ver = urlParams.get('version');
    // TODO do some more sanity checking here?
    if (! pkg) {
        // No request, show the form
        document.getElementById('no-scan').className = "";
    } else {
        getPackageInfo(pkg, ver);
    }
    document.getElementById('parents').onclick = toggleParents;
};

function getPackageInfo(pkg, ver) {
    fetch(getPrefixedURL(PACKAGE_PREFIX, pkg, ver))
        .then((response) => {
            if (response.status == 200) {
                document.getElementById('scan-started').className = "d-none";
                response.json().then(function(pkgInfo) {
                    gotPackageInfo(pkgInfo);
                });
            } else if (response.status == 202) {
                document.getElementById('scan-started').className = "";
                setTimeout(getPackageInfo, 5000, pkg, ver);
            } else if (response.status == 404) {
                // Show an error an the form
                document.getElementById('scan-started').className = "d-none";
                document.getElementById('no-package').className = "";
                document.getElementById('no-scan').className = "";
                response.json().then(function(jsonError) {
                    document.getElementById('no-package-error').innerText = jsonError.description;
                });
            } else {
                document.getElementById('scan-started').className = "d-none";
                document.getElementById('no-package').className = "";
                document.getElementById('no-scan').className = "";
                response.json().then(function(jsonError) {
                    document.getElementById('no-package-error').innerText = jsonError.description;
                });
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
    let info = 0;

    let pkgLink = 'https://www.npmjs.com/package/' + pkgInfo['package'] +'/v/' + pkgInfo['version'];

    setElementLink(pkgInfo, 'package', pkgLink);
    setElement(pkgInfo, 'version');
    let npmsio_score = pkgInfo['npmsio_score'];
    if (npmsio_score) {
        setElementLink(pkgInfo, 'npmsio_score',
            'https://api.npms.io/v2/package/' + encodeURIComponent(pkgInfo['package']),
            val=npmsio_score.toFixed(2), title='JSON output from NPM including the NPMS IO Score');
    }
    if (pkgInfo.hasOwnProperty('npmsio_scored_package_version')
	&& pkgInfo['npmsio_scored_package_version'] !== pkgInfo["version"]) {
	setElement(pkgInfo, 'npmsio_scored_package_version');
        document.getElementById('outdated-npmsio-score-warning').classList.remove("d-none");
    } else {
	setElement(pkgInfo, 'npmsio_scored_package_version');
        document.getElementById('outdated-npmsio-score-warning').classList.add("d-none");
    }
    setElement(pkgInfo, 'authors');
    setElement(pkgInfo, 'contributors');
    setElement(pkgInfo, 'immediate_deps');
    setElement(pkgInfo, 'all_deps');
    fail += setElement(pkgInfo, 'directVulnsCritical_score');
    fail += setElement(pkgInfo, 'directVulnsHigh_score');
    warn += setElement(pkgInfo, 'directVulnsMedium_score');
    info += setElement(pkgInfo, 'directVulnsLow_score');
    fail += setElement(pkgInfo, 'indirectVulnsCritical_score');
    fail += setElement(pkgInfo, 'indirectVulnsHigh_score');
    warn += setElement(pkgInfo, 'indirectVulnsMedium_score');
    info += setElement(pkgInfo, 'indirectVulnsLow_score');

    const vulnHeader = document.getElementById("vuln-header");
    console.log('Fail ' + fail + ' warn ' + warn + ' info ' + info);
    if (fail > 0) {
        vulnHeader.className += " bg-danger text-white";
    } else if (warn > 0) {
        vulnHeader.className += " bg-warning text-dark";
    } else if (info > 0) {
        vulnHeader.className += " bg-info text-white";
    } else {
        vulnHeader.className += " bg-success text-white";
    }

    let score = calculate_score(pkgInfo, document.getElementById("scoring"));
    document.getElementById('top_score').innerText = score;
    let grade = pkgInfo["score_code"];
    document.getElementById("scan-grade-letter").innerText = grade;
    document.getElementById("scan-grade-container").className += " grade-" + grade.toLowerCase();

    let table = document.getElementById("deps");
    let depJson = pkgInfo['dependencies'];
    for(let i = 0; i < depJson.length; i++) {
        let pkg = depJson[i]['package'];
        let ver = depJson[i]['version'];
        let score = calculate_score(depJson[i]);
        let grade = depJson[i]['score_code'];

        let row = table.insertRow(i+2);
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
        cell = row.insertCell(5);
        cell.innerText = int_or_blank(depJson[i]['directVulnsCritical_score'] + depJson[i]['indirectVulnsCritical_score']);
        cell = row.insertCell(6);
        cell.innerText = int_or_blank(depJson[i]['directVulnsHigh_score'] + depJson[i]['indirectVulnsHigh_score']);
        cell = row.insertCell(7);
        cell.innerText = int_or_blank(depJson[i]['directVulnsMedium_score'] + depJson[i]['indirectVulnsMedium_score']);
        cell = row.insertCell(8);
        cell.innerText = int_or_blank(depJson[i]['directVulnsLow_score'] + depJson[i]['indirectVulnsLow_score']);
    }
    if (pkgInfo['directVulnsCritical_score'] + pkgInfo['directVulnsHigh_score'] +
            pkgInfo['directVulnsMedium_score'] + pkgInfo['directVulnsLow_score'] > 0) {
        // This package has some vulnerabilities, so show them
        fetch(getPrefixedURL(VULNERABILITIES_PREFIX, pkgInfo['package'], pkgInfo['version']))
            .then((response) => {
                if (response.status == 200) {
                    response.json().then(function(vulnInfo) {
                        gotVulnerabilitiesInfo(vulnInfo);
                    });
                }
             })
            .then((data) => {
                console.log(data);
             });
    }

}

function gotVulnerabilitiesInfo(vulnInfo) {
    let table = document.getElementById("vulns");
    let vulnJson = vulnInfo['vulnerabilities'];

    for(let i = 0; i < vulnJson.length; i++) {
        let row = table.insertRow(i);
        let cell = row.insertCell(0);

        var div = document.createElement('div');
        var severity = vulnJson[i].severity;
        if (severity === 'low') {
            div.setAttribute('class', 'bg-info text-light text-center');
        } else if (severity === 'medium') {
            div.setAttribute('class', 'bg-warning text-dark text-center');
        } else if (severity === 'high') {
            div.setAttribute('class', 'bg-danger text-light text-center');
        } else if (severity === 'critical') {
            div.setAttribute('class', 'bg-danger text-light text-center');
        } else {
            div.setAttribute('class', 'bg-warning text-dark text-center');
        }
        div.textContent = vulnJson[i].severity.toUpperCase();
        cell.appendChild(div);

        cell = row.insertCell(1);
        a = document.createElement('a');
        a.appendChild(document.createTextNode(vulnJson[i].title));
        a.title = vulnJson[i].title;
        a.href = vulnJson[i].url;
        cell.appendChild(a);
    }
}

function int_or_blank(n) {
    if (n === 0) {
        return '';
    }
    return n;
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
    let total = calculate_element_score(json, 0, parseInt(json["npmsio_score"] * 100), scoringElem, i++, 'NPMSIO Score x 100');
    let all_deps = json["all_deps"];
    if (all_deps <= 5) {
        total = calculate_element_score(json, total, 20, scoringElem, i++, 'All dependencies <= 5');
    } else if (all_deps <= 20) {
        total = calculate_element_score(json, total, 10, scoringElem, i++, 'All dependencies <= 20');
    } else if (all_deps >= 500) {
        total = calculate_element_score(json, total, -20, scoringElem, i++, 'All dependencies >= 500');
    } else if (all_deps >= 100) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'All dependencies >= 100');
    }

    if (json["directVulnsCritical_score"] > 0) {
        total = calculate_element_score(json, total, -20, scoringElem, i++, 'Critical vulnerability in package');
    }
    if (json["directVulnsHigh_score"] > 0) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'High vulnerability in package');
    }
    if (json["directVulnsMedium_score"] > 0) {
        total = calculate_element_score(json, total, -5, scoringElem, i++, 'Medium vulnerability in package');
    }
    if (json["indirectVulnsCritical_score"] > 0) {
        total = calculate_element_score(json, total, -10, scoringElem, i++, 'Critical vulnerability in dependency');
    }
    if (json["indirectVulnsHigh_score"] > 0) {
        total = calculate_element_score(json, total, -7, scoringElem, i++, 'High vulnerability in dependency');
    }
    if (json["indirectVulnsMedium_score"] > 0) {
        total = calculate_element_score(json, total, -3, scoringElem, i++, 'Medium vulnerability in dependency');
    }
    if (scoringElem) {
        calculate_element_score(json, 0, total, scoringElem, i++, 'Total');
    }
    return total;
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

function setElementLink(json, elem, link, val='', title='') {
    const el = document.getElementById(elem);
    if (val === '') {
        val = json[elem];
    }
    if (el) {
        let a = document.createElement('a');
        let linkText = document.createTextNode(val);
        a.appendChild(linkText);
        a.href = link;
        a.title = title;
        el.appendChild(a);
    } else {
        console.log('No element for id: ' + elem);
    }
    return val;
}
