# Benchmarks

`benchmarks/bench.py` times the built-in transport of `pathlib_next.http` and
`RequestsTransport` on the same requests against a loopback server: 50 GETs of a
1 KiB file, one GET of a 1 MiB file and 20 PUTs of 1 KiB.

```bash
python benchmarks/bench.py            # run the benchmarks
python benchmarks/bench.py --help     # options; runs nothing
python benchmarks/bench.py --save     # also write benchmarks/results/<name>.json
```

Compare two runs on their medians, and only between runs from the same machine
and interpreter. The result schema and the committed results are described in
[`benchmarks/README.md`](https://github.com/jose-pr/pathlib-next-requests/blob/main/benchmarks/README.md).
A run on a developer machine is a sanity check; performance claims come from CI
runs.
