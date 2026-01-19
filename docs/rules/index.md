# Rules Reference

This section documents each rule in detail, explaining:

- **What triggers it** — the exact pattern detected
- **Why it's dangerous** — real-world failure scenarios
- **When it's safe to ignore** — legitimate use cases
- **How to fix it** — the safe migration pattern
- **How to suppress it** — if the warning is intentional

## Rules by Category

### Adding Fields

| Rule              | Severity | Description                                |
| ----------------- | -------- | ------------------------------------------ |
| [SM001](SM001.md) | ERROR    | Adding NOT NULL column without default     |
| [SM005](SM005.md) | WARNING  | Adding foreign key validates existing rows |

### Removing Fields

| Rule              | Severity | Description                           |
| ----------------- | -------- | ------------------------------------- |
| [SM002](SM002.md) | WARNING  | Dropping column during rolling deploy |
| [SM003](SM003.md) | WARNING  | Dropping table during rolling deploy  |

### Altering Fields

| Rule              | Severity | Description                          |
| ----------------- | -------- | ------------------------------------ |
| [SM004](SM004.md) | WARNING  | Changing column type (table rewrite) |
| [SM006](SM006.md) | INFO     | Renaming column breaks old code      |
| [SM013](SM013.md) | WARNING  | Decreasing VARCHAR length            |
| [SM014](SM014.md) | WARNING  | Renaming model/table                 |

### Indexes & Constraints

| Rule              | Severity | Description                                             |
| ----------------- | -------- | ------------------------------------------------------- |
| [SM009](SM009.md) | ERROR    | Adding unique constraint (table scan)                   |
| [SM010](SM010.md) | ERROR    | Index creation without CONCURRENTLY (PostgreSQL)        |
| [SM011](SM011.md) | ERROR    | Unique constraint without concurrent index (PostgreSQL) |
| [SM015](SM015.md) | WARNING  | Using deprecated unique_together                        |
| [SM017](SM017.md) | WARNING  | Adding CHECK constraint (validates rows)                |

### RunSQL & RunPython

| Rule              | Severity | Description                                      |
| ----------------- | -------- | ------------------------------------------------ |
| [SM007](SM007.md) | WARNING  | RunSQL without reverse_sql                       |
| [SM008](SM008.md) | INFO     | RunPython data migration                         |
| [SM012](SM012.md) | ERROR    | ALTER TYPE ADD VALUE in transaction (PostgreSQL) |
| [SM016](SM016.md) | INFO     | RunPython without reverse_code                   |

## Severity Levels

| Level       | Exit Code                      | Meaning                                             |
| ----------- | ------------------------------ | --------------------------------------------------- |
| **ERROR**   | 1                              | Will likely break production. Fix before deploying. |
| **WARNING** | 0 (1 with `--fail-on-warning`) | Might cause issues. Review carefully.               |
| **INFO**    | 0                              | Best practice recommendation. Consider addressing.  |

## Quick Reference

```
SM001  ERROR    not_null_without_default    Adding NOT NULL without default
SM002  WARNING  drop_column_unsafe          Removing column during deploy
SM003  WARNING  drop_table_unsafe           Removing table during deploy
SM004  WARNING  alter_column_type           Changing column type
SM005  WARNING  add_foreign_key             FK validates existing rows
SM006  INFO     rename_column               Renaming breaks old code
SM007  WARNING  run_sql_no_reverse          RunSQL without reverse_sql
SM008  INFO     data_migration              RunPython data migration
SM009  ERROR    unique_constraint           Adding unique (table scan)
SM010  ERROR    non_concurrent_index        Index without CONCURRENTLY
SM011  ERROR    non_concurrent_unique       Unique without concurrent index
SM012  ERROR    enum_in_transaction         Enum ADD VALUE in transaction
SM013  WARNING  alter_varchar_length        Decreasing VARCHAR length
SM014  WARNING  rename_model                Renaming model/table
SM015  WARNING  alter_unique_together       Deprecated unique_together
SM016  INFO     run_python_no_reverse       RunPython without reverse
SM017  WARNING  check_constraint            CHECK validates rows
```
