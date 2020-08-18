# Finding Attack Vectors in Most-Depended on Packages

## `ecosystem-analysis.py`

This script goes through the output from `package-analysis.py` and calculates the following for the entire ecosystem:
- Total leaks
- Average leaks/person
- Percentage of packages that are maintained

Currently the output is printed to the terminal.

## `email-analysis.py`

This script goes through the output from `package-analysis.py` and calculates the following for the entire ecosystem:
- Users with 1 or more leaks (compared to the total amount of users)
- The number of emails with leaks that had the following domains
  - Gmail
  - .edu
  - .gov
  - other

Currently the output is printed to the terminal.

## `package-analysis.py`

This script gets maintainer and contributor emails for the top 50 most depended-on packages (based on libraries.io) for the Cargo, NPM and PyPI ecosystems, and then checks their email for leaks on HaveIBeenPwned. It also records some other statistics about the package, like whether it is actively maintained, how many packages depend on it, etc.

### APIs
- **Cargo**: `https://crates.io/api/v1/crates/<package>`
- **NPM**: `https://api.npms.io/v2/package/<package>`
  - This includes information from the native NPM API (`https://registry.npmjs.org/<package`) plus more info
- **PyPI**: `https://pypi.org/pypi/<package>/json`
- **HaveIBeenPwned**: `https://api.haveibeenpwned.com/breachedaccount/range/` (k-Anonymity search)

### JSON Output

#### Legend
| key                              |type           | npm                | cargo              | PyPI               |
|----------------------------------|---------------|--------------------|--------------------|--------------------|
| `package`                        | string        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `emails`                         | list[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `source`                         | string        | :white_check_mark: | :white_check_mark: |                    |
| `ci`                             | dict[string]  | :white_check_mark: | :white_check_mark: |                    |
| `last-release`                   | string        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `downloads`                      | integer       | :white_check_mark: | :white_check_mark: |                    |
| `dependents`                     | integer       | :white_check_mark: | :white_check_mark: |                    |
| `dependencies`                   | list[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `leaks`                          | dict[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `total-leaks`                    | integer       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `total-viable-leaks`             | integer       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `average-leaks`                  | double        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `average-viable-leaks`           | double        | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `transitive-dependencies`        | list[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `transitive-emails`              | list[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `transitive-leaks`               | dict[string]  | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `transitive-total-leaks`         | integer       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `transitive-total-viable-leaks`  | integer       | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| `maintained`                     | boolean       | :white_check_mark: | :white_check_mark: | :white_check_mark: |

#### Definitions
- `package`: name of the package
- `emails`: list of emails of users with publish capabilities (maintainers/owners)
- `source`: link to GitHub repository
- `ci`: dict of dicts with different CI contexts as keys, the "inner" dicts have the following keys:
  - `state`: whether or not the check succeeded
  - `date`: date when the check was made
- `last-release`: date of last release in `YYYY-MM-DD HH:MM:SS` format
- `downloads`: number of total downloads
- `dependents`: number of dependent packages (only direct dependents)
- `dependencies`: list of direct dependencies of the package
- `leaks`: dict of dicts with emails from `emails` as keys, the "inner" dicts have the following keys:
  - `leakNum`: number of leaks for this email
  - `viableLeakNum`: number of viable leaks for this email (e.g. occurred within the past year)
  - `leakWebsites`: list of websites this email was leaked from
- `total-leaks`: total number of leaks between all maintainers and contributors in `emails`
- `total-leaks`: total number of viable leaks between all maintainers and contributors in `emails`
- `average-leaks`: average amount of leaks per person (total leaks / number of unique emails)
- `average-leaks`: average amount of viable leaks per person (total viable leaks / number of unique emails)
- `transitive-dependencies`: list of all dependencies of the package (direct + transitive)
- `transitive-emails`: list of emails of users with publish capabilities for every package in `transitive-dependencies`
- `transitive-leaks`: dict of dicts with emails from `transitive-emails` as keys, the "inner" dicts have the following keys:
  - `leakNum`: number of leaks for this email
  - `viableLeakNum`: number of viable leaks for this email (e.g. occurred within the past year)
  - `leakWebsites`: list of websites this email was leaked from
- `transitive-total-leaks`: total number of leaks between all maintainers and contributors in `transitive-emails`
- `transitive-total-viable-leaks`: total number of viable leaks between all maintainers and contributors in `transitive-emails`
- `maintained`: whether the latest release was published in the past year
