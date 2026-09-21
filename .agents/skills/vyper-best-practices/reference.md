# Vyper Best Practices — Reference

Extended conventions and references for the Vyper Best Practices skill.

## Official Resources

- [Vyper Style Guide](https://docs.vyperlang.org/en/latest/style-guide.html)
- [Vyper Documentation](https://docs.vyperlang.org)
- [Using Modules](https://docs.vyperlang.org/en/latest/using-modules.html)
- [NatSpec](https://docs.vyperlang.org/en/latest/natspec.html)
- [snekmate](https://github.com/pcaversaccio/snekmate) — Vyper library of secure, gas-optimized implementations

## Pragma Reference

Common pragma combinations:

```vyper
# pragma version ^0.4.0
# pragma evm-version shanghai
# pragma optimize gas
# pragma nonreentrancy on
```

## Module `initializes` vs `uses`

| Directive   | Use case                                                    |
|------------|--------------------------------------------------------------|
| `initializes` | Contract owns module state; calls `__init__()` in `__init__` |
| `uses`        | Contract accesses module state; parent initializes          |

## Walrus Dependency Syntax

When module B depends on module A that your contract also uses:

```vyper
initializes: ow
initializes: erc721[ownable := ow]
```

The `ownable := ow` binds the `ownable` parameter expected by `erc721` to your local `ow` module.
