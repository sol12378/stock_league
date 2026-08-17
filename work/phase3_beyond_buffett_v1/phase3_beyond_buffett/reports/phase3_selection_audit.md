# Selection Audit

- Final count: 20
- Role composition: {'Buffett Core': 5, 'Emerging Core': 5, 'Transformation Core': 5, 'Dual Moat': 3, 'Bridge / Diversifier': 2}
- Sector counts: {'Retail Trade': 3, 'Machinery': 3, 'Information & Communication': 3, 'Electric Appliances': 3, 'Other Products': 1, 'Nonferrous Metals': 1, 'Services': 1, 'Wholesale Trade': 1, 'Construction': 1, 'Chemicals': 1, 'Metal Products': 1, 'Iron and Steel': 1}
- Phase1 fixed names: 5
- Remaining names all from Top1200: True
- Constraint violations: **none**

The constrained greedy procedure fixes Buffett Core, selects Dual, reserves scarce evidence-qualified sector capacity by filling Emerging, and then fills Transformation and Bridge while checking hard exclusions and sector/theme counts. This feasibility ordering does not change the requested role quotas. The audit trail is in `data/phase3_selection_audit_trail.csv`.
