# Reading Notes

## [Small World with High Risks: A Study of Security Threats in the npm Ecosystem](https://www.usenix.org/system/files/sec19-zimmermann.pdf)

### Introduction

- Installing an average npm package will depend on the trust of 79 packages and 39 maintainers
- Up to 40% of all packages depend on code with at least one known vulnerability
- If we were to make 140 maintainers (out of 150,000) "trusted", it would halve the risk that comes from maintainers being compromised
- Vetting the code of new releases from the top 300 packages would reduce the risk by half

### Security risks in the npm Ecosystem

- Particularities of npm
  - **Locked dependencies**: dependencies for a package are outlined in `package.json` and specify a version (or range of versions) that are supported. This can lead to different packages and versions being installed across different computers. To avoid this, developers can write a `package-lock.json` file which locks all dependencies (and dependencies of dependencies) to a specific version until the file is regenerated. This means that if a dependency gets a patch, the author of the package must manually update the versions in `package-lock.json` if they want the newest version to be installed.
  - **Heavy Reuse**: in the npm ecosystem, packages have a high number of transitive dependencies.
  - **Micropackages**: there are lots of packages that only have a few lines of code, but they increase the attack surface because of the reuse culture.
  - **No Privilege Separation**: all packages run with the privileges of the application. In addition, these packages often run un-sandboxed on machines.
  - **No Systematic Vetting**: there is no established process for vetting code/packages.
  - **Publishing Model**: A user can publish a package simply by making an account. Publishing a package does not require publishing any code or version control system as proof.

- Threat Models
  - **Malicious Packages**: a developer could release a package that can deploy payloads or carry out other malicious behaviors when it is installed or used.
  - **Exploiting Unmaintained Legacy Code**: some packages that have vulnerabilities are never fixed due to abandonment or lack of upkeep.
  - **Package Takeover**: an attacker could trick current maintainers/authors into giving them maintainer access to their packages, and then change the code to be malicious.
  - **Account Takeover**: an attacker could compromise the account of a maintainer/author.
  - **Collusion Attack**: some combination of the above models.

### Results

- npm is the world's largest software ecosystem
- The average package affects about 230 other packages
- The top packages reach over 100,000 other packages
- Some maintainers maintain over 100 packages
- The average package transitively relies on 40 maintainers
- 391 influential maintainers affect more that 10,000 packages
- 20 maintainers can reach more than half of the ecosystem
- 141 advisories published where packages download over HTTP instead of HTTPS, and 129 directory traversal advisories
- Roughly 2/3 of advisories are unpatched
  - But, many of these are typosquatting vulns, which cannot be fixed

### Potential Mitigations
- **Raising Developer Awareness**: adding some sort of metric to the npm metadata that shows how many packages are implicitly trusted.
- **Warning About Vulnerable Packages**: the `npm audit` tool exists, but it only checks direct dependencies, and obviously only documents known vulnerabilities.
- **Code Vetting**: both manual and automatic code analysis measures could be implemented.
- **Training and Vetting Maintainers**: ensure the most influential maintainers have MFA enabled, know basic security practices, etc.

## [Supply-chain attack hits RubyGems repository with 725 malicious packages](https://arstechnica.com/information-technology/2020/04/725-bitcoin-stealing-apps-snuck-into-ruby-repository/)

- 2 user accounts had 725 malicious packages that were downloaded over 100,000 times
- Typosquatting
- The scripts would continually check the user's clipboard, see if it was the format of a crypto wallet address, and then replace it with the attacker's address

## [Keeping Rust projects secure with cargo-audit 0.9](https://blog.rust-lang.org/inside-rust/2019/10/03/Keeping-secure-with-cargo-audit-0.9.html)

- `cargo audit` will inspect `Cargo.lock` files and compares them with the Rust vulnerability advisories
- Informational advisories: aren't explicitly a security vuln, but may cause security issues (like abandoned packages)

## [npm Ecosystem Attacks](https://thomashunter.name/presentations/npm-ecosystem-attacks/)

- Ownership transfer - should npm force semver major with new owner?
- Need a [CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy) for Node.js

## [Securing Node.js Applications with Intrinsic](https://medium.com/intrinsic/securing-node-js-applications-with-intrinsic-db47ff86cff8)

We offer policies for the following types of operations:
  - Child Process Execution
  - Filesystem Operations
  - Outbound HTTP Requests
  - TCP/UDP Communication
  - Potentially dangerous process features, such as process.kill()
  - Databases, such as MongoDB or PostgreSQL
  - Tokenization, such as AWS Environment Variables

