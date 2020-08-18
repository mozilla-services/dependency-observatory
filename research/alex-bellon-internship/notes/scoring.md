# Scoring

- Currently one maintainer is -10 points, but 5 or more maintainers is +10. I think that there should be another negative point value for 10 (arbitrary number) or more maintainers, as adding too many maintainers is adding a lot more attack vectors. It also may call into question how lax the project is in terms of adding maintainers (especially if one ends up being malicious)
- Same thoughts as above for contributors (although not as bad since theoretically they don't all have publish access)
- Right now points are only taken away once for a vuln. Should it compound with more open vulns?
- I think it would be useful to normalize scores, although maybe on a 5 or 10 point scale instead of 1

## False Positives

Most of the packages still score high because:
- They had a high npms.io score to begin with
- They had very few dependencies (<= 5 or <= 20, which add 20 and 10 points respectively). Since the max amount of points you can lose is 20 (critical vuln), having few dependencies can basically negate any points lost.
- Packages are only docked at most once for each level of vulnerability. This means that if the only difference between two packages were the number of high vulnerabilities, they would have the same score even though one is technically less secure.

#### express 2.4.0
- A, 105
- 1 Moderate vuln
- Boosted by low dep count

#### handlebars 4.2.0
- B, 77 points
- 4 High vulns, 1 Moderate
- Boosted by npms.io score and low dep count

#### lodash 3.0.0
- A, 103 points
- 2 High vulns, 2 Low
- Boosted by low dep count, vuln points only take off once

#### qs 6.1.0
- A, 91
- 1 High vuln
- Boosted by low dep count

## False Negatives

#### cli-usage 0.1.10
- C, 49 points
- 0 vulns
- Dragged down by npmsio score (49)

#### mversion 1.13.0
- C, 59 points
- 0 vulns
- Dragged down by npms.io score (69) and lots of deps (-10)

## Interesting
#### taffy 2.6.2
- B, 67 points
- npms.io score is 47 and +20 (roughly half of the raw score) for 0 deps
