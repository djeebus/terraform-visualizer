import collections
import os
import re

import click
import hcl2


@click.command()
@click.argument('path', type=click.Path(file_okay=False, dir_okay=True))
def cli(path):
    all_items = collections.defaultdict(dict)
    walk_path(path, all_items)

    _write_graph(all_items)


def _write_graph(all_items):

    all_refs = set()
    non_root = set()
    edges = set()

    item_fmts = {
        'data': '[({name})]',
        'module': '(({name}))',
        'variable': '([{name}])',
    }

    print('```mermaid')
    print('  graph LR')
    for key, items in all_items.items():
        print()
        for name, item in items.items():
            full_name = f'{key}.{name}'

            item_fmt = item_fmts.get(item.get('__type__'))
            if item_fmt:
                click.echo(f'  {full_name}{item_fmt.format(name=full_name)}')
            else:
                click.echo(f'  {full_name}')

            all_refs.add(full_name)
            refs = list(_get_refs(item))
            if not refs:
                parent = item.get('__parent__')
                if parent:
                    refs.append(parent)

            if refs:
                non_root.add(full_name)
                for ref in refs:
                    edge_key = ref, full_name
                    if edge_key in edges:
                        continue

                    print(f'  {ref} --> {full_name}  %% {item["__path__"]}')
                    edges.add(edge_key)

    print('```')


def _parse_data(path, item_type, name, item, all_items):
    return item_type, name, item


def _parse_default(path, item_type, name, item, all_items):
    return item_type, name, item


def _parse_local(path, item_type, name, item, all_items):
    return 'local', name, dict()


def _parse_module(path, item_type, name, item, all_items):
    module_path = os.path.join(path, item['source'])
    module_path = os.path.abspath(module_path)
    walk_path(module_path, all_items, parent=f'module.{name}')

    return item_type, name, item


def _parse_provider(path, item_type, name, item, all_items):
    return


def _parse_resource(path, item_type, name, item, all_items):
    item_type = name
    (name, item), = item.items()
    return item_type, name, item


def _parse_variable(path, item_type, name, item, all_items):
    return 'var', name, item


parsers = {
    'data': _parse_data,
    'locals': _parse_local,
    'module': _parse_module,
    'provider': _parse_provider,
    'resource': _parse_resource,
    'variable': _parse_variable,
}


def walk_path(path, all_items, parent=None):
    for file in os.listdir(path):
        _, ext = os.path.splitext(file)
        if ext != '.tf':
            continue

        full_path = os.path.join(path, file)
        click.echo(f'parsing {full_path} ...')
        with open(full_path, 'r') as fp:
            data = hcl2.load(fp)

        for item_type, items in data.items():
            if item_type == 'terraform':
                continue

            for item_set in items:
                for name, item in item_set.items():
                    parser = parsers.get(item_type, _parse_default)
                    result = parser(path, item_type, name, item, all_items)
                    if not result:
                        continue

                    this_item_type, name, item = result
                    item["__path__"] = full_path
                    item["__parent__"] = parent
                    item["__type__"] = item_type
                    all_items[this_item_type][name] = item


ref_re = re.compile(r'\$\{.*?(\w+\.\w+).*}')


def _get_refs(item, *, key=None):
    if isinstance(item, dict):
        for key, value in item.items():
            yield from _get_refs(value, key=key)
        return

    if isinstance(item, list):
        for subitem in item:
            yield from _get_refs(subitem, key=key)
        return

    if not isinstance(item, str):
        return

    # parse strings to see if there's a ref
    m = ref_re.search(item)
    if m:
        yield m.group(1)


if __name__ == '__main__':
    cli()
