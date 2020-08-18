# DEFCON/BlackHat 2020

## DEFCON

### [Hacking the Supply Chain: The Ripple20 Vulnerabilities](https://www.youtube.com/watch?v=wHsjf2mAHIM)

- Ripple20
  - 19 zero-days in Treck TCP/IP stack
  - Amplified by supply chain
  - 4 are critical RCE, 8 are med/high
- The software (and therefore vulns) were passed along through the supply chain to an OS, then to a System on Module, then to a product
- Some vulns can't be patched because companies went out of business, they can't repair/patch their devices, or they won't patch it
- CVE 2020-11901
  - RCE in Treck's DNS resolver
  - Can be attacked outside of the network, traverses NAT boundaries
  - DNS Refresher
    - Common Types
      - A - IPv4 address for domain
      - CNAME - Alias (canonical name)
      - MX - Domain name of a mail server for domain
    - DNS message compression
      - Use pointers to previous occurences of labels instead of rewriting the whole label
  - Code to expand label length can lead to heap based BO vuln
    - No bounds checking
  - Also has an integer overflow issue

### [Discovering Hidden Properties to Attack Node.js Ecosystem](https://www.youtube.com/watch?v=oGeEoaplMWA)

- 13 zero-days
- NodeJS is made to execute JS outside of the browser, based on Chrome's v8 engine
- Hidden Property Abusing
  - Injecting an additional key/value pair to a property that already exists in the object
  - Prototype inheritance hijacking
  - Root cause is that Node fails to isolate unsafe objects (input) from critical internal states
- Lynx - tool to help with this attack
  - Find hidden properties by injecting dummy data and seeing where it propogates to

## BlackHat

### [The Devil's in the Dependency: Data-Driven Software Composition Analysis](https://www.blackhat.com/us-20/briefings/schedule/#the-devils-in-the-dependency-data-driven-software-composition-analysis-20208)

- Library usage depends on the language
- Most vulnerabilites can be fixed with an update
- ~20% of all vulnerable libraries have PoCs

### [Engineering Empathy: Adapting Software Engineering Principles and Process to Security](https://www.blackhat.com/us-20/briefings/schedule/#engineering-empathy-adapting-software-engineering-principles-and-process-to-security-19659)

Slides aren't working :(
