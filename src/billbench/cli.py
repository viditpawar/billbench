import typer

app = typer.Typer(help="billbench: LLM bill-summarization eval harness")


@app.command()
def build_dataset(config: str = "configs/eval.yaml", out: str = "data/bills.jsonl"):
    """Fetch bills + CRS summaries from Congress.gov and write a stratified dataset."""
    from .dataset import build
    build(config, out)


if __name__ == "__main__":
    app()
