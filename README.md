# Think Lab

Think Lab copies instrument files into an archive and verifies every copy with
SHA-256. It has one source file and no runtime dependencies.

## Use

Requires Python 3.11+.

```powershell
python -m pip install -e .
Copy-Item config/machines.example.toml config/machines.toml
think-lab config/machines.toml
```

Edit `config/machines.toml` to use real, collector-visible paths and set
`enabled = true`.

The archive layout is:

```text
<archive>/<machine>/<dataset>/<sha256>/<filename>
```

Existing content is skipped. New files are copied to a temporary path, verified,
and atomically renamed.

## Test

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

Do not enable a machine until you know its files are complete before collection;
Think Lab does not yet wait for actively written files to stabilize.
