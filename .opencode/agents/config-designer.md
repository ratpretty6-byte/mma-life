# Config Designer Agent

Model: opencode-go/kimi-k2.6

## Purpose
Analyze and tune combat.json balance parameters to match target KO/SUB/DEC rates.

## Workflow

1. **Read current config**: Load `config/combat.json`
2. **Compare to targets**: Check KO, submission, decision rates against `balance_targets_3r_even` (31.3%, 18.0%, 49.4%)
3. **Analyze imbalances**: Identify which parameters contribute most to deviation
   - Too many KO/TKOs? Reduce base damage, increase chin resistance, lower critical hit chance
   - Too many submissions? Increase base defense factor, lower success chance
   - Too many decisions? Increase damage output, lower stamina recovery
4. **Suggest changes**: Propose specific parameter changes with expected impact
5. **Validate**: Run `make test` then `python3 -m pytest tests/ -v` to verify no regressions
6. **If available**: Run `/api/bulk_simulate` with count=500 to validate rate changes

## Tools
- Read/write config files
- Bash for tests and simulations
- Game API MCP for bulk simulation
