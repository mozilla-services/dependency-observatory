# Past Supply Chain Attacks/Incidents

- Valid cases for SSH key access
- Valid cases for Pastebin access

### Template
- **Language/Ecosystem**:
- **Package Manager (and version)**:
- **Package Versioning Scheme (if any) e.g. semver, calver**:
- **Indicators of Compromise (URLs, shasums; vulnerable versions)**:
- **Threat Model**:
  - Malicious Packages (TM-mal)
  - Exploiting Unmaintained Legacy Code (TM-leg)
  - Package Takeover (TM-pkg)
  - Account Takeover (TM-acc)
  - Collusion Attack (TM-coll)
- **Evasion Techniques used (if any) process hollowing, etc.**:
- **General/Targeted**:
- **Attacker Motivation**:
- **Mitigations**:

## [`left-pad`](https://blog.npmjs.org/post/141577284765/kik-left-pad-and-npm) - Mar 22 2016
- **Language/Ecosystem**: Node.js
- **Package Manager**: npm
- **Package Versioning Scheme**: semver
- **Indicators of Compromise**: Failing dependency resolutions
- **Threat Model**: Package Takeover (TM-pkg)
- **Evasion Techniques**:
- **General/Targeted**: General
- **Attacker Motivation**: Mistake/not intended to be an attack
- **Mitigations**: Republishing the package, make it more difficult to un-publish

#### Notes
- There was a dispute over the package name `kik`. When the developer involved did not get to keep the name, they unpublished a large number of their packages, including the popular `left-pad` package.
- This caused thousands of dependency resolutions to fail
- Another user then republished the package, but since they published as version `1.0.0` when lots of packages specifically required version `0.0.3`, lots of resolutions continued to fail
- Eventually the package was republished as version `0.0.3`
- It was too easy for someone to unpublish a package

## [`getcookies`](https://blog.npmjs.org/post/173526807575/reported-malicious-module-getcookies) - May 2 2018
- **Language/Ecosystem**: Node.js
- **Package Manager**: npm
- **Package Versioning Scheme**: semver
- **Indicators of Compromise**: Report from community
- **Threat Model**: Malicious Packages (TM-mal)
- **Evasion Techniques**: Obfuscated the back door a bit
- **General/Targeted**: General
- **Attacker Motivation**: RCE
- **Mitigations**: Remove malicious user and package, un-publish affected packages and packager versions

#### Notes
- A user published the `getcookies` module that contained a backdoor which could result in the attacker getting RCE
  - The dependency tree for a very popular package (`mailparser`) contained `getcookies`
  ```
  mailparser
  └── http-fetch-cookies
       └── express-cookies
            └── getcookies
  ```

## [`event-stream`](https://blog.npmjs.org/post/173526807575/reported-malicious-module-getcookies) - Nov 26 2018
- **Language/Ecosystem**: Node.js
- **Package Manager**: npm
- **Package Versioning Scheme**: semver
- **Indicators of Compromise**: Malicious code found in package source
- **Threat Model**: Package Takeover (TM-pkg)
- **Evasion Techniques**: Hiding the code from the public repository, minifying/obfuscating
- **General/Targeted**: Targeted
- **Attacker Motivation**:
- **Mitigations**: Turn on CSP,

#### Notes
- A malicious user gained the trust of a package maintainer, then added a dependency on a malicious package they created specifically for the attack
- The malicious code was in the published package, but was not contained in the public Git repo
- There is no requirement that the code in an npm module needs to match the code in a Git repo
- The malicious package attempted to steal Bitcoin

## [`eslint`](https://eslint.org/blog/2018/07/postmortem-for-malicious-package-publishes) - Jul 12 2018
- **Language/Ecosystem**: Node.js
- **Package Manager**: npm
- **Package Versioning Scheme**: semver
- **Indicators of Compromise**: Issue on GitHub
- **Threat Model**: Account Takeover (TM-acc)
- **Evasion Techniques**: Downloaded the malicious code from Pastebin rather than having the raw source in the package
- **General/Targeted**: Targeted
- **Attacker Motivation**: Gain npm credentials
- **Mitigations**: Enable 2FA, use password managers

#### Notes
- A maintainer's account was compromised and was used to publish a malicious version of the package
- The malicious code would then send the attackers the user's `.npmrc` file, which usually contains authorization tokens

## [Octopus Scanner](https://securitylab.github.com/research/octopus-scanner-malware-open-source-supply-chain) - Mar 9 2020
- **Language/Ecosystem**: GitHub
- **Package Manager**:
- **Package Versioning Scheme**:
- **Indicators of Compromise**: Notification from researcher
- **Threat Model**: Malicious Packages (TM-mal)
- **Evasion Techniques**: Hide the malicious JAR as a text file
- **General/Targeted**: General
- **Attacker Motivation**: Get control of infected machines
- **Mitigations**:

#### Notes
- The malware would infect Java projects in NetBeans and drop a RAT
- Uses the build process to establish persistence and spread itself

## Other smaller incidents
- [`stream-combine`](https://www.npmjs.com/advisories/774) - Jan 25 2019
  - Steals data then sends it back to remote server
- [`portionfatty12`](https://snyk.io/vuln/SNYK-JS-PORTIONFATTY12-73508) - Jan 11 2019
  - Sends the content of your public key to a remote server
- [`rrgod`](https://snyk.io/vuln/SNYK-JS-RRGOD-73507) - Jan 10 2019
  - The package downloads and executes a python script from the internet
- [`text-qrcode`](https://snyk.io/vuln/SNYK-JS-TEXTQRCODE-73501) - Nov 29 2018
  - Malicious code that overwrites a `randomBytes` method to reduce the bytes of entropy from 32 to 3
- [`commander-js`](https://snyk.io/vuln/SNYK-JS-COMMANDERJS-73506) - Jan 9 2019
  - Has a postinstall script that downloads and evaluates a JSON file from the internet
- [`discordi.js`](https://snyk.io/vuln/npm:discordi.js:20171009) - Oct 9 2017
  - Steals Discord credentials and sends them to Pastebin
- [`jquey`](https://snyk.io/vuln/npm:jquey:20171006) - Oct 4 2017
  - - Steals SSH keys and bash history and sends it to remote server
- [`coffescript`](https://snyk.io/vuln/npm:coffescript:20171006) - Aug 2 2017
  - Steals SSH keys and bash history and sends it to remote server
- [`boogeyman`](https://snyk.io/vuln/SNYK-JS-BOOGEYMAN-173686) - Jul 31 2018
  - Steals SSH keys and `.npmrc` after downloading payload from Pastebin
