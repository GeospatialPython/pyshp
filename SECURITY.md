# Security
If you have found a security issue in PyShp - then thankyou!  Accordingly, we trust your expertise and your judgement in deciding the next step.  We would greatly appreciate being contacted privately, and given some grace period in accordance with normal Responsible Disclosure.  But for reasons below, this is not a requirement.  Public disclosure is fine too.  We will respect your decision.  We just want to fix the issue, or otherwise
handle it as best we can.  It is in nobody's interest to attribute blame.

## Bug bounty
There is no bug bounty.  But one maintainer has bought people a drink before, for far less. 

## Overview / attack surface
 - PyShp is a pure-Python library that typically gets called from other Python code.  Attackers with the ability to run Python code on a target in the first place, can already peform any function Python allows them to.  As long as PyShp was not the means by which the Attacker gained the ability to run arbitrary Python code, PyShp cannot prevent this.
 - `eval`, `compile` and `exec` etc. are not used, and should be considered to be banned.
 - The vulnerabilities we fail to consider are even more important than those we are aware of.  That said, by its very nature, PyShp does read arbitrary binary data.  An attack via a maliciously crafted shapefile is possible.  To mitigate this, PyShp -should- only convert arbitrary binary data into specific Python types (floats, ints, strings, booleans, dates, lists, arrays, tuples and dicts).  These do contain arbitrary data, but they should never result in arbitrary code execution (or even in Python raising a non-standard system-affecting Exception or crash).
 - We therefore consider the overall security risk from using PyShp to be low.  If you think otherwise, please contact a maintainer.