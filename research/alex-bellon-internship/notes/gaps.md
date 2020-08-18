# Gaps

## All
- The distinction between Authors, Maintainers, Contributors, Owners, etc. and description of their powers/responsibilities are usually not well defined. Many times they cannot be found in one place in the documentation (or in the documentation at all) and you can only get definitions from various GitHub issues.
- No indicator of whether Maintainers/Owners are using 2FA/MFA
  - Nice to have in public facing APIs

## Cargo

## NPM

## PyPI
- There are multiple maintainers listed on the PyPI page for a package, but the JSON API only provides one maintainer and maintainer email (if that)
- The key to the field where the source (usually) is isn't standardized. Some packages call it `code`, some call it `source`, and some don't even put it in the proper "Links" section; they put it in the Description, which is a giant freeform string.
- There is a downloads field (three, actually) but the values are always -1 for some reason
- There's no dependent count recorded anywhere nor list of dependencies

## GitHub Advisories API
- Often don't link to the NPM official advisory
