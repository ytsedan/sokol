#-------------------------------------------------------------------------------
#   gen_json.py
#
#   Convert clang AST dump into a simplfied JSON API description.
#-------------------------------------------------------------------------------
import json
import sys

def is_api_decl(decl, prefix):
    if 'name' in decl:
        return decl['name'].startswith(prefix)
    else:
        return False

def parse_struct(decl):
    outp = {}
    outp['kind'] = 'struct'
    outp['name'] = decl['name']
    outp['items'] = []
    for item_decl in decl['inner']:
        if item_decl['kind'] != 'FieldDecl':
            sys.exit(f"ERROR: Structs must only contain simple fields ({decl['name']})")
        item = {}
        if 'name' in item_decl:
            item['name'] = item_decl['name']
        item['type'] = item_decl['type']['qualType']
        outp['items'].append(item)
    return outp

def parse_enum(decl):
    outp = {}
    outp['kind'] = 'enum'
    outp['name'] = decl['name']
    outp['items'] = []
    for item_decl in decl['inner']:
        if item_decl['kind'] == 'EnumConstantDecl':
            item = {}
            item['name'] = item_decl['name']
            if 'inner' in item_decl:
                const_expr = item_decl['inner'][0]
                if const_expr['kind'] != 'ConstantExpr':
                    sys.exit(f"ERROR: Enum values must be a ConstantExpr ({decl['name']})")
                if const_expr['valueCategory'] != 'rvalue':
                    sys.exit(f"ERROR: Enum value ConstantExpr must be 'rvalue' ({decl['name']})")
                if not ((len(const_expr['inner']) == 1) and (const_expr['inner'][0]['kind'] == 'IntegerLiteral')):
                    sys.exit(f"ERROR: Enum value ConstantExpr must have exactly one IntegerLiteral ({decl['name']})")
                item['value'] = const_expr['inner'][0]['value']
        outp['items'].append(item)
    return outp

def parse_func(decl):
    outp = {}
    outp['kind'] = 'func'
    outp['name'] = decl['name']
    outp['type'] = decl['type']['qualType']
    return outp

def parse_decl(decl):
    kind = decl['kind']
    if kind == 'RecordDecl':
        return parse_struct(decl)
    elif kind == 'EnumDecl':
        return parse_enum(decl)
    elif kind == 'FunctionDecl':
        return parse_func(decl)
    else:
        return None

def parse_ast(ast, module, prefix):
    outp = {}
    outp['module'] = module
    outp['prefix'] = prefix
    outp['decls'] = []
    for decl in ast['inner']:
        if is_api_decl(decl, prefix):
            outp_decl = parse_decl(decl)
            if outp_decl is not None:
                outp['decls'].append(outp_decl)
    return outp

def main():
    if len(sys.argv) != 5:
        print('simplify.py [input.json] [output.json] [module] [prefix]')
        exit(10)

    input_json = sys.argv[1]
    output_json = sys.argv[2]
    module = sys.argv[3]
    prefix = sys.argv[4]

    with open(input_json, 'r') as finp:
        inp = json.load(finp)
        outp = parse_ast(inp, module, prefix)
        with open(output_json, 'w') as foutp:
            json.dump(outp, foutp, indent='  ')

if __name__ == '__main__':
    main()
