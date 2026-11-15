# pdf-stand

PDF → JSON table extraction stand (**pdfplumber**, MIT).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pdf-stand parse tests/corpus/pass/01_simple.pdf
```

HTTP:

```bash
docker compose up --build
curl -F "file=@tests/corpus/pass/01_simple.pdf" http://localhost:8131/parse
```

## Corpus gate

`tests/corpus/pass/` has **20** digital PDFs. Every push/PR runs pytest — all must parse to matching golden JSON.

## Deploy

Production host: **`80.87.196.33:8131`** only. See [docs/deploy.md](docs/deploy.md).

## License

MIT