## [The security risks of changing package owners](https://blog.npmjs.org/post/182828408610/the-security-risks-of-changing-package-owners)

- Average npm packages has over 2000 dependencies
- Make change of ownership a breaking change with Semver
  - Does this mean a new version for every new maintainer? That could get tedious

## [How npm is Jeopardizing Open Source Projects](https://www.cs.tufts.edu/comp/116/archive/spring2018/etolhurst.pdf)

- If the integrity of open source applications is compromised, then people will go back to commercial software where their data is more likely to be sold
- It is very easy to hide files, just add the file to the `.gitignore`, and then add the `.gitignore` to the `exclude` file in `.git/info/exclude`.
- In the “package.json” file, add a “files” field which contains the JavaScript file(s) which you want to execute in your package but do not want the user to see.
- Could be mitigated by having some sort of comparison on NPM that shows whether the source code matches the code on GitHub

## [An Empirical Analysis of Vulnerabilities in Python Packages for Web Applications](https://arxiv.org/pdf/1810.13310.pdf)

- Not all vulns have CVEs, especially small/abandoned/obscure packages
- If a package is vulnerable for a certain release, there is a high probability that future releases have a vulnerability
  - It's also very likely that once a non-vulnerable release is made, the following releases will also not be vulnerable
- XSS and input validation are the most common vulns
- The majority of vulns are of mild severity

## [Gathering Weak npm Credentials](https://github.com/ChALkeR/notes/blob/master/Gathering-weak-npm-credentials.md)

>- Bruteforce attack using very weak passwords gave me 5994 total packages from 2803 accounts.
>- Utilizing datasets from known public leaks gave me 61536 total packages from 13358 accounts (directly).
>- Fuzzing the passwords from those known public leaks a bit (appending numbers, replacing other company names with «npm», etc) gave me 7064 packages from 856 accounts.
>- New npm credentials leaks (GitHub, Google, etc) gave me 645 total packages from 136 accounts.

## [npm Maintainers Security Review](https://dendritictech.com/post/npm-maintainers-security-review/)

- Many high profile maintainers use insecure 2FA/MFA (if any) like SMS

## [I'm harvesting credit card numbers and passwords from your site. Here's how.](https://medium.com/hackernoon/im-harvesting-credit-card-numbers-and-passwords-from-your-site-here-s-how-9a8cb347c5b5)

- It's relatively easy to get *someone* to accept a PR that adds a new dependency, and because of chaining dependencies, you can easily get reach to very popular packages
- You can build the malicious package such that it is undetectable when it is being monitored or being run in a test environment
  - You can also only run your code during typical off-hours
- You can hide code from GitHub that still gets published to the npm package
- You can minify and obfuscate code such that it passes any monitoring or manual inspection
- A lot of sites don't have strong CSPs, or CSPs at all
- More details about how to avoid this in his [follow-up post](https://medium.com/hackernoon/part-2-how-to-stop-me-harvesting-credit-card-numbers-and-passwords-from-your-site-844f739659b9)

## [Why npm lockfiles can be a security blindspot for injecting malicious modules](https://snyk.io/blog/why-npm-lockfiles-can-be-a-security-blindspot-for-injecting-malicious-modules/)

- > When a lockfile is present, whether that is Yarn’s `yarn.lock` or npm’s `package-lock.json`, an install will consult the lockfile as the primary source of truth for package versions and their sources for dependencies installation.
- You can easily replace source URLs in lockfiles with malicious ones, and usually people will not notice because lockfile diffs are already really long normally
- Lockfiles would mainly pose a risk to project maintainers and collaborators, since the lockfile is not used when the package is published

## [Why package signing is not the holy grail](https://www.python.org/dev/peps/pep-0458/)

- The problem is finding what public key you need to verify against
  - > If you do not have a well defined model of trust then all you’ve done is thrown cryptography at a problem in order to give the people involved the ability to say that their system has signature verification.
  - The package/repository you are checking can't be the one to provide the key, because if the package is compromised it's very easy to change the key as well
- There are also multiple people who can release packages, which would require multiple keys per package and further complicates any system

## [The State of Package Signing Across Package Managers](https://dev.to/tidelift/the-state-of-package-signing-across-package-managers-328i)

- **npm**: signs packages with its own PGP key
- **PyPI**: has support for author signing with GPG, but there's no verification of those signatures
- **cargo**: there are discussions about it

## Supply Chain Compromises
- [supply-chain-compromises](ttps://github.com/in-toto/supply-chain-compromises)
- [Attacks-on-software-repositories](https://github.com/theupdateframework/pip/wiki/Attacks-on-software-repositories)
