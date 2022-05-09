import dataclasses


@dataclasses.dataclass
class Vertex:
    type: str
    id: str
    label: str


@dataclasses.dataclass
class Edge:
    type: str
    from_: str
    to: str


@dataclasses.dataclass
class File:
    filename: str
    vertices: list[Vertex]
    edges: list[Edge]


@dataclasses.dataclass
class Subgraph:
    dirname: str
    files: list
