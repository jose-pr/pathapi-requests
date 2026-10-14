# Benchmarks

`bench.py` times the built-in transport of `pathapi.http` and this package's
`RequestsTransport` on the same requests: 50 GETs of a 1 KiB file, one GET of a
1 MiB file and 20 PUTs of 1 KiB, through an `HTTPClient`.
Nothing here contacts an external host: an in-process loopback server answers.

## Reproduce

From the repository root, in a virtualenv with the package installed:

```bash
python -m pip install -e ".[dev]"
python benchmarks/bench.py --save
```

| Option | Effect |
| --- | --- |
| `--save` | Write the run to `benchmarks/results/<name>.json`. |
| `--name NAME` | File name without `.json`. Default `<version>-py<major.minor>-<os>-<arch>`. |
| `--results-dir DIR` | Write somewhere other than `benchmarks/results/`. |
| `--samples N` | Samples per case (1-100). Default 5. |
| `--note TEXT` | Free text stored in the JSON. |

## Comparing runs

Compare on the **median**: one sample's time hides run-to-run noise. Only compare
runs from the same machine and interpreter. A run on a developer machine is a
sanity check; performance claims in the changelog or release notes come from CI
runs (`test.yml` with `benchmark` set).

## Result schema (`pathapi-requests.bench/1`)

One JSON object per run: `schema`, `name`, `source` (`"ci"` or `"local"`),
`note`, `created_utc`, `package` (`name`, `version`), `dependencies` (`pathapi`,
`requests`), `git` (`commit`, `dirty`; null outside a checkout), `python`,
`interpreter`, `platform`, `processor`, and `metrics`: per case, `min_ms`,
`median_ms`, `max_ms`, `samples` and `calls_per_sample`, in milliseconds per
call.
