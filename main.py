import click

from graph import write_graph
from process import Parser


@click.command()
@click.argument('path', type=click.Path(file_okay=False, dir_okay=True))
def cli(path):
    parser = Parser(path)
    files, subgraphs = parser.parse()

    write_graph(files, subgraphs)


if __name__ == '__main__':
    cli()
