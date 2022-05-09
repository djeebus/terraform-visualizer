import functools
import os
import re
import typing

import hcl2

from models import Edge, File, Subgraph, Vertex

VerticesAndEdges = typing.Tuple[typing.List[Vertex], typing.List[Edge]]

ref_re = re.compile(r'\$\{.*?(\w+\.\w+(\.\w+)?).*}')


def to(cls):
    def _to(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            result = func(*args, **kwargs)
            return cls(result)
        return wrapped
    return _to


class Parser:
    def __init__(self, path):
        self._subgraphs = dict()
        self._module_names_to_paths = dict()

        self.path = path

    def parse(self) -> typing.Tuple[typing.List[File], typing.List[Subgraph]]:
        files = self._parse_dir(self.path)
        subgraphs = list(self._subgraphs.values())
        return files, subgraphs

    def _parse_dir(self, path, *, prefix=None) -> typing.List[File]:
        files = list()
        for fname in os.listdir(path):
            _, ext = os.path.splitext(fname)
            if ext != '.tf':
                continue

            full_path = os.path.join(path, fname)
            with open(full_path, 'r') as fp:
                data = hcl2.load(fp)

            file = File(fname, list(), list())
            files.append(file)

            for item_type, items in data.items():
                if item_type == 'terraform':
                    continue

                for item_set in items:
                    for name, item in item_set.items():
                        parser_name = f'_parse_{item_type}'
                        parser = getattr(self, parser_name)
                        vertices, edges = parser(path, name, item)
                        file.vertices += _add_prefix_to_vertices(vertices, prefix)
                        file.edges += _add_prefix_to_edges(edges, prefix)

        return files

    def _parse_data(self, path, name, item) -> VerticesAndEdges:
        item_type = name
        (name, item), = item.items()

        item_id = f'data.{item_type}.{name}'
        vertex = Vertex('data', item_id, item_id)
        edges = self._find_edges(item_id, item)

        return [vertex], edges

    def _parse_locals(self, path, name, item) -> VerticesAndEdges:
        item_id = f'local.{name}'
        vertex = Vertex('local', item_id, item_id)
        edges = self._find_edges(item_id, item)

        return [vertex], edges

    def _parse_module(self, path, name, item) -> VerticesAndEdges:
        # module vertex
        item_id = f'module.{name}'
        vertex = Vertex('module', item_id, item_id)
        edges = self._find_edges(item_id, item)

        relpath = item['source']
        fullpath = os.path.join(path, relpath)
        fullpath = os.path.abspath(fullpath)

        files = self._parse_dir(fullpath, prefix=f'module:{relpath}:')

        subgraph = Subgraph(relpath, files)
        self._subgraphs[fullpath] = subgraph

        self._module_names_to_paths[f'module.{name}'] = relpath

        # edges.append(Edge('indirect'))

        return [vertex], edges

    def _parse_output(self, path, name, item) -> VerticesAndEdges:
        item_id = f'output.{name}'
        vertex = Vertex('output', item_id, item_id)
        edges = self._find_edges(item_id, item)

        return [vertex], edges

    def _parse_provider(self, path, name, item) -> VerticesAndEdges:
        name = item.get('alias', name)
        item_id = f'provider.{name}'
        edges = self._find_edges(item_id, item)
        vertex = Vertex('provider', item_id, item_id)

        return [vertex], edges

    def _parse_resource(self, path, name, item) -> VerticesAndEdges:
        item_type = name
        (name, item), = item.items()

        item_id = f'resource.{item_type}.{name}'
        vertex = Vertex('resource', item_id, item_id)

        edges = self._find_edges(item_id, item)

        return [vertex], edges

    def _parse_variable(self, path, name, item) -> VerticesAndEdges:
        item_id = f'var.{name}'
        vertex = Vertex('variable', item_id, item_id)
        edges = self._find_edges(item_id, item)

        return [vertex], edges

    @to(list)
    def _find_edges(self, item_id, item):
        if isinstance(item, dict):
            for key, value in item.items():
                yield from self._find_edges(item_id, value)
            return

        if isinstance(item, list):
            for subitem in item:
                yield from self._find_edges(item_id, subitem)
            return

        if not isinstance(item, str):
            return

        # parse strings to see if there's a ref
        m = ref_re.search(item)
        if m:
            dep = m.group(1)
            yield from self._generate_edge(dep, item_id)

    def _generate_edge(self, from_, to) -> typing.Iterable[Edge]:
        ref_type, *_ = from_.split('.')
        edge_generator = getattr(
            self, f'_generate_edge_from_{ref_type}_ref', self._generate_edge_from_ref,
        )
        yield from edge_generator(from_, to)

    def _generate_edge_from_ref(self, from_, to):
        from_parts = from_.split('.')
        max_parts = _max_parts_by_prefix.get(from_parts[0], default_max_parts)
        from_parts = from_parts[:max_parts]

        yield Edge('direct', '.'.join(from_parts), to)

    def _generate_edge_from_module_ref(self, parent_id, module_id):
        module_output_id = self._build_module_output_id(module_id)
        yield Edge('indirect', module_output_id, parent_id)

        yield Edge('direct', parent_id, module_id)

    def _build_module_output_id(self, module_id):
        # split into
        parts = module_id.split('.')
        parent_module_path = '.'.join(parts[:2])
        rel_path = self._module_names_to_paths[parent_module_path]
        var_path = '.'.join(parts[2:])

        return f'module:{rel_path}:output.{var_path}'


default_max_parts = 2
_max_parts_by_prefix = {
    'module': 3,
}


def _add_prefix_to_vertices(vertices: typing.List[Vertex], prefix):
    if prefix:
        for v in vertices:
            v.id = f'{prefix}{v.id}'

    return vertices


def _add_prefix_to_edges(edges: typing.List[Edge], prefix):
    if prefix:
        for e in edges:
            e.from_ = f'{prefix}{e.from_}'
            e.to = f'{prefix}{e.to}'

    return edges
