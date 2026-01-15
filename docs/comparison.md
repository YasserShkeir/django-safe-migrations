# Comparison with Other Libraries

There are several tools available for ensuring Django migration safety. Each tool approaches the problem differently, focusing on either backward compatibility (rolling updates) or zero-downtime safety (database locking).

`django-safe-migrations` aims to combine the **static analysis** benefits of a linter with the **deep database safety checks** of a runtime tool.

## Feature Comparison Matrix

| Feature                 | django-safe-migrations                         | django-migration-linter                 | django-strong-migrations                  |
| :---------------------- | :--------------------------------------------- | :-------------------------------------- | :---------------------------------------- |
| **Primary Focus**       | **Database Locking** & Operational Safety      | Backward Compatibility (Code vs Schema) | Database Locking & Zero Downtime          |
| **Analysis Method**     | **Static Analysis** (inspects code)            | Static Analysis (inspects code)         | **Runtime Inspection** (during `migrate`) |
| **Database Connection** | **Optional** (Checks run offline)              | Optional / Not Required                 | **Required** (checks live DB state)       |
| **CI/CD Friendly**      | **Native** (GitHub Actions, JSON, Pre-commit)  | Native                                  | Requires DB container/connection          |
| **Granularity**         | Operation & Line-level                         | Migration-level                         | Operation-level                           |
| **PostgreSQL Support**  | **Deep** (Concurrent indexes, constraints)     | Basic                                   | Deep                                      |
| **MySQL Support**       | Basic                                          | Good                                    | PostgreSQL focused                        |
| **Remediation**         | **Code Suggestions** implementation guides     | Error messages                          | Safe pattern helpers                      |

---

## Detailed Comparison

### vs. `django-migration-linter`

**django-migration-linter** is the gold standard for **backward compatibility**. Its primary goal is to ensure that a migration applied to the database won't break application code that hasn't been reloaded yet (important for zero-downtime _deployments_).

- **When to use the Linter**: If your main concern is "will my old API servers crash because I renamed a column?"
- **When to use Safe Migrations**: If your main concern is "will this migration verify a constraint on 100M rows and lock the DB for 30 minutes?"
- **Conclusion**: These tools are **complementary**. You should ideally run both.

### vs. `django-strong-migrations`

**django-strong-migrations** (and its Rails inspiration) protects against database locking by hooking into the `migrate` command. It often forces you to use specific "safe" context managers in your code.

- **Pros of Strong Migrations**: Being at runtime, it can inspect actual database state (e.g., table size).
- **Cons of Strong Migrations**: It requires the checks to run _inside_ the environment. If you want to catch these issues in a lightweight CI step without spinning up a database, it's harder.
- **The Safe Migrations Advantage**: `django-safe-migrations` detects the same unsafe patterns (like adding an index non-concurrently) via **static analysis**. This means you get the feedback in your editor or PR diff immediately, without needing a database connection. It also doesn't force you to rewrite your migrations with proprietary helpers; standard Django migrations works fine, we just warn you when they are unsafe.

### Unique Features of `django-safe-migrations`

1.  **Hybrid Ruleset**: We cover both "scary locking operations" (like `strong_migrations`) and "unsafe dropping of data" (like the linter).
2.  **Suggestive Fixes**: We don't just say "Error". We output the actual Python code snippet you should specifically use to fix the issue (e.g., proper 3-step migration for adding a column).
3.  **Modern Ecosystem**: Built from the ground up for GitHub Actions (annotations support) and modern Django versions (3.2 - 5.1+).
