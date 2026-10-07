# Focused tests

Run:

```powershell
.\scripts\verify-research.ps1
```

The key regression checks prove that static and feedback policies diverge on feasible candidates, changing any `observed_*` value cannot change a policy selection, aggregation uses only `observed_*`, empirical rows require complete profiles, and the experiment exposes all seven production-router dimensions.
