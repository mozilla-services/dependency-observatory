let httpRequest;
let parentsRequest;

const PACKAGE_PREFIX = '/package/';
const PARENTS_PREFIX = '/parents/';

window.onload = function() {
    let urlParams = new URLSearchParams(window.location.search);
    let pkg = urlParams.get('package');
    let ver = urlParams.get('version');
    // TODO do some sanity checking here?
    getPackageInfo(pkg, ver);
}

function getPackageInfo(pkg, ver) {
    httpRequest = new XMLHttpRequest();
    httpRequest.onreadystatechange = gotPackageInfo;
    httpRequest.open('GET', PACKAGE_PREFIX + pkg + '/' + ver);
    httpRequest.send();
}

function gotPackageInfo() {
    if (httpRequest.readyState === XMLHttpRequest.DONE) {
        if (httpRequest.status === 200) {
            const json = JSON.parse(httpRequest.responseText);
            setElement(json, 'package');
            setElement(json, 'version');
            setElement(json, 'npmsio_score');
            setElement(json, 'authors');
            setElement(json, 'contributors');
            setElement(json, 'immediate_deps');
            setElement(json, 'all_deps');
            setElement(json, 'directVulnsCritical_count');
            setElement(json, 'directVulnsHigh_count');
            setElement(json, 'directVulnsModerate_count');
            setElement(json, 'directVulnsLow_count');
            setElement(json, 'indirectVulnsCritical_count');
            setElement(json, 'indirectVulnsHigh_count');
            setElement(json, 'indirectVulnsModerate_count');
            setElement(json, 'indirectVulnsLow_count');


            let score = calculate_score(json);
            document.getElementById('top_score').innerText = score;
            let grade = get_grade(score);
            document.getElementById("scan-grade-letter").innerText = grade;
            document.getElementById("scan-grade-container").className += " grade-" + grade.toLowerCase();

            let table = document.getElementById("deps");
            let depJson = json['dependencies'];
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

        } else {
            let node = document.getElementById('div1');
            let newNode = document.createElement('p');
            newNode.appendChild(document.createTextNode('There was a problem with the request.'));
            node.appendChild(newNode);
        }
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
    if (json["directVulnsCritical_count"] > 0) {
        score -=20;
    }
    if (json["directVulnsHigh_count"] > 0) {
        score -=10;
    }
    if (json["directVulnsModerate_count"] > 0) {
        score -=5;
    }
    if (json["indirectVulnsCritical_count"] > 0) {
        score -=10;
    }
    if (json["indirectVulnsHigh_count"] > 0) {
        score -=7;
    }
    if (json["indirectVulnsModerate_count"] > 0) {
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
        parentsRequest = new XMLHttpRequest();
        parentsRequest.onreadystatechange = gotParentsInfo;
        parentsRequest.open('GET', PARENTS_PREFIX + pkg + '/' + ver);
        parentsRequest.send();
    } else {
        while(table.hasChildNodes()) {
           table.removeChild(table.firstChild);
        }
    }
}

function gotParentsInfo() {
    if (parentsRequest.readyState === XMLHttpRequest.DONE) {
        if (parentsRequest.status === 200) {
            let table = document.getElementById("parenttable");
            const json = JSON.parse(parentsRequest.responseText);
            let parentsJson = json['parents'];
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

        } else {
            let node = document.getElementById('div1');
            let newNode = document.createElement('p');
            newNode.appendChild(document.createTextNode('There was a problem with the request.'));
            node.appendChild(newNode);
        }
    }
}

function setElement(json, elem) {
    document.getElementById(elem).innerText = json[elem];
}