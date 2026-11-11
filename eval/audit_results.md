Model: gemini-3.5-flash-lite · 28 claims (8 correct, 20 wrong)

| Prompt | Catch rate (wrong claims flagged) | False alarms (correct claims flagged) | Exact verdict | Missed | False alarms |
|---|---|---|---|---|---|
| audit v2 | 0.9 | 0.0 | 0.893 | O03, O09 | – |
| audit v3 | 0.95 | 0.0 | 0.929 | O03 | – |

Per case (expected → verdict per version):

- S01 expected **overstated** → v2: overstated, v3: overstated · Minimum of 1 year experience providing technical support
- S02 expected **supported** → v2: supported, v3: supported · Basic understanding of Windows OS and MacOS
- S03 expected **supported** → v2: supported, v3: supported · A degree or diploma in Computer Science, Management Informat
- S04 expected **supported** → v2: supported, v3: supported · Experience with Active Directory and Azure Active Directory 
- S05 expected **supported** → v2: supported, v3: supported · Basic knowledge of network hardware (cabling, routers, switc
- S06 expected **supported** → v2: supported, v3: supported · Hands-on experience with Docker
- S07 expected **supported** → v2: supported, v3: supported · Professional English (written and spoken)
- S08 expected **supported** → v2: supported, v3: supported · Experience with Apache Spark or another distributed processi
- O01 expected **overstated** → v2: overstated, v3: overstated · Minimum of 1 year experience providing technical support
- O02 expected **overstated** → v2: overstated, v3: overstated · Minimum of 2 years in a customer service position
- O03 expected **overstated** → v2: supported, v3: supported · Experience with Active Directory and Azure Active Directory 
- O04 expected **overstated** → v2: overstated, v3: overstated · Minimum of 2 years in a customer service position
- O05 expected **overstated** → v2: overstated, v3: overstated · At least 3 years of professional experience with Apache Spar
- O06 expected **overstated** → v2: overstated, v3: overstated · At least 2 years of professional experience with Python
- O07 expected **overstated** → v2: overstated, v3: overstated · Strong SQL skills (PostgreSQL or equivalent)
- O08 expected **overstated** → v2: overstated, v3: overstated · Professional English (written and spoken)
- U01 expected **unsupported** → v2: unsupported, v3: unsupported · At least one industry certification such as CompTIA A+, Comp
- U02 expected **unsupported** → v2: unsupported, v3: unsupported · Good understanding of network protocols
- U03 expected **unsupported** → v2: unsupported, v3: unsupported · Basic understanding of Windows OS and MacOS
- U04 expected **unsupported** → v2: unsupported, v3: unsupported · Kubernetes
- U05 expected **unsupported** → v2: unsupported, v3: unsupported · Experience with a cloud platform (Azure or AWS)
- U06 expected **unsupported** → v2: unsupported, v3: unsupported · CI/CD practices
- U07 expected **unsupported** → v2: overstated, v3: overstated · Engineering degree or Master's degree in computer science
- U08 expected **unsupported** → v2: unsupported, v3: unsupported · Experience with Active Directory environments
- S09 expected **supported** → v2: supported, v3: supported · Minimum of 1 year experience providing technical support
- O09 expected **overstated** → v2: supported, v3: overstated · Experience troubleshooting computer hardware and software is
- O10 expected **overstated** → v2: overstated, v3: overstated · Experience administering Microsoft 365 (users, licences, Exc
- O11 expected **overstated** → v2: overstated, v3: overstated · Experience supporting network infrastructure (routers, switc
