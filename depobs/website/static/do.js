window.onload = function() {
    let urlParams = new URLSearchParams(window.location.search);
    let pkg = urlParams.get('package');
    let ver = urlParams.get('version');
    // TODO do some sanity checking here?
    getPackageInfo(pkg, ver);
}

let httpRequest;

function getPackageInfo(pkg, ver) {
    httpRequest = new XMLHttpRequest();
    httpRequest.onreadystatechange = gotPackageInfo;
    httpRequest.open('GET', 'https://depobs.dev.mozaws.net/package/' + pkg + '/' + ver);
    httpRequest.send();
}

function gotPackageInfo() {
    if (httpRequest.readyState === XMLHttpRequest.DONE) {
        if (httpRequest.status === 200) {
            const json = JSON.parse(httpRequest.responseText);
            setElement(json, 'package');
            setElement(json, 'version');
            setElement(json, 'top_score');
            //setElement(json, 'npms_io_score');
            setElement(json, 'authors');
            setElement(json, 'contributors');
            setElement(json, 'immediate_deps');
            setElement(json, 'all_deps');

            let depJson = json['dependencies'];
            for(let i = 0; i < depJson.length; i++) {
                let table = document.getElementById("deps");
                let pkg = depJson[i]['package'];
                let ver = depJson[i]['version'];

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
                cell.innerText = depJson[i]['top_score'];
                cell = row.insertCell(3);
                cell.innerText = depJson[i]['direct_dep_count'];
                cell = row.insertCell(4);
                cell.innerText = depJson[i]['all_dep_count'];
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