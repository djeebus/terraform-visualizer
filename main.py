import collections
import functools
import itertools
import os
import re
import typing

import click
import hcl2


@click.command()
@click.argument('path', type=click.Path(file_okay=False, dir_okay=True))
def cli(path):
    vertices, module_names_to_paths = _collect_vertices(path)
    click.echo(f"found {len(vertices)} items")
    edges = _find_edges(vertices, module_names_to_paths)

    _write_graph(vertices, edges)


def to(cls):
    def _to(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            result = func(*args, **kwargs)
            return cls(result)
        return wrapped
    return _to


@to(list)
def _find_edges(vertices, module_names_to_paths):
    for vertex in vertices:
        name = vertex['__id__']
        deps = _get_deps(vertex, module_names_to_paths)

        for ref in deps:
            yield ref, name


item_fmts = {
    'data': '{id}[({label})]',
    'locals': '{id}({label})',
    'module': '{id}(({label}))',
    'output': '{id}({label})',
    'provider': '{id}({label})',
    'resource': '{id}({label})',
    'variable': '{id}([{label}])',
}


def _write_graph(vertices, edges):
    print('```mermaid')
    print('  graph LR')

    print()
    printed_full_names = set()
    vertices = sorted(vertices, key=lambda v: v['__parent__'])
    grouped = itertools.groupby(vertices, key=lambda v: v['__parent__'])
    modules = list()
    for parent, vertices in grouped:
        if parent:
            print(f'  subgraph {parent}')

        for vertex in vertices:
            if vertex['__type__'] == 'module':
                modules.append(vertex)
                continue

            _print_label(vertex, printed_full_names)

        if parent:
            print('  end')
        print()

    for module in modules:
        _print_label(module, printed_full_names)

    print()
    added_edges = set()
    for ref, full_name in edges:
        edge_key = ref, full_name
        if edge_key in added_edges:
            continue

        print(f'  {ref} --> {full_name}')
        added_edges.add(edge_key)
    print('```')


def _print_label(vertex, printed_full_names: set):
    vertex_id = vertex['__id__']
    if vertex_id in printed_full_names:
        return

    label = vertex['__name__']

    item_fmt = item_fmts[vertex['__type__']]
    click.echo(f'    {item_fmt.format(id=vertex_id, label=label)}')
    printed_full_names.add(vertex_id)


def _collect_vertices(path) -> typing.Tuple[list, dict]:
    root_path = path
    work = [(path, '')]
    done = set()

    vertices = list()
    module_names_to_paths = dict()

    while work:
        path, parent = work.pop()
        if path in done:
            continue

        for file in os.listdir(path):
            _, ext = os.path.splitext(file)
            if ext != '.tf':
                continue

            full_path = os.path.join(path, file)
            # click.echo(f'parsing {full_path} ...')
            with open(full_path, 'r') as fp:
                data = hcl2.load(fp)

            for item_type, items in data.items():
                if item_type == 'terraform':
                    continue

                for item_set in items:
                    for name, item in item_set.items():
                        if item_type == 'locals':
                            item = {'value': item}
                        item["__path__"] = full_path
                        item["__parent__"] = parent
                        item["__type__"] = item_type
                        item["__name__"] = f'{item_type}.{name}'
                        item["__id__"] = _canonical_name(item_type, name, item, parent)
                        vertices.append(item)

                        if item_type == 'module':
                            module_path = os.path.join(path, item['source'])
                            rel_path = os.path.relpath(module_path, root_path)

                            module_names_to_paths[f'module.{name}'] = rel_path
                            work.append((module_path, f'module:{rel_path}'))

    return vertices, module_names_to_paths


def _canonical_name(item_type, name, item, parent):
    if item_type == 'variable':
        item_type = 'var'
    elif item_type == 'resource':
        item_type = name
        name, = (k for k in item.keys() if k.startswith('__') is False)
    elif item_type == 'provider':
        alias = item.get('alias')
        if alias:
            name = f'{name}.{alias}'

    if parent:
        return f'{parent}.{item_type}.{name}'
    return f'{item_type}.{name}'


ref_re = re.compile(r'\$\{.*?(\w+\.\w+).*}')


@to(list)
def _get_deps(item, module_names_to_paths):
    if isinstance(item, dict):
        for key, value in item.items():
            yield from _get_deps(value, module_names_to_paths)
        return

    if isinstance(item, list):
        for subitem in item:
            yield from _get_deps(subitem, module_names_to_paths)
        return

    if not isinstance(item, str):
        return

    # parse strings to see if there's a ref
    m = ref_re.search(item)
    if m:
        dep = m.group(1)
        if dep.startswith('module.'):
            dep = module_names_to_paths[dep]
        yield dep


if __name__ == '__main__':
    cli()
