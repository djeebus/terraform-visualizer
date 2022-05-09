import dataclasses
import typing

from models import File, Subgraph


def write_graph(files: typing.List[File], subgraphs: typing.List[Subgraph]):
    print('```mermaid')
    print('graph LR')

    for file in files:
        _write_graph_file(file)

    for subgraph in subgraphs:
        dirname = subgraph.dirname
        files = subgraph.files

        print(f"  %% {dirname}")
        print(f"  subgraph module:{dirname} [{dirname}]")

        for file in files:
            _write_graph_file(file, prefix='  ')

        print(f"  end")
    print("```")


vertex_fmts = {
    'data': '{id}[({label})]',
    'local': '{id}({label})',
    'module': '{id}(({label}))',
    'output': '{id}({label})',
    'provider': '{id}({label})',
    'resource': '{id}({label})',
    'variable': '{id}([{label}])',
}

edge_type_fmts = {
    'direct': '{from_} --> {to}',
    'indirect': '{from_} -.-> {to}',
}


def _write_graph_file(file: File, prefix=''):
    filename = file.filename
    vertices = file.vertices
    edges = file.edges

    print(f'{prefix}  %% {filename}')
    if vertices:
        for vertex in vertices:
            vertex_type = vertex.type
            vertex_fmt = vertex_fmts[vertex_type]
            print(f'{prefix}  {vertex_fmt.format(**dataclasses.asdict(vertex))}')
        print()

    if edges:
        for edge in edges:
            edge_type = edge.type
            edge_fmt = edge_type_fmts[edge_type]
            print(f'{prefix}  {edge_fmt.format(**dataclasses.asdict(edge))}')
        print()

    print()
