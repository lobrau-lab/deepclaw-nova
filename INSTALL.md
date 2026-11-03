# DeepClaw Nova installation

## Embedded MLX runtime

Use the Python environment that will run Nova:

```bash
sh scripts/install_embedded.sh /path/to/python
```

For the existing local environment:

```bash
sh scripts/install_embedded.sh ./venv/bin/python
```

The installer intentionally passes `--no-deps`. `mlx-vlm` currently declares
optional server/UI/audio dependencies, including `sentencepiece`; Python 3.15
has no compatible `sentencepiece` wheel on this host, and pip otherwise tries
to build it with CMake. Nova's native Qwen tokenizer path does not need it.
The required direct runtime packages are pinned in `requirements.txt` and
`requirements-embedded.txt`.

After installation:

```bash
claw status
claw "inspect the current repository and report its health"
```
